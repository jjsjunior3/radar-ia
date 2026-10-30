"""Preparacao editorial diaria por EventBridge, com uma reivindicacao por edicao."""
import json
import os
import time
from datetime import datetime,timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from zoneinfo import ZoneInfo
import boto3
from botocore.config import Config
from openai import OpenAI
from .catalog import read_catalog,verify_private
from .collection import collect_sources
from .jobs import JobStore,JobQueue,editorial_job_id
from .news import Fetcher
from .production import Production,read_json,fingerprint
from .production_store import ProductionStore
from .script import generate_script
from .agents import CollectionAgent,EditorialAgents,BudgetClient
from .editorial_learning import load_feedback

ZONE=ZoneInfo('America/Sao_Paulo')


def scheduled_edition(event,now):
    if not isinstance(event,dict) or set(event)!={'scheduled_time','source'} or event['source']!='eventbridge':
        raise ValueError('Evento de agendamento invalido')
    planned=datetime.fromisoformat(event['scheduled_time'].replace('Z','+00:00'))
    if planned.tzinfo is None or not 0<=(now-planned).total_seconds()<=3600:
        raise ValueError('Disparo fora da janela de uma hora')
    local=planned.astimezone(ZONE)
    if local.weekday()>4 or (local.hour,local.minute)!=(8,30):raise ValueError('Disparo fora do horario editorial')
    return local.date().isoformat()


def process(event,jobs,s3,secrets,bucket,prefix,owner,secret_arn,sources,now=None,generator=None,automatic_queue=None):
    now=now or datetime.now(timezone.utc);day=scheduled_edition(event,now)
    if not owner:raise ValueError('Responsavel nao configurado')
    identifier=editorial_job_id(day)
    jobs.create({'job_id':identifier,'date':day,'action':'editorial','user_id':owner,'status':'queued',
        'scheduled_at':event['scheduled_time'],'created_at':now.isoformat(),'updated_at':now.isoformat(),
        'expires_at':int(now.timestamp()+30*86400),'can_retry':False})
    if not jobs.claim(identifier):return {'status':'duplicate','date':day}
    try:
        jobs.update(identifier,'running',started_at=now.isoformat(),delay_seconds=int((now-datetime.fromisoformat(event['scheduled_time'].replace('Z','+00:00'))).total_seconds()))
        verify_private(s3,bucket)
        with TemporaryDirectory(prefix='radar-editorial-') as output:
            store=ProductionStore(s3,bucket,prefix,output,day);store.load()
            run=Production(output,now,day=day,persist=store.save)
            catalog,_=read_catalog(s3,bucket,f'{prefix}/catalog.json')
            deadline=time.monotonic()+480
            class BoundedFetcher(Fetcher):
                def get(self,url):
                    remaining=deadline-time.monotonic()
                    if remaining<=0:raise TimeoutError('Limite da coleta editorial')
                    return super().get(url)
            run.prepare(sources,catalog,collector=lambda configured,current,since:CollectionAgent.collect(configured,current,since,fetcher_factory=BoundedFetcher))
            if run.state['stage'] in ('prepared','draft_in_progress','draft_failed'):
                run.revalidate(sources,fetcher_factory=BoundedFetcher)
                if generator is None:
                    # Recuperar resposta salva nao exige ler chave nem abrir cliente pago.
                    if (run.folder/'resposta-original.json').exists() or (run.folder/'roteiro.json').exists():
                        run.draft(lambda *args:(_ for _ in ()).throw(ValueError('Resposta deveria estar salva')))
                    else:
                        brief=read_json(run.folder/'briefing.json')
                        brief['editorial_memory']=load_feedback(s3,bucket,prefix,day,owner)
                        run.save_json(run.folder/'briefing.json',brief)
                        key=secrets.get_secret_value(SecretId=secret_arn)['SecretString'].strip()
                        if not key:raise ValueError('Credencial ausente')
                        with OpenAI(api_key=key,base_url='https://openrouter.ai/api/v1',timeout=90,max_retries=0) as client:
                            agents=EditorialAgents(run,BudgetClient(client),os.getenv('OPENROUTER_MODEL','google/gemini-2.5-flash'))
                            if agents.select():run.draft(agents.generate)
                else:run.draft(generator)
            if automatic_queue is not None and run.state['stage']=='awaiting_script_review':
                run.approve_script(mode='automatic')
                brief,script,_=run.approved_bundle()
                summary={'date':day,'digest':fingerprint({'brief':brief,'script':script.model_dump()}),
                    'planned_for':brief['planned_for'],'audio_revision':run.state.get('audio_revision','initial'),
                    'can_generate_audio':True}
                automatic_queue.start(summary,'audio',{'digest':summary['digest'],'confirmed':True},owner,automatic=True)
            jobs.update(identifier,'succeeded',edition_stage=run.state['stage'])
            return {'status':'succeeded','date':day,'stage':run.state['stage']}
    except Exception as exc:
        jobs.update(identifier,'failed',can_retry=False,error_code=type(exc).__name__)
        # Sem mensagem do provedor, URL ou chave nos logs; o checkpoint guarda a tentativa.
        raise RuntimeError('Falha editorial; consultar tarefa e checkpoint privados') from None


def handler(event,context):
    config=Config(signature_version='s3v4',connect_timeout=10,read_timeout=60,retries={'total_max_attempts':1},
        request_checksum_calculation='when_required',response_checksum_validation='when_required')
    s3=boto3.client('s3',config=config)
    jobs=JobStore(boto3.resource('dynamodb').Table(os.environ['JOBS_TABLE']))
    sources=read_json(Path(__file__).parent/'config/sources.json')
    if event=={'diagnostic':True}:
        # Apenas leitura: valida pacote Linux, bucket, segredo existente e tabela; sem LLM.
        verify_private(s3,os.environ['S3_BUCKET'])
        boto3.client('secretsmanager',config=config).describe_secret(SecretId=os.environ['OPENROUTER_SECRET_ARN'])
        jobs.get(editorial_job_id(datetime.now(ZONE).date().isoformat()))
        print(json.dumps({'event':'editorial_diagnostic_ok','generation':False}))
        return {'status':'diagnostic_ok','generation':False}
    automatic_queue=JobQueue(jobs,boto3.client('sqs',config=config),os.environ['AUDIO_QUEUE_URL']) if os.getenv('AUTOMATIC_PUBLICATION')=='true' else None
    return process(event,jobs,s3,boto3.client('secretsmanager',config=config),os.environ['S3_BUCKET'],
        os.getenv('S3_PREFIX','radar-ia').strip('/'),os.environ['REVIEWER_SUB'],os.environ['OPENROUTER_SECRET_ARN'],sources,automatic_queue=automatic_queue)
