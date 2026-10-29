from datetime import datetime, timezone
import pytest
from radar_ia.schedule_diagnostics import interpret


def report(**changes):
    return {'default_branch':'main','workflow_state':'active','schedule_enabled':'true',
        'schedule_in_default_branch':"schedule: cron definido",'scheduled_runs':[],**changes}


def test_before_local_schedule_is_not_reported_as_failure():
    result=interpret(report(),datetime(2026,10,29,11,29,tzinfo=timezone.utc))
    assert result['state']=='waiting'
    assert result['expected_today']=='2026-10-29T08:30:00-03:00'


def test_no_schedule_after_expected_time_requires_diagnosis():
    result=interpret(report(),datetime(2026,10,29,15,tzinfo=timezone.utc))
    assert result['state']=='missing_scheduled_run'
    assert 'não está confirmada' in result['message']


def test_weekend_does_not_expect_a_daily_run():
    result=interpret(report(),datetime(2026,10,31,15,tzinfo=timezone.utc))
    assert result['state']=='no_edition_expected'
    assert result['next_expected']=='2026-11-02T08:30:00-03:00'


@pytest.mark.parametrize('status,conclusion,expected',[
    ('queued',None,'running'),('in_progress',None,'running'),
    ('completed','success','run_succeeded'),('completed','failure','run_failed')])
def test_today_scheduled_run_is_interpreted(status,conclusion,expected):
    run={'created_at':'2026-10-29T11:35:00Z','status':status,'conclusion':conclusion}
    result=interpret(report(scheduled_runs=[run]),datetime(2026,10,29,15,tzinfo=timezone.utc))
    assert result['state']==expected


def test_yesterday_run_does_not_satisfy_today_even_with_utc_date_today():
    run={'created_at':'2026-10-29T01:00:00Z','status':'completed','conclusion':'success'}
    result=interpret(report(scheduled_runs=[run]),datetime(2026,10,29,15,tzinfo=timezone.utc))
    assert result['state']=='missing_scheduled_run'


def test_repository_configuration_and_unsent_commits_are_visible():
    result=interpret(report(default_branch='develop',workflow_state='disabled_manually',schedule_enabled='false',
        local_head='new',remote_head='old',workflow_matches_local=False),datetime(2026,10,29,15,tzinfo=timezone.utc))
    assert len(result['warnings'])==5


def test_naive_time_is_rejected():
    with pytest.raises(ValueError):interpret(report(),datetime(2026,10,29,15))


def test_successful_but_late_registration_is_not_silently_reported_as_on_time():
    run={'created_at':'2026-10-29T17:29:58Z','status':'completed','conclusion':'success'}
    result=interpret(report(scheduled_runs=[run]),datetime(2026,10,29,19,tzinfo=timezone.utc))
    assert result['state']=='run_succeeded'
    assert result['registration_offset_minutes']==360.0
    assert 'causa do atraso' in result['warnings'][0]
