"""API hospedada. Invocação permitida somente via API Gateway com JWT validado."""
import base64
import json
import math
import os
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from botocore.config import Config
from .review_api import ReviewStore, ReviewConflict
from .jobs import JobStore, JobQueue, job_id, public_job, editorial_job_id
from .push import PushStore,test_notice


class Conflict(Exception): pass


def calculate_progress(previous, duration, change):
    position=change.get('position',previous.get('position',0))
    if type(position) not in (int,float) or not math.isfinite(position) or not 0<=position<=duration:
        raise ValueError('Posição inválida')
    heard=change.get('heard')
    if heard is not None and type(heard) is not bool: raise ValueError('Marcação inválida')
    if heard is None:
        heard=bool(previous.get('heard',False) or previous.get('position',0)<.95*duration<=position)
    return {'position':position,'heard':heard,'updated_at':datetime.now(timezone.utc).isoformat()}


class Backend:
    def __init__(self):
        self.bucket=os.environ['S3_BUCKET']
        self.prefix=os.getenv('S3_PREFIX','radar-ia').strip('/')
        self.reviewer_sub=os.getenv('REVIEWER_SUB','')
        self.s3=boto3.client('s3',config=Config(signature_version='s3v4'))
        self.table=boto3.resource('dynamodb').Table(os.environ['PROGRESS_TABLE'])
        self.jobs=JobStore(boto3.resource('dynamodb').Table(os.environ['JOBS_TABLE']))
        self.queue=JobQueue(self.jobs,boto3.client('sqs'),os.environ['AUDIO_QUEUE_URL'])

    def can_review(self,user_id):
        return bool(self.reviewer_sub and user_id==self.reviewer_sub)

    def production(self,edition):
        summary=ReviewStore(self.s3,self.bucket,self.prefix).summary(edition)
        summary['jobs']=[public_job(self.jobs.get(job_id(summary,action))) for action in ('audio','publish')]
        editorial=self.jobs.get(editorial_job_id(edition))
        summary['editorial_job']=public_job(editorial)
        previous=editorial
        for offset in range(1,8):
            if previous:break
            previous=self.jobs.get(editorial_job_id((date.fromisoformat(edition)-timedelta(days=offset)).isoformat()))
        summary['last_editorial_job']=public_job(previous)
        summary['schedule_enabled']=os.getenv('EDITORIAL_SCHEDULE_ENABLED')=='true'
        return summary

    def approve_script(self,edition,data,user_id):
        return ReviewStore(self.s3,self.bucket,self.prefix).approve_script(edition,data,user_id)

    def approve_audio(self,edition,data,user_id):
        return ReviewStore(self.s3,self.bucket,self.prefix).approve_audio(edition,data,user_id)

    def start_job(self,edition,action,data,user_id):
        summary=ReviewStore(self.s3,self.bucket,self.prefix).summary(edition)
        return self.queue.start(summary,action,data,user_id)

    def job(self,identifier,user_id):
        item=self.jobs.get(identifier)
        if not item or item['user_id']!=user_id:raise ReviewConflict()
        return public_job(item)

    def preview(self,edition):
        summary=ReviewStore(self.s3,self.bucket,self.prefix).summary(edition)
        if not summary.get('audio_digest') or summary['stage'] not in ('awaiting_audio_review','audio_approved','completed'):raise ReviewConflict()
        # WAV privado vem do checkpoint aprovado; sem link permanente ou acesso público.
        key=f"{self.prefix}/production/previews/{edition}/{summary['audio_digest']}.wav"
        self.s3.head_object(Bucket=self.bucket,Key=key)
        return {'url':self.s3.generate_presigned_url('get_object',Params={'Bucket':self.bucket,'Key':key},ExpiresIn=300),'expires_in':300}

    def push(self,user_id,action,data=None):
        if not os.getenv('VAPID_PUBLIC_KEY'):
            if action=='config':return {'enabled':False}
            raise ValueError('Avisos nao configurados')
        store=PushStore(boto3.resource('dynamodb').Table(os.environ['PUSH_TABLE']))
        if action=='config':return {'public_key':os.environ['VAPID_PUBLIC_KEY'],'count':len(store.devices(user_id).get('devices',{}))}
        if action=='subscribe':return store.subscribe(user_id,data)
        if not isinstance(data,dict) or set(data)!={'id'}:raise ValueError('Dispositivo invalido')
        if action=='unsubscribe':return store.change(user_id,data['id'])
        if data['id'] not in store.devices(user_id).get('devices',{}):raise ValueError('Dispositivo nao cadastrado')
        return test_notice(boto3.client('sqs'),os.environ['NOTIFICATION_QUEUE_URL'],user_id,data['id'])

    def episodes(self):
        response=self.s3.get_object(Bucket=self.bucket,Key=f'{self.prefix}/catalog.json')
        with response['Body'] as body:
            data=json.loads(body.read(2_000_001))
        if data.get('schema_version')!=1: raise ValueError('Catálogo incompatível')
        return data['episodes']

    def states(self,user_id):
        result={}
        options={'KeyConditionExpression':Key('user_id').eq(user_id),'ConsistentRead':True}
        while True:
            response=self.table.query(**options)
            for item in response['Items']:
                result[item['episode_id']]={'position':float(item['position']),'heard':item['heard'],'updated_at':item['updated_at']}
            if 'LastEvaluatedKey' not in response: break
            options['ExclusiveStartKey']=response['LastEvaluatedKey']
        return result

    def save(self,user_id,episode,change):
        key={'user_id':user_id,'episode_id':episode['id']}
        previous=self.table.get_item(Key=key,ConsistentRead=True).get('Item',{})
        prior={'position':float(previous.get('position',0)),'heard':previous.get('heard',False)}
        result=calculate_progress(prior,episode['duration_seconds'],change)
        version=int(previous.get('version',0))
        item=dict(key,position=Decimal(str(result['position'])),heard=result['heard'],updated_at=result['updated_at'],version=version+1)
        condition={'ConditionExpression':'#v = :old','ExpressionAttributeNames':{'#v':'version'},'ExpressionAttributeValues':{':old':version}} if previous else {'ConditionExpression':'attribute_not_exists(user_id)'}
        try: self.table.put_item(Item=item,**condition)
        except ClientError as exc:
            if exc.response['Error']['Code']=='ConditionalCheckFailedException': raise Conflict() from None
            raise
        return result

    def audio(self,episode):
        key=episode['audio_key']
        if not key.startswith(f'{self.prefix}/episodes/'): raise ValueError('Chave inválida')
        return self.s3.generate_presigned_url('get_object',Params={'Bucket':self.bucket,'Key':key},ExpiresIn=300)


def reply(status,data):
    return {'statusCode':status,'headers':{'content-type':'application/json; charset=utf-8','cache-control':'no-store','referrer-policy':'no-referrer'},'body':json.dumps(data,ensure_ascii=False)}


def handle(event,backend):
    claims=event.get('requestContext',{}).get('authorizer',{}).get('jwt',{}).get('claims',{})
    user_id=claims.get('sub')
    # Assinatura, emissor, audiência e validade são conferidos pelo authorizer.
    if not user_id or claims.get('token_use')!='access': return reply(401,{'error':'Entre novamente para continuar.'})
    method=event.get('requestContext',{}).get('http',{}).get('method','')
    route=event.get('routeKey','')
    try:
        push_routes={'GET /api/push/config':'config','POST /api/push/subscribe':'subscribe',
            'POST /api/push/unsubscribe':'unsubscribe','POST /api/push/test':'test'}
        if route in push_routes:
            if not backend.can_review(user_id):return reply(403,{'error':'Avisos disponiveis somente para a conta responsavel.'})
            data=None
            if method=='POST':
                body=event.get('body') or ''
                if event.get('isBase64Encoded'):body=base64.b64decode(body,validate=True).decode()
                if len(body.encode())>4096:raise ValueError('Requisicao excede limite')
                data=json.loads(body)
            return reply(200,backend.push(user_id,push_routes[route],data))
        actions={'POST /api/production/{date}/approve-script':'approve-script',
            'POST /api/production/{date}/generate-audio':'audio',
            'POST /api/production/{date}/approve-audio':'approve-audio',
            'POST /api/production/{date}/publish':'publish'}
        if route in actions or route in ('GET /api/production/{date}','GET /api/production/{date}/preview','GET /api/jobs/{job_id}'):
            if not backend.can_review(user_id):return reply(403,{'error':'Revisão disponível somente para o responsável pela edição.'})
            edition=event.get('pathParameters',{}).get('date')
            if method=='GET':
                if route=='GET /api/production/{date}':return reply(200,backend.production(edition))
                if route=='GET /api/production/{date}/preview':return reply(200,backend.preview(edition))
                return reply(200,backend.job(event.get('pathParameters',{}).get('job_id'),user_id))
            if method=='POST' and route in actions:
                body=event.get('body') or ''
                if event.get('isBase64Encoded'):body=base64.b64decode(body,validate=True).decode()
                if len(body.encode())>4096:raise ValueError('Requisição excede limite')
                data=json.loads(body);action=actions[route]
                if action=='approve-script':return reply(200,backend.approve_script(edition,data,user_id))
                if action=='approve-audio':return reply(200,backend.approve_audio(edition,data,user_id))
                return reply(202,backend.start_job(edition,action,data,user_id))
            return reply(404,{'error':'Rota não encontrada'})
        episodes=backend.episodes()
        if route=='GET /api/episodes' and method=='GET':
            states=backend.states(user_id)
            return reply(200,{'mode':'cloud','episodes':[dict(e,progress=states.get(e['id'],{'position':0,'heard':False})) for e in episodes]})
        if route=='GET /api/audio/{episode_id}' and method=='GET':
            episode=next((e for e in episodes if e['id']==event.get('pathParameters',{}).get('episode_id')),None)
            return reply(200,{'url':backend.audio(episode),'expires_in':300}) if episode else reply(404,{'error':'Episódio não encontrado'})
        if route=='POST /api/progress' and method=='POST':
            body=event.get('body') or ''
            if event.get('isBase64Encoded'): body=base64.b64decode(body,validate=True).decode()
            if len(body.encode())>4096: raise ValueError('Requisição excede limite')
            data=json.loads(body)
            if not isinstance(data,dict) or set(data)-{'episode_id','position','heard'}: raise ValueError('Campos inválidos')
            episode=next((e for e in episodes if e['id']==data.get('episode_id')),None)
            if not episode: return reply(404,{'error':'Episódio não encontrado'})
            return reply(200,backend.save(user_id,episode,data))
        return reply(404,{'error':'Rota não encontrada'})
    except ReviewConflict:return reply(409,{'error':'A edição mudou. Atualize o roteiro e revise a versão atual antes de aprovar.'})
    except Conflict:return reply(409,{'error':'O progresso mudou em outro dispositivo. Atualize a biblioteca antes de salvar novamente.'})
    except (ValueError,TypeError):return reply(400,{'error':'Requisição ou dados inválidos'})
    except Exception:return reply(503,{'error':'Serviço indisponível. Tente novamente mais tarde.'})


_backend=None

def handler(event,context):
    global _backend
    if _backend is None: _backend=Backend()
    return handle(event,_backend)
