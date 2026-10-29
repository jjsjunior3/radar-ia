"""Publica somente arquivos da interface; não atualiza infraestrutura ou políticas."""
import argparse
import json
import os
import time
from pathlib import Path
import boto3
from botocore.config import Config
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]
ASSETS={'index.html':'text/html; charset=utf-8','style.css':'text/css; charset=utf-8','auth.js':'text/javascript; charset=utf-8','app.js':'text/javascript; charset=utf-8','icon.svg':'image/svg+xml','manifest.webmanifest':'application/manifest+json'}


def main():
    parser=argparse.ArgumentParser(description='Atualização estática sem modificar infraestrutura AWS')
    parser.add_argument('--publish',action='store_true')
    args=parser.parse_args()
    load_dotenv(ROOT/'.env')
    outputs=json.loads((ROOT/'local-output/deploy/outputs.json').read_text(encoding='utf-8'))
    if not args.publish:
        print('Arquivos preparados:',', '.join(ASSETS))
        print('Sem alterações AWS; --publish envia somente esses arquivos e invalida cache CloudFront.')
        return
    session=boto3.Session(region_name=os.getenv('AWS_REGION','us-east-1'))
    config=Config(retries={'total_max_attempts':1},connect_timeout=10,read_timeout=30)
    s3=session.client('s3',config=config)
    for name,mime in ASSETS.items():
        s3.put_object(Bucket=outputs['WebBucket'],Key=name,Body=(ROOT/'src/radar_ia/web'/name).read_bytes(),ContentType=mime,CacheControl='no-cache',ServerSideEncryption='AES256')
    result=session.client('cloudfront',config=config).create_invalidation(DistributionId=outputs['DistributionId'],InvalidationBatch={'Paths':{'Quantity':1,'Items':['/*']},'CallerReference':'web-'+str(time.time_ns())})
    (ROOT/'local-output/deploy/latest-web-invalidation.json').write_text(json.dumps({'id':result['Invalidation']['Id'],'status':result['Invalidation']['Status']},indent=2),encoding='utf-8')
    print('Interface atualizada:',outputs['WebUrl'])
    print('Invalidação de cache:',result['Invalidation']['Status'])


if __name__=='__main__':main()
