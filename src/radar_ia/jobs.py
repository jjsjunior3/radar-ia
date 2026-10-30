"""Tarefas idempotentes: API enfileira, worker reivindica uma única execução."""
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from botocore.exceptions import ClientError
from .review_api import ReviewConflict
from .speech_markup import RENDERER_VERSION
from .audio import DEFAULT_VOICE


def utcnow():return datetime.now(timezone.utc)


def editorial_job_id(day):
    return hashlib.sha256(('editorial-v1:'+day).encode()).hexdigest()


def job_id(summary, action):
    binding={'date':summary['date'],'action':action,'script':summary.get('digest'),
        'revision':summary.get('audio_revision','initial'),'voice':DEFAULT_VOICE,
        'renderer':RENDERER_VERSION,'audio':summary.get('audio_digest') if action=='publish' else None}
    return hashlib.sha256(json.dumps(binding,sort_keys=True).encode()).hexdigest()


class JobStore:
    def __init__(self,table):self.table=table
    def get(self,identifier):
        if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{64}',identifier):raise ValueError('Tarefa inválida')
        return self.table.get_item(Key={'job_id':identifier},ConsistentRead=True).get('Item')
    def create(self,item):
        try:self.table.put_item(Item=item,ConditionExpression='attribute_not_exists(job_id)')
        except ClientError as exc:
            if exc.response['Error']['Code']!='ConditionalCheckFailedException':raise
            return self.get(item['job_id'])
        return item
    def claim(self,identifier):
        try:
            response=self.table.update_item(Key={'job_id':identifier},
                UpdateExpression='SET #s = :running, updated_at = :now',
                ConditionExpression='#s = :queued',ExpressionAttributeNames={'#s':'status'},
                ExpressionAttributeValues={':running':'running',':queued':'queued',':now':utcnow().isoformat()},ReturnValues='ALL_NEW')
        except ClientError as exc:
            if exc.response['Error']['Code']=='ConditionalCheckFailedException':return None
            raise
        return response['Attributes']
    def update(self,identifier,status,**fields):
        fields.update(status=status,updated_at=utcnow().isoformat())
        names={f'#n{i}':key for i,key in enumerate(fields)}
        values={f':v{i}':value for i,value in enumerate(fields.values())}
        self.table.update_item(Key={'job_id':identifier},
            UpdateExpression='SET '+', '.join(f'#n{i} = :v{i}' for i in range(len(fields))),
            ExpressionAttributeNames=names,ExpressionAttributeValues=values)
    def requeue(self,item):
        try:
            self.table.update_item(Key={'job_id':item['job_id']},UpdateExpression='SET #s = :queued, updated_at = :now',
                ConditionExpression='#s = :failed AND can_retry = :yes',ExpressionAttributeNames={'#s':'status'},
                ExpressionAttributeValues={':queued':'queued',':failed':'failed',':yes':True,':now':utcnow().isoformat()})
        except ClientError as exc:
            if exc.response['Error']['Code']=='ConditionalCheckFailedException':return self.get(item['job_id'])
            raise
        return self.get(item['job_id'])


def public_job(item,now=None):
    if not item:return None
    now=now or utcnow();status=item['status']
    age=(now-datetime.fromisoformat(item['updated_at'])).total_seconds()
    if status=='running' and age>1200:status='needs_review'
    result={'id':item['job_id'],'action':item['action'],'status':status,'updated_at':item['updated_at'],
        'completed_chunks':int(item.get('completed_chunks',0)),'total_chunks':int(item.get('total_chunks',0)),
        'can_retry':bool(status=='failed' and item.get('can_retry') or status=='queued' and age>120)}
    for key in ('date','started_at','scheduled_at','edition_stage','error_code'):
        if key in item:result[key]=str(item[key])
    if 'delay_seconds' in item:result['delay_seconds']=int(item['delay_seconds'])
    if item.get('action') not in ('audio','publish'):result['can_retry']=False
    return result


class JobQueue:
    def __init__(self,store,sqs,url):self.store,self.sqs,self.url=store,sqs,url
    def start(self,summary,action,data,user_id,*,automatic=False):
        if action not in ('audio','publish') or not isinstance(data,dict) or set(data)!={'digest','confirmed'} or data['confirmed'] is not True:
            raise ValueError('Confirmação inválida')
        expected=summary.get('digest') if action=='audio' else summary.get('audio_digest')
        if not expected or data['digest']!=expected:raise ReviewConflict()
        identifier=job_id(summary,action);item=self.store.get(identifier)
        if item and item['user_id']!=user_id:raise ReviewConflict()
        if item:
            state=public_job(item)
            if state['status']=='needs_review':raise ReviewConflict()
            if item['status']=='failed':
                if not item.get('can_retry'):raise ReviewConflict()
                item=self.store.requeue(item)
        else:
            if not summary.get('can_generate_audio' if action=='audio' else 'can_publish'):raise ReviewConflict()
            now=utcnow()
            if action=='audio':
                planned=datetime.fromisoformat(summary['planned_for'])
                if planned.tzinfo is None or not 0<=(now-planned).total_seconds()<=86400:raise ReviewConflict()
            item=self.store.create({'job_id':identifier,'date':summary['date'],'action':action,'user_id':user_id,
                'script_digest':summary['digest'],'audio_digest':summary.get('audio_digest',''),
                'voice':DEFAULT_VOICE,'renderer':RENDERER_VERSION,'automatic':bool(automatic),'status':'queued','created_at':now.isoformat(),
                'updated_at':now.isoformat(),'expires_at':int((now+timedelta(days=30)).timestamp())})
        if item['status']=='queued':
            # Reenviar a mesma mensagem é seguro: a reivindicação condicional é única.
            self.sqs.send_message(QueueUrl=self.url,MessageBody=json.dumps({'job_id':identifier}))
        return public_job(item)
