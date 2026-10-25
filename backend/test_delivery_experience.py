import asyncio
from datetime import datetime,timezone,timedelta
from test_completion import system,H,website,send_website

def test_rating_and_delivery_plan_are_customer_bound_and_repeat_safe(system,monkeypatch):
    app,c,engine=system;cid,wh=website(c,monkeypatch)
    v=c.post('/agent/versions',headers=H,json={'collect_ratings':True}).json();c.post('/agent/versions/'+v['id']+'/publish',headers=H)
    o=c.post('/orders',headers=H,json={'conversation_id':cid,'customer':'QA','phone':'01700000000','address':'House 1 Dhaka','items':[{'product_id':1,'quantity':1}],'request_id':'delivery-rating-test'}).json()
    rating=c.get('/workspace',headers=H).json()['ratings'][0]
    send_website(c,engine,wh,'RATE '+rating['code']+' 5');send_website(c,engine,wh,'RATE '+rating['code']+' 1')
    assert c.get('/workspace',headers=H).json()['ratings'][0]['rating']==5
    c.patch('/orders/'+o['id'],headers=H,json={'status':'shipped','tracking':'QA123'})
    body={'expected_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),'tracking_url':'https://steadfast.com.bd/t/QA123'}
    a=c.put('/orders/'+o['id']+'/delivery-plan',headers=H,json=body);assert a.status_code==200,a.text
    assert c.put('/orders/'+o['id']+'/delivery-plan',headers=H,json=body).json()['id']==a.json()['id']
    assert c.put('/orders/'+o['id']+'/delivery-plan',headers=H,json={**body,'tracking_url':'http://127.0.0.1/private'}).status_code==422
