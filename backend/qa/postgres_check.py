"""Run against a disposable QA database only; creates test business schemas."""
import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from main import app,engine,create_workspace
from server import BusinessGateway

assert os.getenv('NOTOCHAT_DISPOSABLE_DATABASE')=='1','Explicit disposable database opt-in required'
secret='postgres-qa-proof-secret-at-least-thirty-two-characters'
gateway=BusinessGateway(app,engine,create_workspace,secret=secret)
client=TestClient(gateway)
prefix=uuid.uuid4().hex
orgA='qa_A_'+prefix;orgB='qa_B_'+prefix

def call(org,method,path,body=None,role="owner"):
    raw=json.dumps(body).encode() if body is not None else b''
    p={'organization_id':org,'user_id':'qa_owner','role':role,'method':method,'path':path,'body_sha256':hashlib.sha256(raw).hexdigest(),'timestamp':int(time.time()),'nonce':str(uuid.uuid4())}
    encoded=base64.urlsafe_b64encode(json.dumps(p).encode()).decode().rstrip('=')
    return client.request(method,path,content=raw,headers={'Content-Type':'application/json','X-NotoChat-Identity':encoded,'X-NotoChat-Signature':hmac.new(secret.encode(),encoded.encode(),hashlib.sha256).hexdigest()})

p=call(orgA,'POST','/products',{'name':'Schema A stock','price':100,'stock':3})
assert p.status_code==200,p.text
assert call(orgB,'GET','/catalog').json()==[]
c=call(orgA,'POST','/conversations',{'customer':'Schema A customer'}).json()
assert call(orgB,'GET','/conversations').json()==[]

bodies=[{'conversation_id':c['id'],'customer':'QA buyer','phone':'01700000000','address':'QA address, Dhaka','items':[{'product_id':p.json()['id'],'quantity':2}],'delivery_charge':70,'request_id':str(uuid.uuid4())} for _ in range(2)]
with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda b:call(orgA,'POST','/orders',b),bodies))
assert sorted(r.status_code for r in results)==[200,409],[r.text for r in results]
assert call(orgA,'GET','/catalog').json()[0]['stock']==1
winner=next((b,r) for b,r in zip(bodies,results) if r.status_code==200)
assert call(orgA,'POST','/orders',winner[0]).json()['id']==winner[1].json()['id']
assert call(orgA,'GET','/catalog').json()[0]['stock']==1

from datetime import datetime,timezone,timedelta
booking={'conversation_id':c['id'],'customer':'QA buyer','service':'Consultation','resource':'Room 1','starts_at':(datetime.now(timezone.utc)+timedelta(days=3)).isoformat(),'duration_minutes':60}
with ThreadPoolExecutor(max_workers=2) as pool:bookings=list(pool.map(lambda _:call(orgA,'POST','/bookings',booking),range(2)))
assert sorted(r.status_code for r in bookings)==[200,409],[r.text for r in bookings]
print('PASS: real PostgreSQL schema isolation, concurrent stock reservation, idempotency and booking serialization')

# JSON-based channel scopes also run against PostgreSQL, not only SQLite.
private=call(orgA,'POST','/conversations',{'customer':'Hidden WhatsApp contact','channel':'WhatsApp'}).json()
policy=call(orgA,'PUT','/access/policies/qa_owner',{'channels':['Website'],'assigned_only':False})
assert policy.status_code==200,policy.text
scoped=call(orgA,'GET','/conversations',role='member')
assert scoped.status_code==200,scoped.text
assert all(x['channel']=='Website' for x in scoped.json())
assert call(orgA,'GET',f"/conversations/{private['id']}/messages",role='member').status_code==404

# Two concurrent verified callbacks cannot post a credit twice.
from sqlalchemy import select
from sqlalchemy.orm import Session
from main import Base
import httpx
os.environ['SSLCOMMERZ_STORE_ID']='qa-store';os.environ['SSLCOMMERZ_STORE_PASSWORD']='qa-password'
Record=Base.WorkspaceRecord
business_app=gateway.workspace(orgA)
with Session(business_app.state.engine) as s:
    s.add(Record(id='payment:qa-credit',kind='payments',data={'expected_paisa':1000,'status':'pending','sandbox':True}));s.commit()
class Response:
    def raise_for_status(self):pass
    def json(self):return {'tran_id':'qa-credit','val_id':'qa-val','status':'VALID','amount':'10.00','currency':'BDT','risk_level':'0'}
class ProviderClient:
    def __init__(self,**kwargs):pass
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
    async def get(self,*args,**kwargs):return Response()
httpx.AsyncClient=ProviderClient
with ThreadPoolExecutor(max_workers=2) as pool:
    callbacks=list(pool.map(lambda _:client.post('/business/'+orgA+'/payments/ipn',content='val_id=qa-val'),range(2)))
assert all(r.status_code==200 for r in callbacks),[r.text for r in callbacks]
assert call(orgA,'GET','/billing').json()['sandbox_balance']==10
print('PASS: PostgreSQL channel scopes and concurrent credit callback idempotency')

# Concurrent broadcast confirmation and two workers deliver each website message once.
import asyncio
from main import Conversation,Message
customers=[c['id'],call(orgA,'POST','/conversations',{'customer':'Second outreach QA customer','channel':'Website'}).json()['id']]
with Session(business_app.state.engine) as s:
    for cid in customers:
        customer=s.get(Conversation,cid);customer.mode='ai'
        rid=f'conversation:{cid}';record=s.get(Record,rid)
        data={'source':'website-widget','last_verified_inbound':datetime.now(timezone.utc).isoformat(),'last_inbound':datetime.now(timezone.utc).isoformat(),'marketing_opt_in':True}
        if record:record.data=data
        else:s.add(Record(id=rid,kind='conversation',data=data))
    s.commit()
broadcast=call(orgA,'POST','/broadcasts/preview',{'text':'Concurrent outreach QA','channel':'Website'}).json()
with ThreadPoolExecutor(max_workers=2) as pool:
    confirmations=list(pool.map(lambda _:call(orgA,'POST','/broadcasts/'+broadcast['id']+'/send',{'confirm':'SEND ELIGIBLE RECIPIENTS'}),range(2)))
assert all(r.status_code==200 for r in confirmations),[r.text for r in confirmations]
assert len(call(orgA,'GET','/jobs').json())==2
with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda _:asyncio.run(business_app.state.run_jobs()),range(2)))
result=next(x for x in call(orgA,'GET','/workspace').json()['broadcasts'] if x['id']==broadcast['id'])
assert result['status']=='completed' and result['sent']==2,result
with Session(business_app.state.engine) as s:
    for cid in customers:assert len(list(s.scalars(select(Message).where(Message.conversation_id==cid,Message.text=='Concurrent outreach QA'))))==1
print('PASS: PostgreSQL concurrent broadcast confirmation, worker claims, exact sent counts and duplicate prevention')

# Multi-product quote integrity plus simultaneous retries after waiting on stock locks.
cart_products=[call(orgA,'POST','/products',{'name':'Cart QA '+str(i),'price':price,'stock':3}).json() for i,price in enumerate([100,50])]
cart={'conversation_id':c['id'],'customer':'Cart QA','phone':'01700000000','address':'Synthetic address Dhaka','items':[{'product_id':p['id'],'quantity':2,'expected_unit_price':p['price']} for p in cart_products],'delivery_charge':70,'request_id':uuid.uuid4().hex}
with ThreadPoolExecutor(max_workers=2) as pool:retries=list(pool.map(lambda _:call(orgA,'POST','/orders',cart),range(2)))
assert all(r.status_code==200 for r in retries),[r.text for r in retries]
assert retries[0].json()['id']==retries[1].json()['id'] and retries[0].json()['total']==370
stocks={p['id']:p['stock'] for p in call(orgA,'GET','/catalog').json()}
assert all(stocks[p['id']]==1 for p in cart_products)
quote={**cart,'request_id':uuid.uuid4().hex,'items':[{'product_id':p['id'],'quantity':1,'expected_unit_price':p['price']} for p in cart_products]}
changed=cart_products[1]
call(orgA,'PUT','/products/'+str(changed['id']),{'name':changed['name'],'price':51,'stock':1})
assert call(orgA,'POST','/orders',quote).status_code==409
assert next(p for p in call(orgA,'GET','/catalog').json() if p['id']==cart_products[0]['id'])['stock']==1
print('PASS: PostgreSQL multi-item quote checks and concurrent identical-cart retries reserve all items exactly once')

# Page configuration mutations serialize instead of dropping another page's state.
from cryptography.fernet import Fernet
os.environ['CREDENTIAL_ENCRYPTION_KEY']=Fernet.generate_key().decode()
with Session(business_app.state.engine) as s:
    config={'META_PAGES':{'111':{'name':'Page A','access_token':'qa-page-a','enabled':True},'222':{'name':'Page B','access_token':'qa-page-b','enabled':True}}}
    s.add(Record(id='connections:private',kind='private_credentials',data={'ciphertext':business_app.state.credential_cipher().encrypt(json.dumps(config).encode()).decode()}));s.commit()
with ThreadPoolExecutor(max_workers=2) as pool:
    a=pool.submit(call,orgA,'PATCH','/connections/meta/pages/111',{'enabled':False})
    b=pool.submit(call,orgA,'PUT','/connections/configuration',{'widget_enabled':True})
    results=[a.result(),b.result()]
assert all(r.status_code==200 for r in results),[r.text for r in results]
config=call(orgA,'GET','/connections/configuration').json()
assert config['widget_enabled'] and {p['id']:p['enabled'] for p in config['pages']}=={'111':False,'222':True}
print('PASS: PostgreSQL concurrent page/settings updates preserve encrypted page list and pause state')

# Two analysis jobs for the same signed attachment can call the mocked AI only once.
import base64
media_chat=call(orgA,'POST','/conversations',{'customer':'Media QA','channel':'Messenger'}).json()
os.environ['OPENAI_API_KEY']='qa-fake-ai';os.environ['OPENAI_MODEL']='qa-fake-model'
attachment_id='attachment:qa-concurrent'
with Session(business_app.state.engine) as s:
    message=Message(conversation_id=media_chat['id'],role='customer',text='[Synthetic image]');s.add(message);s.flush()
    s.add(Record(id=f'verified_message:{message.id}',kind='verified_message',data={'conversation_id':media_chat['id'],'message_id':message.id,'source':'signed-meta-webhook'}))
    s.add(Record(id=attachment_id,kind='attachments',data={'conversation_id':media_chat['id'],'message_id':message.id,'channel':'Messenger','account':'222','kind':'image','status':'ready','received_at':time.time(),'attempts':0}))
    encrypted=business_app.state.credential_cipher().encrypt(json.dumps({'url':'https://scontent.fbcdn.net/qa.png'}).encode()).decode()
    s.add(Record(id='source:'+attachment_id,kind='private_attachment',data={'conversation_id':media_chat['id'],'ciphertext':encrypted,'expires_at':time.time()+86400}))
    for i in range(2):business_app.state.enqueue(s,'media_analyze',{'conversation_id':media_chat['id'],'attachment_id':attachment_id,'automatic':False},key='concurrent-media-'+str(i))
    s.commit()
media_calls=[]
class MediaResponse:
    status_code=200
    headers={'content-type':'image/png'}
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
    async def aiter_bytes(self):yield b'\x89PNG\r\n\x1a\nsynthetic'
    def raise_for_status(self):pass
    def json(self):return {'output':[{'content':[{'type':'output_text','text':'Synthetic review draft'}]}],'usage':{'input_tokens':1,'output_tokens':1}}
class MediaProvider:
    def __init__(self,**kwargs):pass
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
    def stream(self,*args,**kwargs):return MediaResponse()
    async def post(self,url,**kwargs):media_calls.append(url);return MediaResponse()
httpx.AsyncClient=MediaProvider
with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda _:asyncio.run(business_app.state.run_jobs()),range(2)))
with Session(business_app.state.engine) as s:
    media=s.get(Record,attachment_id)
    assert media.data['status']=='complete' and media.data['attempts']==1,media.data
    assert s.get(Record,'source:'+attachment_id) is None
assert media_calls==['https://api.openai.com/v1/responses'],media_calls
print('PASS: PostgreSQL concurrent media jobs generate one review draft and one mocked AI call')

# Booking-intake retries reuse the original requested slot under a real row lock.
from datetime import datetime,timezone,timedelta
retry_booking={'conversation_id':c['id'],'customer':'QA intake','service':'QA appointment','starts_at':(datetime.now(timezone.utc)+timedelta(days=10)).isoformat(),'resource':'Intake QA','request_id':'intake-qa-'+prefix}
with ThreadPoolExecutor(max_workers=2) as pool:booking_retries=list(pool.map(lambda _:call(orgA,'POST','/bookings',retry_booking),range(2)))
assert all(r.status_code==200 for r in booking_retries),[r.text for r in booking_retries]
assert booking_retries[0].json()['id']==booking_retries[1].json()['id']
print('PASS: PostgreSQL concurrent booking-intake request retries reserve one slot')

# A concurrent page-connect offer is credited once; repeated usage is charged once.
os.environ.update(PAGE_CONNECT_TRIAL_PAISA='2500',PAGE_CONNECT_TRIAL_POLICY_ID='disposable-qa-offer',PAGE_CONNECT_TRIAL_SCOPE='workspace')
with Session(business_app.state.engine) as s:before=s.get(Record,'billing:wallet').data['balance_paisa']
def grant_trial(_):
    with Session(business_app.state.engine) as s:
        result=business_app.state.grant_page_trial(s,'synthetic-page');s.commit();return result
with ThreadPoolExecutor(max_workers=2) as pool:grants=list(pool.map(grant_trial,range(2)))
assert sum(bool(g.get('granted')) for g in grants)==1
with Session(business_app.state.engine) as s:assert s.get(Record,'billing:wallet').data['balance_paisa']==before+2500
os.environ.update(AI_BILLING_ENABLED='1',AI_INPUT_PAISA_PER_MILLION='1000000',AI_OUTPUT_PAISA_PER_MILLION='1000000')
def same_usage(_):
    with Session(business_app.state.engine) as s:
        business_app.state.charge_usage(s,{'id':'concurrent-usage-'+prefix,'tokens':{'input_tokens':1,'output_tokens':1}});s.commit()
with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(same_usage,range(2)))
with Session(business_app.state.engine) as s:assert s.get(Record,'billing:wallet').data['balance_paisa']==before+2498
print('PASS: PostgreSQL concurrent trial grant and repeated usage each post one ledger entry')
