import base64,json,io
from unittest.mock import Mock
import pytest
from radar_ia.push import PushStore,validate_subscription,subscription_id
from radar_ia.notifications import deliver
from radar_ia.jobs import JobStore
from test_jobs import Table
from botocore.exceptions import ClientError


def subscription(suffix='one'):
    encode=lambda value:base64.urlsafe_b64encode(value).rstrip(b'=').decode()
    return {'endpoint':'https://fcm.googleapis.com/fcm/send/'+suffix,'keys':{'p256dh':encode(b'\x04'+bytes(64)),'auth':encode(bytes(16))}}


class DeviceTable:
    def __init__(self):self.items={};self.conflict=False
    def get_item(self,**kw):
        item=self.items.get(kw['Key']['user_id']);return {'Item':json.loads(json.dumps(item))} if item else {}
    def put_item(self,**kw):
        item=kw['Item'];old=self.items.get(item['user_id'])
        if self.conflict or old and kw.get('ExpressionAttributeValues',{}).get(':v')!=old['version']:
            raise ClientError({'Error':{'Code':'ConditionalCheckFailedException'}},'PutItem')
        self.items[item['user_id']]=item


@pytest.mark.parametrize('url',['https://localhost/fcm/send/test','https://127.0.0.1/fcm/send/test','http://fcm.googleapis.com/fcm/send/test',
 'https://evil.example/fcm/send/test','https://fcm.googleapis.com.evil.example/fcm/send/test','https://user@fcm.googleapis.com/fcm/send/test',
 'https://fcm.googleapis.com:8443/fcm/send/test','https://fcm.googleapis.com/fcm/send/test?token=secret'])
def test_ssrf_targets_and_unexpected_endpoints_rejected(url):
    data=subscription();data['endpoint']=url
    with pytest.raises(ValueError):validate_subscription(data)


def test_device_limit_and_conditional_update_preserve_other_devices():
    store=PushStore(DeviceTable())
    for index in range(5):store.subscribe('owner',subscription(str(index)))
    with pytest.raises(ValueError):store.subscribe('owner',subscription('six'))
    store.subscribe('owner',subscription('0'))
    assert len(store.devices('owner')['devices'])==5
    store.change('owner',subscription_id(subscription('0')))
    assert len(store.devices('owner')['devices'])==4


def test_unpublished_episode_never_notifies_and_duplicate_delivery_is_noop():
    store=PushStore(DeviceTable());store.subscribe('owner',subscription());jobs=JobStore(Table());send=Mock(return_value=201)
    s3=Mock();episode='2026-10-29-'+'a'*16;message={'kind':'episode','episode_id':episode}
    s3.get_object.return_value={'Body':io.BytesIO(json.dumps({'schema_version':1,'episodes':[]}).encode()),'ETag':'etag'}
    with pytest.raises(ValueError):deliver(message,store,jobs,s3,'bucket','radar','owner',send)
    send.assert_not_called()
    for _ in range(2):
        s3.get_object.return_value={'Body':io.BytesIO(json.dumps({'schema_version':1,'episodes':[{'id':episode}]}).encode()),'ETag':'etag'}
        deliver(message,store,jobs,s3,'bucket','radar','owner',send)
    send.assert_called_once();payload=send.call_args.args[1]
    assert 'url' not in payload and 'title' in payload


def test_expired_device_is_removed_and_uncertain_send_does_not_repeat():
    store=PushStore(DeviceTable());first=store.subscribe('owner',subscription())['id'];jobs=JobStore(Table())
    message={'kind':'test','user_id':'owner','subscription_id':first,'request_id':'test-one'}
    deliver(message,store,jobs,Mock(),'bucket','radar','owner',Mock(return_value=410))
    assert not store.devices('owner')['devices']
    store.subscribe('owner',subscription());send=Mock(side_effect=TimeoutError('private-endpoint'))
    message['request_id']='test-two'
    deliver(message,store,jobs,Mock(),'bucket','radar','owner',send)
    deliver(message,store,jobs,Mock(),'bucket','radar','owner',send)
    send.assert_called_once();assert list(jobs.table.items.values())[-1]['status']=='needs_review'


def test_other_user_cannot_subscribe_or_request_test():
    from radar_ia.hosted_api import handle
    from test_review_api import event
    backend=Mock();backend.can_review.return_value=False
    for route in ['GET /api/push/config','POST /api/push/subscribe','POST /api/push/test','POST /api/push/unsubscribe']:
        assert handle(event(route,uid='other',data={}),backend)['statusCode']==403
    backend.push.assert_not_called()
