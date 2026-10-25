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

def call(org,method,path,body=None):
    raw=json.dumps(body).encode() if body is not None else b''
    p={'organization_id':org,'user_id':'qa_owner','role':'owner','method':method,'path':path,'body_sha256':hashlib.sha256(raw).hexdigest(),'timestamp':int(time.time()),'nonce':str(uuid.uuid4())}
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
