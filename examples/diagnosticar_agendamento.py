"""Diagnóstico somente leitura via GitHub CLI; não gera conteúdo nem muda configurações."""
import argparse
import base64
import json
import subprocess
from pathlib import Path


def query(endpoint):
    response=subprocess.run(['gh','api',endpoint],capture_output=True,text=True)
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
    file=query(f'repos/{args.repo}/contents/.github/workflows/production.yml?ref={repo["default_branch"]}')
    text=base64.b64decode(file['content']).decode('utf-8-sig')
    schedule=[];inside=False
    for line in text.splitlines():
        if line.startswith('  schedule:'):inside=True
        elif inside and line and not line.startswith('    '):break
        if inside:schedule.append(line)
    runs=query(f'repos/{args.repo}/actions/workflows/production.yml/runs?per_page=10')['workflow_runs']
    scheduled=query(f'repos/{args.repo}/actions/workflows/production.yml/runs?event=schedule&per_page=5')['workflow_runs']
    report={'repository':repo['full_name'],'default_branch':repo['default_branch'],
        'workflow_state':workflow['state'],'workflow_path':workflow['path'],
        'schedule_enabled':variable['value'],'schedule_in_default_branch':'\n'.join(schedule),
        'recent_runs':[{'id':r['id'],'event':r['event'],'status':r['status'],'conclusion':r['conclusion'],
                        'created_at':r['created_at'],'head_sha':r['head_sha']} for r in runs],
        'scheduled_runs_found':len(scheduled)}
    target=Path('local-output/diagnostico-agendamento.json');target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
    print('Relatório salvo em:',target.resolve())
    if workflow['state']!='active':print('Diagnóstico: workflow não está ativo no GitHub.')
    if variable['value']!='true':print('Diagnóstico: variável de ativação não está exatamente true.')
    if not schedule:print('Diagnóstico: cron não encontrado na branch padrão.')
    if workflow['state']=='active' and variable['value']=='true' and schedule and not scheduled:
        print('Configuração básica presente, mas sem eventos schedule registrados. A causa do não disparo ainda não está confirmada.')


if __name__=='__main__':main()
