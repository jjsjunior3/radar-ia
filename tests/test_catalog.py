import io
import json
import wave
import pytest
from botocore.exceptions import ClientError
from radar_ia.catalog import BLOCK, upload_episode


class FakeS3:
    def __init__(self): self.objects={}; self.calls=[]; self.block=dict(BLOCK); self.conflict=False
    def get_public_access_block(self,**kw): return {'PublicAccessBlockConfiguration':self.block}
    def get_bucket_ownership_controls(self,**kw): return {'OwnershipControls':{'Rules':[{'ObjectOwnership':'BucketOwnerEnforced'}]}}
    def get_bucket_encryption(self,**kw): return {'ServerSideEncryptionConfiguration':{}}
    def get_object(self,**kw):
        if kw['Key'] not in self.objects:
            raise ClientError({'Error':{'Code':'NoSuchKey'}},'GetObject')
        return {'Body':io.BytesIO(self.objects[kw['Key']]),'ETag':'"current"'}
    def put_object(self,**kw):
        self.calls.append(kw)
        if self.conflict and kw['Key'].endswith('catalog.json'):
            raise ClientError({'Error':{'Code':'PreconditionFailed'}},'PutObject')
        self.objects[kw['Key']]=kw['Body']


def upload(client):
    data=io.BytesIO()
    with wave.open(data,'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b'\0\0'*16000)
    return upload_episode(client,'private-bucket','radar-ia',audio=data.getvalue(),script={'text':'teste'},narration='teste',brief={'theme':'Ferramentas','news':[{'url':'https://example.org'}]},date='2026-10-28',title='Teste')


def test_assets_precede_catalog_and_no_public_acl():
    client=FakeS3()
    episode,created=upload(client)
    assert created and episode['duration_seconds']==1
    assert client.calls[-1]['Key']=='radar-ia/catalog.json'
    assert client.calls[-1]['IfNoneMatch']=='*'
    assert all('ACL' not in call for call in client.calls)
    assert all(call['ServerSideEncryption']=='AES256' for call in client.calls)


def test_duplicate_upload_is_idempotent():
    client=FakeS3(); first,_=upload(client); count=len(client.calls)
    second,created=upload(client)
    assert first==second and not created
    assert len(client.calls)==count


def test_public_bucket_blocks_upload():
    client=FakeS3(); client.block['BlockPublicPolicy']=False
    with pytest.raises(ValueError): upload(client)
    assert not client.calls


def test_catalog_conflict_does_not_publish_entry():
    client=FakeS3(); client.conflict=True
    with pytest.raises(ClientError): upload(client)
    assert 'radar-ia/catalog.json' not in client.objects


def test_existing_catalog_uses_etag_condition():
    client=FakeS3(); client.objects['radar-ia/catalog.json']=json.dumps({'schema_version':1,'episodes':[]}).encode()
    upload(client)
    assert client.calls[-1]['IfMatch']=='"current"'
