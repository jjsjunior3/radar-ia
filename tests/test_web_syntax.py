"""Valida o novo componente no Node instalado pelo CI, sem dependências npm."""
from pathlib import Path
import shutil
import subprocess
import pytest


@pytest.mark.parametrize('name',['production.js','notifications.js','sw.js'])
def test_production_panel_javascript_parses(name):
    node=shutil.which('node')
    if not node:pytest.skip('Node não instalado neste ambiente; CI usa Node 22')
    source=Path(__file__).parents[1]/'src/radar_ia/web'/name
    result=subprocess.run([node,'--check',str(source)],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stderr


def test_push_worker_behaviour():
    node=shutil.which('node')
    if not node:pytest.skip('Node ausente; CI instala Node 22')
    test=Path(__file__).parents[1]/'tests/web/push.test.cjs'
    result=subprocess.run([node,'--test',str(test)],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stderr+result.stdout
