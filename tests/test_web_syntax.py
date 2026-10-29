"""Valida o novo componente no Node instalado pelo CI, sem dependências npm."""
from pathlib import Path
import shutil
import subprocess
import pytest


def test_production_panel_javascript_parses():
    node=shutil.which('node')
    if not node:pytest.skip('Node não instalado neste ambiente; CI usa Node 22')
    source=Path(__file__).parents[1]/'src/radar_ia/web/production.js'
    result=subprocess.run([node,'--check',str(source)],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stderr
