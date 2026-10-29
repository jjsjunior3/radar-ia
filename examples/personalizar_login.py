"""Aplica marca e CSS ao login classico Cognito, sem mudar autenticacao ou plano."""
import argparse
import json
from datetime import datetime,timezone
from pathlib import Path
import boto3
from dotenv import load_dotenv
from botocore.config import Config

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description='Identidade visual do login Cognito do Radar IA')
    parser.add_argument('--apply',action='store_true',help='Enviar logo e CSS para o client existente')
    args=parser.parse_args()
    css=(ROOT/'infra/cognito/login.css').read_text(encoding='utf-8-sig')
    image=(ROOT/'infra/cognito/logo.png').read_bytes()
    if len(css.encode())>3072 or len(image)>100*1024 or not image.startswith(b'\x89PNG\r\n\x1a\n'):
        raise SystemExit('CSS deve ter ate 3 KiB e logo PNG ate 100 KiB.')
    print(f'Preparado: CSS {len(css.encode())} bytes; logo {len(image)} bytes.')
    if not args.apply:
        print('Nenhuma alteracao AWS. --apply envia a identidade visual para o login existente.')
        return
    load_dotenv(ROOT/'.env')
    outputs=json.loads((ROOT/'local-output/deploy/outputs.json').read_text(encoding='utf-8'))
    client=boto3.Session(region_name='us-east-1').client('cognito-idp',config=Config(connect_timeout=10,read_timeout=40,retries={'total_max_attempts':1}))
    domain=outputs['AuthDomain'].split('://')[1].split('.')[0]
    description=client.describe_user_pool_domain(Domain=domain)['DomainDescription']
    if description.get('UserPoolId')!=outputs['UserPoolId'] or description.get('ManagedLoginVersion',1)!=1:
        raise SystemExit('Dominio/pool divergente ou login nao e classico; nenhuma migracao automatica.')
    previous=client.get_ui_customization(UserPoolId=outputs['UserPoolId'],ClientId=outputs['ClientId'])['UICustomization']
    folder=ROOT/'local-output/login-branding';folder.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    (folder/f'backup-{stamp}.json').write_text(json.dumps(previous,default=str,ensure_ascii=False,indent=2),encoding='utf-8')
    client.set_ui_customization(UserPoolId=outputs['UserPoolId'],ClientId=outputs['ClientId'],CSS=css,ImageFile=image)
    current=client.get_ui_customization(UserPoolId=outputs['UserPoolId'],ClientId=outputs['ClientId'])['UICustomization']
    if current.get('CSS')!=css or not current.get('ImageUrl'):raise SystemExit('Envio concluido, mas verificacao retornou dados inesperados; revisar configuracao.')
    print('Marca e CSS aplicados e conferidos no Cognito. A propagacao visual pode levar cerca de um minuto.')


if __name__=='__main__':main()
