"""Cria bucket exclusivo do Radar IA; sem --create, somente mostra configuração."""
import argparse
import json
import os
from pathlib import Path
from dotenv import load_dotenv
import boto3
from botocore.config import Config
from radar_ia.catalog import BLOCK, verify_private


def main():
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--create',action='store_true')
    group.add_argument('--check',action='store_true')
    args=parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1]/'.env')
    bucket=os.getenv('S3_BUCKET','').strip()
    region=os.getenv('AWS_REGION','us-east-1')
    if not bucket: raise SystemExit('Configure S3_BUCKET no .env')
    print('Bucket:',bucket,'| Região:',region)
    if not args.create and not args.check:
        print('Sem alterações na AWS. --create cria o bucket; --check verifica a proteção.')
        return
    client=boto3.Session().client('s3',region_name=region,config=Config(signature_version='s3v4',retries={'total_max_attempts':1},read_timeout=30,connect_timeout=10))
    if args.create:
        options={'Bucket':bucket,'ObjectOwnership':'BucketOwnerEnforced'}
        if region!='us-east-1': options['CreateBucketConfiguration']={'LocationConstraint':region}
        # Não chamar CreateBucket sobre nome já existente: us-east-1 tem comportamento legado.
        try:
            client.head_bucket(Bucket=bucket)
        except client.exceptions.ClientError as exc:
            if exc.response['Error']['Code'] not in ('404','NoSuchBucket'):
                raise SystemExit('Nome já existente ou acesso negado; não modificar esse bucket.') from None
        else:
            raise SystemExit('Bucket já existe. Use --check; configuração existente foi preservada.')
        client.create_bucket(**options)
        client.put_public_access_block(Bucket=bucket,PublicAccessBlockConfiguration=BLOCK)
        client.put_bucket_encryption(Bucket=bucket,ServerSideEncryptionConfiguration={'Rules':[{'ApplyServerSideEncryptionByDefault':{'SSEAlgorithm':'AES256'}}]})
        client.put_bucket_policy(Bucket=bucket,Policy=json.dumps({'Version':'2012-10-17','Statement':[{'Sid':'DenyInsecureTransport','Effect':'Deny','Principal':'*','Action':'s3:*','Resource':[f'arn:aws:s3:::{bucket}',f'arn:aws:s3:::{bucket}/*'],'Condition':{'Bool':{'aws:SecureTransport':'false'}}}]}))
        client.put_bucket_tagging(Bucket=bucket,Tagging={'TagSet':[{'Key':'Project','Value':'RadarIA'},{'Key':'Environment','Value':'private-mvp'}]})
    verify_private(client,bucket)
    print('Proteções verificadas: acesso público bloqueado, ACLs desativadas e criptografia configurada.')


if __name__=='__main__': main()
