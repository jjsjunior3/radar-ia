"""API hospedada. Invocação permitida somente via API Gateway com JWT validado."""
import base64
import json
import math
import os
from datetime import datetime, timezone
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from botocore.config import Config


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
        self.s3=boto3.client('s3',config=Config(signature_version='s3v4'))
        self.table=boto3.resource('dynamodb').Table(os.environ['PROGRESS_TABLE'])

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
    except Conflict:return reply(409,{'error':'O progresso mudou em outro dispositivo. Atualize a biblioteca antes de salvar novamente.'})
    except (ValueError,TypeError):return reply(400,{'error':'Requisição ou dados inválidos'})
    except Exception:return reply(503,{'error':'Serviço indisponível. Tente novamente mais tarde.'})


_backend=None

def handler(event,context):
    global _backend
    if _backend is None: _backend=Backend()
    return handle(event,_backend)
