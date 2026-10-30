"""Entrega de avisos apos commit do catalogo; ledger por episodio e dispositivo."""
import hashlib
import json
import os
import time
from datetime import datetime,timezone
from .push import PushStore,validate_subscription
from .jobs import JobStore


def deliver(message,store,jobs,s3,bucket,prefix,owner,send):
    if not isinstance(message,dict):raise ValueError('Mensagem invalida')
    kind=message.get('kind');devices=store.devices(owner).get('devices',{})
    if kind=='episode' and set(message)=={'kind','episode_id'}:
        from .catalog import read_catalog
        catalog,_=read_catalog(s3,bucket,f'{prefix}/catalog.json')
        if not any(item['id']==message['episode_id'] for item in catalog['episodes']):raise ValueError('Episodio nao publicado')
        reference=message['episode_id'];selected=devices
        payload={'title':'Radar IA','body':'Um novo episódio está pronto na sua biblioteca privada.','tag':'radar-'+reference}
    elif kind=='human_review' and set(message)=={'kind','date','digest'}:
        from .review_api import ReviewStore
        summary=ReviewStore(s3,bucket,prefix).summary(message['date'])
        if summary['stage']!='awaiting_human_review' or summary.get('digest')!=message['digest']:
            return {'processed':0,'skipped':'no_longer_pending'}
        reference=message['date']+':'+message['digest'];selected=devices
        payload={'title':'Radar IA','body':'Uma edição precisa da sua revisão no Radar IA.',
                 'tag':'radar-review-'+message['date']+'-'+message['digest'][:12],'view':'review'}
    elif kind=='test' and set(message)=={'kind','user_id','subscription_id','request_id'} and message['user_id']==owner:
        reference=message['request_id'];selected={key:value for key,value in devices.items() if key==message['subscription_id']}
        payload={'title':'Radar IA','body':'Tudo certo! Os avisos estão ativados neste dispositivo.','tag':'radar-test'}
    else:raise ValueError('Mensagem invalida')
    results=[]
    for identifier,subscription in selected.items():
        validate_subscription(subscription)
        key=hashlib.sha256(f'notice:{kind}:{reference}:{identifier}'.encode()).hexdigest()
        now=datetime.now(timezone.utc).isoformat()
        jobs.create({'job_id':key,'action':'notification','status':'queued','user_id':owner,'created_at':now,'updated_at':now,
            'expires_at':int(time.time()+90*86400),'can_retry':False})
        if not jobs.claim(key):continue
        try:
            status=send(subscription,payload)
            if status in (404,410):
                store.change(owner,identifier);jobs.update(key,'expired',can_retry=False)
            elif 200<=status<=202:jobs.update(key,'succeeded',can_retry=False)
            else:jobs.update(key,'failed',can_retry=False,error_code='PushHTTP'+str(status))
        except Exception as exc:
            # Nao registrar endpoint, credenciais ou resposta do provedor.
            jobs.update(key,'needs_review',can_retry=False,error_code=type(exc).__name__)
        results.append(key)
    return {'processed':len(results)}


def dispatch(message,s3,jobs,bucket,prefix,owner):
    import boto3
    import requests
    from pywebpush import webpush,WebPushException
    store=PushStore(boto3.resource('dynamodb').Table(os.environ['PUSH_TABLE']))
    secret=json.loads(boto3.client('secretsmanager').get_secret_value(SecretId=os.environ['VAPID_SECRET_ARN'])['SecretString'])
    class NoRedirects(requests.Session):
        def request(self,*args,**kwargs):
            kwargs['allow_redirects']=False
            return super().request(*args,**kwargs)
    def send(subscription,payload):
        with NoRedirects() as session:
            session.trust_env=False
            try:
                response=webpush(subscription_info=subscription,data=json.dumps(payload,ensure_ascii=False),
                    vapid_private_key=secret['private_key'],vapid_claims={'sub':secret['subject']},
                    ttl=86400,timeout=15,requests_session=session)
                return response.status_code
            except WebPushException as exc:
                if exc.response is not None:return exc.response.status_code
                raise
    return deliver(message,store,jobs,s3,bucket,prefix,owner,send)

def diagnostic():
    """Valida assinatura/criptografia com transporte em memoria; nao envia push."""
    import base64
    import boto3
    import requests
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    from pywebpush import webpush
    secret=json.loads(boto3.client('secretsmanager').get_secret_value(SecretId=os.environ['VAPID_SECRET_ARN'])['SecretString'])
    receiver=ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    encode=lambda data:base64.urlsafe_b64encode(data).rstrip(b'=').decode()
    subscription={'endpoint':'https://fcm.googleapis.com/fcm/send/diagnostic','keys':{'p256dh':encode(receiver),'auth':encode(os.urandom(16))}}
    class Offline(requests.Session):
        def request(self,method,url,**kwargs):
            assert url==subscription['endpoint']
            assert b'private-test' not in kwargs['data'] and len(kwargs['data'])>32
            assert any(key.lower()=='authorization' and str(value).startswith('vapid ') for key,value in kwargs['headers'].items())
            response=requests.Response();response.status_code=202;response._content=b'';return response
    with Offline() as session:
        webpush(subscription_info=subscription,data='private-test',vapid_private_key=secret['private_key'],
            vapid_claims={'sub':secret['subject']},requests_session=session,timeout=5)
    return {'crypto':True,'sent':False,'generation':False}
