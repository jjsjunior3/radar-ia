import io
from datetime import datetime, timezone
import pytest
from radar_ia.production import Production, write_json, read_json
from radar_ia.script import validate_script


@pytest.fixture
def run(tmp_path):
    run=Production(tmp_path, datetime(2026,10,28,12,tzinfo=timezone.utc))
    brief={'theme':'Teste','news':[{'id':1,'summary_original':'Evidence','url':'https://example.org/news'}], 'collection_cutoff':'2026-10-28T12:00:00+00:00'}
    payload={'intro_pt':'Boletim.','stories':[{'news_id':1,'title_pt':'Teste','summary_pt':'Resumo.','narration_pt':'Caching significa armazenamento para reutilização.'}], 'glossary':[{'term_en':'Caching','explanation_pt':'armazenamento para reutilização','news_ids':[1]}], 'outro_pt':'Até amanhã.'}
    write_json(run.folder/'briefing.json',brief)
    write_json(run.folder/'fila-editorial.json',[{'url':'https://example.org/news','title':'Teste'}])
    run.stage('prepared')
    run.draft(lambda brief,save:(validate_script(payload,brief),{}))
    return run


def test_uncertain_llm_call_not_repeated(tmp_path):
    run=Production(tmp_path)
    run.stage('prepared')
    calls=[]
    def fail(*args):
        calls.append(True)
        raise TimeoutError()
    with pytest.raises(TimeoutError):run.draft(fail)
    with pytest.raises(ValueError,match='incerto'):run.draft(fail)
    assert len(calls)==1


def test_script_edit_invalidates_approval(run):
    run.approve_script()
    data=read_json(run.folder/'roteiro.json');data['outro_pt']='Outro encerramento.'
    write_json(run.folder/'roteiro.json',data)
    with pytest.raises(ValueError,match='aprovação'):run.approved_bundle()


def test_audio_retry_reuses_saved_chunks(run):
    run.approve_script()
    class Polly:
        calls=0
        def synthesize_speech(self,**kwargs):
            self.calls+=1
            return {'AudioStream':io.BytesIO(b'\0\0'*16000)}
    polly=Polly()
    run.synthesize(polly)
    calls=polly.calls
    run.synthesize(polly)
    assert polly.calls==calls
    assert run.state['stage']=='awaiting_audio_review'


def test_publication_failure_does_not_advance_coverage(run):
    run.approve_script()
    class Polly:
        def synthesize_speech(self,**kwargs):return {'AudioStream':io.BytesIO(b'\0\0'*16000)}
    run.synthesize(Polly());run.approve_audio()
    def fail(*args):raise TimeoutError()
    with pytest.raises(TimeoutError):run.publish(fail)
    assert not run.global_path.exists()
    run.publish(lambda *args:{'id':'episode-1'})
    state=read_json(run.global_path)
    assert state['last_covered_at']=='2026-10-28T12:00:00+00:00'
    assert state['queue'][0]['used_in']==['episode-1']
    assert run.state['stage']=='completed'


def test_existing_catalog_episode_never_generates_again(tmp_path):
    run=Production(tmp_path, datetime(2026,10,28,12,tzinfo=timezone.utc))
    def forbidden(*args):raise AssertionError('Não coletar')
    run.prepare([],{'episodes':[{'id':'existing','date':'2026-10-28'}]},collector=forbidden)
    assert run.state['stage']=='completed'
    assert run.state['episode_id']=='existing'


def test_collection_selects_variable_count_and_empty_day(tmp_path):
    now=datetime(2026,10,28,12,tzinfo=timezone.utc)
    candidate={'title':'New SDK for LLM agents','summary':'API for inference and agents',
        'url':'https://example.org/news','published':now.isoformat(),
        'source':'https://example.org/feed','source_name':'Example'}
    def collector(sources,now,since):
        return {'collected_at':now.isoformat(),'candidates':[candidate]}
    run=Production(tmp_path/'one',now)
    run.prepare([],{'episodes':[]},collector=collector)
    assert len(read_json(run.folder/'briefing.json')['news'])==1
    assert run.state['stage']=='prepared'
    empty=Production(tmp_path/'empty',now)
    empty.prepare([],{'episodes':[]},collector=lambda *args:{'collected_at':now.isoformat(),'candidates':[]})
    assert empty.state['stage']=='no_content'
    assert not empty.global_path.exists()


def test_changed_audio_cannot_be_approved(run):
    run.approve_script()
    class Polly:
        def synthesize_speech(self,**kwargs):return {'AudioStream':io.BytesIO(b'\0\0'*16000)}
    run.synthesize(Polly())
    (run.folder/'episode.wav').write_bytes(b'changed')
    with pytest.raises(ValueError,match='Áudio alterado'):run.approve_audio()


def test_lost_polly_response_blocks_automatic_charge_retry(run):
    run.approve_script()
    class Polly:
        calls=0
        def synthesize_speech(self,**kwargs):
            self.calls+=1
            raise TimeoutError()
    polly=Polly()
    with pytest.raises(TimeoutError):run.synthesize(polly)
    with pytest.raises(ValueError,match='não repetir cobrança'):run.synthesize(polly)
    assert polly.calls==1


def test_replan_does_not_discard_generated_script(run):
    with pytest.raises(ValueError,match='antes de iniciar'):run.replan()
    assert (run.folder/'roteiro.json').exists()


def test_replan_does_not_refresh_expired_collection(tmp_path):
    run=Production(tmp_path,datetime(2026,10,29,15,tzinfo=timezone.utc))
    run.stage('prepared')
    write_json(run.folder/'coleta.json',{'collected_at':'2026-10-27T15:00:00+00:00'})
    with pytest.raises(ValueError,match='Coleta antiga'):run.replan()


def test_voice_revision_preserves_old_audio_and_script_approval(run):
    run.approve_script()
    class Polly:
        def synthesize_speech(self,**kwargs):return {'AudioStream':io.BytesIO(b'\0\0'*16000)}
    run.synthesize(Polly(),voice='Camila')
    old=(run.folder/'episode.wav').read_bytes()
    called=[]
    def archive():
        assert (run.folder/'episode.wav').read_bytes()==old
        called.append(True)
        return {'key':'private-backup'}
    run.restart_audio(archive)
    assert called==[True] and run.state['stage']=='script_approved'
    assert not (run.folder/'episode.wav').exists()
    assert list((run.output/'audio-backups').rglob('episode.wav'))[0].read_bytes()==old
    run.approved_bundle()
    metadata=run.synthesize(Polly())
    assert metadata['voice']=='Leo'
    assert run.state['stage']=='awaiting_audio_review'


def test_failed_archive_keeps_existing_audio(run):
    run.approve_script()
    class Polly:
        def synthesize_speech(self,**kwargs):return {'AudioStream':io.BytesIO(b'\0\0'*16000)}
    run.synthesize(Polly())
    def fail():raise OSError('Backup indisponível')
    with pytest.raises(OSError):run.restart_audio(fail)
    assert (run.folder/'episode.wav').exists()
    assert run.state['stage']=='awaiting_audio_review'


def test_cannot_replace_audio_after_approval(run):
    run.stage('audio_approved')
    with pytest.raises(ValueError,match='ainda não aprovado'):run.restart_audio()
