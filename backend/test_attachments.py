import asyncio,base64,hashlib,hmac,json,time
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
from main import Base
from attachments import media_url
from test_completion import system,H
from test_business import gateway,call

PNG=b'\x89PNG\r\n\x1a\n'+b'synthetic-image-for-mocked-provider'

@pytest.fixture
def media_shop(system,monkeypatch):
    for key,value in {'CREDENTIAL_ENCRYPTION_KEY':Fernet.generate_key().decode(),'META_APP_SECRET':'media-secret','META_PAGE_ID':'12345','META_PAGE_ACCESS_TOKEN':'fake-page-token','META_GRAPH_VERSION':'v26.0','WHATSAPP_PHONE_NUMBER_ID':'77777','WHATSAPP_ACCESS_TOKEN':'fake-wa-token','OPENAI_API_KEY':'fake-ai','OPENAI_MODEL':'fake-model','OPENAI_TRANSCRIBE_MODEL':'fake-audio'}.items():monkeypatch.setenv(key,value)
    return system

def event(mid='media-1',url='https://scontent.fbcdn.net/photo.png?secret=private',kind='image'):
    return {'object':'page','entry':[{'id':'12345','messaging':[{'recipient':{'id':'12345'},'sender':{'id':'customer'},'timestamp':int(time.time()*1000),'message':{'mid':mid,'attachments':[{'type':kind,'payload':{'url':url}}]}}]}]}

def incoming(c,payload,path='/webhooks/meta',secret='media-secret'):
    raw=json.dumps(payload).encode();return c.post(path,content=raw,headers={'X-Hub-Signature-256':'sha256='+hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()})

def provider(monkeypatch,raw=PNG,mime='image/png',status=200,metadata=None,fail=False,declared=None):
    calls=[]
    class Response:
        status_code=status
        headers={'content-type':mime,**({'content-length':str(declared)} if declared is not None else {})}
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def aiter_bytes(self):
            for i in range(0,len(raw),16):yield raw[i:i+16]
        def raise_for_status(self):
            if fail:raise ValueError('Simulated provider failure')
        def json(self):return metadata or {}
    class Client:
        def __init__(self,**kwargs):assert not kwargs.get('follow_redirects',False)
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def get(self,url,**kwargs):calls.append(('GET',url,kwargs));return Response()
        def stream(self,method,url,**kwargs):calls.append(('STREAM',url,kwargs));return Response()
        async def post(self,url,**kwargs):
            calls.append(('POST',url,kwargs));r=Response();r.json=lambda:{'text':'Customer asks about a shirt','output':[{'content':[{'type':'output_text','text':'Review: image resembles catalog shirt'}]}],'usage':{'input_tokens':5,'output_tokens':5}};return r
    monkeypatch.setattr('httpx.AsyncClient',Client);return calls

def queue_and_run(system,cid,rid,retry=False):
    app,c,_=system
    response=c.post(f'/conversations/{cid}/attachments/{rid}/analyze',headers=H,json={'retry':retry})
    assert response.status_code==200,response.text
    asyncio.run(app.state.run_jobs())
    return c.get('/workspace',headers=H).json()

def test_signed_media_is_encrypted_deduplicated_and_analysis_never_sends(media_shop,monkeypatch):
    app,c,engine=media_shop
    assert incoming(c,event()).json()['stored']==1
    assert incoming(c,event()).json()['stored']==0
    before=c.get('/workspace',headers=H).json();a=before['attachments'][0]
    assert len(before['attachments'])==1 and a['status']=='ready' and before['jobs']==[]
    assert 'private' not in json.dumps(a)
    with Session(engine) as s:
        source=s.get(Base.WorkspaceRecord,'source:'+a['id']);assert 'photo.png' not in json.dumps(source.data)
    calls=provider(monkeypatch)
    w=queue_and_run(media_shop,a['conversation_id'],a['id'])
    assert w['attachments'][0]['status']=='complete' and len(w['assistant_drafts'])==1
    assert all(j['output']['sent'] is False for j in w['jobs'])
    assert len(c.get(f"/conversations/{a['conversation_id']}/messages",headers=H).json())==1
    count=len(calls);queue_and_run(media_shop,a['conversation_id'],a['id']);assert len(calls)==count
    assert all(not url.endswith('/messages') for _,url,_ in calls)
    assert next(args for method,_,args in calls if method=='STREAM')['headers']=={}
    with Session(engine) as s:assert s.get(Base.WorkspaceRecord,'source:'+a['id']) is None

@pytest.mark.parametrize('url',['http://scontent.fbcdn.net/x','https://127.0.0.1/x','https://scontent.fbcdn.net.evil.example/x','https://user:password@scontent.fbcdn.net/x','https://scontent.fbcdn.net:444/x','https://scontent.fbcdn.net/x#fragment','https://example.com/image.png'])
def test_untrusted_media_locations_are_never_fetched(media_shop,monkeypatch,url):
    _,c,_=media_shop;calls=provider(monkeypatch)
    assert incoming(c,event(url=url)).status_code==200
    a=c.get('/workspace',headers=H).json()['attachments'][0];assert a['status']=='unsupported'
    assert c.post(f"/conversations/{a['conversation_id']}/attachments/{a['id']}/analyze",headers=H,json={}).status_code==409
    assert calls==[]

@pytest.mark.parametrize('failure',['redirect','mime','bytes','length','stream_limit','ai'])
def test_failed_media_is_not_retried_or_partially_saved_without_explicit_request(media_shop,monkeypatch,failure):
    _,c,_=media_shop;incoming(c,event());a=c.get('/workspace',headers=H).json()['attachments'][0]
    args={}
    if failure=='redirect':args['status']=302
    if failure=='mime':args['mime']='text/html'
    if failure=='bytes':args['raw']=b'<html>not an image</html>'
    if failure=='length':args['declared']=8_000_001
    if failure=='stream_limit':monkeypatch.setattr('attachments.LIMIT',20)
    if failure=='ai':args['fail']=True
    calls=provider(monkeypatch,**args)
    w=queue_and_run(media_shop,a['conversation_id'],a['id']);assert w['attachments'][0]['status']=='failed' and w['assistant_drafts']==[]
    count=len(calls);asyncio.run(media_shop[0].state.run_jobs());assert len(calls)==count
    assert c.post(f"/conversations/{a['conversation_id']}/attachments/{a['id']}/analyze",headers=H,json={}).status_code==409
    monkeypatch.setattr('attachments.LIMIT',8_000_000);provider(monkeypatch)
    assert queue_and_run(media_shop,a['conversation_id'],a['id'],True)['attachments'][0]['status']=='complete'

def test_auto_media_is_opt_in_and_human_takeover_stops_queued_analysis(media_shop,monkeypatch):
    app,c,_=media_shop;calls=provider(monkeypatch)
    version=c.post('/agent/versions',headers=H,json={'auto_reply':True,'auto_media_analysis':True}).json();c.post('/agent/versions/'+version['id']+'/publish',headers=H)
    incoming(c,event());w=c.get('/workspace',headers=H).json();a=w['attachments'][0]
    assert [j['kind'] for j in w['jobs']]==['media_analyze']
    c.patch(f"/conversations/{a['conversation_id']}/mode",headers=H,json={'mode':'human'})
    asyncio.run(app.state.run_jobs());assert calls==[]
    # Operator explicitly requests review in human mode; this is allowed.
    assert queue_and_run(media_shop,a['conversation_id'],a['id'])['attachments'][0]['status']=='complete'

@pytest.mark.parametrize('kind,mime,raw',[('image','image/png',PNG),('audio','audio/ogg',b'OggSsynthetic-audio')])
def test_whatsapp_media_lookup_is_scoped_and_hash_checked(media_shop,monkeypatch,kind,mime,raw):
    _,c,_=media_shop
    digest=base64.b64encode(hashlib.sha256(raw).digest()).decode()
    payload={'object':'whatsapp_business_account','entry':[{'changes':[{'field':'messages','value':{'metadata':{'phone_number_id':'77777'},'messages':[{'id':'wamid1','from':'customer','timestamp':str(int(time.time())),'type':kind,kind:{'id':'98765','mime_type':mime,'sha256':digest}}]}}]}]}
    assert incoming(c,payload).json()['stored']==1
    a=c.get('/workspace',headers=H).json()['attachments'][0]
    calls=provider(monkeypatch,raw=raw,mime=mime,metadata={'url':'https://lookaside.fbsbx.com/media','mime_type':mime,'file_size':len(raw)})
    assert queue_and_run(media_shop,a['conversation_id'],a['id'])['attachments'][0]['status']=='complete'
    assert calls[0][1]=='https://graph.facebook.com/v26.0/98765'
    assert calls[0][2]['headers']['Authorization']=='Bearer fake-wa-token'
    assert next(args for method,_,args in calls if method=='STREAM')['headers']['Authorization']=='Bearer fake-wa-token'

def test_unsigned_events_and_cross_business_attachment_ids_are_rejected(gateway,monkeypatch):
    c,g=gateway;monkeypatch.setenv('CREDENTIAL_ENCRYPTION_KEY',Fernet.generate_key().decode())
    settings={'app_secret':'media-secret','page_id':'12345','page_access_token':'fake','graph_version':'v26.0'}
    call(c,'org_A','PUT','/connections/configuration',settings)
    call(c,'org_B','POST','/conversations',{'customer':'B customer'})
    path='/business/org_A/webhooks/meta'
    assert c.post(path,json=event()).status_code==403
    assert incoming(c,event(),path).json()['stored']==1
    a=call(c,'org_A','GET','/workspace').json()['attachments'][0]
    assert call(c,'org_B','GET','/workspace').json()['attachments']==[]
    assert call(c,'org_B','POST',f"/conversations/1/attachments/{a['id']}/analyze",{}).status_code==404
    assert call(c,'org_A','POST',f"/conversations/999/attachments/{a['id']}/analyze",{}).status_code==404
