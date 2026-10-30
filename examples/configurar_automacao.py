"""Cria um plano CloudFormation para alternar publicação automática; não executa o plano."""
import argparse
import hashlib
import json
import time
from pathlib import Path
import boto3
from botocore.config import Config
from dotenv import load_dotenv
from deploy_private_app import package
from package_worker import package_worker,package_editorial

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',action='store_true')
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--enable',action='store_true')
    mode.add_argument('--disable',action='store_true')
    args=parser.parse_args()
    if not args.plan:
        print('Sem alteração. Use --plan com --enable ou --disable; o plano exige execução separada.')
        return
    load_dotenv(ROOT/'.env')
    cfg=Config(connect_timeout=10,read_timeout=90,retries={'total_max_attempts':1},request_checksum_calculation='when_required',response_checksum_validation='when_required')
    session=boto3.Session(region_name='us-east-1')
    cf=session.client('cloudformation',config=cfg);stack='radar-ia-private-app'
    current=cf.describe_stacks(StackName=stack)['Stacks'][0]
    if current['StackStatus']!='UPDATE_COMPLETE':raise SystemExit('Aguarde uma stack saudável.')
    previous={p['ParameterKey']:p['ParameterValue'] for p in current['Parameters']}
    updates={'AutomaticPublicationEnabled':'true' if args.enable else 'false'}
    if args.enable:
        if not previous.get('ReviewerSub') or not previous.get('EditorialCodeKey') or not previous.get('VapidSecretArn'):
            raise SystemExit('Configure responsável, agendamento e notificações antes da automação.')
        s3=session.client('s3',config=cfg)
        for parameter,archive in [('ApiCodeKey',package()),('WorkerCodeKey',package_worker()),('EditorialCodeKey',package_editorial())]:
            payload=archive.read_bytes();key='radar-ia/deployments/'+hashlib.sha256(payload).hexdigest()[:24]+'/'+archive.name
            s3.put_object(Bucket=previous['AudioBucket'],Key=key,Body=payload,ServerSideEncryption='AES256',ContentType='application/zip')
            updates[parameter]=key
    template=(ROOT/'infra/private-app.json').read_text(encoding='utf-8')
    cf.validate_template(TemplateBody=template)
    parameters=[{'ParameterKey':key,'UsePreviousValue':True} for key in previous if key not in updates]
    parameters.extend({'ParameterKey':key,'ParameterValue':value} for key,value in updates.items())
    name='automatic-'+str(time.time_ns())
    cf.create_change_set(StackName=stack,ChangeSetName=name,ChangeSetType='UPDATE',TemplateBody=template,Parameters=parameters,Capabilities=['CAPABILITY_IAM'])
    cf.get_waiter('change_set_create_complete').wait(StackName=stack,ChangeSetName=name,WaiterConfig={'Delay':5,'MaxAttempts':30})
    changes=cf.describe_change_set(StackName=stack,ChangeSetName=name)['Changes']
    target=ROOT/'local-output/deploy/automatic-change-set.json'
    target.write_text(json.dumps({'stack':stack,'change_set':name,'enabled':args.enable,'changes':changes},indent=2,default=str),encoding='utf-8')
    for item in changes:
        change=item['ResourceChange'];print(change['Action'],change['LogicalResourceId'],'| Replacement:',change.get('Replacement'))
    print('Plano preparado sem execução:',name)
    print('Reveja o plano; execute com aws cloudformation execute-change-set --stack-name',stack,'--change-set-name',name,'--profile radar-ia')


if __name__=='__main__':main()
