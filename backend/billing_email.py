"""Opt-in generic low-credit email outbox; delivery is disabled unless configured."""
import os,smtplib,ssl
from email.message import EmailMessage
from datetime import datetime,timezone
from fastapi import Depends
from pydantic import BaseModel,Field
from sqlalchemy import select,update
from sqlalchemy.orm import Session

class Settings(BaseModel):
    enabled:bool=False
    email:str=Field(default='',max_length=254,pattern=r'^(?:[^\s@]+@[^\s@]+\.[^\s@]+)?$')

def install_email(app,engine,Record,authorize,session,put):
    @app.get('/billing/notifications',dependencies=[Depends(authorize)])
    def get(s=Depends(session)):
        r=s.get(Record,'billing:email');return r.data if r else Settings().model_dump()
    @app.put('/billing/notifications',dependencies=[Depends(authorize)])
    def configure(body:Settings,s=Depends(session)):
        d=put(s,'billing_email_settings',body.model_dump(),'billing:email');s.commit();return d
    def queue(s,key):
        settings=s.get(Record,'billing:email');rid='billing_email:'+key
        if settings and settings.data.get('enabled') and settings.data.get('email') and not s.get(Record,rid):put(s,'billing_email',{'status':'pending','created_at':datetime.now(timezone.utc).isoformat()},rid)
    def flush():
        if os.getenv('ENABLE_EMAIL_SEND')!='1' or not (os.getenv('SMTP_USERNAME') or os.getenv('SMTP_USER')) or not all(os.getenv(k) for k in ('SMTP_HOST','SMTP_FROM','SMTP_PASSWORD')):return 0
        count=0
        with Session(engine) as s:
            for r in s.scalars(select(Record).where(Record.kind=='billing_email',Record.data['status'].as_string()=='pending').limit(10)):
                config=s.get(Record,'billing:email')
                if not config or not config.data.get('enabled') or not config.data.get('email'):r.data={**r.data,'status':'cancelled'};s.commit();continue
                claimed=s.execute(update(Record).where(Record.id==r.id,Record.data['status'].as_string()=='pending').values(data={**r.data,'status':'attempting'}));s.commit()
                if claimed.rowcount!=1:continue
                try:
                    message=EmailMessage();message['From']=os.environ['SMTP_FROM'];message['To']=config.data['email'];message['Subject']='NotoChat AI credit is low';message.set_content('Your NotoChat workspace AI credit is low. Sign in to review billing and recharge. No customer data is included in this email.')
                    with smtplib.SMTP(os.environ['SMTP_HOST'],int(os.getenv('SMTP_PORT','587')),timeout=15) as client:
                        client.starttls(context=ssl.create_default_context());client.login(os.getenv('SMTP_USERNAME') or os.environ['SMTP_USER'],os.environ['SMTP_PASSWORD']);client.send_message(message)
                    r.data={**r.data,'status':'sent'};count+=1
                except Exception:r.data={**r.data,'status':'unconfirmed'}  # Never blindly resend an ambiguous SMTP outcome.
                s.commit()
        return count
    app.state.queue_credit_email=queue;app.state.flush_credit_email=flush
