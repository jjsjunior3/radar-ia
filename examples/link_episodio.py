"""Gera acesso temporário ao áudio já enviado; não modifica o bucket."""
import argparse
import json
from pathlib import Path
import os
import boto3
from botocore.config import Config
from dotenv import load_dotenv


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--receipt',required=True,type=Path)
    args=parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1]/'.env')
    receipt=json.loads(args.receipt.read_text(encoding='utf-8'))
    if receipt['bucket']!=os.getenv('S3_BUCKET',''):
        raise SystemExit('Recibo não corresponde ao bucket configurado.')
    client=boto3.Session().client('s3',region_name=os.getenv('AWS_REGION','us-east-1'),config=Config(signature_version='s3v4'))
    url=client.generate_presigned_url('get_object',Params={'Bucket':receipt['bucket'],'Key':receipt['episode']['audio_key']},ExpiresIn=300)
    target=args.receipt.parent/'link-temporario.txt'
    target.write_text(url,encoding='utf-8')
    print('Link salvo em:',target.resolve())
    print('Abra no navegador. Válido por até 5 minutos, limitado também à validade das credenciais. Não compartilhar publicamente.')


if __name__=='__main__': main()
