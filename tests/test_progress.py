import math
import pytest
from radar_ia.progress import ProgressStore
from radar_ia.local_app import Library


def test_progress_survives_restart(tmp_path):
    path=tmp_path/'progress.sqlite3'
    ProgressStore(path).save('episode',200,position=40)
    assert ProgressStore(path).all()['episode']['position']==40


def test_auto_heard_at_95_percent(tmp_path):
    store=ProgressStore(tmp_path/'p.sqlite3')
    assert store.save('episode',200,position=189)['heard'] is False
    assert store.save('episode',200,position=190)['heard'] is True


def test_manual_unheard_preserves_position(tmp_path):
    store=ProgressStore(tmp_path/'p.sqlite3')
    store.save('episode',200,position=195)
    result=store.save('episode',200,heard=False)
    assert result['position']==195 and result['heard'] is False
    assert store.save('episode',200,position=196)['heard'] is False


@pytest.mark.parametrize('position',[-1,201,float('nan'),float('inf'),True,'20'])
def test_invalid_progress_rejected(tmp_path,position):
    with pytest.raises(ValueError): ProgressStore(tmp_path/'p.sqlite3').save('episode',200,position=position)


def test_episodes_have_independent_progress(tmp_path):
    store=ProgressStore(tmp_path/'p.sqlite3')
    store.save('first',200,position=40)
    store.save('second',200,heard=True)
    assert store.all()['first']['heard'] is False
    assert store.all()['second']['position']==0


def test_demo_never_creates_aws_client(tmp_path,monkeypatch):
    import boto3
    monkeypatch.setattr(boto3,'Session',lambda **kw: pytest.fail('Não deve acessar AWS'))
    library=Library(tmp_path,demo=True)
    assert library.listing()['mode']=='demo'
    with pytest.raises(ValueError):library.audio_url(library.episodes()[0])
