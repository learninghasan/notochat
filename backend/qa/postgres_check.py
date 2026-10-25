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
