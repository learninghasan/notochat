import asyncio
from datetime import datetime,timezone,timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from main import Base,create_workspace

H={'Authorization':'Bearer test-token'}
@pytest.fixture
def system(tmp_path,monkeypatch):
    monkeypatch.setenv('WIDGET_ENABLED','1')
    engine=create_engine('sqlite:///'+str(tmp_path/'outreach.db'))
    app=create_workspace(engine);c=TestClient(app)
    token=c.post('/widget/sessions',json={'name':'Outreach customer'}).json()['token']
    c.post('/widget/messages',headers={'Authorization':'Bearer '+token},json={'text':'Interested in your products'})
    cid=next(x['id'] for x in c.get('/conversations',headers=H).json() if x['customer']=='Outreach customer')
    c.patch(f'/conversations/{cid}/mode',headers=H,json={'mode':'ai'})
    return app,c,engine,cid

def consent(c,cid,allowed=True):
    r=c.put(f'/conversations/{cid}/marketing-consent',headers=H,json={'allowed':allowed,'evidence':'Customer requested offers in website chat'})
    assert r.status_code==200,r.text

def broadcast(c):
    b=c.post('/broadcasts/preview',headers=H,json={'text':'Our seasonal offer','channel':'Website'}).json()
    r=c.post('/broadcasts/'+b['id']+'/send',headers=H,json={'confirm':'SEND ELIGIBLE RECIPIENTS'})
    assert r.status_code==200,r.text
    return r.json()

def test_broadcast_requires_consent_and_explicit_confirmation(system):
    app,c,_,cid=system
    b=broadcast(c);assert b['queued_ids']==[] and b['blocked'][0]['reason']=='Recorded marketing consent is required'
    consent(c,cid)
    b=c.post('/broadcasts/preview',headers=H,json={'text':'Offer'}).json()
    assert c.post('/broadcasts/'+b['id']+'/send',headers=H,json={}).status_code==422
    assert asyncio.run(app.state.run_jobs())==[]

def test_broadcast_is_idempotent_and_counts_actual_delivery(system):
    app,c,_,cid=system;consent(c,cid);b=broadcast(c)
    c.post('/broadcasts/'+b['id']+'/send',headers=H,json={'confirm':'SEND ELIGIBLE RECIPIENTS'})
    assert len(c.get('/jobs',headers=H).json())==1
    assert len(asyncio.run(app.state.run_jobs()))==1
    assert asyncio.run(app.state.run_jobs())==[]
    assert sum(m['text']=='Our seasonal offer' for m in c.get(f'/conversations/{cid}/messages',headers=H).json())==1
    saved=next(x for x in c.get('/workspace',headers=H).json()['broadcasts'] if x['id']==b['id'])
    assert saved['status']=='completed' and saved['sent']==1

@pytest.mark.parametrize('change',['withdraw','takeover','expire'])
def test_queued_broadcast_rechecks_before_delivery(system,change):
    app,c,engine,cid=system;consent(c,cid);broadcast(c)
    if change=='withdraw':consent(c,cid,False)
    elif change=='takeover':c.patch(f'/conversations/{cid}/mode',headers=H,json={'mode':'human'})
    else:
        with Session(engine) as s:
            r=s.get(Base.WorkspaceRecord,f'conversation:{cid}');r.data={**r.data,'last_verified_inbound':(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()};s.commit()
        # A local test message must not reopen the verified window.
        c.post(f'/conversations/{cid}/incoming',headers=H,json={'text':'Local test'})
    asyncio.run(app.state.run_jobs())
    assert c.get('/jobs',headers=H).json()[0]['output']['sent'] is False
    assert not any(m['text']=='Our seasonal offer' for m in c.get(f'/conversations/{cid}/messages',headers=H).json())

@pytest.mark.parametrize('kind,expected',[('followup',False),('review',False),('booking-reminder',True),('delivery',True)])
def test_automatic_reminder_consent_rules(system,kind,expected):
    app,c,_,cid=system
    a=c.post('/automations',headers=H,json={'conversation_id':cid,'kind':kind,'text':'Scheduled notification','auto_send':True,'due_at':(datetime.now(timezone.utc)-timedelta(seconds=2)).isoformat()}).json()
    c.post('/automations/'+a['id']+'/activate',headers=H)
    asyncio.run(app.state.run_jobs())
    assert c.get('/jobs',headers=H).json()[0]['output']['sent']==expected

def test_cancelled_broadcast_completes_without_sending(system):
    app,c,_,cid=system;consent(c,cid);broadcast(c)
    job=c.get('/jobs',headers=H).json()[0]
    assert c.post('/jobs/'+job['id']+'/cancel',headers=H).status_code==200
    assert asyncio.run(app.state.run_jobs())==[]
    assert c.get('/workspace',headers=H).json()['broadcasts'][0]['status']=='completed'

def test_old_preview_requires_refresh(system):
    _,c,engine,cid=system;consent(c,cid)
    b=c.post('/broadcasts/preview',headers=H,json={'text':'Old offer'}).json()
    with Session(engine) as s:
        r=s.get(Base.WorkspaceRecord,b['id']);r.data={**r.data,'created_at':(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()};s.commit()
    assert c.post('/broadcasts/'+b['id']+'/send',headers=H,json={'confirm':'SEND ELIGIBLE RECIPIENTS'}).status_code==409
