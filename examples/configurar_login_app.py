"""Acesso inicial: execução manual pelo proprietário; senha nunca aparece em argumentos/logs."""
import argparse
import getpass
import json
import os
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description='Criar acesso privado e definir senha interativamente')
    parser.add_argument('--email',help='Usa APP_LOGIN_EMAIL do .env quando omitido')
    args=parser.parse_args()
    load_dotenv(ROOT/'.env')
    email=args.email or os.getenv('APP_LOGIN_EMAIL','')
    if not email or '@' not in email:raise SystemExit('Configure APP_LOGIN_EMAIL no .env')
    outputs_path=ROOT/'local-output/deploy/outputs.json'
    if not outputs_path.exists():raise SystemExit('Implante a infraestrutura primeiro.')
    outputs=json.loads(outputs_path.read_text(encoding='utf-8'))
    client=boto3.Session().client('cognito-idp',region_name=os.getenv('AWS_REGION','us-east-1'))
    policy=client.describe_user_pool(UserPoolId=outputs['UserPoolId'])['UserPool']['Policies']['PasswordPolicy']
    minimum=policy['MinimumLength']
    print(f'Política conferida na AWS: mínimo {minimum} caracteres.')
    print('A senha será enviada diretamente ao Cognito. Não a cole no chat.')
    password=getpass.getpass(f'Crie uma senha para o app (mínimo {minimum} caracteres): ')
    confirm=getpass.getpass('Confirme a senha: ')
    if password!=confirm:raise SystemExit('Senhas diferentes; nenhuma alteração foi feita.')
    invalid=(len(password)<minimum or
        policy.get('RequireLowercase',False) and not any(c.islower() for c in password) or
        policy.get('RequireUppercase',False) and not any(c.isupper() for c in password) or
        policy.get('RequireNumbers',False) and not any(c.isdigit() for c in password) or
        policy.get('RequireSymbols',False) and not any(not c.isalnum() for c in password))
    if invalid:
        raise SystemExit(f'Confira a política: mínimo {minimum} e os requisitos de maiúsculas, minúsculas, número e símbolo ativos no Cognito.')
    try:
        client.admin_create_user(UserPoolId=outputs['UserPoolId'],Username=email,UserAttributes=[{'Name':'email','Value':email}],MessageAction='SUPPRESS')
    except ClientError as exc:
        if exc.response['Error']['Code']!='UsernameExistsException':raise
        user=client.admin_get_user(UserPoolId=outputs['UserPoolId'],Username=email)
        if user.get('UserStatus')=='CONFIRMED':
            answer=input('Usuário já tem senha configurada. Digite ALTERAR para trocá-la: ')
            if answer!='ALTERAR':raise SystemExit('Senha existente preservada.')
        else:
            print('Usuário já criado; concluindo a definição da senha.')
    try:
        client.admin_set_user_password(UserPoolId=outputs['UserPoolId'],Username=email,Password=password,Permanent=True)
    except ClientError as exc:
        if exc.response['Error']['Code']=='InvalidPasswordException':
            raise SystemExit('Cognito recusou a senha. Confira a política mostrada acima; esta tentativa não definiu a senha.') from None
        raise
    password=confirm=None
    print('Acesso criado/configurado. Nenhum convite por e-mail foi enviado.')
    print('Abra:',outputs['WebUrl'])
    print('E-mail ainda não verificado; recuperação por e-mail precisa ser configurada posteriormente.')


if __name__=='__main__':main()
