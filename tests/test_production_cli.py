import pytest
from radar_ia.production_cli import execute,parser
from radar_ia.cli import main


def test_paid_operation_requires_explicit_flag(tmp_path,monkeypatch,capsys):
    monkeypatch.delenv('S3_BUCKET',raising=False)
    execute(parser().parse_args(['draft']),tmp_path)
    assert 'Nenhuma chamada' in capsys.readouterr().out


def test_review_requires_explicit_confirmation(tmp_path):
    with pytest.raises(ValueError,match='--reviewed'):
        execute(parser().parse_args(['approve-script']),tmp_path)


def test_default_cli_only_displays_help(capsys):
    main([])
    assert 'production' in capsys.readouterr().out


def test_production_help_routes_without_aws(capsys):
    with pytest.raises(SystemExit) as exc:main(['production','--help'])
    assert exc.value.code==0
    assert 'approve-audio' in capsys.readouterr().out


def test_aws_failure_reports_operation_without_response_details(monkeypatch):
    from botocore.exceptions import ClientError
    import radar_ia.production_cli as cli
    def denied(*args):
        raise ClientError({'Error':{'Code':'AccessDenied','Message':'PRIVATE_RESPONSE'}},'GetObject')
    monkeypatch.setattr(cli,'execute',denied)
    with pytest.raises(SystemExit) as result:cli.main(['prepare','--local'])
    assert 'GetObject' in str(result.value)
    assert 'AccessDenied' in str(result.value)
    assert 'PRIVATE_RESPONSE' not in str(result.value)
