import io
import json
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from botocore.exceptions import ClientError
from radar_ia.jobs import JobStore,JobQueue,public_job
from radar_ia.review_api import ReviewConflict
from radar_ia import worker
from test_review_api import store
from radar_ia.audio import DEFAULT_VOICE
from radar_ia.speech_markup import RENDERER_VERSION


def conditional():return ClientError({'Error':{'Code':'ConditionalCheckFailedException'}},'UpdateItem')


class Table:
    def __init__(self):self.items={}
    def get_item(self,**kw):return {'Item':dict(self.items[kw['Key']['job_id']])} if kw['Key']['job_id'] in self.items else {}
    def put_item(self,**kw):
        item=kw['Item']
        if item['job_id'] in self.items:raise conditional()
        self.items[item['job_id']]=dict(item)
    def update_item(self,**kw):
        item=self.items.get(kw['Key']['job_id']);values=kw['ExpressionAttributeValues'];condition=kw.get('ConditionExpression','')
        if ':running' in values:
            if not item or item['status']!='queued':raise conditional()
        if ':failed' in values:
            if not item or item['status']!='failed' or not item.get('can_retry'):raise conditional()
        for assignment in kw['UpdateExpression'][4:].split(', '):
            key,value=assignment.split(' = ');key=kw.get('ExpressionAttributeNames',{}).get(key,key);item[key]=values[value]
        return {'Attributes':dict(item)}


def setup():
    table=Table();store=JobStore(table);sqs=Mock();queue=JobQueue(store,sqs,'queue')
    summary={'date':'2026-10-29','digest':'a'*64,'can_generate_audio':True,'planned_for':datetime.now(timezone.utc).isoformat()}
    return store,sqs,queue,summary


def test_double_click_duplicate_delivery_and_enqueue_gap_do_not_repeat_claim():
    store,sqs,queue,summary=setup();data={'digest':summary['digest'],'confirmed':True}
    sqs.send_message.side_effect=TimeoutError
    with pytest.raises(TimeoutError):queue.start(summary,'audio',data,'owner')
    sqs.send_message.side_effect=None
    first=queue.start(summary,'audio',data,'owner');second=queue.start(summary,'audio',data,'owner')
    assert first['id']==second['id'] and len(store.table.items)==1
    assert store.claim(first['id'])['status']=='running'
    assert store.claim(first['id']) is None
    queue.start(summary,'audio',data,'owner')
    assert sqs.send_message.call_count==3


@pytest.mark.parametrize('change',[{'confirmed':False},{'digest':'b'*64}])
def test_generation_requires_current_content_and_explicit_consent(change):
    store,sqs,queue,summary=setup();data=dict(digest=summary['digest'],confirmed=True);data.update(change)
    with pytest.raises((ValueError,ReviewConflict)):queue.start(summary,'audio',data,'owner')
    assert not store.table.items;sqs.send_message.assert_not_called()


def test_unapproved_or_expired_script_cannot_be_queued():
    store,sqs,queue,summary=setup();data=dict(digest=summary['digest'],confirmed=True)
    summary['can_generate_audio']=False
    with pytest.raises(ReviewConflict):queue.start(summary,'audio',data,'owner')
    summary['can_generate_audio']=True;summary['planned_for']=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()
    with pytest.raises(ReviewConflict):queue.start(summary,'audio',data,'owner')
    sqs.send_message.assert_not_called()


def test_uncertain_job_cannot_be_requeued_even_after_timeout():
    store,sqs,queue,summary=setup();data=dict(digest=summary['digest'],confirmed=True)
    job=queue.start(summary,'audio',data,'owner');store.claim(job['id'])
    store.update(job['id'],'needs_review',can_retry=False)
    with pytest.raises(ReviewConflict):queue.start(summary,'audio',data,'owner')
    assert sqs.send_message.call_count==1
    item=store.get(job['id']);item.update(status='running',updated_at=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat())
    assert public_job(item)['status']=='needs_review'


def test_worker_preserves_uncertain_paid_marker_before_temporary_cleanup(monkeypatch):
    store,sqs,queue,summary=setup();job=queue.start(summary,'audio',dict(digest=summary['digest'],confirmed=True),'owner')
    monkeypatch.setattr(worker,'verify_private',lambda *a:None)
    monkeypatch.setattr(worker,'ProductionStore',lambda *a:SimpleNamespace(load=lambda:None,save=lambda:None))
    monkeypatch.setattr(worker,'fingerprint',lambda value:summary['digest'])
    class Run:
        def __init__(self,output,**kw):
            from pathlib import Path
            self.folder=Path(output);self.state={'stage':'script_approved'}
        def approved_bundle(self):return {},SimpleNamespace(model_dump=lambda:{}),'Olá.'
        def revalidate(self,sources):pass
        def synthesize(self,polly,**kw):
            folder=self.folder/'audio-chunks';folder.mkdir()
            (folder/'0.json').write_text(json.dumps({'status':'request_started'}))
            polly.synthesize_speech();raise TimeoutError('resposta perdida')
    monkeypatch.setattr(worker,'Production',Run);polly=Mock()
    assert worker.process(job['id'],store,Mock(),polly,'bucket','radar','owner',[])=='needs_review'
    assert store.get(job['id'])['can_retry'] is False
    assert worker.process(job['id'],store,Mock(),polly,'bucket','radar','owner',[])=='duplicate'
    polly.synthesize_speech.assert_called_once()


def test_other_user_cannot_trigger_generation_or_publication():
    from radar_ia.hosted_api import handle
    from test_review_api import event
    backend=SimpleNamespace(can_review=lambda uid:False,start_job=Mock())
    for suffix in ['generate-audio','publish','approve-audio']:
        assert handle(event('POST /api/production/{date}/'+suffix,uid='other',data={}),backend)['statusCode']==403
    backend.start_job.assert_not_called()

@pytest.mark.parametrize('automatic', [False, True, 'human_override'])
def test_mobile_flow_reuses_real_production_and_publishes_only_approved_audio(monkeypatch,store,tmp_path,automatic):
    from tempfile import TemporaryDirectory
    monkeypatch.setattr(worker,"TemporaryDirectory",lambda **kw:TemporaryDirectory(dir=tmp_path,**kw))
    import hashlib,zipfile
    from test_review_api import pack
    from radar_ia.review_api import ReviewStore
    from radar_ia import catalog
    class CloudS3:
        def __init__(self,objects):self.objects=dict(objects)
        def list_objects_v2(self,**kw):return {'Contents':[{'Key':key} for key in self.objects if key.startswith(kw['Prefix'])]}
        def get_object(self,**kw):
            if kw['Key'] not in self.objects:raise ClientError({'Error':{'Code':'NoSuchKey'}},'GetObject')
            raw=self.objects[kw['Key']];return {'Body':io.BytesIO(raw),'ETag':hashlib.sha256(raw).hexdigest()}
        def put_object(self,**kw):
            prior=self.objects.get(kw['Key'])
            if kw.get('IfNoneMatch')=='*' and prior is not None or kw.get('IfMatch') and (prior is None or kw['IfMatch']!=hashlib.sha256(prior).hexdigest()):
                raise ClientError({'Error':{'Code':'PreconditionFailed'}},'PutObject')
            self.objects[kw['Key']]=kw['Body'];return {'ETag':hashlib.sha256(kw['Body']).hexdigest()}
    date='2026-10-29';key=store.key(date);now=datetime.now(timezone.utc).isoformat()
    with zipfile.ZipFile(io.BytesIO(store.s3.objects[key])) as archive:files={name:archive.read(name) for name in archive.namelist()}
    brief=json.loads(files['briefing.json']);brief.update(planned_for=now,collection_cutoff=now)
    files['briefing.json']=json.dumps(brief)
    if automatic=='human_override':
        files['agents/escalation.json']='{"reason":"two_rejections"}'
    elif automatic:
        from radar_ia.production import fingerprint
        files['agents/approval.json']=json.dumps({'policy':'editorial-agents-v1','approved':True,
            'script_digest':fingerprint({'brief':brief,'script':json.loads(files['roteiro.json'])})})
    store.s3.objects[key]=pack(files)
    s3=CloudS3(store.s3.objects);reviews=ReviewStore(s3,'bucket','radar')
    summary=reviews.summary(date);reviews.approve_script(date,dict(digest=summary['digest'],confirmed=True),'owner')
    jobs,sqs,queue,_=setup();summary=reviews.summary(date)
    audio=queue.start(summary,'audio',dict(digest=summary['digest'],confirmed=True),'owner',automatic=automatic)
    if automatic:
        monkeypatch.setenv('AUTOMATIC_PUBLICATION','true')
        monkeypatch.setenv('NOTIFICATION_QUEUE_URL','notifications')
        from radar_ia import push
        def notify(client,url,episode_id):
            assert json.loads(s3.objects['radar/catalog.json'])['episodes'][0]['id']==episode_id
        notice=Mock(side_effect=notify)
        monkeypatch.setattr(push,'episode_notice',notice)
        monkeypatch.setattr(worker.boto3,'client',Mock())
    monkeypatch.setattr(worker,'verify_private',lambda *a:None);monkeypatch.setattr(catalog,'verify_private',lambda *a:None)
    monkeypatch.setattr(worker.Production,'revalidate',lambda *a:None)
    polly=Mock();polly.synthesize_speech.side_effect=lambda **kw:{'AudioStream':io.BytesIO(bytes(32000))}
    assert worker.process(audio['id'],jobs,s3,polly,'bucket','radar','owner',[])=='succeeded', jobs.get(audio['id']).get('error_code')
    summary=reviews.summary(date)
    if automatic:
        assert summary['stage']=='completed'
        with zipfile.ZipFile(io.BytesIO(s3.objects[key])) as archive:
            assert json.loads(archive.read('aprovacao-audio.json'))['mode']=='automatic'
        assert len(json.loads(s3.objects['radar/catalog.json'])['episodes'])==1
        assert worker.process(audio['id'],jobs,s3,polly,'bucket','radar','owner',[])=='duplicate'
        assert polly.synthesize_speech.call_count==1
        notice.assert_called_once()
        return
    assert summary['can_approve_audio'] and not summary['can_publish']
    with pytest.raises(ReviewConflict):queue.start(summary,'publish',dict(digest=summary['audio_digest'],confirmed=True),'owner')
    summary=reviews.approve_audio(date,dict(digest=summary['audio_digest'],confirmed=True),'owner')
    publication=queue.start(summary,'publish',dict(digest=summary['audio_digest'],confirmed=True),'owner')
    assert worker.process(publication['id'],jobs,s3,polly,'bucket','radar','owner',[])=='succeeded'
    assert reviews.summary(date)['stage']=='completed'
    assert len(json.loads(s3.objects['radar/catalog.json'])['episodes'])==1
    assert worker.process(audio['id'],jobs,s3,polly,'bucket','radar','owner',[])=='duplicate'
    assert polly.synthesize_speech.call_count==1


def test_worker_queue_has_timeout_margin_and_api_cannot_synthesize():
    import json
    from pathlib import Path
    resources=json.loads((Path(__file__).parents[1]/'infra/private-app.json').read_text(encoding='utf-8'))['Resources']
    timeout=resources['WorkerFunction']['Properties']['Timeout']
    assert resources['AudioQueue']['Properties']['VisibilityTimeout']>=6*timeout
    assert resources['WorkerQueueMapping']['Properties']['BatchSize']==1
    assert resources['WorkerQueueMapping']['Properties']['ScalingConfig']['MaximumConcurrency']==2
    assert resources['JobsTable']['Properties']['TimeToLiveSpecification']['Enabled']
    api=resources['ApiRole']['Properties']['Policies'][0]['PolicyDocument']['Statement']
    assert not any('polly:SynthesizeSpeech' in statement['Action'] for statement in api)


def test_disabled_automatic_mode_blocks_paid_work(monkeypatch):
    jobs,sqs,queue,summary=setup()
    job=queue.start(summary,'audio',dict(digest=summary['digest'],confirmed=True),'owner',automatic=True)
    monkeypatch.delenv('AUTOMATIC_PUBLICATION',raising=False)
    polly=Mock()
    assert worker.process(job['id'],jobs,Mock(),polly,'bucket','radar','owner',[])=='failed'
    polly.synthesize_speech.assert_not_called()
    assert jobs.get(job['id'])['can_retry'] is False
