"""Configura variáveis e segredo do repositório sem exibir a chave."""
import argparse
import json
import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',default='jjsjunior3/radar-ia')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    load_dotenv()
    path=Path('local-output/github-aws/outputs.json')
    if not path.exists():raise SystemExit('Execute configurar_github_aws.py --create primeiro.')
    values=json.loads(path.read_text(encoding='utf-8'))
    key=os.getenv('OPENROUTER_API_KEY','').strip()
    if not key:raise SystemExit('Configure OPENROUTER_API_KEY no .env local.')
    print('Variáveis: AWS_ROLE_ARN, S3_BUCKET, RADAR_SCHEDULE_ENABLED=false')
    print('Segredo: OPENROUTER_API_KEY (valor oculto)')
    if not args.apply:
        print('Nenhuma alteração. --apply configura o GitHub; rotina permanece desativada.')
        return
    for name,value in {**values,'RADAR_SCHEDULE_ENABLED':'false'}.items():
        result=subprocess.run(['gh','variable','set',name,'--repo',args.repo,'--body',value],capture_output=True)
        if result.returncode:raise SystemExit(f'Falha ao configurar {name}. Confirme a autenticação do gh no seu terminal.')
    result=subprocess.run(['gh','secret','set','OPENROUTER_API_KEY','--repo',args.repo],input=key.encode(),capture_output=True)
    if result.returncode:raise SystemExit('Falha ao cadastrar segredo; valor não exibido. Confirme autenticação e permissões no GitHub.')
    print('GitHub configurado. Nenhuma geração iniciada. Execute primeiro a etapa prepare manualmente.')


if __name__=='__main__':main()
