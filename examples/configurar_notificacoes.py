"""Configura VAPID em Secrets Manager e planeja a atualizacao; sem enviar avisos."""
import argparse,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
import boto3
from dotenv import load_dotenv
from botocore.config import Config
from botocore.exceptions import ClientError
from deploy_private_app import package
from package_worker import package_worker

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',action='store_true');args=parser.parse_args()
    if not args.plan:print('Nenhuma alteracao. --plan prepara segredo, pacotes e change set sem executar.');return
    load_dotenv(ROOT/'.env')
    session=boto3.Session(region_name='us-east-1')
    cfg=Config(connect_timeout=10,read_timeout=90,retries={'total_max_attempts':1},request_checksum_calculation='when_required',response_checksum_validation='when_required')
    cf=session.client('cloudformation',config=cfg);stack='radar-ia-private-app';current=cf.describe_stacks(StackName=stack)['Stacks'][0]
    if current['StackStatus']!='UPDATE_COMPLETE':raise SystemExit('Aguarde a stack concluir antes de planejar.')
    parameters={x['ParameterKey']:x['ParameterValue'] for x in current['Parameters']};outputs={x['OutputKey']:x['OutputValue'] for x in current['Outputs']}
    secrets=session.client('secretsmanager',config=cfg);name='radar-ia/webpush-vapid'
    try:
        record=secrets.describe_secret(SecretId=name)
        key=json.loads(secrets.get_secret_value(SecretId=record['ARN'])['SecretString'])
    except ClientError as exc:
        if exc.response['Error']['Code']!='ResourceNotFoundException':raise
        node=os.getenv('NODE_BINARY') or shutil.which('node')
        if not node:raise SystemExit('Instale Node ou configure NODE_BINARY para gerar a chave VAPID.')
        code="const c=require('node:crypto');const k=c.generateKeyPairSync('ec',{namedCurve:'prime256v1'}).privateKey.export({format:'jwk'});process.stdout.write(JSON.stringify({private_key:k.d,public_key:Buffer.concat([Buffer.from([4]),Buffer.from(k.x,'base64url'),Buffer.from(k.y,'base64url')]).toString('base64url')}));"
        key=json.loads(subprocess.check_output([node,'-e',code],text=True));key['subject']=outputs['WebUrl']
        record=secrets.create_secret(Name=name,SecretString=json.dumps(key),Description='VAPID Web Push Radar IA; chave privada fora dos pacotes',Tags=[{'Key':'Project','Value':'RadarIA'}])
    updates={'VapidSecretArn':record['ARN'],'VapidPublicKey':key['public_key']}
    s3=session.client('s3',config=cfg)
    for parameter,archive in [('ApiCodeKey',package()),('WorkerCodeKey',package_worker())]:
        payload=archive.read_bytes();code_key='radar-ia/deployments/'+hashlib.sha256(payload).hexdigest()[:24]+'/'+archive.name
        s3.put_object(Bucket=parameters['AudioBucket'],Key=code_key,Body=payload,ServerSideEncryption='AES256',ContentType='application/zip');updates[parameter]=code_key
    options=[{'ParameterKey':key,'UsePreviousValue':True} for key in parameters if key not in updates]
    options.extend({'ParameterKey':key,'ParameterValue':value} for key,value in updates.items())
    name='push-'+str(time.time_ns());template=(ROOT/'infra/private-app.json').read_text(encoding='utf-8');cf.validate_template(TemplateBody=template)
    cf.create_change_set(StackName=stack,ChangeSetName=name,ChangeSetType='UPDATE',TemplateBody=template,Parameters=options,Capabilities=['CAPABILITY_IAM'])
    cf.get_waiter('change_set_create_complete').wait(StackName=stack,ChangeSetName=name,WaiterConfig={'Delay':5,'MaxAttempts':24})
    plan=cf.describe_change_set(StackName=stack,ChangeSetName=name)
    (ROOT/'local-output/deploy/push-change-set.json').write_text(json.dumps({'stack':stack,'change_set':name,'changes':plan['Changes']},indent=2,default=str),encoding='utf-8')
    for item in plan['Changes']:
        change=item['ResourceChange'];print(change['Action'],change['LogicalResourceId'],'| Replacement:',change.get('Replacement','False'))
    print('Plano preparado; nenhuma notificacao enviada:',name)


if __name__=='__main__':main()
