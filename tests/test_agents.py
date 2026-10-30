import copy,json
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from radar_ia.agents import EditorialAgents,AgentJournal,EditorialReview,BudgetClient
from radar_ia.production import Production,write_json,read_json,fingerprint
from test_script import brief,payload


def response(payload):
    raw={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(payload),'refusal':None}}],
         'model':'test','id':'test','usage':None}
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=raw['choices'][0]['message']['content'],refusal=None))],
        model='test',id='test',usage=None,model_dump=lambda:raw)


def setup(tmp_path,brief,outputs):
    run=Production(tmp_path);write_json(run.folder/'briefing.json',brief);run.stage('prepared')
    create=Mock(side_effect=[response(p) for p in outputs])
    client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return run,EditorialAgents(run,client,'test'),create


def selected():return {'candidates':[{'news_id':1,'score':4,'reason':'Ferramenta útil com evidência no resumo.'}]}
def review(approved):return {'approved':approved,'quality':4 if approved else 2,'findings':[] if approved else [
    {'news_id':1,'severity':'blocking','issue':'Atribuição insuficiente','correction':'Atribua a alegação à fonte.'}]}


def test_rejected_script_receives_analysis_then_only_approved_version_can_advance(tmp_path,brief,payload):
    revised=copy.deepcopy(payload);revised['intro_pt']='Segundo a fonte, este é o boletim.'
    run,agents,create=setup(tmp_path,brief,[selected(),payload,review(False),revised,review(True)])
    assert agents.select()
    run.draft(agents.generate)
    assert run.state['stage']=='awaiting_script_review'
    assert read_json(run.folder/'agents/approval.json')['round']==2
    second_writer=json.loads(create.call_args_list[3].kwargs['messages'][1]['content'])
    assert second_writer['revision_feedback']['review']['findings'][0]['correction']=='Atribua a alegação à fonte.'
    assert read_json(run.folder/'roteiro.json')['intro_pt']==revised['intro_pt']
    run.approve_script(mode='automatic')
    assert read_json(run.folder/'aprovacao-roteiro.json')['mode']=='automatic'
    changed=read_json(run.folder/'roteiro.json');changed['intro_pt']='Mudou depois da avaliação'
    write_json(run.folder/'roteiro.json',changed)
    with pytest.raises(ValueError,match='aprovação editorial'):run.approve_script(mode='automatic')
    assert create.call_count==5


def test_three_rejections_block_publication_and_do_not_save_final_script(tmp_path,brief,payload):
    outputs=[selected()]+[p for _ in range(3) for p in (payload,review(False))]
    run,agents,create=setup(tmp_path,brief,outputs);assert agents.select()
    with pytest.raises(ValueError,match='três versões'):run.draft(agents.generate)
    assert run.state['stage']=='draft_failed'
    assert not (run.folder/'roteiro.json').exists()
    assert not (run.folder/'resposta-original.json').exists()
    assert not (run.folder/'agents/approval.json').exists()
    assert create.call_count==7


def test_no_relevant_news_stops_before_writer_and_polly(tmp_path,brief):
    verdict=selected();verdict['candidates'][0]['score']=1
    run,agents,create=setup(tmp_path,brief,[verdict])
    assert not agents.select() and run.state['stage']=='no_content'
    assert create.call_count==1


def test_unknown_relevance_id_is_rejected(tmp_path,brief):
    verdict=selected();verdict['candidates'][0]['news_id']=99
    run,agents,_=setup(tmp_path,brief,[verdict])
    with pytest.raises(ValueError,match='IDs'):agents.select()


def test_contradictory_reviewer_approval_cannot_reach_audio(tmp_path,brief,payload):
    verdict=review(False);verdict.update(approved=True,quality=5)
    run,agents,_=setup(tmp_path,brief,[selected(),payload,verdict]);agents.select()
    with pytest.raises(ValueError,match='contraditória'):run.draft(agents.generate)
    assert not (run.folder/'agents/approval.json').exists()


def test_unknown_result_is_never_automatically_charged_again(tmp_path):
    journal=AgentJournal(Production(tmp_path));invoke=Mock(side_effect=TimeoutError())
    with pytest.raises(TimeoutError):journal.call('reviewer-1',{'test':True},invoke)
    with pytest.raises(ValueError,match='incerto'):journal.call('reviewer-1',{'test':True},invoke)
    invoke.assert_called_once()


def test_received_response_is_reused_and_changed_context_is_blocked(tmp_path):
    journal=AgentJournal(Production(tmp_path));invoke=Mock(return_value={'saved':True})
    assert journal.call('stage',{'test':True},invoke)=={'saved':True}
    assert journal.call('stage',{'test':True},invoke)=={'saved':True}
    with pytest.raises(ValueError,match='Contexto'):journal.call('stage',{'test':False},invoke)
    invoke.assert_called_once()


def test_time_budget_blocks_new_paid_call(monkeypatch):
    client=Mock();budget=BudgetClient(client,seconds=0)
    with pytest.raises(TimeoutError):budget.chat.completions.create(model='test')
    client.with_options.assert_not_called()


def test_invalid_received_script_is_corrected_with_validation_analysis(tmp_path,brief,payload):
    run,agents,create=setup(tmp_path,brief,[selected(),{},payload,review(True)])
    agents.select();run.draft(agents.generate)
    correction=json.loads(create.call_args_list[2].kwargs['messages'][1]['content'])['revision_feedback']
    assert 'validation_error' in correction
    assert read_json(run.folder/'agents/approval.json')['round']==2
    assert (run.folder/'agents/writer-1/response.json').exists()


def test_automatic_approval_requires_evaluator_receipt(tmp_path,brief,payload):
    from radar_ia.script import validate_script
    run=Production(tmp_path);write_json(run.folder/'briefing.json',brief);run.stage('prepared')
    run.draft(lambda b,save:(validate_script(payload,b),{}))
    with pytest.raises(ValueError,match='aprovação editorial'):run.approve_script(mode='automatic')
    assert not (run.folder/'aprovacao-roteiro.json').exists()
