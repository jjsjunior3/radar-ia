"""Pipe UTF-8 no Windows e fallback de token antigo, sem chamadas ao GitHub."""
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys


def load_query():
    return runpy.run_path(str(Path(__file__).parents[1]/'examples/diagnosticar_agendamento.py'))


def test_github_json_with_unicode_survives_a_real_subprocess_pipe(monkeypatch):
    module=load_query()
    real_run=subprocess.run
    payload={'message':'Ação e documentação — 工程'}
    raw=json.dumps(payload,ensure_ascii=False).encode('utf-8')
    def fake_gh(command,**kwargs):
        return real_run([sys.executable,'-c',f'import sys;sys.stdout.buffer.write({raw!r})'],**kwargs)
    monkeypatch.setattr(module['subprocess'],'run',fake_gh)
    assert module['query']('repos/example')==payload


def test_invalid_environment_token_can_fall_back_to_authorized_login(monkeypatch):
    module=load_query()
    monkeypatch.setenv('GH_TOKEN','fake-stale-token')
    calls=[]
    def fake_gh(command,**kwargs):
        env=kwargs.get('env',os.environ)
        calls.append('GH_TOKEN' in env)
        if len(calls)==1:
            return subprocess.CompletedProcess(command,1,'','HTTP 401: Bad credentials')
        return subprocess.CompletedProcess(command,0,'{"login":"test-user"}','')
    monkeypatch.setattr(module['subprocess'],'run',fake_gh)
    assert module['query']('user')=={'login':'test-user'}
    assert calls==[True,False]
