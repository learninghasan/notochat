import asyncio
from datetime import datetime,timezone,timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from main import create_workspace,Base


@pytest.fixture
def isolated(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'jobs.db'))
    app=create_workspace(engine)
    return app,TestClient(app),engine


def reminder(client,conversation=1,recent=True):
    headers={'Authorization':'Bearer test-token'}
    if recent:client.post(f'/conversations/{conversation}/incoming',headers=headers,json={'text':'Recent customer message'})
    a=client.post('/automations',headers=headers,json={'conversation_id':conversation,'kind':'followup','text':'Reminder for review','due_at':(datetime.now(timezone.utc)-timedelta(seconds=2)).isoformat()}).json()
    result=client.post('/automations/'+a['id']+'/activate',headers=headers)
    assert result.status_code==200,result.text
    return a,headers


def test_worker_prepares_once_without_customer_send(isolated):
    app,c,engine=isolated
    a,h=reminder(c)
    before=len(c.get('/conversations/1/messages',headers=h).json())
    assert len(asyncio.run(app.state.run_jobs()))==1
    assert asyncio.run(app.state.run_jobs())==[]
    data=c.get('/workspace',headers=h).json()
    assert next(x for x in data['automations'] if x['id']==a['id'])['status']=='ready'
    assert len(c.get('/conversations/1/messages',headers=h).json())==before
    assert data['jobs'][0]['output']['sent'] is False


def test_worker_rechecks_reply_window_at_execution(isolated):
    app,c,_=isolated
    a,h=reminder(c,conversation=2,recent=False)
    asyncio.run(app.state.run_jobs())
    data=c.get('/workspace',headers=h).json()
    assert next(x for x in data['automations'] if x['id']==a['id'])['status']=='blocked'
    assert data['jobs'][0]['output']['sent'] is False


def test_cancelled_job_is_not_processed(isolated):
    app,c,_=isolated
    _,h=reminder(c)
    job=c.get('/jobs',headers=h).json()[0]
    assert c.post('/jobs/'+job['id']+'/cancel',headers=h).status_code==200
    assert asyncio.run(app.state.run_jobs())==[]


def test_ai_jobs_retry_with_backoff_without_fabricated_output(isolated,monkeypatch):
    app,c,_=isolated
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    h={'Authorization':'Bearer test-token'}
    assert c.post('/conversations/1/assistant/jobs',headers=h).status_code==200
    asyncio.run(app.state.run_jobs())
    job=c.get('/jobs',headers=h).json()[0]
    assert job['status']=='pending' and job['attempts']==1
    assert 'not configured' in job['error']
    assert datetime.fromisoformat(job['next_run_at'])>datetime.now(timezone.utc)
    assert c.get('/workspace',headers=h).json()['assistant_drafts']==[]
    assert asyncio.run(app.state.run_jobs())==[]


def test_expired_lease_is_recovered(isolated):
    app,c,engine=isolated
    a,h=reminder(c)
    Record=Base.WorkspaceRecord
    with Session(engine) as s:
        r=s.scalar(select(Record).where(Record.kind=='jobs'))
        r.data={**r.data,'status':'running','lease_until':(datetime.now(timezone.utc)-timedelta(seconds=10)).isoformat(),'attempts':1};s.commit()
    assert len(asyncio.run(app.state.run_jobs()))==1
    assert c.get('/jobs',headers=h).json()[0]['attempts']==2


def test_automatic_draft_queues_only_when_enabled_and_skips_after_takeover(isolated):
    app,c,_=isolated;h={'Authorization':'Bearer test-token'}
    c.post('/conversations/1/incoming',headers=h,json={'text':'Not enabled yet'})
    assert c.get('/jobs',headers=h).json()==[]
    version=c.post('/agent/versions',headers=h,json={'auto_draft':True}).json()
    c.post('/agent/versions/'+version['id']+'/publish',headers=h)
    c.post('/conversations/1/incoming',headers=h,json={'text':'Please check the price'})
    assert len(c.get('/jobs',headers=h).json())==1
    c.post('/conversations/1/handover',headers=h,json={'reason':'Manual takeover','duration_minutes':0})
    asyncio.run(app.state.run_jobs())
    job=c.get('/jobs',headers=h).json()[0]
    assert job['status']=='done' and job['output']['skipped']=='Human took over'
