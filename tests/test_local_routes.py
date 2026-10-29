from radar_ia.local_app import Library, handler_for
import io
import json


def request(tmp_path,path='/',method='GET',headers=None,data=None):
    library=Library(tmp_path,demo=True)
    handler=object.__new__(handler_for(library,8765))
    handler.path=path
    body=json.dumps(data).encode() if data is not None else b''
    handler.headers={'Host':'127.0.0.1:8765','Content-Length':str(len(body)),**(headers or {})}
    handler.rfile=io.BytesIO(body)
    result=[]
    handler.reply=lambda status,payload,mime=None:result.append((status,payload))
    getattr(handler,'do_'+method)()
    return result[0],library


def test_home_and_assets_are_available_without_aws(tmp_path):
    (status,payload),_=request(tmp_path)
    assert status==200 and b'RADAR' in payload


def test_episode_api_has_progress(tmp_path):
    (status,payload),_=request(tmp_path,'/api/episodes')
    assert status==200 and payload['episodes'][0]['progress']['position']==0


def test_post_progress_requires_origin_and_custom_header(tmp_path):
    (status,_),_=request(tmp_path,'/api/progress','POST',data={'episode_id':'demo-1','position':20})
    assert status==403


def test_post_progress_persists(tmp_path):
    (status,payload),lib=request(tmp_path,'/api/progress','POST',headers={'Origin':'http://127.0.0.1:8765','X-Radar-Client':'web'},data={'episode_id':'demo-1','position':20})
    assert status==200 and lib.progress.all()['demo-1']['position']==20


def test_foreign_host_blocked(tmp_path):
    (status,_),_=request(tmp_path,headers={'Host':'evil.example'})
    assert status==403


def test_unknown_episode_cannot_save_state(tmp_path):
    (status,_),_=request(tmp_path,'/api/progress','POST',headers={'Origin':'http://127.0.0.1:8765','X-Radar-Client':'web'},data={'episode_id':'unknown','heard':True})
    assert status==404


def test_path_traversal_not_served(tmp_path):
    (status,_),_=request(tmp_path,'/../../.env')
    assert status==404
