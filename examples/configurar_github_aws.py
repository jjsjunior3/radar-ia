"""Prepara IAM para Actions; sem --create apenas salva documentos para revisão."""
import argparse
import json
import os
import subprocess
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from radar_ia.github_iam import documents, oidc_subject


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='jjsjunior3/radar-ia')
    parser.add_argument('--create', action='store_true')
    args = parser.parse_args()
    load_dotenv()
    # O comando roda no terminal autenticado do proprietário. Nunca captura tokens.
    result = subprocess.run(['gh','api',f'repos/{args.repo}'],capture_output=True,text=True)
    if result.returncode:
        raise SystemExit('Não foi possível consultar o repositório. Confirme gh auth status no seu terminal.')
    repo = json.loads(result.stdout)
    if repo['full_name'].lower() != args.repo.lower():
        raise SystemExit('Repositório retornado diverge do solicitado')
    subject = oidc_subject(repo)
    session = boto3.Session(region_name=os.getenv('AWS_REGION','us-east-1'))
    cfg = Config(retries={'total_max_attempts':1},connect_timeout=10,read_timeout=30)
    account = session.client('sts',config=cfg).get_caller_identity()['Account']
    bucket = os.environ.get('S3_BUCKET','').strip()
    trust, policy = documents(account,bucket,os.getenv('S3_PREFIX','radar-ia'),subject)
    target=Path('local-output/github-aws');target.mkdir(parents=True,exist_ok=True)
    for name,data in [('trust.json',trust),('permissions.json',policy)]:
        (target/name).write_text(json.dumps(data,indent=2),encoding='utf-8')
    print('Repositório:',repo['full_name'],'| Branch: main')
    print('Subject exato:',subject)
    print('Documentos IAM:',target.resolve())
    if not args.create:
        print('Nenhuma alteração na AWS. --create cria a função restrita ao projeto.')
        return
    iam=session.client('iam',config=cfg)
    provider=f'arn:aws:iam::{account}:oidc-provider/token.actions.githubusercontent.com'
    try:
        details=iam.get_open_id_connect_provider(OpenIDConnectProviderArn=provider)
        if 'sts.amazonaws.com' not in details['ClientIDList']:
            raise SystemExit('Provedor OIDC existente sem audiência STS; revisar antes de alterar recurso compartilhado.')
    except ClientError as exc:
        if exc.response['Error']['Code']!='NoSuchEntity':raise
        iam.create_open_id_connect_provider(Url='https://token.actions.githubusercontent.com',ClientIDList=['sts.amazonaws.com'],Tags=[{'Key':'Project','Value':'radar-ia'}])
    name='radar-ia-github-production'
    try:
        current=iam.get_role(RoleName=name)['Role']
    except ClientError as exc:
        if exc.response['Error']['Code']!='NoSuchEntity':raise
        current=None
    if current:
        if not any(t['Key']=='Project' and t['Value']=='radar-ia' for t in current.get('Tags',[])):
            raise SystemExit('Função existente sem identificação do projeto; não sobrescrever.')
        # Não amplia uma função existente silenciosamente.
        try:
            existing=iam.get_role_policy(RoleName=name,PolicyName='RadarProduction')['PolicyDocument']
        except ClientError as exc:
            if exc.response['Error']['Code']!='NoSuchEntity':raise
            existing=None
        if current['AssumeRolePolicyDocument']!=trust or (existing is not None and existing!=policy):
            raise SystemExit('Função existente diverge dos documentos gerados. Revisar diferenças antes de atualizar.')
        if existing is None:
            # Recupera criação interrompida entre a função e sua política restrita.
            iam.put_role_policy(RoleName=name,PolicyName='RadarProduction',PolicyDocument=json.dumps(policy))
    else:
        iam.create_role(RoleName=name,AssumeRolePolicyDocument=json.dumps(trust),MaxSessionDuration=3600,
            Description='Radar IA: GitHub Actions main, dados privados e Polly',Tags=[{'Key':'Project','Value':'radar-ia'}])
        iam.put_role_policy(RoleName=name,PolicyName='RadarProduction',PolicyDocument=json.dumps(policy))
    arn=f'arn:aws:iam::{account}:role/{name}'
    (target/'outputs.json').write_text(json.dumps({'AWS_ROLE_ARN':arn,'S3_BUCKET':bucket},indent=2),encoding='utf-8')
    print('Função preparada:',arn)
    print('Configure AWS_ROLE_ARN e S3_BUCKET como variáveis do repositório. Veja docs/07-producao-acompanhada.md.')


if __name__=='__main__':main()
