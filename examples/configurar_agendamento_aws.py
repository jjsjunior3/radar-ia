"""Planeja agendamento AWS sem executar o change set nem gerar tokens de LLM."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path
import boto3
import httpx
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from package_worker import package_editorial

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description='Preparar o agendamento editorial na AWS')
    parser.add_argument('--plan',action='store_true',help='Guardar chave existente em Secrets Manager, empacotar Lambda e criar change set desativado')
    parser.add_argument('--activate-plan',action='store_true',help='Criar change set que habilita o agendamento ja instalado e validado')
    args=parser.parse_args()
    if not (args.plan or args.activate_plan):
        print('Nenhuma alteracao. --plan instala desativado; --activate-plan planeja ativacao apos validacao.')
        return
    if args.plan and args.activate_plan:raise SystemExit('Escolha somente uma etapa.')
    load_dotenv(ROOT/'.env');session=boto3.Session(region_name='us-east-1')
    cfg=Config(connect_timeout=10,read_timeout=60,retries={'total_max_attempts':1},request_checksum_calculation='when_required',response_checksum_validation='when_required')
    cf=session.client('cloudformation',config=cfg);stack='radar-ia-private-app'
    current=cf.describe_stacks(StackName=stack)['Stacks'][0]
    if current['StackStatus'] not in ('UPDATE_COMPLETE','CREATE_COMPLETE'):raise SystemExit('Aguarde uma stack saudavel antes de planejar.')
    previous={item['ParameterKey']:item['ParameterValue'] for item in current['Parameters']}
    updates={'EditorialScheduleEnabled':'true' if args.activate_plan else 'false'}
    if args.plan:
        key=os.getenv('OPENROUTER_API_KEY','').strip()
        if not key:raise SystemExit('Configure a chave OpenRouter local; seu valor nao sera exibido.')
        try:
            auth=httpx.get('https://openrouter.ai/api/v1/key',headers={'Authorization':'Bearer '+key},timeout=20)
        except httpx.HTTPError:raise SystemExit('Nao foi possivel verificar a credencial; nenhuma chamada de geracao solicitada.') from None
        if auth.status_code!=200:raise SystemExit('OpenRouter recusou a credencial; revisar configuracao local.')
        secrets=session.client('secretsmanager',config=cfg);name='radar-ia/openrouter'
        try:secret=secrets.describe_secret(SecretId=name)
        except ClientError as exc:
            if exc.response['Error']['Code']!='ResourceNotFoundException':raise
            secret=secrets.create_secret(Name=name,SecretString=key,Description='OpenRouter Radar IA: acesso exclusivo da producao editorial',Tags=[{'Key':'Project','Value':'RadarIA'}])
        # Chave existente nunca e substituida implicitamente.
        archive=package_editorial();payload=archive.read_bytes();code_key='radar-ia/deployments/'+hashlib.sha256(payload).hexdigest()[:24]+'/editorial.zip'
        session.client('s3',config=cfg).put_object(Bucket=previous['AudioBucket'],Key=code_key,Body=payload,ServerSideEncryption='AES256',ContentType='application/zip')
        updates.update(EditorialCodeKey=code_key,OpenRouterSecretArn=secret['ARN'])
    elif not previous.get('EditorialCodeKey') or not previous.get('OpenRouterSecretArn'):
        raise SystemExit('Instale e valide o agendamento desativado primeiro.')
    parameters=[{'ParameterKey':name,'UsePreviousValue':True} for name in previous if name not in updates]
    parameters.extend({'ParameterKey':name,'ParameterValue':value} for name,value in updates.items())
    template=(ROOT/'infra/private-app.json').read_text(encoding='utf-8');cf.validate_template(TemplateBody=template)
    name='editorial-'+str(time.time_ns())
    cf.create_change_set(StackName=stack,ChangeSetName=name,ChangeSetType='UPDATE',TemplateBody=template,Parameters=parameters,Capabilities=['CAPABILITY_IAM'])
    cf.get_waiter('change_set_create_complete').wait(StackName=stack,ChangeSetName=name,WaiterConfig={'Delay':5,'MaxAttempts':24})
    plan=cf.describe_change_set(StackName=stack,ChangeSetName=name)
    record={'stack':stack,'change_set':name,'changes':plan['Changes']}
    folder=ROOT/'local-output/deploy';folder.mkdir(exist_ok=True)
    (folder/'editorial-change-set.json').write_text(json.dumps(record,indent=2,default=str),encoding='utf-8')
    for item in plan['Changes']:
        change=item['ResourceChange'];print(change['Action'],change['LogicalResourceId'],'| Replacement:',change.get('Replacement','False'))
    print('Change set preparado, sem executar:',name)


if __name__=='__main__':main()
