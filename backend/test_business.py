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


def test_member_channel_scope_filters_lists_direct_ids_orders_and_workspace(gateway):
    c,_=gateway
    a=call(c,'scope_org','POST','/conversations',{'customer':'Messenger customer','channel':'Messenger'}).json()
    b=call(c,'scope_org','POST','/conversations',{'customer':'Private WhatsApp customer','channel':'WhatsApp'}).json()
    p=call(c,'scope_org','POST','/products',{'name':'Product','stock':5,'price':100}).json()
    order=call(c,'scope_org','POST','/orders',{'conversation_id':b['id'],'customer':'Secret','phone':'01700000000','address':'Private address','items':[{'product_id':p['id'],'quantity':1}],'request_id':'private-order'}).json()
    assert call(c,'scope_org','PUT','/access/policies/user_test',{'channels':['Messenger'],'assigned_only':False}).status_code==200
    chats=call(c,'scope_org','GET','/conversations',role='member').json()
    assert [x['id'] for x in chats]==[a['id']]
    assert call(c,'scope_org','GET',f"/conversations/{b['id']}/messages",role='member').status_code==404
    assert call(c,'scope_org','GET','/orders/'+order['id']+'/receipt',role='member').status_code==404
    assert call(c,'scope_org','GET','/workspace',role='member').json()['orders']==[]
    assert call(c,'scope_org','GET','/access/policies',role='member').status_code==403


def test_assigned_only_scope_uses_account_user_id_not_display_name(gateway):
    c,_=gateway
    a=call(c,'assigned_org','POST','/conversations',{'customer':'Assigned customer','channel':'Messenger'}).json()
    call(c,'assigned_org','POST',f"/conversations/{a['id']}/handover",{'assignee':'Display name','assignee_user_id':'user_test','reason':'Assigned','duration_minutes':0})
    call(c,'assigned_org','PUT','/access/policies/user_test',{'channels':['Messenger'],'assigned_only':True})
    assert len(call(c,'assigned_org','GET','/conversations',role='member').json())==1
    call(c,'assigned_org','POST',f"/conversations/{a['id']}/handover",{'assignee':'user_test','assignee_user_id':'someone_else','reason':'Reassigned','duration_minutes':0})
    assert call(c,'assigned_org','GET','/conversations',role='member').json()==[]


def test_export_excludes_secrets_and_audit_is_business_scoped(gateway,monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setenv('CREDENTIAL_ENCRYPTION_KEY',Fernet.generate_key().decode())
    c,_=gateway
    call(c,'export_A','PUT','/connections/configuration',{'app_secret':'must-never-export'})
    call(c,'export_A','POST','/conversations',{'customer':'Exported customer'})
    exported=call(c,'export_A','GET','/workspace/export')
    assert exported.status_code==200 and 'Exported customer' in exported.text
    assert 'must-never-export' not in exported.text and 'ciphertext' not in exported.text
    assert call(c,'export_A','GET','/workspace/export',role='member').status_code==403
    audit=call(c,'export_A','GET','/audit').json()
    assert any(e['path']=='/conversations' for e in audit)
    assert call(c,'export_B','GET','/audit').json()==[]
