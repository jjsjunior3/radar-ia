"""Documentos IAM restritos ao repositório, branch e bucket do Radar IA."""
import re


def oidc_subject(repo):
    name = repo['full_name']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', name):
        raise ValueError('Nome de repositório inválido')
    # GitHub usa subject com IDs para repositórios criados após 15/07/2026.
    if repo['created_at'] >= '2026-07-15T00:00:00Z':
        owner, repository = name.split('/')
        owner_id, repo_id = int(repo['owner']['id']), int(repo['id'])
        return f'repo:{owner}@{owner_id}/{repository}@{repo_id}:ref:refs/heads/main'
    return f'repo:{name}:ref:refs/heads/main'


def documents(account, bucket, prefix, subject, region='us-east-1'):
    if not re.fullmatch(r'\d{12}', account) or not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', bucket):
        raise ValueError('Conta ou bucket inválidos')
    prefix = prefix.strip('/')
    if not re.fullmatch(r'[A-Za-z0-9/_-]+', prefix):
        raise ValueError('Prefixo inválido')
    trust = {'Version':'2012-10-17','Statement':[{'Effect':'Allow',
        'Principal':{'Federated':f'arn:aws:iam::{account}:oidc-provider/token.actions.githubusercontent.com'},
        'Action':'sts:AssumeRoleWithWebIdentity','Condition':{'StringEquals':{
            'token.actions.githubusercontent.com:aud':'sts.amazonaws.com',
            'token.actions.githubusercontent.com:sub':subject}}}]}
    arn = f'arn:aws:s3:::{bucket}'
    policy = {'Version':'2012-10-17','Statement':[
        {'Effect':'Allow','Action':['s3:GetBucketPublicAccessBlock','s3:GetBucketOwnershipControls','s3:GetEncryptionConfiguration'],'Resource':arn},
        {'Effect':'Allow','Action':['s3:GetObject','s3:PutObject'],'Resource':[
            f'{arn}/{prefix}/catalog.json',f'{arn}/{prefix}/episodes/*',f'{arn}/{prefix}/production/*']},
        {'Effect':'Allow','Action':'polly:SynthesizeSpeech','Resource':'*',
            'Condition':{'StringEquals':{'aws:RequestedRegion':region}}}]}
    return trust, policy
