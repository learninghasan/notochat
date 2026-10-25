import os
import tempfile
os.environ["DATABASE_URL"]="sqlite:///"+tempfile.mktemp(suffix=".db")
os.environ["APP_TOKEN"]="test-token"
from fastapi.testclient import TestClient
from main import app
client=TestClient(app)
headers={"Authorization":"Bearer test-token"}
def test_unauthorized():
    assert client.get("/conversations").status_code==401

def test_handover_reply_and_return():
    assert client.post("/conversations/1/messages",headers=headers,json={"text":"hello"}).status_code==409
    assert client.patch("/conversations/1/mode",headers=headers,json={"mode":"human"}).status_code==200
    r=client.post("/conversations/1/messages",headers=headers,json={"text":"ধন্যবাদ"})
    assert r.status_code==200 and "local-only" in r.json()["delivery"]
    assert client.get("/conversations/1/messages",headers=headers).json()[-1]["text"]=="ধন্যবাদ"
    assert client.patch("/conversations/1/mode",headers=headers,json={"mode":"ai"}).status_code==200

def test_missing_conversation_and_invalid_mode():
    assert client.get("/conversations/999/messages",headers=headers).status_code==404
    assert client.patch("/conversations/1/mode",headers=headers,json={"mode":"admin"}).status_code==422

def test_ai_fails_clearly_without_configuration(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY",raising=False)
    assert client.post("/conversations/1/draft",headers=headers).status_code==503


def make_product(stock=5):
    r=client.post('/products',headers=headers,json={'name':'Test cotton shirt','price':1250,'stock':stock,'sku':''})
    assert r.status_code==200,r.text
    return r.json()


def order_body(p,request_id=None):
    import uuid
    return {'conversation_id':1,'customer':'Test customer','phone':'01700000000','address':'House 1, Dhaka','items':[{'product_id':p['id'],'quantity':2}],'delivery_charge':70,'payment_method':'COD','request_id':request_id or str(uuid.uuid4())}


def test_catalog_order_totals_idempotency_and_stock_restoration():
    p=make_product();body=order_body(p)
    r=client.post('/orders',headers=headers,json=body)
    assert r.status_code==200,r.text
    order=r.json();assert order['total']==2570
    assert order['items'][0]['unit_price']==1250
    assert order['payment_status']=='unverified'
    assert client.post('/orders',headers=headers,json=body).json()['id']==order['id']
    catalog=client.get('/catalog',headers=headers).json()
    assert next(x for x in catalog if x['id']==p['id'])['stock']==3
    r=client.patch('/orders/'+order['id'],headers=headers,json={'status':'cancelled'})
    assert r.status_code==200
    client.patch('/orders/'+order['id'],headers=headers,json={'status':'cancelled'})
    catalog=client.get('/catalog',headers=headers).json()
    assert next(x for x in catalog if x['id']==p['id'])['stock']==5
    assert client.patch('/orders/'+order['id'],headers=headers,json={'status':'shipped','tracking':'x'}).status_code==409


def test_out_of_stock_order_rolls_back_every_product():
    a,b=make_product(3),make_product(0)
    body=order_body(a);body['items'].append({'product_id':b['id'],'quantity':1})
    assert client.post('/orders',headers=headers,json=body).status_code==409
    assert next(x for x in client.get('/catalog',headers=headers).json() if x['id']==a['id'])['stock']==3


def test_duplicate_product_lines_are_aggregated_before_stock_check():
    p=make_product(3);body=order_body(p)
    body['items'].append({'product_id':p['id'],'quantity':2})
    assert client.post('/orders',headers=headers,json=body).status_code==409


def test_delivery_transition_requires_tracking():
    p=make_product();o=client.post('/orders',headers=headers,json=order_body(p)).json()
    assert client.patch('/orders/'+o['id'],headers=headers,json={'status':'shipped'}).status_code==422
    assert client.patch('/orders/'+o['id'],headers=headers,json={'status':'shipped','tracking':'MANUAL-001'}).status_code==200
    assert client.patch('/orders/'+o['id'],headers=headers,json={'status':'delivered'}).status_code==200
    assert client.get('/orders/'+o['id']+'/receipt',headers=headers).json()['payment_verified'] is False


def test_booking_overlap_and_reminder_creation():
    from datetime import datetime,timezone,timedelta
    start=datetime.now(timezone.utc)+timedelta(days=5)
    body={'conversation_id':1,'customer':'Test','service':'Consultation','starts_at':start.isoformat(),'duration_minutes':60,'advance':500,'resource':'Test room'}
    b=client.post('/bookings',headers=headers,json=body)
    assert b.status_code==200,b.text
    assert client.post('/bookings',headers=headers,json=body).status_code==409
    assert client.patch('/bookings/'+b.json()['id'],headers=headers,json={'status':'confirmed'}).status_code==200
    w=client.get('/workspace',headers=headers).json()
    assert len([a for a in w['automations'] if a['kind']=='booking-reminder'])==2
    assert client.patch('/bookings/'+b.json()['id'],headers=headers,json={'status':'confirmed'}).status_code==200
    assert len([a for a in client.get('/workspace',headers=headers).json()['automations'] if a['kind']=='booking-reminder'])==2


def test_agent_draft_is_not_live_until_publish_and_can_restore():
    w=client.get('/workspace',headers=headers).json();original=w['agent']['delivery_inside']
    d=client.post('/agent/versions',headers=headers,json={'delivery_inside':99}).json()
    assert client.get('/workspace',headers=headers).json()['agent']['delivery_inside']==original
    assert client.post('/agent/versions/'+d['id']+'/publish',headers=headers).json()['delivery_inside']==99
    versions=client.get('/workspace',headers=headers).json()['agent_versions']
    previous=next(v for v in versions if v.get('state')=='previous' and v['delivery_inside']==original)
    assert client.post('/agent/versions/'+previous['id']+'/publish',headers=headers).json()['delivery_inside']==original


def test_unicode_knowledge_search_and_delete():
    r=client.post('/knowledge',headers=headers,json={'title':'রিটার্ন নীতি','text':'পণ্য এক্সচেঞ্জ করতে টিমের সঙ্গে যোগাযোগ করুন।'})
    assert r.status_code==200
    results=client.get('/knowledge/search',headers=headers,params={'q':'এক্সচেঞ্জ'}).json()
    assert results and results[0]['match_type']=='keyword'
    assert client.delete('/knowledge/'+r.json()['id'],headers=headers).status_code==200


def test_handover_notification_and_expiry():
    r=client.post('/conversations/2/handover',headers=headers,json={'assignee':'Test agent','reason':'Exchange request','duration_minutes':60})
    assert r.status_code==200
    w=client.get('/workspace',headers=headers).json()
    n=next(n for n in w['notifications'] if n['detail']=='Exchange request')
    assert client.post('/notifications/'+n['id']+'/ack',headers=headers).json()['done'] is True
    assert w['conversation_meta']['2']['assignee']=='Test agent'


def test_followup_policy_blocks_without_recent_inbound():
    from datetime import datetime,timezone,timedelta
    a=client.post('/automations',headers=headers,json={'conversation_id':3,'kind':'followup','text':'Can we help?','due_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()}).json()
    p=client.post('/automations/'+a['id']+'/preview',headers=headers).json()
    assert p['eligible'] is False and p['sent'] is False
    assert client.post('/conversations/3/incoming',headers=headers,json={'text':'New inquiry'}).status_code==200
    p=client.post('/automations/'+a['id']+'/preview',headers=headers).json()
    assert p['eligible'] is True and p['sent'] is False


def test_new_routes_are_protected_and_team_profiles_do_not_send_invites():
    assert client.get('/workspace').status_code==401
    assert client.post('/orders',json={}).status_code==401
    assert client.get('/billing').status_code==401
    r=client.post('/team',headers=headers,json={'name':'Teammate','email':'test@example.com','role':'Agent'})
    assert r.status_code==200 and 'no invitation' in r.json()['access']


def test_invalid_media_and_unconfigured_provider_fail_clearly(monkeypatch):
    assert client.post('/conversations/1/media',headers=headers,json={'kind':'image','mime_type':'image/png','content_base64':'!!!!'}).status_code==422
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    import base64
    assert client.post('/conversations/1/media',headers=headers,json={'kind':'image','mime_type':'image/png','content_base64':base64.b64encode(b'sample').decode()}).status_code==503


def test_meta_verification_signature_and_deduplication(monkeypatch):
    import json,hashlib,hmac
    from datetime import datetime,timezone
    monkeypatch.setenv('META_VERIFY_TOKEN','verify-test')
    monkeypatch.setenv('META_APP_SECRET','app-test')
    monkeypatch.setenv('META_PAGE_ID','page-123')
    assert client.get('/webhooks/meta',params={'hub.mode':'subscribe','hub.verify_token':'wrong','hub.challenge':'123'}).status_code==403
    response=client.get('/webhooks/meta',params={'hub.mode':'subscribe','hub.verify_token':'verify-test','hub.challenge':'123'})
    assert response.status_code==200 and response.text=='123'
    data={'object':'page','entry':[{'messaging':[{'sender':{'id':'customer-123'},'recipient':{'id':'page-123'},'timestamp':int(datetime.now(timezone.utc).timestamp()*1000),'message':{'mid':'msg-123','text':'Hello from Messenger'}}]}]}
    raw=json.dumps(data).encode();signature='sha256='+hmac.new(b'app-test',raw,hashlib.sha256).hexdigest()
    assert client.post('/webhooks/meta',content=raw,headers={'x-hub-signature-256':'invalid'}).status_code==403
    r=client.post('/webhooks/meta',content=raw,headers={'x-hub-signature-256':signature})
    assert r.status_code==200 and r.json()['stored']==1
    assert client.post('/webhooks/meta',content=raw,headers={'x-hub-signature-256':signature}).json()['stored']==0
    cs=client.get('/conversations',headers=headers).json()
    c=next(c for c in cs if c['customer'].endswith('er-123'))
    assert len(client.get('/conversations/'+str(c['id'])+'/messages',headers=headers).json())==1
    assert client.post('/conversations/'+str(c['id'])+'/deliver',headers=headers,json={'message_id':1}).status_code==503


def test_meta_unsigned_test_messages_cannot_enable_live_delivery(monkeypatch):
    monkeypatch.setenv('ENABLE_LIVE_SEND','1')
    client.patch('/conversations/1/mode',headers=headers,json={'mode':'human'})
    client.post('/conversations/1/incoming',headers=headers,json={'text':'Local test inquiry'})
    client.post('/conversations/1/messages',headers=headers,json={'text':'Local test reply'})
    message=client.get('/conversations/1/messages',headers=headers).json()[-1]
    assert client.post('/conversations/1/deliver',headers=headers,json={'message_id':message['id']}).status_code==409


def test_website_widget_sessions_are_isolated_and_admin_token_is_not_a_widget_token(monkeypatch):
    monkeypatch.setenv('WIDGET_ENABLED','1')
    assert client.get('/widget').status_code==200
    assert client.get('/widget/messages',headers=headers).status_code==401
    a=client.post('/widget/sessions',json={'name':'Widget customer A'}).json()
    b=client.post('/widget/sessions',json={'name':'Widget customer B'}).json()
    ah={'Authorization':'Bearer '+a['token']};bh={'Authorization':'Bearer '+b['token']}
    assert client.post('/widget/messages',headers=ah,json={'text':'Hello from website'}).status_code==200
    assert len(client.get('/widget/messages',headers=ah).json())==1
    assert client.get('/widget/messages',headers=bh).json()==[]
    assert client.post('/widget/messages',headers=ah,json={'text':'Too fast'}).status_code==429
    c=next(c for c in client.get('/conversations',headers=headers).json() if c['customer']=='Widget customer A')
    assert client.post('/conversations/'+str(c['id'])+'/messages',headers=headers,json={'text':'Team reply to website'}).status_code==200
    assert client.get('/widget/messages',headers=ah).json()[-1]['text']=='Team reply to website'


def test_widget_disabled_by_default(monkeypatch):
    monkeypatch.delenv('WIDGET_ENABLED',raising=False)
    assert client.get('/widget').status_code==503
    assert client.post('/widget/sessions',json={'name':'Test'}).status_code==503


def test_live_transport_payload_and_no_duplicate_send(monkeypatch):
    import json,hashlib,hmac,time
    monkeypatch.setenv('META_APP_SECRET','transport-secret')
    monkeypatch.setenv('META_PAGE_ID','transport-page')
    monkeypatch.setenv('META_PAGE_ACCESS_TOKEN','test-provider-token')
    monkeypatch.setenv('META_GRAPH_VERSION','v26.0')
    monkeypatch.setenv('ENABLE_LIVE_SEND','1')
    raw=json.dumps({'object':'page','entry':[{'messaging':[{'sender':{'id':'transport-user'},'recipient':{'id':'transport-page'},'timestamp':int(time.time()*1000),'message':{'mid':'transport-inbound','text':'Hello'}}]}]}).encode()
    signature='sha256='+hmac.new(b'transport-secret',raw,hashlib.sha256).hexdigest()
    assert client.post('/webhooks/meta',content=raw,headers={'x-hub-signature-256':signature}).status_code==200
    c=next(c for c in client.get('/conversations',headers=headers).json() if c['customer'].endswith('t-user'))
    client.post('/conversations/'+str(c['id'])+'/messages',headers=headers,json={'text':'Hello back'})
    message=client.get('/conversations/'+str(c['id'])+'/messages',headers=headers).json()[-1]
    calls=[]
    class Response:
        def raise_for_status(self): pass
        def json(self):return {'message_id':'provider-message-123'}
    class FakeClient:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):calls.append((url,kwargs));return Response()
    monkeypatch.setattr('httpx.AsyncClient',FakeClient)
    path='/conversations/'+str(c['id'])+'/deliver'
    assert client.post(path,headers=headers,json={'message_id':message['id']}).json()['status']=='sent'
    assert client.post(path,headers=headers,json={'message_id':message['id']}).json()['status']=='sent'
    assert len(calls)==1
    assert calls[0][1]['json']['recipient']['id']=='transport-user'
    assert calls[0][1]['json']['messaging_type']=='RESPONSE'


def test_ai_assistant_uses_context_and_records_provider_usage(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY','test-key')
    monkeypatch.setenv('OPENAI_MODEL','test-model')
    calls=[]
    class Response:
        def raise_for_status(self):pass
        def json(self):return {'output':[{'content':[{'type':'output_text','text':'Review this summary.'}]}],'usage':{'input_tokens':100,'output_tokens':8}}
    class FakeClient:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):calls.append(kwargs);return Response()
    monkeypatch.setattr('httpx.AsyncClient',FakeClient)
    r=client.post('/conversations/1/assistant',headers=headers,json={'action':'summary'})
    assert r.status_code==200 and r.json()['requires_review'] is True
    assert 'catalog' in calls[0]['json']['input']
    usage=client.get('/billing',headers=headers).json()['usage']
    assert any(u['tokens'].get('input_tokens')==100 for u in usage)


def test_order_idempotency_key_cannot_be_reused_with_changed_details():
    p=make_product();body=order_body(p)
    assert client.post('/orders',headers=headers,json=body).status_code==200
    body['address']='Different address, Dhaka'
    assert client.post('/orders',headers=headers,json=body).status_code==409
