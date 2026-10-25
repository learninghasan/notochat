import asyncio
from datetime import datetime,timezone,timedelta
from test_completion import system,H,website,send_website,opt_in_sales

def test_booking_intake_questions_confirmation_and_duplicate_protection(system,monkeypatch):
    app,c,engine=system;opt_in_sales(c);cid,wh=website(c,monkeypatch)
    config={'enabled':True,'services':[{'name':'Consultation','resource':'Room A','duration_minutes':30}],'questions':['Your phone?','Any requirements?']}
    assert c.put('/booking-intake',headers=H,json=config).status_code==200
    def send(text):
        send_website(c,engine,wh,text);asyncio.run(app.state.run_jobs());return c.get(f'/conversations/{cid}/messages',headers=H).json()[-1]['text']
    assert 'Consultation' in send('BOOK')
    assert 'service numbers' in send('999')
    send('1');send('Rafi')
    assert 'timezone' in send('tomorrow')
    at=(datetime.now(timezone.utc)+timedelta(days=3)).isoformat()
    assert send(at)=='Your phone?'
    assert send('01700000000')=='Any requirements?'
    summary=send('Wheelchair access');assert 'REQUEST ' in summary
    assert c.get('/workspace',headers=H).json()['bookings']==[]
    code=summary.split('REQUEST ')[-1].split()[0]
    assert 'pending owner confirmation' in send('REQUEST '+code)
    assert 'already recorded' in send('REQUEST '+code)
    bookings=c.get('/workspace',headers=H).json()['bookings'];assert len(bookings)==1 and bookings[0]['status']=='requested'
    assert bookings[0]['intake_answers'][1]['answer']=='Wheelchair access'
    assert bookings[0]['payment_status']=='unverified'

def test_invalid_configuration_and_local_test_messages_cannot_start_intake(system):
    app,c,_=system
    assert c.put('/booking-intake',headers=H,json={'enabled':True}).status_code==422
    assert c.put('/booking-intake',headers=H,json={'questions':['x'*301]}).status_code==422
    opt_in_sales(c)
    c.post('/conversations/1/incoming',headers=H,json={'text':'BOOK'});asyncio.run(app.state.run_jobs())
    assert c.get('/workspace',headers=H).json()['bookings']==[]

def test_booking_request_retry_and_changed_payload_conflict(system):
    _,c,_=system
    at=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
    data={'conversation_id':1,'customer':'Customer','service':'Consultation','starts_at':at,'request_id':'booking-retry-123'}
    first=c.post('/bookings',headers=H,json=data);assert first.status_code==200
    assert c.post('/bookings',headers=H,json=data).json()['id']==first.json()['id']
    assert c.post('/bookings',headers=H,json={**data,'customer':'Changed'}).status_code==409


from test_business import gateway,call

def test_intake_settings_and_owner_confirmation_are_tenant_scoped(gateway):
    c,_=gateway
    cid=call(c,'booking_A','POST','/conversations',{'customer':'A'}).json()['id']
    config={'enabled':True,'services':[{'name':'Service A'}]}
    assert call(c,'booking_A','PUT','/booking-intake',config,role='member').status_code==403
    assert call(c,'booking_A','PUT','/booking-intake',config).status_code==200
    assert call(c,'booking_B','GET','/booking-intake').json()['enabled'] is False
    b=call(c,'booking_A','POST','/bookings',{'conversation_id':cid,'customer':'A','service':'Service A','starts_at':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()}).json()
    assert call(c,'booking_A','PATCH','/bookings/'+b['id'],{'status':'confirmed'},role='member').status_code==403
    assert call(c,'booking_B','PATCH','/bookings/'+b['id'],{'status':'confirmed'}).status_code==404
    assert call(c,'booking_A','PATCH','/bookings/'+b['id'],{'status':'confirmed'}).status_code==200
