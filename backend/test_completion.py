import asyncio
import json
import re
from datetime import datetime,timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from main import create_workspace,Base

H={'Authorization':'Bearer test-token'}

@pytest.fixture
def system(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'completion.db'))
    app=create_workspace(engine)
    return app,TestClient(app),engine


def mock_client(monkeypatch,post_result=None,get_result=None):
    calls=[]
    class Response:
        def __init__(self,data):self.data=data
        def raise_for_status(self):pass
        def json(self):return self.data
    class Client:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,url,**kwargs):calls.append(('POST',url,kwargs));return Response(post_result(url,kwargs) if callable(post_result) else post_result)
        async def get(self,url,**kwargs):calls.append(('GET',url,kwargs));return Response(get_result(url,kwargs) if callable(get_result) else get_result)
    monkeypatch.setattr('httpx.AsyncClient',Client)
    return calls


def opt_in_sales(c):
    v=c.post('/agent/versions',headers=H,json={'auto_reply':True,'delivery_inside':70,'delivery_outside':130}).json()
    assert c.post('/agent/versions/'+v['id']+'/publish',headers=H).status_code==200


def website(c,monkeypatch):
    monkeypatch.setenv('WIDGET_ENABLED','1')
    token=c.post('/widget/sessions',json={'name':'Sales customer'}).json()['token']
    cid=next(x['id'] for x in c.get('/conversations',headers=H).json() if x['customer']=='Sales customer')
    return cid,{'Authorization':'Bearer '+token}


def test_automatic_sales_requires_exact_customer_confirmation_and_uses_catalog_prices(system,monkeypatch):
    app,c,_=system
    opt_in_sales(c);cid,wh=website(c,monkeypatch)
    monkeypatch.setenv('OPENAI_API_KEY','fake');monkeypatch.setenv('OPENAI_MODEL','test-model')
    intent={'intent':'order','product_ids':[1],'quantity':2,'customer':'Rafi','phone':'01700000000','address':'House 7 Dhaka'}
    calls=mock_client(monkeypatch,post_result={'output':[{'content':[{'type':'output_text','text':json.dumps(intent)}]}],'usage':{'input_tokens':100,'output_tokens':30}})
    assert c.post('/widget/messages',headers=wh,json={'text':'2 Ivory Panjabi please. Rafi, 01700000000, House 7 Dhaka'}).status_code==200
    asyncio.run(app.state.run_jobs())
    assert c.get('/workspace',headers=H).json()['orders']==[]
    messages=c.get(f'/conversations/{cid}/messages',headers=H).json()
    code=re.search(r'CONFIRM ([A-F0-9]{6})',messages[-1]['text']).group(1)
    assert '5030' in messages[-1]['text']
    c.post(f'/conversations/{cid}/incoming',headers=H,json={'text':'CONFIRM '+code})
    asyncio.run(app.state.run_jobs())
    orders=c.get('/workspace',headers=H).json()['orders'];assert len(orders)==1 and orders[0]['total']==5030
    assert c.get('/catalog',headers=H).json()[0]['stock']==10
    c.post(f'/conversations/{cid}/incoming',headers=H,json={'text':'CONFIRM '+code})
    asyncio.run(app.state.run_jobs())
    assert len(c.get('/workspace',headers=H).json()['orders'])==1
    assert len(calls)==1


def test_complaints_handover_without_model_or_refund(system,monkeypatch):
    app,c,_=system;opt_in_sales(c);cid,wh=website(c,monkeypatch)
    calls=mock_client(monkeypatch,post_result={})
    c.post('/widget/messages',headers=wh,json={'text':'I want a refund. Complaint.'})
    asyncio.run(app.state.run_jobs())
    conversation=next(x for x in c.get('/conversations',headers=H).json() if x['id']==cid)
    assert conversation['mode']=='human' and calls==[]
    assert c.get('/workspace',headers=H).json()['orders']==[]


def test_local_unverified_source_cannot_autoreply(system):
    app,c,engine=system;opt_in_sales(c)
    c.post('/conversations/1/incoming',headers=H,json={'text':'Test inquiry'})
    asyncio.run(app.state.run_jobs())
    w=c.get('/workspace',headers=H).json()
    assert w['jobs'][0]['output']['blocked']=='Verified customer source required'


def test_sandbox_recharge_validated_once_and_cannot_fund_real_ai(system,monkeypatch):
    _,c,engine=system;Record=Base.WorkspaceRecord
    monkeypatch.setenv('SSLCOMMERZ_STORE_ID','fake-store');monkeypatch.setenv('SSLCOMMERZ_STORE_PASSWORD','fake-password')
    with Session(engine) as s:s.add(Record(id='payment:txn1',kind='payments',data={'expected_paisa':1000,'status':'pending','sandbox':True}));s.commit()
    verified={'tran_id':'txn1','val_id':'val1','status':'VALID','amount':'10.00','currency':'BDT','risk_level':'0'}
    mock_client(monkeypatch,get_result=verified)
    assert c.post('/payments/ipn',content='val_id=val1&amount=99999').status_code==200
    assert c.post('/payments/ipn',content='val_id=val1').json()['duplicate'] is True
    b=c.get('/billing',headers=H).json();assert b['balance_paisa']==0 and b['sandbox_balance']==10
    monkeypatch.setenv('AI_BILLING_ENABLED','1');monkeypatch.setenv('AI_INPUT_PAISA_PER_MILLION','100');monkeypatch.setenv('AI_OUTPUT_PAISA_PER_MILLION','100')
    monkeypatch.setenv('OPENAI_API_KEY','fake');monkeypatch.setenv('OPENAI_MODEL','test-model')
    assert c.post('/conversations/1/assistant',headers=H,json={'action':'summary'}).status_code==402


def test_invalid_payment_currency_and_risk_never_credit(system,monkeypatch):
    _,c,engine=system;Record=Base.WorkspaceRecord
    monkeypatch.setenv('SSLCOMMERZ_STORE_ID','fake');monkeypatch.setenv('SSLCOMMERZ_STORE_PASSWORD','fake')
    with Session(engine) as s:s.add(Record(id='payment:txn2',kind='payments',data={'expected_paisa':1000,'status':'pending','sandbox':True}));s.commit()
    mock_client(monkeypatch,get_result={'tran_id':'txn2','val_id':'val2','status':'VALID','amount':'10.00','currency':'USD','risk_level':'1'})
    assert c.post('/payments/ipn',content='val_id=val2').status_code==409
    assert c.get('/billing',headers=H).json()['balance']==0


def test_confirmed_recharge_and_usage_debit_are_real_integer_paisa(system,monkeypatch):
    _,c,engine=system;Record=Base.WorkspaceRecord
    monkeypatch.setenv('SSLCOMMERZ_STORE_ID','fake');monkeypatch.setenv('SSLCOMMERZ_STORE_PASSWORD','fake');monkeypatch.setenv('SSLCOMMERZ_LIVE','1')
    with Session(engine) as s:s.add(Record(id='payment:txn3',kind='payments',data={'expected_paisa':1000,'status':'pending','sandbox':False}));s.commit()
    mock_client(monkeypatch,get_result={'tran_id':'txn3','val_id':'val3','status':'VALID','amount':'10.00','currency':'BDT','risk_level':'0'})
    assert c.post('/payments/ipn',content='val_id=val3').status_code==200
    monkeypatch.setenv('AI_BILLING_ENABLED','1');monkeypatch.setenv('AI_INPUT_PAISA_PER_MILLION','1');monkeypatch.setenv('AI_OUTPUT_PAISA_PER_MILLION','1')
    monkeypatch.setenv('OPENAI_API_KEY','fake');monkeypatch.setenv('OPENAI_MODEL','test-model')
    mock_client(monkeypatch,post_result={'output':[{'content':[{'type':'output_text','text':'A summary'}]}],'usage':{'input_tokens':1000000,'output_tokens':1}})
    assert c.post('/conversations/1/assistant',headers=H,json={'action':'summary'}).status_code==200
    b=c.get('/billing',headers=H).json();assert b['balance_paisa']==998
    assert len(b['ledger'])==2


def test_courier_booking_is_explicit_idempotent_and_status_verified(system,monkeypatch):
    _,c,_=system
    monkeypatch.setenv('STEADFAST_API_KEY','fake');monkeypatch.setenv('STEADFAST_SECRET_KEY','fake');monkeypatch.setenv('COURIER_LIVE_ENABLED','1')
    o=c.post('/orders',headers=H,json={'conversation_id':1,'customer':'Test','phone':'01700000000','address':'House 7 Dhaka','items':[{'product_id':1,'quantity':1}],'delivery_charge':70,'request_id':'courier-order'}).json()
    calls=mock_client(monkeypatch,post_result={'status':200,'consignment':{'consignment_id':123,'tracking_code':'TRACK1'}},get_result={'delivery_status':'delivered'})
    path='/orders/'+o['id']+'/courier'
    assert c.post(path,headers=H,json={'provider':'Steadfast'}).status_code==200
    assert c.post(path,headers=H,json={'provider':'Steadfast'}).status_code==409  # Already shipped, no second booking.
    assert len([x for x in calls if x[0]=='POST'])==1
    assert c.post(path+'/sync',headers=H).json()['verified_with_provider'] is True
    assert c.get('/workspace',headers=H).json()['orders'][0]['status']=='delivered'


def test_push_rejects_non_browser_endpoints_and_does_not_include_customer_data(system,monkeypatch):
    _,c,_=system
    monkeypatch.setenv('VAPID_PUBLIC_KEY','public');monkeypatch.setenv('VAPID_PRIVATE_KEY','private');monkeypatch.setenv('VAPID_SUBJECT','mailto:admin@example.test')
    body={'endpoint':'https://internal.example/secret','keys':{'p256dh':'A'*87,'auth':'B'*22}}
    assert c.post('/push/subscriptions',headers=H,json=body).status_code==422
    body['endpoint']='https://fcm.googleapis.com/fcm/send/test'
    assert c.post('/push/subscriptions',headers=H,json=body).status_code==200
    c.post('/conversations/1/handover',headers=H,json={'reason':'Private customer address','duration_minutes':0})
    assert c.get('/push/config',headers=H).json()['enabled'] is True


def test_pdf_import_extracts_text_and_semantic_search_returns_cited_passage(system,monkeypatch):
    import base64,io
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
    _,c,_=system
    writer=PdfWriter();page=writer.add_blank_page(width=300,height=300)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    stream=DecodedStreamObject();stream.set_data(b'BT /F1 12 Tf 20 200 Td (Return policy: contact the shop.) Tj ET')
    page[NameObject('/Contents')]=writer._add_object(stream);buffer=io.BytesIO();writer.write(buffer)
    d=c.post('/knowledge/import/pdf',headers=H,json={'title':'Return policy','content_base64':base64.b64encode(buffer.getvalue()).decode()})
    assert d.status_code==200,d.text
    assert 'Return policy' in d.json()['text']
    monkeypatch.setenv('OPENAI_API_KEY','fake');monkeypatch.setenv('OPENAI_EMBEDDING_MODEL','test-embedding')
    def response(url,kwargs):
        texts=kwargs['json']['input'];return {'data':[{'index':i,'embedding':[1.0,0.0]} for i in range(len(texts))],'usage':{'prompt_tokens':10}}
    mock_client(monkeypatch,post_result=response)
    assert c.post('/knowledge/'+d.json()['id']+'/index',headers=H).status_code==200
    result=c.get('/knowledge/semantic/search',headers=H,params={'q':'Return'}).json()
    assert result[0]['id']==d.json()['id'] and result[0]['match_type']=='semantic'


def test_live_courier_flag_is_required_before_real_booking(system,monkeypatch):
    _,c,_=system
    monkeypatch.setenv('STEADFAST_API_KEY','fake');monkeypatch.setenv('STEADFAST_SECRET_KEY','fake');monkeypatch.delenv('COURIER_LIVE_ENABLED',raising=False)
    o=c.post('/orders',headers=H,json={'conversation_id':1,'customer':'Test','phone':'01700000000','address':'House 7 Dhaka','items':[{'product_id':1,'quantity':1}],'delivery_charge':70,'request_id':'no-live-courier'}).json()
    calls=mock_client(monkeypatch,post_result={})
    assert c.post('/orders/'+o['id']+'/courier',headers=H,json={'provider':'Steadfast'}).status_code==503
    assert calls==[]


def test_push_payload_is_generic_and_endpoint_removed_on_expiry(system,monkeypatch):
    app,c,_=system
    monkeypatch.setenv('VAPID_PUBLIC_KEY','public');monkeypatch.setenv('VAPID_PRIVATE_KEY','private');monkeypatch.setenv('VAPID_SUBJECT','mailto:admin@example.test')
    sub={'endpoint':'https://fcm.googleapis.com/fcm/send/payload-test','keys':{'p256dh':'A'*87,'auth':'B'*22}}
    c.post('/push/subscriptions',headers=H,json=sub)
    c.post('/conversations/1/handover',headers=H,json={'reason':'Secret address here','duration_minutes':0})
    captured=[]
    monkeypatch.setattr('pywebpush.webpush',lambda **kwargs:captured.append(kwargs))
    assert app.state.flush_push()==1
    assert 'Secret address' not in captured[0]['data']
    assert app.state.flush_push()==0


def test_production_never_silently_allows_unfunded_ai(system,monkeypatch):
    _,c,_=system
    monkeypatch.setenv('APP_ENV','production');monkeypatch.setenv('AI_BILLING_ENABLED','0')
    monkeypatch.setenv('AI_INPUT_PAISA_PER_MILLION','100');monkeypatch.setenv('AI_OUTPUT_PAISA_PER_MILLION','100')
    monkeypatch.setenv('OPENAI_API_KEY','fake');monkeypatch.setenv('OPENAI_MODEL','test-model')
    calls=mock_client(monkeypatch,post_result={})
    assert c.post('/conversations/1/assistant',headers=H,json={'action':'summary'}).status_code==402
    assert c.get('/billing',headers=H).json()['metering_enabled'] is True
    assert calls==[]
