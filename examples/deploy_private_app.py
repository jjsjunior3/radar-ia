"""Empacota/deploy AWS do app privado. Sem --deploy, somente gera pacote local."""
import argparse
import hashlib
import json
import os
import zipfile
import time
from pathlib import Path
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, WaiterError
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]


def package():
    folder=ROOT/'local-output'/'deploy'
    folder.mkdir(parents=True,exist_ok=True)
    archive=folder/'api.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        # Lista permitida: nunca empacotar .env, credenciais ou dados locais.
        z.writestr('radar_ia/__init__.py','')
        z.write(ROOT/'src/radar_ia/hosted_api.py','radar_ia/hosted_api.py')
        for module in ('review_api','jobs','audio','speech_markup','push','editorial_learning'):
            z.write(ROOT/f'src/radar_ia/{module}.py',f'radar_ia/{module}.py')
    return archive


def stack_exists_or_recover(cf, stack, recover, folder):
    try:
        description=cf.describe_stacks(StackName=stack)['Stacks'][0]
    except ClientError as exc:
        if exc.response['Error']['Code']=='ValidationError' and 'does not exist' in exc.response['Error'].get('Message',''):
            return False
        raise
    status=description['StackStatus']
    if status=='ROLLBACK_COMPLETE':
        if not recover:
            raise SystemExit('A criação anterior foi revertida. Use --deploy --recover-failed para recriar somente a stack falhada, preservando recursos retidos e o bucket de áudio externo.')
        resources=cf.list_stack_resources(StackName=stack)['StackResourceSummaries']
        if any(r['ResourceStatus'] not in ('DELETE_COMPLETE','DELETE_SKIPPED') for r in resources):
            raise SystemExit('Stack falhada contém estado inesperado; revisar recursos antes de recuperar.')
        snapshot={'stack':stack,'status':status,'resources':resources,'note':'Recursos DELETE_SKIPPED permanecem retidos; bucket de áudio externo não pertence à stack.'}
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'failed-stack-inventory.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
        print('Recuperação: inventário salvo. Removendo somente o registro da stack ROLLBACK_COMPLETE; recursos retidos serão preservados.',flush=True)
        if description.get('EnableTerminationProtection'):
            cf.update_termination_protection(EnableTerminationProtection=False,StackName=stack)
        cf.delete_stack(StackName=stack)
        cf.get_waiter('stack_delete_complete').wait(StackName=stack,WaiterConfig={'Delay':10,'MaxAttempts':180})
        return False
    if status not in ('CREATE_COMPLETE','UPDATE_COMPLETE','UPDATE_ROLLBACK_COMPLETE'):
        raise SystemExit(f'Stack em {status}; não iniciar nova implantação enquanto esse estado não for revisado.')
    return True


def wait_for_stack(cf, waiter, stack):
    try:
        cf.get_waiter(waiter).wait(StackName=stack,WaiterConfig={'Delay':10,'MaxAttempts':180})
    except WaiterError:
        events=cf.describe_stack_events(StackName=stack)['StackEvents']
        failures=[e for e in events if e['ResourceStatus'] in ('CREATE_FAILED','UPDATE_FAILED') and 'cancelled' not in e.get('ResourceStatusReason','').lower()]
        for event in failures[:5]:
            print(event['LogicalResourceId']+': '+event.get('ResourceStatusReason','Sem motivo informado'),flush=True)
        raise SystemExit('CloudFormation não concluiu a implantação. Causas acima; não configure o login ainda.') from None


def main():
    parser=argparse.ArgumentParser(description='Infraestrutura AWS privada do Radar IA')
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--deploy',action='store_true',help='Criar/atualizar infraestrutura e enviar interface; gera custos AWS')
    mode.add_argument('--plan',action='store_true',help='Empacotar, enviar pacote e criar change set para stack existente, sem executar a atualização')
    parser.add_argument('--recover-failed',action='store_true',help='Recriar somente stack ROLLBACK_COMPLETE; preservar recursos retidos e áudio existente')
    args=parser.parse_args()
    load_dotenv(ROOT/'.env')
    archive=package()
    print('API empacotada em:',archive)
    if args.plan and args.recover_failed:raise SystemExit('--plan não pode recuperar ou recriar uma stack falhada.')
    if not (args.deploy or args.plan):
        print('Nenhuma alteração AWS. --deploy cria/atualiza CloudFront, Cognito, API Gateway, Lambda, DynamoDB e permissões IAM de execução.')
        return
    from package_worker import package_worker
    worker_archive=package_worker()
    region=os.getenv('AWS_REGION','us-east-1')
    if region!='us-east-1': raise SystemExit('Este template inicial foi preparado e restringido a us-east-1.')
    bucket=os.getenv('S3_BUCKET','').strip()
    if not bucket:raise SystemExit('Configure S3_BUCKET')
    session=boto3.Session(region_name=region)
    config=Config(retries={'total_max_attempts':1},connect_timeout=10,read_timeout=60,request_checksum_calculation='when_required',response_checksum_validation='when_required')
    s3=session.client('s3',config=config)
    cf=session.client('cloudformation',config=config)
    stack='radar-ia-private-app'
    key='radar-ia/deployments/'+hashlib.sha256(archive.read_bytes()).hexdigest()[:24]+'/api.zip'
    s3.put_object(Bucket=bucket,Key=key,Body=archive.read_bytes(),ServerSideEncryption='AES256',ContentType='application/zip')
    worker_key='radar-ia/deployments/'+hashlib.sha256(worker_archive.read_bytes()).hexdigest()[:24]+'/worker.zip'
    s3.put_object(Bucket=bucket,Key=worker_key,Body=worker_archive.read_bytes(),ServerSideEncryption='AES256',ContentType='application/zip')
    parameters=[{'ParameterKey':'WorkerCodeKey','ParameterValue':worker_key},{'ParameterKey':'AudioBucket','ParameterValue':bucket},{'ParameterKey':'AudioPrefix','ParameterValue':os.getenv('S3_PREFIX','radar-ia')},{'ParameterKey':'ApiCodeKey','ParameterValue':key}]
    exists=stack_exists_or_recover(cf,stack,args.recover_failed,ROOT/'local-output/deploy')
    reviewer=os.getenv('APP_REVIEWER_SUB','').strip()
    if exists:
        current=cf.describe_stacks(StackName=stack)['Stacks'][0]
        old={item['OutputKey']:item['OutputValue'] for item in current['Outputs']}
        for parameter in current.get('Parameters',[]):
            if parameter['ParameterKey'] in ('EditorialCodeKey','OpenRouterSecretArn','EditorialScheduleEnabled','VapidSecretArn','VapidPublicKey','AutomaticPublicationEnabled'):
                parameters.append({'ParameterKey':parameter['ParameterKey'],'UsePreviousValue':True})
        email=os.getenv('APP_LOGIN_EMAIL','').strip()
        if email:
            user=session.client('cognito-idp',config=config).admin_get_user(UserPoolId=old['UserPoolId'],Username=email)
            reviewer=next(item['Value'] for item in user['UserAttributes'] if item['Name']=='sub')
        elif not reviewer:
            reviewer=next((item['ParameterValue'] for item in current.get('Parameters',[]) if item['ParameterKey']=='ReviewerSub'),'')
    parameters.append({'ParameterKey':'ReviewerSub','ParameterValue':reviewer})
    template=(ROOT/'infra/private-app.json').read_text(encoding='utf-8')
    cf.validate_template(TemplateBody=template)
    options=dict(StackName=stack,TemplateBody=template,Parameters=parameters,Capabilities=['CAPABILITY_IAM'],Tags=[{'Key':'Project','Value':'RadarIA'}])
    if args.plan:
        if not exists:raise SystemExit('--plan exige uma stack existente e saudável.')
        name='review-'+str(time.time_ns())
        cf.create_change_set(**options,ChangeSetName=name,ChangeSetType='UPDATE')
        cf.get_waiter('change_set_create_complete').wait(StackName=stack,ChangeSetName=name,WaiterConfig={'Delay':5,'MaxAttempts':24})
        plan=cf.describe_change_set(StackName=stack,ChangeSetName=name)
        record={'stack':stack,'change_set':name,'changes':plan['Changes']}
        (ROOT/'local-output/deploy/latest-change-set.json').write_text(json.dumps(record,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
        for item in plan['Changes']:
            change=item['ResourceChange']
            print(change['Action'],change['LogicalResourceId'],'| Replacement:',change.get('Replacement','False'))
        print('Change set preparado, sem executar:',name)
        return
    if exists:
        try:cf.update_stack(**options)
        except ClientError as exc:
            if 'No updates are to be performed' not in exc.response['Error'].get('Message',''):raise
        else:
            print('Atualização iniciada. Aguardando CloudFormation…',flush=True)
            wait_for_stack(cf,'stack_update_complete',stack)
    else:
        cf.create_stack(**options,EnableTerminationProtection=True)
        print('Criação iniciada. CloudFront pode levar vários minutos…',flush=True)
        wait_for_stack(cf,'stack_create_complete',stack)
    description=cf.describe_stacks(StackName=stack)['Stacks'][0]
    outputs={o['OutputKey']:o['OutputValue'] for o in description['Outputs']}
    (ROOT/'local-output/deploy/outputs.json').write_text(json.dumps(outputs,ensure_ascii=False,indent=2),encoding='utf-8')
    public={'apiBase':outputs['ApiUrl'],'authDomain':outputs['AuthDomain'],'clientId':outputs['ClientId']}
    # Somente arquivos web explicitamente selecionados. Código do app é público; dados exigem login.
    assets=['notifications.js','sw.js','production.js','index.html','style.css','auth.js','app.js','icon.svg','manifest.webmanifest']
    mimes={'html':'text/html; charset=utf-8','css':'text/css; charset=utf-8','js':'text/javascript; charset=utf-8','svg':'image/svg+xml','webmanifest':'application/manifest+json'}
    for name in assets:
        s3.put_object(Bucket=outputs['WebBucket'],Key=name,Body=(ROOT/'src/radar_ia/web'/name).read_bytes(),ContentType=mimes[name.rsplit('.',1)[1]],CacheControl='no-cache',ServerSideEncryption='AES256')
    s3.put_object(Bucket=outputs['WebBucket'],Key='config.json',Body=json.dumps(public).encode(),ContentType='application/json',CacheControl='no-store',ServerSideEncryption='AES256')
    session.client('cloudfront',config=config).create_invalidation(DistributionId=outputs['DistributionId'],InvalidationBatch={'Paths':{'Quantity':1,'Items':['/*']},'CallerReference':hashlib.sha256(os.urandom(24)).hexdigest()})
    print('Interface enviada. URL:',outputs['WebUrl'])
    print('Cadastro público desativado; ainda é necessário criar o usuário e definir senha.')


if __name__=='__main__':main()
