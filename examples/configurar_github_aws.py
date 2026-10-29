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

from radar_ia.github_iam import documents, oidc_subject, is_listbucket_migration


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='jjsjunior3/radar-ia')
    parser.add_argument('--create', action='store_true')
    parser.add_argument('--update', action='store_true', help='Corrige somente a permissão ListBucket da política anterior conhecida')
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
    if not (args.create or args.update):
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
        if args.update:raise SystemExit('Provedor OIDC não encontrado; --update não cria recursos novos.') from None
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
        if current['AssumeRolePolicyDocument']!=trust:
            raise SystemExit('Função existente diverge dos documentos gerados. Revisar diferenças antes de atualizar.')
        if existing is not None and existing!=policy:
            if not (args.update and is_listbucket_migration(existing,policy)):
                raise SystemExit('Política existente diverge. --update aceita somente a correção conhecida de ListBucket; outras diferenças exigem revisão.')
            (target/'permissions-before-update.json').write_text(json.dumps(existing,indent=2),encoding='utf-8')
            iam.put_role_policy(RoleName=name,PolicyName='RadarProduction',PolicyDocument=json.dumps(policy))
            print('Correção aplicada: s3:ListBucket somente no bucket do projeto. Confiança OIDC preservada.')
        if existing is None:
            if args.update:raise SystemExit('Política anterior não encontrada; --update exige a versão conhecida existente.')
            # Recupera criação interrompida entre a função e sua política restrita.
            iam.put_role_policy(RoleName=name,PolicyName='RadarProduction',PolicyDocument=json.dumps(policy))
    else:
        if args.update:
            raise SystemExit('Função não encontrada; --update não cria uma função nova.')
        iam.create_role(RoleName=name,AssumeRolePolicyDocument=json.dumps(trust),MaxSessionDuration=3600,
            Description='Radar IA: GitHub Actions main, dados privados e Polly',Tags=[{'Key':'Project','Value':'radar-ia'}])
        iam.put_role_policy(RoleName=name,PolicyName='RadarProduction',PolicyDocument=json.dumps(policy))
    arn=f'arn:aws:iam::{account}:role/{name}'
    (target/'outputs.json').write_text(json.dumps({'AWS_ROLE_ARN':arn,'S3_BUCKET':bucket},indent=2),encoding='utf-8')
    print('Função preparada:',arn)
    print('Configure AWS_ROLE_ARN e S3_BUCKET como variáveis do repositório. Veja docs/07-producao-acompanhada.md.')


if __name__=='__main__':main()
