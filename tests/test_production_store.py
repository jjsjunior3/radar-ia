import hashlib
import io
import zipfile

import pytest
from botocore.exceptions import ClientError

from radar_ia.production_store import ProductionStore
from radar_ia.production import Production, write_json
from radar_ia.catalog import BLOCK, read_catalog, upload_episode


class S3:
    def __init__(self):self.objects={}
    def get_public_access_block(self,**kwargs):return {'PublicAccessBlockConfiguration':dict(BLOCK)}
    def get_bucket_ownership_controls(self,**kwargs):return {'OwnershipControls':{'Rules':[{'ObjectOwnership':'BucketOwnerEnforced'}]}}
    def get_bucket_encryption(self,**kwargs):return {}
    def get_object(self,**kwargs):
        if kwargs['Key'] not in self.objects:
            raise ClientError({'Error':{'Code':'NoSuchKey'}},'GetObject')
        body=self.objects[kwargs['Key']]
        return {'Body':io.BytesIO(body),'ETag':hashlib.sha256(body).hexdigest()}
    def put_object(self,**kwargs):
        key=kwargs['Key'];old=self.objects.get(key)
        if (kwargs.get('IfNoneMatch')=='*' and old is not None) or ('IfMatch' in kwargs and (old is None or hashlib.sha256(old).hexdigest()!=kwargs['IfMatch'])):
            raise ClientError({'Error':{'Code':'PreconditionFailed'}},'PutObject')
        assert kwargs['ServerSideEncryption']=='AES256'
        self.objects[key]=kwargs['Body']
        return {'ETag':hashlib.sha256(kwargs['Body']).hexdigest()}


def test_restore_private_edition_and_editorial_state(tmp_path):
    s3=S3();store=ProductionStore(s3,'bucket','radar',tmp_path/'first','2026-10-28')
    store.load();store.folder.mkdir(parents=True)
    write_json(store.folder/'checkpoint.json',{'stage':'prepared'})
    write_json(store.root/'editorial-state.json',{'queue':[]})
    store.save();store.save_editorial()
    restored=ProductionStore(s3,'bucket','radar',tmp_path/'second','2026-10-28');restored.load()
    assert (restored.folder/'checkpoint.json').read_bytes()==(store.folder/'checkpoint.json').read_bytes()
    assert (restored.root/'editorial-state.json').exists()


def test_concurrent_writer_cannot_overwrite_checkpoint(tmp_path):
    s3=S3();first=ProductionStore(s3,'bucket','radar',tmp_path/'a','2026-10-28')
    second=ProductionStore(s3,'bucket','radar',tmp_path/'b','2026-10-28')
    first.load();second.load()
    first.folder.mkdir(parents=True);second.folder.mkdir(parents=True)
    write_json(first.folder/'checkpoint.json',{'stage':'draft_in_progress'})
    first.save()
    with pytest.raises(ClientError):second.save()


@pytest.mark.parametrize('name',['../escape.json','/absolute.json','C:/escape.json',r'..\escape.json'])
def test_remote_snapshot_cannot_escape_folder(tmp_path,name):
    s3=S3();store=ProductionStore(s3,'bucket','radar',tmp_path,'2026-10-28')
    body=io.BytesIO()
    with zipfile.ZipFile(body,'w') as archive:archive.writestr(name,b'bad')
    s3.objects[store.key]=body.getvalue()
    with pytest.raises(ValueError,match='Caminho'):store.load()
    assert not (tmp_path/'production'/'escape.json').exists()


def test_remote_checkpoint_failure_prevents_paid_request(tmp_path):
    calls=[]
    def unavailable():raise OSError('S3 indisponível')
    run=Production(tmp_path,persist=unavailable)
    run.state['stage']='prepared'
    write_json(run.folder/'briefing.json',{'news':[]})
    with pytest.raises(OSError):run.draft(lambda *args:calls.append(True))
    assert calls==[]


def test_whole_edition_survives_fresh_runner_between_steps(tmp_path):
    from datetime import datetime,timezone
    from radar_ia.script import validate_script
    from radar_ia.production import read_json
    now=datetime(2026,10,28,12,tzinfo=timezone.utc)
    s3=S3();counter=iter(range(20));calls=[]
    def runner():
        output=tmp_path/str(next(counter))
        store=ProductionStore(s3,'bucket','radar',output,'2026-10-28');store.load()
        return Production(output,now,persist=store.save),store
    candidate={'title':'New SDK for LLM agents','summary':'API for inference and agents',
        'url':'https://example.org/news','published':now.isoformat(),
        'source':'https://example.org/feed','source_name':'Example'}
    run,_=runner()
    run.prepare([],{'episodes':[]},collector=lambda *args:{'collected_at':now.isoformat(),'candidates':[candidate]})
    run,_=runner()
    def generate(brief,save):
        calls.append('llm')
        payload={'intro_pt':'Boletim.','stories':[{'news_id':1,'title_pt':'Teste','summary_pt':'Resumo.','narration_pt':'Caching significa armazenamento para reutilização.'}],
            'glossary':[{'term_en':'Caching','explanation_pt':'armazenamento para reutilização','news_ids':[1]}],'outro_pt':'Até amanhã.'}
        save({'choices':[{'finish_reason':'stop','message':{'content':__import__('json').dumps(payload)}}]})
        return validate_script(payload,brief),{}
    run.draft(generate)
    run,_=runner();run.approve_script()
    class Polly:
        def synthesize_speech(self,**kwargs):
            calls.append('polly')
            return {'AudioStream':io.BytesIO(b'\0\0'*16000)}
    run,_=runner();run.synthesize(Polly())
    run,_=runner();run.synthesize(Polly());run.approve_audio()
    def upload(audio,script,narration,brief,day):
        return upload_episode(s3,'bucket','radar',audio=audio,script=script,narration=narration,brief=brief,date=day,title='Teste')[0]
    run,store=runner();run.publish(upload);store.save_editorial()
    run,store=runner();run.publish(upload);store.save_editorial()
    assert calls==['llm','polly']
    assert len(read_catalog(s3,'bucket','radar/catalog.json')[0]['episodes'])==1
    assert read_json(run.global_path)['last_covered_at']==now.isoformat()
    assert run.state['stage']=='completed'


def test_audio_archive_keeps_previous_snapshot_outside_current_edition(tmp_path):
    s3=S3();store=ProductionStore(s3,'bucket','radar',tmp_path,'2026-10-28')
    store.load();store.folder.mkdir(parents=True)
    write_json(store.folder/'checkpoint.json',{'stage':'awaiting_audio_review'})
    (store.folder/'episode.wav').write_bytes(b'old audio')
    store.save()
    original=s3.objects[store.key]
    receipt=store.archive_audio_revision()
    assert s3.objects[receipt['key']]==original
    assert store.archive_audio_revision()==receipt
    assert '/audio-archives/2026-10-28/' in receipt['key']
