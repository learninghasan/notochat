import base64
import hashlib
import hmac
import json
import time
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from main import app,create_workspace
from server import BusinessGateway

SECRET='test-gateway-secret-at-least-thirty-two-characters'

@pytest.fixture
def gateway(tmp_path):
    g=BusinessGateway(app,create_engine('sqlite:///'+str(tmp_path/'registry.db')),create_workspace,secret=SECRET,sqlite_dir=tmp_path/'businesses')
    return TestClient(g),g


def proof(org,method,path,body=b'',role='owner',**changes):
    p={'user_id':'user_test','organization_id':org,'role':role,'method':method,'path':path,'body_sha256':hashlib.sha256(body).hexdigest(),'timestamp':int(time.time()),'nonce':str(uuid.uuid4()),**changes}
    encoded=base64.urlsafe_b64encode(json.dumps(p).encode()).decode().rstrip('=')
    return {'X-NotoChat-Identity':encoded,'X-NotoChat-Signature':hmac.new(SECRET.encode(),encoded.encode(),hashlib.sha256).hexdigest(),'Content-Type':'application/json'}


def call(c,org,method,path,body=None,role='owner'):
    raw=json.dumps(body).encode() if body is not None else b''
    return c.request(method,path,content=raw,headers=proof(org,method,path,raw,role))


def test_business_catalog_conversation_and_orders_are_isolated(gateway):
    c,g=gateway
    p=call(c,'org_A','POST','/products',{'name':'Private product A','price':100,'stock':5})
    assert p.status_code==200,p.text
    customer=call(c,'org_A','POST','/conversations',{'customer':'Private A customer','channel':'Website'})
    assert customer.status_code==200,customer.text
    assert call(c,'org_A','GET','/catalog').json()[0]['name']=='Private product A'
    assert call(c,'org_B','GET','/catalog').json()==[]
    assert call(c,'org_B','GET','/conversations').json()==[]
    assert call(c,'org_B','GET','/conversations/'+str(customer.json()['id'])+'/messages').status_code==404
    w=call(c,'org_B','GET','/workspace').json()
    assert w['orders']==[] and w['knowledge']==[]
    assert g.workspace('org_A') is not g.workspace('org_B')


def test_ownership_permissions_enforced_on_server(gateway):
    c,_=gateway
    assert call(c,'org_A','POST','/products',{'name':'Forbidden','price':1,'stock':1},role='member').status_code==403
    assert call(c,'org_A','POST','/agent/versions',{'delivery_inside':1},role='member').status_code==403
    assert call(c,'org_A','POST','/team',{'name':'Agent','email':'a@example.test'},role='member').status_code==403
    assert call(c,'org_A','POST','/conversations',{'customer':'Allowed support contact'},role='member').status_code==200


def test_signature_binds_body_method_path_time_and_nonce(gateway):
    c,_=gateway
    headers=proof('org_A','GET','/catalog')
    assert c.get('/catalog',headers=headers).status_code==200
    assert c.get('/catalog',headers=headers).status_code==401
    assert c.get('/catalog?q=changed',headers=proof('org_A','GET','/catalog')).status_code==401
    assert c.get('/catalog',headers=proof('org_A','GET','/catalog',timestamp=time.time()-60)).status_code==401
    assert c.post('/products',content=b'{"name":"tampered"}',headers=proof('org_A','POST','/products',b'{}')).status_code==401
    assert c.get('/catalog',headers={'X-NotoChat-Identity':'forged','X-NotoChat-Signature':'fake'}).status_code==401


def test_legacy_token_does_not_grant_access_to_business_data(gateway,monkeypatch):
    c,_=gateway
    monkeypatch.setenv('APP_TOKEN','legacy-test')
    call(c,'org_A','POST','/products',{'name':'Business secret','price':1,'stock':1})
    legacy=c.get('/catalog',headers={'Authorization':'Bearer legacy-test'})
    assert legacy.status_code==200
    assert all(p['name']!='Business secret' for p in legacy.json())


def test_tenant_channels_do_not_inherit_global_legacy_tokens(gateway,monkeypatch):
    c,_=gateway
    monkeypatch.setenv('WIDGET_ENABLED','1')
    assert call(c,'org_A','GET','/widget').status_code==503
    assert call(c,'org_A','GET','/webhooks/meta').status_code==503


def test_credentials_encrypted_and_public_business_callbacks_are_isolated(gateway,monkeypatch):
    from cryptography.fernet import Fernet
    from main import Base
    from sqlalchemy.orm import Session
    monkeypatch.setenv('CREDENTIAL_ENCRYPTION_KEY',Fernet.generate_key().decode())
    c,g=gateway
    settings={'app_secret':'business-A-secret','verify_token':'verify-A','graph_version':'v26.0','page_id':'page-A','page_access_token':'secret-token-A','widget_enabled':True,'widget_origins':['https://shop.example']}
    r=call(c,'org_A','PUT','/connections/configuration',settings)
    assert r.status_code==200,r.text
    status=call(c,'org_A','GET','/connections/configuration').json()
    assert status['app_secret'] is True and 'business-A-secret' not in json.dumps(status)
    assert call(c,'org_A','GET','/connections/configuration',role='member').status_code==403
    # Public callback routing goes only to a registered business and validates its own token.
    assert c.get('/business/org_A/webhooks/meta',params={'hub.mode':'subscribe','hub.verify_token':'verify-A','hub.challenge':'123'}).text=='123'
    call(c,'org_B','GET','/workspace')
    assert c.get('/business/org_B/webhooks/meta',params={'hub.mode':'subscribe','hub.verify_token':'verify-A','hub.challenge':'123'}).status_code==503
    assert c.get('/business/not_registered/widget').status_code==404
    assert c.get('/business/org_A/widget').status_code==200
    assert c.get('/business/org_B/widget').status_code==503
    app=g.workspace('org_A')
    # Storage contains ciphertext only, not a cleartext access token.
    with Session(app.state.engine) as s:
        raw=s.get(Base.WorkspaceRecord,'connections:private').data
        assert 'secret-token-A' not in json.dumps(raw)
    session=c.post('/business/org_A/widget/sessions',json={'name':'Visitor A'}).json()
    assert 'token' in session
    assert c.get('/business/org_B/widget/messages',headers={'Authorization':'Bearer '+session['token']}).status_code==503
