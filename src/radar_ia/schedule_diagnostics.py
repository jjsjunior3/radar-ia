"""Interpreta evidências do GitHub sem disparar jobs ou assumir causa da falha."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

LOCAL_ZONE = ZoneInfo('America/Sao_Paulo')


def interpret(report, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Diagnóstico exige horário com fuso')
    local = now.astimezone(LOCAL_ZONE)
    expected = datetime.combine(local.date(), time(8, 30), LOCAL_ZONE)
    warnings = []
    if report.get('default_branch') != 'main':
        warnings.append('A branch padrão não é main; o job atual permite somente main.')
    if report.get('workflow_state') != 'active':
        warnings.append('O workflow não está ativo no GitHub.')
    if report.get('schedule_enabled') != 'true':
        warnings.append('RADAR_SCHEDULE_ENABLED não está exatamente true.')
    if not report.get('schedule_in_default_branch', '').strip():
        warnings.append('Bloco schedule ausente no arquivo da branch padrão.')
    if report.get('local_head') and report.get('remote_head') and report['local_head'] != report['remote_head']:
        warnings.append('O commit local é diferente do commit da branch padrão no GitHub.')
    if report.get('workflow_matches_local') is False:
        warnings.append('O arquivo de workflow remoto difere da versão local.')

    today = []
    for run in report.get('scheduled_runs', []):
        created = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
        if created.astimezone(LOCAL_ZONE).date() == local.date():
            today.append(run)
    today.sort(key=lambda run: run['created_at'])
    registration_offset = None
    if today:
        first_created = datetime.fromisoformat(today[0]['created_at'].replace('Z', '+00:00'))
        registration_offset = round((first_created-expected).total_seconds()/60, 1)
        if registration_offset >= 30:
            warnings.append(f'O registro da execução agendada ocorreu {registration_offset:.0f} min após o horário configurado. Isso não identifica a causa do atraso.')
        run = today[-1]
        if run['status'] != 'completed':
            state, message = 'running', 'Há uma execução agendada de hoje em fila ou em andamento.'
        elif run.get('conclusion') == 'success':
            state, message = 'run_succeeded', 'Há execução agendada de hoje concluída com sucesso; conferir também a etapa da edição no S3.'
        else:
            state, message = 'run_failed', f"A execução agendada de hoje terminou com: {run.get('conclusion')}."
    elif local.weekday() > 4:
        state, message = 'no_edition_expected', 'Sem edição regular prevista para o fim de semana.'
    elif local < expected:
        state, message = 'waiting', 'Ainda não chegou o horário previsto de hoje.'
    else:
        state, message = 'missing_scheduled_run', 'Não há evento schedule de hoje nos registros consultados. A causa ainda não está confirmada.'

    next_expected = expected
    if next_expected <= local or next_expected.weekday() > 4:
        next_expected += timedelta(days=1)
        while next_expected.weekday() > 4:
            next_expected += timedelta(days=1)
    return {'checked_at': now.isoformat(), 'local_time': local.isoformat(), 'timezone': str(LOCAL_ZONE),
        'expected_today': expected.isoformat() if local.weekday() < 5 else None,
        'next_expected': next_expected.isoformat(), 'state': state, 'message': message,
        'warnings': warnings, 'scheduled_runs_today': today,
        'registration_offset_minutes':registration_offset}
