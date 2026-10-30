from datetime import datetime,timezone
import io,json,zipfile
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from radar_ia import scheduled_editorial as module
from radar_ia.jobs import JobStore,editorial_job_id
from radar_ia.script import validate_script
from test_jobs import Table
from test_review_api import store

NOW=datetime(2026,10,29,11,30,30,tzinfo=timezone.utc)
EVENT={'scheduled_time':'2026-10-29T11:30:00Z','source':'eventbridge'}


@pytest.mark.parametrize('event',[
 {'scheduled_time':'2026-10-29T08:30:00Z','source':'eventbridge'},
 {'scheduled_time':'2026-10-29T12:30:00Z','source':'eventbridge'},
 {'scheduled_time':'2026-10-29T11:30:00','source':'eventbridge'},
 {'scheduled_time':'2026-10-29T11:30:00Z','source':'browser'},
 dict(EVENT,extra=True)])
def test_invalid_or_stale_event_never_claims_or_calls_provider(event):
    jobs=Mock();provider=Mock()
    with pytest.raises(ValueError):module.process(event,jobs,Mock(),Mock(),'bucket','radar','owner','secret',[],now=NOW,generator=provider)
    jobs.create.assert_not_called();provider.assert_not_called()


def test_weekdays_timezone_and_one_hour_window():
    assert module.scheduled_edition(EVENT,NOW)=='2026-10-29'
    with pytest.raises(ValueError):module.scheduled_edition({'scheduled_time':'2026-10-31T11:30:00Z','source':'eventbridge'},datetime(2026,10,31,11,30,1,tzinfo=timezone.utc))
    with pytest.raises(ValueError):module.scheduled_edition(EVENT,datetime(2026,10,29,12,31,tzinfo=timezone.utc))


def prepare(monkeypatch,store,tmp_path):
    monkeypatch.setattr(module,'TemporaryDirectory',lambda **kw:TemporaryDirectory(dir=tmp_path,**kw))
    monkeypatch.setattr(module,'verify_private',lambda *a:None)
    monkeypatch.setattr(module,'read_catalog',lambda *a:({'episodes':[]},None))
    monkeypatch.setattr(module.Production,'revalidate',lambda *a,**kw:None)
    raw=store.s3.objects[store.key('2026-10-29')]
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:files={name:archive.read(name) for name in archive.namelist()}
    brief=json.loads(files['briefing.json']);brief['planned_for']=NOW.isoformat();files['briefing.json']=json.dumps(brief).encode();script=validate_script(json.loads(files['roteiro.json']),brief)
    files={key:value for key,value in files.items() if key not in ('roteiro.json','narracao.txt')}
    files['checkpoint.json']=json.dumps({'date':'2026-10-29','stage':'prepared'}).encode()
    snapshots=[]
    class Store:
        def __init__(self,s3,bucket,prefix,output,day):
            from pathlib import Path
            self.folder=Path(output)/'production'/day
        def load(self):
            self.folder.mkdir(parents=True)
            for name,raw in files.items():(self.folder/name).write_bytes(raw)
        def save(self):snapshots.append(json.loads((self.folder/'checkpoint.json').read_text())['stage'])
    monkeypatch.setattr(module,'ProductionStore',Store)
    return script,snapshots


def test_daily_draft_saves_checkpoint_before_paid_call_and_duplicate_is_noop(monkeypatch,store,tmp_path):
    script,snapshots=prepare(monkeypatch,store,tmp_path);jobs=JobStore(Table());generator=Mock()
    def generate(brief,save):
        assert snapshots[-1]=='draft_in_progress'
        save({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(script.model_dump())}}]})
        return script,{'status':'test'}
    generator.side_effect=generate;secrets=Mock()
    result=module.process(EVENT,jobs,Mock(),secrets,'bucket','radar','owner','secret',[],now=NOW,generator=generator)
    assert result['stage']=='awaiting_script_review'
    assert module.process(EVENT,jobs,Mock(),secrets,'bucket','radar','owner','secret',[],now=NOW,generator=generator)['status']=='duplicate'
    generator.assert_called_once();secrets.get_secret_value.assert_not_called()
    assert jobs.get(editorial_job_id('2026-10-29'))['status']=='succeeded'


def test_uncertain_paid_result_is_failed_without_automatic_retry_or_secret_in_error(monkeypatch,store,tmp_path):
    prepare(monkeypatch,store,tmp_path);jobs=JobStore(Table());generator=Mock(side_effect=TimeoutError('private-provider-data'))
    with pytest.raises(RuntimeError,match='Falha editorial') as error:
        module.process(EVENT,jobs,Mock(),Mock(),'bucket','radar','owner','secret',[],now=NOW,generator=generator)
    assert 'private-provider-data' not in str(error.value)
    assert jobs.get(editorial_job_id('2026-10-29'))['can_retry'] is False
    assert module.process(EVENT,jobs,Mock(),Mock(),'bucket','radar','owner','secret',[],now=NOW,generator=generator)['status']=='duplicate'
    generator.assert_called_once()

def test_existing_catalog_entry_skips_rss_and_llm(monkeypatch,store,tmp_path):
    prepare(monkeypatch,store,tmp_path)
    monkeypatch.setattr(module,'read_catalog',lambda *a:({'episodes':[{'date':'2026-10-29','id':'existing'}]},None))
    jobs=JobStore(Table());generator=Mock();secrets=Mock()
    result=module.process(EVENT,jobs,Mock(),secrets,'bucket','radar','owner','secret',[],now=NOW,generator=generator)
    assert result['stage']=='completed'
    generator.assert_not_called();secrets.get_secret_value.assert_not_called()


def test_infrastructure_timezone_permissions_retry_and_initial_disabled_state():
    from pathlib import Path
    template=json.loads((Path(__file__).parents[1]/'infra/private-app.json').read_text(encoding='utf-8'))
    resources=template['Resources'];schedule=resources['EditorialSchedule']['Properties']
    assert schedule['ScheduleExpression']=='cron(30 8 ? * MON-FRI *)'
    assert schedule['ScheduleExpressionTimezone']=='America/Sao_Paulo'
    assert schedule['FlexibleTimeWindow']=={'Mode':'OFF'}
    assert template['Parameters']['EditorialScheduleEnabled']['Default']=='false'
    assert resources['EditorialAsyncConfig']['Properties']['MaximumRetryAttempts']==0
    statements=resources['EditorialRole']['Properties']['Policies'][0]['PolicyDocument']['Statement']
    assert not any('polly:SynthesizeSpeech' in entry['Action'] for entry in statements)
    writes=[entry for entry in statements if 's3:PutObject' in entry['Action']]
    assert len(writes)==1 and writes[0]['Resource']['Fn::Sub'].endswith('/production/editions/*')
    secrets=[entry for entry in statements if 'secretsmanager:GetSecretValue' in entry['Action']]
    assert secrets[0]['Resource']=={'Ref':'OpenRouterSecretArn'}


def test_automatic_editorial_marks_policy_and_queues_audio_without_polly(monkeypatch,store,tmp_path):
    script,snapshots=prepare(monkeypatch,store,tmp_path)
    queue=Mock();jobs=JobStore(Table())
    def generate(brief,save):
        from radar_ia.production import fingerprint
        for folder in tmp_path.glob('radar-editorial-*/production/*'):
            (folder/'agents').mkdir(exist_ok=True)
            (folder/'agents/approval.json').write_text(json.dumps({'policy':'editorial-agents-v1','approved':True,'script_digest':fingerprint({'brief':brief,'script':script.model_dump()})}))
        return script,{}
    result=module.process(EVENT,jobs,Mock(),Mock(),'bucket','radar','owner','secret',[],now=NOW,generator=generate,automatic_queue=queue)
    assert result['stage']=='script_approved'
    queue.start.assert_called_once()
    args,kwargs=queue.start.call_args
    assert args[1]=='audio' and args[3]=='owner' and kwargs=={'automatic':True}
    assert 'script_approved' in snapshots
    assert module.process(EVENT,jobs,Mock(),Mock(),'bucket','radar','owner','secret',[],now=NOW,generator=generate,automatic_queue=queue)['status']=='duplicate'
    queue.start.assert_called_once()
