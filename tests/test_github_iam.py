import pytest
from radar_ia.github_iam import oidc_subject,documents,is_listbucket_migration


def test_new_repo_subject_has_immutable_ids_and_main_only():
    repo={'full_name':'junior/radar-ia','owner':{'id':123},'id':456,'created_at':'2026-10-28T12:00:00Z'}
    subject=oidc_subject(repo)
    assert subject=='repo:junior@123/radar-ia@456:ref:refs/heads/main'
    trust,policy=documents('123456789012','radar-private','radar-ia',subject)
    assert trust['Statement'][0]['Condition']['StringEquals']['token.actions.githubusercontent.com:sub']==subject
    actions=[a for s in policy['Statement'] for a in ([s['Action']] if isinstance(s['Action'],str) else s['Action'])]
    assert 'polly:SynthesizeSpeech' in actions
    assert all(not a.startswith(('iam:','cognito','dynamodb:')) for a in actions)
    assert 's3:DeleteObject' not in actions
    listing=[s for s in policy['Statement'] if s['Action']=='s3:ListBucket']
    assert len(listing)==1 and listing[0]['Resource']=='arn:aws:s3:::radar-private'
    assert policy['Statement'][1]['Resource']==[
        'arn:aws:s3:::radar-private/radar-ia/catalog.json',
        'arn:aws:s3:::radar-private/radar-ia/episodes/*',
        'arn:aws:s3:::radar-private/radar-ia/production/*']


def test_older_repo_uses_name_subject():
    assert oidc_subject({'full_name':'junior/radar-ia','created_at':'2025-01-01T00:00:00Z'})=='repo:junior/radar-ia:ref:refs/heads/main'


@pytest.mark.parametrize('prefix',['*','../other','radar?'])
def test_invalid_prefix_rejected(prefix):
    with pytest.raises(ValueError):documents('123456789012','radar-private',prefix,'subject')


def test_update_accepts_only_exact_known_previous_policy():
    import copy
    _,desired=documents('123456789012','radar-private','radar-ia','subject')
    old=copy.deepcopy(desired)
    old['Statement']=old['Statement'][:-1]
    assert is_listbucket_migration(old,desired)
    old['Statement'][1]['Resource']=['*']
    assert not is_listbucket_migration(old,desired)
    assert not is_listbucket_migration(desired,desired)
