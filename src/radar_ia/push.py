"""Assinaturas Web Push privadas e validadas; sem dependencias de criptografia na API."""
import base64
import hashlib
import json
import re
import time
from urllib.parse import urlsplit
from botocore.exceptions import ClientError
from .review_api import ReviewConflict


def validate_subscription(data):
    if not isinstance(data,dict) or set(data)-{'endpoint','expirationTime','keys'} or not {'endpoint','keys'}<=set(data):raise ValueError('Assinatura invalida')
    endpoint=data['endpoint']
    if not isinstance(endpoint,str) or not 20<len(endpoint)<=2048:raise ValueError('Endereco invalido')
    url=urlsplit(endpoint)
    paths={'fcm.googleapis.com':('/fcm/send/','/wp/'),'updates.push.services.mozilla.com':('/wpush/v2/',)}
    if url.scheme!='https' or url.hostname not in paths or url.username or url.password or url.port not in (None,443) or url.query or url.fragment or not url.path.startswith(paths[url.hostname]):raise ValueError('Provedor push nao permitido')
    keys=data['keys']
    if not isinstance(keys,dict) or set(keys)!={'p256dh','auth'}:raise ValueError('Chaves invalidas')
    for key,size in [('p256dh',65),('auth',16)]:
        value=keys[key]
        if not isinstance(value,str) or not re.fullmatch('[A-Za-z0-9_-]+={0,2}',value):raise ValueError('Chave invalida')
        raw=base64.urlsafe_b64decode(value+'='*((-len(value))%4))
        if len(raw)!=size or key=='p256dh' and raw[0]!=4:raise ValueError('Chave invalida')
    return {'endpoint':endpoint,'keys':dict(keys)}


def subscription_id(subscription):return hashlib.sha256(subscription['endpoint'].encode()).hexdigest()


class PushStore:
    def __init__(self,table):self.table=table
    def devices(self,user_id):return self.table.get_item(Key={'user_id':user_id},ConsistentRead=True).get('Item',{})
    def change(self,user_id,identifier,subscription=None):
        if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{64}',identifier):raise ValueError('Dispositivo invalido')
        current=self.devices(user_id);devices=dict(current.get('devices',{}))
        if subscription is not None and devices.get(identifier)==subscription:return {'id':identifier,'count':len(devices)}
        if subscription is None:devices.pop(identifier,None)
        else:
            devices[identifier]=subscription
            if len(devices)>5:raise ValueError('Limite de cinco dispositivos; desative um antes de adicionar outro')
        item={'user_id':user_id,'devices':devices,'version':int(current.get('version',0))+1}
        condition={'ConditionExpression':'#v = :v','ExpressionAttributeNames':{'#v':'version'},'ExpressionAttributeValues':{':v':current['version']}} if current else {'ConditionExpression':'attribute_not_exists(user_id)'}
        try:self.table.put_item(Item=item,**condition)
        except ClientError as exc:
            if exc.response['Error']['Code']=='ConditionalCheckFailedException':raise ReviewConflict() from None
            raise
        return {'id':identifier,'count':len(devices)}
    def subscribe(self,user_id,data):
        subscription=validate_subscription(data)
        return self.change(user_id,subscription_id(subscription),subscription)


def test_notice(sqs,queue,user_id,identifier,now=None):
    if not isinstance(identifier,str) or not re.fullmatch('[a-f0-9]{64}',identifier):raise ValueError('Dispositivo invalido')
    minute=int((now or time.time())//60)
    request=hashlib.sha256(f'test:{user_id}:{identifier}:{minute}'.encode()).hexdigest()
    sqs.send_message(QueueUrl=queue,MessageBody=json.dumps({'kind':'test','user_id':user_id,'subscription_id':identifier,'request_id':request}))
    return {'status':'queued'}


def episode_notice(sqs,queue,episode_id):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}-[a-f0-9]{16}',episode_id):raise ValueError('Episodio invalido')
    sqs.send_message(QueueUrl=queue,MessageBody=json.dumps({'kind':'episode','episode_id':episode_id}))
