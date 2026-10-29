import hashlib
import io
import json
import zipfile
from datetime import datetime,timezone
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError
from radar_ia.hosted_api import handle
from radar_ia.review_api import ReviewStore,ReviewConflict
from radar_ia.production import Production
from radar_ia.script import spoken_text,validate_script


class S3:
    def __init__(self):self.objects={};self.reads=0;self.writes=0;self.conflict=False
    def list_objects_v2(self,**kw):
        self.reads+=1
        return {'Contents':[{'Key':k} for k in sorted(self.objects) if k.startswith(kw['Prefix'])][:kw['MaxKeys']]}
    def get_object(self,**kw):
        self.reads+=1;raw=self.objects[kw['Key']]
        return {'Body':io.BytesIO(raw),'ETag':hashlib.sha256(raw).hexdigest()}
    def put_object(self,**kw):
        old=self.objects[kw['Key']]
        if self.conflict or kw['IfMatch']!=hashlib.sha256(old).hexdigest():
            raise ClientError({'Error':{'Code':'PreconditionFailed'}},'PutObject')
        assert kw['ServerSideEncryption']=='AES256'
        self.writes+=1;self.objects[kw['Key']]=kw['Body']


def pack(files):
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in files.items():archive.writestr(name,data)
    return output.getvalue()


@pytest.fixture
def store():
    s3=S3();store=ReviewStore(s3,'bucket','radar')
    brief={'theme':'Engenharia de IA','news':[{'id':1,'title_original':'Prompt caching','summary_original':'Reuse context',
        'source':'Example','url':'https://example.org/news','published':'2026-10-29T09:00:00+00:00'}]}
    script={'intro_pt':'Boletim.','stories':[{'news_id':1,'title_pt':'Teste','summary_pt':'Resumo.',
        'narration_pt':'Caching significa armazenamento para reutilização.'}],
        'glossary':[{'term_en':'Caching','explanation_pt':'armazenamento para reutilização','news_ids':[1]}],'outro_pt':'Até amanhã.'}
    files={'checkpoint.json':json.dumps({'date':'2026-10-29','stage':'awaiting_script_review'}),
        'briefing.json':json.dumps(brief),'roteiro.json':json.dumps(script),
        'narracao.txt':spoken_text(validate_script(script,brief)).replace('\n','\r\n')}
    s3.objects[store.key('2026-10-29')]=pack(files)
    return store


def event(route='GET /api/production/{date}',uid='owner',data=None,edition='2026-10-29'):
    return {'routeKey':route,'pathParameters':{'date':edition},
        'requestContext':{'http':{'method':route.split()[0]},'authorizer':{'jwt':{'claims':{'sub':uid,'token_use':'access'}}}},
        'body':json.dumps(data) if data is not None else None}


def backend(store):
    return SimpleNamespace(can_review=lambda uid:uid=='owner',production=store.summary,
        approve_script=store.approve_script,episodes=lambda:pytest.fail('Revisão não depende do catálogo publicado'))


def test_only_owner_can_read_production(store):
    response=handle(event(uid='listener'),backend(store))
    assert response['statusCode']==403 and store.s3.reads==0


def test_only_owner_can_approve(store):
    response=handle(event('POST /api/production/{date}/approve-script',uid='listener',data={}),backend(store))
    assert response['statusCode']==403 and store.s3.writes==0


def test_owner_reads_script_and_sources_without_changing_state(store):
    response=handle(event(),backend(store));data=json.loads(response['body'])
    assert response['statusCode']==200 and data['can_approve_script']
    assert data['sources'][0]['url']=='https://example.org/news'
    assert '\r' not in data['narration'] and store.s3.writes==0


def test_web_approval_is_compatible_with_production_worker(store,tmp_path):
    summary=store.summary('2026-10-29')
    data={'digest':summary['digest'],'confirmed':True}
    response=handle(event('POST /api/production/{date}/approve-script',data=data),backend(store))
    assert response['statusCode']==200 and json.loads(response['body'])['stage']=='script_approved'
    raw,_=store.load('2026-10-29')
    run=Production(tmp_path,datetime(2026,10,29,12,tzinfo=timezone.utc))
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for name in archive.namelist():(run.folder/name).write_bytes(archive.read(name))
    run.approved_bundle()
    approval=json.loads((run.folder/'aprovacao-roteiro.json').read_text())
    assert approval['approved_by']=='owner' and approval['channel']=='web'
    assert 'episode.wav' not in zipfile.ZipFile(io.BytesIO(raw)).namelist()


def test_repeated_approval_is_idempotent(store):
    data={'digest':store.summary('2026-10-29')['digest'],'confirmed':True}
    store.approve_script('2026-10-29',data,'owner');writes=store.s3.writes
    store.approve_script('2026-10-29',data,'owner')
    assert store.s3.writes==writes


def test_stale_content_and_concurrent_update_are_not_approved(store):
    data={'digest':'0'*64,'confirmed':True}
    with pytest.raises(ReviewConflict):store.approve_script('2026-10-29',data,'owner')
    data['digest']=store.summary('2026-10-29')['digest'];store.s3.conflict=True
    response=handle(event('POST /api/production/{date}/approve-script',data=data),backend(store))
    assert response['statusCode']==409 and store.s3.writes==0


@pytest.mark.parametrize('data',[{'digest':'0'*64,'confirmed':False},{'digest':'0'*64,'confirmed':'true'},
    {'digest':'0'*64,'confirmed':True,'user_id':'owner'},[]])
def test_explicit_confirmation_and_exact_fields_are_required(store,data):
    response=handle(event('POST /api/production/{date}/approve-script',data=data),backend(store))
    assert response['statusCode']==400 and store.s3.writes==0


def test_absent_edition_is_new_and_invalid_path_never_reaches_s3(store):
    assert store.summary('2026-10-30')['stage']=='new'
    previous=store.s3.reads
    response=handle(event(edition='../2026-10-29'),backend(store))
    assert response['statusCode']==400 and store.s3.reads==previous


def test_audio_approval_verifies_wave_and_binds_exact_version(store):
    from radar_ia.audio import wav_from_pcm
    data={'digest':store.summary('2026-10-29')['digest'],'confirmed':True}
    store.approve_script('2026-10-29',data,'owner')
    raw,_=store.load('2026-10-29')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:files={name:archive.read(name) for name in archive.namelist()}
    audio,_=wav_from_pcm(bytes(32000));digest=hashlib.sha256(audio).hexdigest()
    text=store.summary('2026-10-29')['narration']
    files.update({'episode.wav':audio,'metadados-audio.json':json.dumps({'audio_sha256':digest,'script_sha256':hashlib.sha256(text.encode()).hexdigest(),'duration_seconds':1,'voice':'Leo'}),
        'checkpoint.json':json.dumps({'date':'2026-10-29','stage':'awaiting_audio_review'})})
    store.s3.objects[store.key('2026-10-29')]=pack(files)
    with pytest.raises(ReviewConflict):store.approve_audio('2026-10-29',{'digest':'b'*64,'confirmed':True},'owner')
    approved=store.approve_audio('2026-10-29',{'digest':digest,'confirmed':True},'owner')
    assert approved['stage']=='audio_approved' and approved['can_publish']
    before=store.s3.writes
    store.approve_audio('2026-10-29',{'digest':digest,'confirmed':True},'owner')
    assert before==store.s3.writes
