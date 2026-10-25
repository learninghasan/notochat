import asyncio
from datetime import datetime,timezone,timedelta
from sqlalchemy.orm import Session
from main import Base
from test_completion import system,H,website,send_website

def test_lead_lifecycle_defaults_to_draft_and_cancels_on_new_customer_message(system,monkeypatch):
    app,c,engine=system;cid,wh=website(c,monkeypatch);send_website(c,engine,wh,'Question')
    body={'conversation_id':cid,'name':'Test','temperature':'Hot'}
    c.post('/leads',headers=H,json=body);c.post('/leads',headers=H,json=body)
    drafts=c.get('/workspace',headers=H).json()['automations'];assert len(drafts)==1 and drafts[0]['status']=='draft'
    c.post('/automations/'+drafts[0]['id']+'/activate',headers=H)
    send_website(c,engine,wh,'Newer question')
    with Session(engine) as s:
        for r in s.query(Base.WorkspaceRecord).filter_by(kind='jobs'):r.data={**r.data,'next_run_at':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()}
        s.commit()
    asyncio.run(app.state.run_jobs())
    w=c.get('/workspace',headers=H).json();assert w['automations'][0]['status']=='blocked' and w['outreach']==[]

def test_lifecycle_auto_opt_in_still_requires_marketing_consent(system,monkeypatch):
    app,c,engine=system;cid,wh=website(c,monkeypatch);send_website(c,engine,wh,'Question')
    v=c.post('/agent/versions',headers=H,json={'auto_lifecycle':True}).json();c.post('/agent/versions/'+v['id']+'/publish',headers=H)
    c.patch(f'/conversations/{cid}/mode',headers=H,json={'mode':'ai'})
    c.post('/leads',headers=H,json={'conversation_id':cid,'name':'Test','temperature':'Warm'})
    with Session(engine) as s:
        for r in s.query(Base.WorkspaceRecord).filter_by(kind='jobs'):r.data={**r.data,'next_run_at':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()}
        s.commit()
    asyncio.run(app.state.run_jobs());w=c.get('/workspace',headers=H).json()
    assert w['automations'][0]['status']=='blocked' and w['outreach']==[]

def test_order_status_drafts_are_idempotent_and_auto_opt_out_is_rechecked(system,monkeypatch):
    app,c,engine=system;cid,wh=website(c,monkeypatch);send_website(c,engine,wh,'Question')
    v=c.post('/agent/versions',headers=H,json={'auto_lifecycle':True,'review_url':'https://example.test/review'}).json();c.post('/agent/versions/'+v['id']+'/publish',headers=H)
    order=c.post('/orders',headers=H,json={'conversation_id':cid,'customer':'Test','phone':'01700000000','address':'House 7 Dhaka','items':[{'product_id':1,'quantity':1}],'request_id':'lifecycle-order'}).json()
    for _ in range(2):assert c.patch('/orders/'+order['id'],headers=H,json={'status':'shipped','tracking':'TRACK123'}).status_code==200
    a=c.get('/workspace',headers=H).json()['automations'];assert len(a)==1 and 'TRACK123' in a[0]['text']
    v=c.post('/agent/versions',headers=H,json={'auto_lifecycle':False,'review_url':'https://example.test/review'}).json();c.post('/agent/versions/'+v['id']+'/publish',headers=H)
    asyncio.run(app.state.run_jobs());w=c.get('/workspace',headers=H).json()
    assert w['automations'][0]['status']=='blocked' and w['outreach']==[]
    c.patch('/orders/'+order['id'],headers=H,json={'status':'delivered'})
    assert len(c.get('/workspace',headers=H).json()['automations'])==2
