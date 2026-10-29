"""Diagnóstico somente leitura via GitHub CLI; não gera conteúdo nem muda configurações."""
import argparse
import base64
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import urlencode
from radar_ia.schedule_diagnostics import interpret


def query(endpoint):
    command=['gh','api',endpoint]
    response=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
    if response.returncode and 'HTTP 401' in response.stderr and any(os.getenv(key) for key in ('GH_TOKEN','GITHUB_TOKEN')):
        # Uma variável antiga do ambiente não deve esconder o login recém-autorizado.
        env={key:value for key,value in os.environ.items() if key not in ('GH_TOKEN','GITHUB_TOKEN')}
        response=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',env=env)
    if response.returncode:
        raise SystemExit('Consulta GitHub recusada. Execute este diagnóstico no terminal em que gh está autenticado.')
    return json.loads(response.stdout)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',default='jjsjunior3/radar-ia')
    args=parser.parse_args()
    repo=query(f'repos/{args.repo}')
    workflow=query(f'repos/{args.repo}/actions/workflows/production.yml')
    variable=query(f'repos/{args.repo}/actions/variables/RADAR_SCHEDULE_ENABLED')
    file=query(f'repos/{args.repo}/contents/.github/workflows/production.yml?'+urlencode({'ref':repo['default_branch']}))
    text=base64.b64decode(file['content']).decode('utf-8-sig')
    schedule=[];inside=False
    for line in text.splitlines():
        if line.startswith('  schedule:'):inside=True
        elif inside and line and not line.startswith('    '):break
        if inside:schedule.append(line)
    runs=query(f'repos/{args.repo}/actions/workflows/production.yml/runs?per_page=10')['workflow_runs']
    scheduled=query(f'repos/{args.repo}/actions/workflows/production.yml/runs?event=schedule&per_page=5')['workflow_runs']
    remote_head=query(f'repos/{args.repo}/commits/'+repo['default_branch'])['sha']
    local_result=subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True,encoding='utf-8')
    local_file=Path('.github/workflows/production.yml')
    def compact(run):
        return {key:run.get(key) for key in ('id','event','status','conclusion','created_at','head_sha','html_url')}
    report={'repository':repo['full_name'],'default_branch':repo['default_branch'],
        'workflow_state':workflow['state'],'workflow_path':workflow['path'],
        'schedule_enabled':variable['value'],'schedule_in_default_branch':'\n'.join(schedule),
        'recent_runs':[{'id':r['id'],'event':r['event'],'status':r['status'],'conclusion':r['conclusion'],
                        'created_at':r['created_at'],'head_sha':r['head_sha']} for r in runs],
        'scheduled_runs_found':len(scheduled),'scheduled_runs':[compact(r) for r in scheduled],
        'local_head':local_result.stdout.strip() if not local_result.returncode else None,
        'remote_head':remote_head,
        'workflow_matches_local':local_file.read_text(encoding='utf-8-sig').replace('\r\n','\n')==text.replace('\r\n','\n') if local_file.exists() else None}
    report['interpretation']=interpret(report)
    target=Path('local-output/diagnostico-agendamento.json');target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    print('Relatório salvo em:',target.resolve())
    print('Resumo:',report['interpretation']['message'])
    for warning in report['interpretation']['warnings']:print('Verificar:',warning)


if __name__=='__main__':main()
