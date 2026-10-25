import time
from sqlalchemy.orm import Session
from test_completion import system,H
from test_attachments import media_shop,incoming,event
from main import Base

def test_native_dot_only_signed_page_echo_not_customer_or_api(media_shop):
    _,c,_=media_shop;incoming(c,event());cid=c.get('/conversations',headers=H).json()[-1]['id'];c.patch(f'/conversations/{cid}/mode',headers=H,json={'mode':'ai'})
    payload={'object':'page','entry':[{'id':'12345','messaging':[{'sender':{'id':'12345'},'recipient':{'id':'customer'},'timestamp':int(time.time()*1000),'message':{'is_echo':True,'mid':'native-dot','text':'.','app_id':'our-api'}}]}]}
    incoming(c,payload);assert c.get('/conversations',headers=H).json()[-1]['mode']=='ai'
    del payload['entry'][0]['messaging'][0]['message']['app_id']
    incoming(c,payload);assert c.get('/conversations',headers=H).json()[-1]['mode']=='human'
    first=c.get('/workspace',headers=H).json()['conversation_meta'][str(cid)]['handover_until'];incoming(c,payload)
    assert c.get('/workspace',headers=H).json()['conversation_meta'][str(cid)]['handover_until']==first

def test_credit_email_outbox_opt_in_mock_delivery_and_no_blind_retry(system,monkeypatch):
    app,c,engine=system;c.put('/billing/notifications',headers=H,json={'enabled':True,'email':'owner@example.test'})
    with Session(engine) as s:app.state.queue_credit_email(s,'synthetic-crossing');app.state.queue_credit_email(s,'synthetic-crossing');s.commit()
    assert app.state.flush_credit_email()==0
    for key,value in {'SMTP_SENDER_VERIFIED':'1','ENABLE_EMAIL_SEND':'1','SMTP_HOST':'smtp.example.test','SMTP_FROM':'no-reply@example.test','SMTP_USERNAME':'fake','SMTP_PASSWORD':'fake'}.items():monkeypatch.setenv(key,value)
    calls=[]
    class SMTP:
        def __init__(self,*a,**k):pass
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def starttls(self,**k):pass
        def login(self,*a):pass
        def send_message(self,m):calls.append(m);raise OSError('ambiguous synthetic failure')
    monkeypatch.setattr('smtplib.SMTP',SMTP)
    assert app.state.flush_credit_email()==0 and len(calls)==1
    assert app.state.flush_credit_email()==0 and len(calls)==1
    assert 'customer' not in calls[0]['Subject'].lower()

def test_audio_billing_requires_explicit_rate_and_provider_duration(system,monkeypatch):
    import pytest
    from fastapi import HTTPException
    app,_,engine=system;monkeypatch.setenv('AI_BILLING_ENABLED','1')
    with Session(engine) as s:
        w=s.get(Base.WorkspaceRecord,'billing:wallet');w.data={**w.data,'balance_paisa':1000};s.commit()
        with pytest.raises(HTTPException):app.state.require_credit(s,'audio')
        monkeypatch.setenv('AI_AUDIO_PAISA_PER_MINUTE','60');app.state.require_credit(s,'audio')
        with pytest.raises(HTTPException):app.state.charge_usage(s,{'id':'missing-duration','action':'audio'})
        app.state.charge_usage(s,{'id':'synthetic-audio','action':'audio','duration_seconds':30});s.commit()
        app.state.charge_usage(s,{'id':'synthetic-audio','action':'audio','duration_seconds':30});s.commit()
        assert s.get(Base.WorkspaceRecord,'billing:wallet').data['balance_paisa']==970
