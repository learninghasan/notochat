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
    assert call(c,'org_A','GET','/oauth/meta/pages').json()==[]
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


def test_start_purges_expired_secrets_only_in_current_business(configured):
    c,g,_=configured
    connect(c,'org_A');connect(c,'org_B')
    engine=g.workspace('org_A').state.engine
    with Session(engine) as s:
        r=s.get(Base.WorkspaceRecord,'oauth-pages:user_test');r.data={**r.data,'expires_at':0}
        s.add(Base.WorkspaceRecord(id='oauth-state:expired',kind='private_oauth',data={'expires_at':0,'status':'consumed'}))
        s.add(Base.WorkspaceRecord(id='unrelated-record',kind='knowledge',data={'expires_at':0,'title':'Keep me'}));s.commit()
    fresh=start(c,'org_A')
    with Session(engine) as s:
        assert s.get(Base.WorkspaceRecord,'oauth-pages:user_test') is None
        assert s.get(Base.WorkspaceRecord,'oauth-state:expired') is None
        assert s.get(Base.WorkspaceRecord,'unrelated-record') is not None
        assert s.get(Base.WorkspaceRecord,'oauth-state:'+hashlib.sha256(fresh.encode()).hexdigest()) is not None
    assert call(c,'org_B','GET','/oauth/meta/pages').status_code==200

def test_multiple_pages_preserve_tokens_route_by_recipient_and_pause_independently(configured,monkeypatch):
    c,g,calls=configured
    connect(c);assert call(c,'org_A','POST','/oauth/meta/select',{'page_id':'12345'}).status_code==200
    def get(url,args):
        if url.endswith('/oauth/access_token'):return {'access_token':'private-user-2'}
        return {'data':[{'id':'22222','name':'Second shop','access_token':'private-page-2','instagram_business_account':{'id':'33333'}}]}
    calls=mock_client(monkeypatch,get_result=get,post_result={'success':True})
    connect(c);r=call(c,'org_A','POST','/oauth/meta/select',{'page_id':'22222'});assert r.status_code==200,r.text
    count=len(calls);assert call(c,'org_A','POST','/oauth/meta/select',{'page_id':'22222'}).status_code==200;assert len(calls)==count
    status=call(c,'org_A','GET','/connections/configuration').json()
    assert {p['id'] for p in status['pages']}=={'12345','22222'}
    assert 'private-page' not in json.dumps(status)
    assert g.workspace('org_A').state.channel_account('Messenger','12345')['META_PAGE_ACCESS_TOKEN']=='private-page-token'
    assert g.workspace('org_A').state.channel_account('Instagram','33333')['INSTAGRAM_ACCESS_TOKEN']=='private-page-2'
    # Same sender and provider message ID on different pages must remain separate.
    body=json.dumps({'object':'page','entry':[{'id':pid,'messaging':[{'recipient':{'id':pid},'sender':{'id':'same-sender'},'timestamp':int(time.time()*1000),'message':{'mid':'same-message-id','text':'Question for '+pid}}]} for pid in ['12345','22222']]}).encode()
    headers={'X-Hub-Signature-256':'sha256='+hmac.new(b'platform-secret',body,hashlib.sha256).hexdigest()}
    assert c.post('/webhooks/meta',content=body,headers=headers).json()['stored']==2
    assert c.post('/webhooks/meta',content=body,headers=headers).json()['stored']==0
    conversations=call(c,'org_A','GET','/conversations').json();assert len(conversations)==2
    w=call(c,'org_A','GET','/workspace').json();assert {m['account'] for m in w['conversation_meta'].values()}=={'12345','22222'}
    assert call(c,'org_B','GET','/conversations').json()==[]
    # Only mocked provider delivery is performed.
    calls=mock_client(monkeypatch,post_result={'message_id':'accepted'})
    assert call(c,'org_A','PUT','/connections/configuration',{'live_send':True}).status_code==200
    for chat in conversations:
        call(c,'org_A','PATCH',f"/conversations/{chat['id']}/mode",{'mode':'human'})
        call(c,'org_A','POST',f"/conversations/{chat['id']}/messages",{'text':'Team reply'})
        mid=call(c,'org_A','GET',f"/conversations/{chat['id']}/messages").json()[-1]['id']
        assert call(c,'org_A','POST',f"/conversations/{chat['id']}/deliver",{'message_id':mid}).status_code==200
    assert {args['headers']['Authorization'] for _,url,args in calls}=={'Bearer private-page-token','Bearer private-page-2'}
    assert call(c,'org_A','PATCH','/connections/meta/pages/12345',{'enabled':False},role='member').status_code==403
    assert call(c,'org_A','PATCH','/connections/meta/pages/12345',{'enabled':False}).status_code==200
    assert g.workspace('org_A').state.channel_account('Messenger','12345') is None
    assert g.workspace('org_A').state.channel_account('Instagram','67890') is None
    assert g.workspace('org_A').state.channel_account('Messenger','22222') is not None
    assert call(c,'org_B','PATCH','/connections/meta/pages/22222',{'enabled':False}).status_code==404
    assert call(c,'org_A','PUT','/connections/configuration',{'page_id':'99999'}).status_code==409
    # Paused page cannot receive new messages, while the other still can.
    newer=body.replace(b'same-message-id',b'new-message-id');headers['X-Hub-Signature-256']='sha256='+hmac.new(b'platform-secret',newer,hashlib.sha256).hexdigest()
    assert c.post('/webhooks/meta',content=newer,headers=headers).json()['stored']==1


def test_explicit_trial_policy_once_per_workspace_and_rollback(configured,monkeypatch):
    c,g,_=configured
    monkeypatch.setenv('PAGE_CONNECT_TRIAL_PAISA','2500')
    monkeypatch.setenv('PAGE_CONNECT_TRIAL_POLICY_ID','synthetic-offer-v1')
    monkeypatch.setenv('PAGE_CONNECT_TRIAL_SCOPE','workspace')
    connect(c)
    assert call(c,'org_A','POST','/oauth/meta/select',{'page_id':'999999'}).status_code==404
    assert call(c,'org_A','GET','/billing').json()['balance_paisa']==0
    assert call(c,'org_A','POST','/oauth/meta/select',{'page_id':'12345'}).status_code==200
    assert call(c,'org_A','POST','/oauth/meta/select',{'page_id':'12345'}).status_code==200
    # Reauthorization and a changed offer must not mint repeated credit.
    monkeypatch.setenv('PAGE_CONNECT_TRIAL_POLICY_ID','synthetic-offer-v2')
    connect(c)
    assert call(c,'org_A','POST','/oauth/meta/select',{'page_id':'12345'}).status_code==200
    billing=call(c,'org_A','GET','/billing').json()
    assert billing['balance_paisa']==2500
    assert len([x for x in billing['ledger'] if x['type']=='page_connect_trial'])==1
    assert call(c,'org_B','GET','/billing').json()['balance_paisa']==0
    app=g.workspace('org_B')
    with Session(app.state.engine) as s:
        app.state.grant_page_trial(s,'synthetic-rollback')
        s.rollback()
    assert call(c,'org_B','GET','/billing').json()['balance_paisa']==0


def test_trial_is_disabled_by_default_and_partial_policy_fails_closed(configured,monkeypatch):
    c,g,_=configured
    for key in ('PAGE_CONNECT_TRIAL_PAISA','PAGE_CONNECT_TRIAL_POLICY_ID','PAGE_CONNECT_TRIAL_SCOPE'):monkeypatch.delenv(key,raising=False)
    connect(c)
    assert call(c,'org_A','POST','/oauth/meta/select',{'page_id':'12345'}).status_code==200
    assert call(c,'org_A','GET','/billing').json()['balance_paisa']==0
    monkeypatch.setenv('PAGE_CONNECT_TRIAL_PAISA','500')
    connect(c)
    assert call(c,'org_A','POST','/oauth/meta/select',{'page_id':'12345'}).status_code==503
    with Session(g.workspace('org_A').state.engine) as s:
        assert s.get(Base.WorkspaceRecord,'billing:wallet').data['balance_paisa']==0
