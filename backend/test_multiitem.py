import asyncio,json,re,hashlib
from datetime import datetime,timezone,timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from main import Base,Product,Message
from test_completion import system,website,opt_in_sales,mock_client,send_website,H
from test_business import gateway,call

@pytest.fixture
def shop(system,monkeypatch):
    app,c,engine=system;opt_in_sales(c);cid,wh=website(c,monkeypatch)
    products=[c.post('/products',headers=H,json={'name':name,'price':price,'stock':5}).json() for name,price in [('Blue shirt',100),('Red scarf',50)]]
    monkeypatch.setenv('OPENAI_API_KEY','fake');monkeypatch.setenv('OPENAI_MODEL','fake-model')
    intent={'intent':'order','product_ids':[],'items':[{'product_id':products[0]['id'],'quantity':2},{'product_id':products[1]['id'],'quantity':3}],'customer':'Rafi','phone':'01700000000','address':'House 7 Dhaka'}
    calls=mock_client(monkeypatch,post_result=lambda *_:{'output':[{'content':[{'type':'output_text','text':json.dumps(intent)}]}],'usage':{'input_tokens':10,'output_tokens':10}})
    return app,c,engine,cid,wh,products,intent,calls

def propose(shop):
    app,c,engine,cid,wh,products,_,_=shop
    send_website(c,engine,wh,'2 Blue shirt and 3 Red scarf. Rafi, 01700000000, House 7 Dhaka')
    asyncio.run(app.state.run_jobs())
    text=c.get(f'/conversations/{cid}/messages',headers=H).json()[-1]['text']
    return re.search(r'CONFIRM ([A-F0-9]{6})',text).group(1),text

def confirm(shop,code):
    app,c,engine,cid,wh,*_=shop;send_website(c,engine,wh,'CONFIRM '+code);asyncio.run(app.state.run_jobs())
    return c.get('/workspace',headers=H).json()['orders']

def test_cart_quotes_every_line_single_delivery_charge_and_orders_once(shop):
    app,c,engine,cid,wh,products,_,calls=shop
    code,text=propose(shop)
    assert 'Blue shirt × 2' in text and 'Red scarf × 3' in text and '480' in text
    assert c.get('/workspace',headers=H).json()['orders']==[]
    orders=confirm(shop,code);assert len(orders)==1
    assert orders[0]['total']==480 and len(orders[0]['items'])==2
    assert confirm(shop,code)[0]['id']==orders[0]['id'] and len(calls)==1
    stocks={p['id']:p['stock'] for p in c.get('/catalog',headers=H).json()}
    assert [stocks[p['id']] for p in products]==[3,2]

@pytest.mark.parametrize('change',['price','stock','delete'])
def test_changed_item_never_partially_reserves_the_other_item(shop,change):
    _,c,engine,_,_,products,*_=shop;code,_=propose(shop)
    with Session(engine) as s:
        product=s.get(Product,products[1]['id'])
        if change=='price':product.price=51
        elif change=='stock':product.stock=2
        else:s.delete(product)
        s.commit()
    assert confirm(shop,code)==[]
    assert next(p for p in c.get('/catalog',headers=H).json() if p['id']==products[0]['id'])['stock']==5

@pytest.mark.parametrize('invalid',['unknown','zero','fractional','extra','too_many'])
def test_untrusted_model_cart_cannot_create_order(shop,invalid):
    app,c,engine,cid,wh,products,intent,_=shop
    if invalid=='unknown':intent['items'][1]['product_id']=99999
    elif invalid=='zero':intent['items'][1]['quantity']=0
    elif invalid=='fractional':intent['items'][1]['quantity']=1.5
    elif invalid=='extra':intent['items'][1]['unit_price']=1
    else:intent['items']*=6
    send_website(c,engine,wh,'Rafi, 01700000000, House 7 Dhaka');asyncio.run(app.state.run_jobs())
    assert c.get('/workspace',headers=H).json()['orders']==[]
    assert not any('CONFIRM ' in m['text'] for m in c.get(f'/conversations/{cid}/messages',headers=H).json())

@pytest.mark.parametrize('case',['expired','wrong','superseded','human'])
def test_confirmation_must_match_current_active_summary(shop,case):
    app,c,engine,cid,wh,_,intent,_=shop;code,_=propose(shop)
    if case=='expired':
        with Session(engine) as s:
            p=s.get(Base.WorkspaceRecord,f'checkout:{cid}');p.data={**p.data,'expires_at':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()};s.commit()
    elif case=='wrong':code='NOTTHECODE'
    elif case=='human':c.patch(f'/conversations/{cid}/mode',headers=H,json={'mode':'human'})
    else:
        intent['intent']='delivery';intent['items']=[]
        send_website(c,engine,wh,'Wait, what is delivery?');asyncio.run(app.state.run_jobs())
    assert confirm(shop,code)==[]

def test_local_test_message_cannot_confirm_real_customer_cart(shop):
    app,c,_,cid,*_=shop;code,_=propose(shop)
    c.post(f'/conversations/{cid}/incoming',headers=H,json={'text':'CONFIRM '+code});asyncio.run(app.state.run_jobs())
    assert c.get('/workspace',headers=H).json()['orders']==[]
    assert any(j.get('output',{}).get('blocked')=='This message is not a verified customer event' for j in c.get('/jobs',headers=H).json())

def test_retry_after_order_commit_before_checkout_receipt_does_not_reserve_twice(shop):
    app,c,engine,cid,*_=shop;code,_=propose(shop);orders=confirm(shop,code)
    # Simulate recovery after order commit but before checkout/response receipt commit.
    with Session(engine) as s:
        checkout=s.get(Base.WorkspaceRecord,f'checkout:{cid}');checkout.data={k:v for k,v in checkout.data.items() if k!='order_id'};s.commit()
    assert len(confirm(shop,code))==1
    assert c.patch('/orders/'+orders[0]['id'],headers=H,json={'status':'cancelled'}).status_code==200
    assert len(confirm(shop,code))==1
    text=c.get(f'/conversations/{cid}/messages',headers=H).json()[-1]['text'];assert 'cancelled' in text
    assert all(p['stock']==5 for p in c.get('/catalog',headers=H).json() if p['id'] in [x['id'] for x in shop[5]])

def test_duplicate_lines_are_merged_and_displayed(shop):
    shop[6]['items']=[{'product_id':shop[5][0]['id'],'quantity':1},{'product_id':shop[5][0]['id'],'quantity':2}]
    code,text=propose(shop);assert 'Blue shirt × 3' in text
    orders=confirm(shop,code);assert len(orders[0]['items'])==1 and orders[0]['items'][0]['quantity']==3

def test_same_confirmation_code_in_another_tenant_cannot_reveal_or_create_order(gateway,monkeypatch):
    from cryptography.fernet import Fernet
    c,g=gateway;monkeypatch.setenv('CREDENTIAL_ENCRYPTION_KEY',Fernet.generate_key().decode())
    for org in ['org_A','org_B']:
        assert call(c,org,'PUT','/connections/configuration',{'widget_enabled':True}).status_code==200
        v=call(c,org,'POST','/agent/versions',{'auto_reply':True}).json();call(c,org,'POST','/agent/versions/'+v['id']+'/publish')
    token=c.post('/business/org_B/widget/sessions',json={'name':'Tenant B'}).json()['token']
    c.post('/business/org_B/widget/messages',headers={'Authorization':'Bearer '+token},json={'text':'CONFIRM ABC123'})
    with Session(g.workspace('org_A').state.engine) as s:
        s.add(Base.WorkspaceRecord(id='checkout:1',kind='checkout',data={'code':'ABC123','customer':'Private A'}));s.commit()
    asyncio.run(g.workspace('org_B').state.run_jobs())
    assert call(c,'org_B','GET','/workspace').json()['orders']==[]
    assert 'Private A' not in call(c,'org_B','GET','/conversations/1/messages').text
