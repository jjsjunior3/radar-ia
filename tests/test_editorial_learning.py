import io,json,hashlib,zipfile
from unittest.mock import Mock
from datetime import date,timedelta
import pytest
from botocore.exceptions import ClientError
from radar_ia.editorial_learning import record_feedback,load_feedback
from radar_ia.review_api import ReviewStore
from radar_ia.hosted_api import Backend
from test_review_api import store,pack


class MemoryS3:
    def __init__(self):self.objects={}
    def get_object(self,**kw):
        if kw['Key'] not in self.objects:raise ClientError({'Error':{'Code':'NoSuchKey'}},'GetObject')
        return {'Body':io.BytesIO(self.objects[kw['Key']])}
    def put_object(self,**kw):
        if kw.get('IfNoneMatch')=='*' and kw['Key'] in self.objects:raise ClientError({'Error':{'Code':'PreconditionFailed'}},'PutObject')
        self.objects[kw['Key']]=kw['Body'];return {}


def summary(day):return {'date':day,'digest':'a'*64,'human_approved_by':'owner','human_feedback':'Explique as siglas antes de usá-las.','narration':'Exemplo aprovado.','theme':'Engenharia'}


def test_only_human_approvals_feed_bounded_recent_memory():
    s3=MemoryS3()
    for offset in range(1,18):record_feedback(s3,'bucket','radar',summary((date(2026,10,30)-timedelta(days=offset)).isoformat()),'owner')
    memory=load_feedback(s3,'bucket','radar','2026-10-30','owner')
    assert len(memory)==5 and memory[0]['date']=='2026-10-29'
    assert memory[0]['feedback']=='Explique as siglas antes de usá-las.'
    assert 'approved_by' not in memory[0]
    before=len(s3.objects);record_feedback(s3,'bucket','radar',summary('2026-10-30'),'other')
    assert len(s3.objects)==before


def test_feedback_is_idempotent_and_invalid_owner_is_rejected():
    s3=MemoryS3();item=summary('2026-10-29')
    record_feedback(s3,'bucket','radar',item,'owner');item['human_feedback']='Não sobrescrever decisão confirmada'
    record_feedback(s3,'bucket','radar',item,'owner')
    assert load_feedback(s3,'bucket','radar','2026-10-30','owner')[0]['feedback']!=item['human_feedback']
    with pytest.raises(ValueError,match='Origem'):load_feedback(s3,'bucket','radar','2026-10-30','other')


def test_human_escalation_shows_reports_and_resumes_only_after_bound_approval(monkeypatch,store):
    key=store.key('2026-10-29')
    with zipfile.ZipFile(io.BytesIO(store.s3.objects[key])) as z:files={name:z.read(name) for name in z.namelist()}
    files['checkpoint.json']=json.dumps({'date':'2026-10-29','stage':'awaiting_human_review'})
    files['agents/escalation.json']='{"reason":"two_rejections"}'
    review={'approved':False,'quality':2,'findings':[{'news_id':1,'severity':'blocking','issue':'Falta atribuição','correction':'Atribua à fonte'}]}
    for i in (1,2):files[f'agents/review-{i}.json']=json.dumps(review)
    store.s3.objects[key]=pack(files)
    original=store.s3.put_object
    def put(**kw):
        if '/feedback/' in kw['Key']:
            store.s3.objects[kw['Key']]=kw['Body'];return {}
        return original(**kw)
    store.s3.put_object=put
    backend=Backend.__new__(Backend);backend.s3=store.s3;backend.bucket='bucket';backend.prefix='radar';backend.queue=Mock()
    backend.production=lambda day:dict(store.summary(day),automatic_publication=True)
    monkeypatch.setenv('AUTOMATIC_PUBLICATION','true')
    before=store.summary('2026-10-29');assert before['can_approve_script'] and len(before['editorial_reviews'])==2
    data={'digest':before['digest'],'confirmed':True,'feedback':'Prefiro transições curtas.'}
    result=backend.approve_script('2026-10-29',data,'owner')
    assert result['stage']=='script_approved'
    assert backend.queue.start.call_args.kwargs=={'automatic':True}
    with zipfile.ZipFile(io.BytesIO(store.s3.objects[key])) as z:
        approval=json.loads(z.read('aprovacao-roteiro.json'))
        assert approval['editorial_override'] and approval['approved_by']=='owner'
        assert approval['feedback']==data['feedback']
    assert 'radar/production/feedback/2026-10-29.json' in store.s3.objects


def test_feedback_length_is_limited_before_any_mutation(store):
    before=store.summary('2026-10-29')
    with pytest.raises(ValueError):store.approve_script('2026-10-29',{'digest':before['digest'],'confirmed':True,'feedback':'x'*2001},'owner')
    assert store.summary('2026-10-29')['stage']=='awaiting_script_review'
