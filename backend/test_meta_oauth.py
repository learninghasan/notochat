import hashlib,hmac,json,time
from urllib.parse import urlparse,parse_qs
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session
from main import Base
from test_business import gateway,call
from test_completion import mock_client

@pytest.fixture
def configured(gateway,monkeypatch):
    for k,v in {'META_OAUTH_APP_ID':'123','META_OAUTH_APP_SECRET':'platform-secret','META_OAUTH_GRAPH_VERSION':'v26.0','META_OAUTH_VERIFY_TOKEN':'verify-platform','PUBLIC_FRONTEND_URL':'https://app.example','CREDENTIAL_ENCRYPTION_KEY':Fernet.generate_key().decode()}.items():monkeypatch.setenv(k,v)
    def get(url,args):
        if url.endswith('/oauth/access_token'):return {'access_token':'private-user-token'}
        return {'data':[{'id':'12345','name':'Example shop','access_token':'private-page-token','instagram_business_account':{'id':'67890'}}]}
    calls=mock_client(monkeypatch,get_result=get,post_result={'success':True})
    return *gateway,calls

def start(c,org='org_A'):
    r=call(c,org,'POST','/oauth/meta/start',{});assert r.status_code==200,r.text
    query=parse_qs(urlparse(r.json()['url']).query)
    assert query['redirect_uri']==['https://app.example/api/oauth/meta/callback']
    return query['state'][0]

def connect(c,org='org_A'):
    state=start(c,org)
    r=call(c,org,'POST','/oauth/meta/complete',{'state':state,'code':'fake-code'});assert r.status_code==200,r.text
    return state

def test_oauth_states_are_account_bound_single_use_and_tokens_encrypted(configured):
    c,g,calls=configured;state=start(c)
    assert call(c,'org_B','POST','/oauth/meta/complete',{'state':state,'code':'fake'}).status_code==400
    assert call(c,'org_A','POST','/oauth/meta/complete',{'state':state,'code':'fake'}).status_code==200
    count=len(calls)
    assert call(c,'org_A','POST','/oauth/meta/complete',{'state':state,'code':'fake'}).status_code==400
    assert len(calls)==count
    pages=call(c,'org_A','GET','/oauth/meta/pages');assert pages.json()[0]['id']=='12345' and 'token' not in pages.text
    assert call(c,'org_A','GET','/oauth/meta/pages',role='member').status_code==403
    with Session(g.workspace('org_A').state.engine) as s:
        stored=json.dumps([r.data for r in s.scalars(select(Base.WorkspaceRecord))]);assert 'private-page-token' not in stored and 'private-user-token' not in stored
    selected=call(c,'org_A','POST','/oauth/meta/select',{'page_id':'12345'});assert selected.status_code==200,selected.text
    assert selected.json()['live_send'] is False and 'token' not in selected.text
    assert call(c,'org_A','GET','/oauth/meta/pages').status_code==409
    assert call(c,'org_A','GET','/connections/configuration').json()['page_access_token'] is True

def test_meta_account_cannot_be_stolen_by_another_business(configured):
    c,_,_=configured;connect(c)
    assert call(c,'org_A','POST','/oauth/meta/select',{'page_id':'12345'}).status_code==200
    connect(c,'org_B')
    assert call(c,'org_B','POST','/oauth/meta/select',{'page_id':'12345'}).status_code==409
    assert call(c,'org_B','GET','/connections/configuration').json()['page_access_token'] is False

def test_shared_webhook_routes_signed_events_to_bound_business_only(configured):
    c,_,_=configured;connect(c)
    call(c,'org_A','POST','/oauth/meta/select',{'page_id':'12345'})
    call(c,'org_B','GET','/workspace')
    assert c.get('/webhooks/meta?hub.mode=subscribe&hub.verify_token=verify-platform&hub.challenge=hello').text=='hello'
    body=json.dumps({'object':'page','entry':[{'id':'12345','messaging':[{'recipient':{'id':'12345'},'sender':{'id':'customer1'},'timestamp':int(time.time()*1000),'message':{'mid':'message-1','text':'Hello NotoChat'}}]}]}).encode()
    assert c.post('/webhooks/meta',content=body).status_code==401
    headers={'X-Hub-Signature-256':'sha256='+hmac.new(b'platform-secret',body,hashlib.sha256).hexdigest()}
    result=c.post('/webhooks/meta',content=body,headers=headers);assert result.status_code==200,result.text
    assert result.json()['stored']==1
    assert c.post('/webhooks/meta',content=body,headers=headers).json()['stored']==0
    assert len(call(c,'org_A','GET','/conversations').json())==1
    assert call(c,'org_B','GET','/conversations').json()==[]

def test_expired_state_and_unlisted_page_are_rejected(configured):
    c,g,_=configured;state=start(c)
    with Session(g.workspace('org_A').state.engine) as s:
        r=s.get(Base.WorkspaceRecord,'oauth-state:'+hashlib.sha256(state.encode()).hexdigest());r.data={**r.data,'expires_at':0};s.commit()
    assert call(c,'org_A','POST','/oauth/meta/complete',{'state':state,'code':'fake'}).status_code==400
    connect(c)
    assert call(c,'org_A','POST','/oauth/meta/select',{'page_id':'99999'}).status_code==404
