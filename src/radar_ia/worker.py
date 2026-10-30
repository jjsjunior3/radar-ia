"""Worker SQS: reutiliza Production sem executar roteiro ou chamadas de LLM."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from .jobs import JobStore
from .production import Production,read_json,fingerprint
from .production_store import ProductionStore
from .speech_markup import RENDERER_VERSION,speech_chunks
from .audio import DEFAULT_VOICE
from .catalog import upload_episode,verify_private


def process(identifier,jobs,s3,polly,bucket,prefix,owner,sources):
    queued=jobs.get(identifier)
    if not queued:return 'ignored'
    job=jobs.claim(identifier)
    if not job:return 'duplicate'
    run=None
    temporary=TemporaryDirectory(prefix="radar-job-")
    try:
        if job['user_id']!=owner or job['action'] not in ('audio','publish') or job['voice']!=DEFAULT_VOICE or job['renderer']!=RENDERER_VERSION:
            raise ValueError('Tarefa não autorizada ou configuração mudou')
        if job.get('automatic') and os.getenv('AUTOMATIC_PUBLICATION')!='true':
            raise ValueError('Publicação automática desativada; revisar tarefa')
        verify_private(s3,bucket)
        output=temporary.name
        store=ProductionStore(s3,bucket,prefix,output,job['date']);store.load()
        run=Production(output,day=job['date'])
        brief,script,text=run.approved_bundle()
        if fingerprint({'brief':brief,'script':script.model_dump()})!=job['script_digest']:
            raise ValueError('Roteiro mudou depois da solicitação')
        if job.get('automatic'):
            approval=read_json(run.folder/'agents'/'approval.json',{})
            human=read_json(run.folder/'aprovacao-roteiro.json',{})
            human_override=human.get('mode')=='human' and human.get('editorial_override') is True and human.get('digest')==job['script_digest'] and human.get('approved_by')==owner
            if not human_override and (approval.get('approved') is not True or approval.get('script_digest')!=job['script_digest'] or approval.get('policy')!='editorial-agents-v1'):
                raise ValueError('Avaliador editorial não aprovou esta versão do roteiro')
        total=len(speech_chunks(text))
        def persist():
            store.save()
            completed=sum(read_json(path,{}).get('status')=='complete' for path in (run.folder/'audio-chunks').glob('*.json'))
            jobs.update(identifier,'running',completed_chunks=completed,total_chunks=total)
        run.persist=persist
        def publish_episode():
            metadata=run.validate_audio(text)
            if job['action']=='publish' and metadata['audio_sha256']!=job['audio_digest']:
                raise ValueError('Áudio mudou depois da solicitação')
            if run.state['stage'] not in ('publish_in_progress','completed'):run.revalidate(sources)
            def upload(audio,payload,narration,brief,edition):
                return upload_episode(s3,bucket,prefix,audio=audio,script=payload,narration=narration,brief=brief,
                    date=edition,title=f"Radar IA — {brief['theme']}")[0]
            episode=run.publish(upload);store.save_editorial()
            if os.getenv("NOTIFICATION_QUEUE_URL"):
                from .push import episode_notice
                episode_notice(boto3.client("sqs"),os.environ["NOTIFICATION_QUEUE_URL"],episode["id"])
        if job['action']=='audio':
            run.revalidate(sources)
            metadata=run.synthesize(polly,voice=DEFAULT_VOICE,engine='generative')
            key=f"{prefix}/production/previews/{job['date']}/{metadata['audio_sha256']}.wav"
            try:
                s3.put_object(Bucket=bucket,Key=key,Body=(run.folder/'episode.wav').read_bytes(),ContentType='audio/wav',
                    ServerSideEncryption='AES256',IfNoneMatch='*')
            except ClientError as exc:
                if exc.response['Error']['Code'] not in ('PreconditionFailed','412'):raise
            if job.get('automatic'):
                # Valida integridade e duração antes da autorização automática; não representa escuta humana.
                if run.state['stage']=='awaiting_audio_review':run.approve_audio(mode='automatic')
                publish_episode()
            jobs.update(identifier,'succeeded',completed_chunks=total,total_chunks=total)
        else:
            publish_episode()
            jobs.update(identifier,'succeeded')
        return 'succeeded'
    except Exception as exc:
        # Marcador sem PCM salvo significa resultado pago incerto: bloquear repetição.
        uncertain=False
        if run:
            for path in (run.folder/'audio-chunks').glob('*.json'):
                if read_json(path,{}).get('status')=='request_started':uncertain=True
        jobs.update(identifier,'needs_review' if uncertain else 'failed',
            can_retry=not uncertain and not isinstance(exc,ValueError),error_code=type(exc).__name__)
        return 'needs_review' if uncertain else 'failed'
    finally:
        temporary.cleanup()


def handler(event,context):
    if event=={"push_diagnostic":True}:
        from .notifications import diagnostic
        return diagnostic()
    cfg=Config(signature_version='s3v4',connect_timeout=10,read_timeout=90,retries={'total_max_attempts':1},
        request_checksum_calculation='when_required',response_checksum_validation='when_required')
    s3=boto3.client('s3',config=cfg);polly=boto3.client('polly',config=cfg)
    jobs=JobStore(boto3.resource('dynamodb').Table(os.environ['JOBS_TABLE']))
    sources=json.loads((Path(__file__).parent/'config/sources.json').read_text(encoding='utf-8'))
    results=[]
    for record in event.get('Records',[]):
        data=json.loads(record['body'])
        if 'kind' in data:
            from .notifications import dispatch
            results.append(dispatch(data,s3,jobs,os.environ['S3_BUCKET'],os.getenv('S3_PREFIX','radar-ia').strip('/'),os.environ['REVIEWER_SUB']))
            continue
        if set(data)!={'job_id'}:raise ValueError('Mensagem inválida')
        results.append(process(data['job_id'],jobs,s3,polly,os.environ['S3_BUCKET'],os.getenv('S3_PREFIX','radar-ia').strip('/'),os.environ['REVIEWER_SUB'],sources))
    return {'processed':len(results),'results':results}
