import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from radar_ia.hosted_api import handle,calculate_progress


class FakeBackend:
    def __init__(self): self.users=[]
    def episodes(self):return [dict(id='ep-1',duration_seconds=200,title='Episódio')]
    def states(self,uid):self.users.append(uid);return {}
    def save(self,uid,episode,data):self.users.append(uid);return calculate_progress({},episode['duration_seconds'],data)
    def audio(self,episode):return 'https://example.org/temporary'


def event(route='GET /api/episodes',uid='user-a',token_use='access',body=None):
    return {'routeKey':route,'requestContext':{'http':{'method':route.split()[0]},'authorizer':{'jwt':{'claims':{'sub':uid,'token_use':token_use}}}},'body':json.dumps(body) if body is not None else None}


def test_no_claims_does_not_read_catalog():
    backend=SimpleNamespace(episodes=lambda:pytest.fail('Não acessar dados sem autenticação'))
    assert handle({},backend)['statusCode']==401


def test_id_token_rejected_even_with_sub():
    assert handle(event(token_use='id'),FakeBackend())['statusCode']==401


def test_user_id_only_from_validated_claims():
    backend=FakeBackend()
    response=handle(event('POST /api/progress',uid='real-user',body={'episode_id':'ep-1','position':20}),backend)
    assert response['statusCode']==200
    assert backend.users==['real-user']


def test_user_override_body_rejected():
    backend=FakeBackend()
    response=handle(event('POST /api/progress',body={'episode_id':'ep-1','position':20,'user_id':'other-user'}),backend)
    assert response['statusCode']==400 and not backend.users


def test_unknown_episode_not_saved():
    backend=FakeBackend()
    response=handle(event('POST /api/progress',body={'episode_id':'unknown','position':20}),backend)
    assert response['statusCode']==404 and not backend.users


def test_private_response_not_cached():
    response=handle(event(),FakeBackend())
    assert response['headers']['cache-control']=='no-store'


def test_manual_unheard_preserves_position_in_cloud():
    result=calculate_progress({'position':195,'heard':True},200,{'heard':False})
    assert result['position']==195 and result['heard'] is False


@pytest.mark.parametrize('position',[True,-1,201,'20',float('nan')])
def test_invalid_cloud_position(position):
    with pytest.raises(ValueError):calculate_progress({},200,{'position':position})


def test_template_disables_signup_and_requires_jwt_scopes():
    template=json.loads((Path(__file__).parents[1]/'infra/private-app.json').read_text(encoding='utf-8'))
    r=template['Resources']
    assert r['UserPool']['Properties']['AdminCreateUserConfig']['AllowAdminCreateUserOnly'] is True
    assert r['WebClient']['Properties']['GenerateSecret'] is False
    assert r['WebClient']['Properties']['AllowedOAuthFlows']==['code']
    routes=[v['Properties'] for v in r.values() if v['Type']=='AWS::ApiGatewayV2::Route']
    assert len(routes)==5
    assert all(route['AuthorizationType']=='JWT' and route['AuthorizationScopes']==['openid'] for route in routes)
    assert all(r['WebBucket']['Properties']['PublicAccessBlockConfiguration'].values())


def test_runtime_role_cannot_publish_audio_or_generate_voice():
    template=json.loads((Path(__file__).parents[1]/'infra/private-app.json').read_text(encoding='utf-8'))
    statements=template['Resources']['ApiRole']['Properties']['Policies'][0]['PolicyDocument']['Statement']
    actions=[action for s in statements for action in s['Action']]
    writes=[s for s in statements if 's3:PutObject' in s['Action']]
    assert len(writes)==1
    assert all(item['Fn::Sub'].endswith('/production/editions/*') for item in writes[0]['Resource'])
    assert 'polly:SynthesizeSpeech' not in actions
    assert 'dynamodb:PutItem' in actions
