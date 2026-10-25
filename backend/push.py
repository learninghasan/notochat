"""Generic device notifications; customer data is never placed in push payloads."""
import hashlib
import json
import os
from datetime import datetime,timezone,timedelta
from urllib.parse import urlsplit
from fastapi import Depends,HTTPException
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select,update,or_,and_
from sqlalchemy.orm import Session

class PushKeys(BaseModel):
    p256dh:str=Field(min_length=40,max_length=200,pattern=r'^[A-Za-z0-9_-]+=*$')
    auth:str=Field(min_length=16,max_length=100,pattern=r'^[A-Za-z0-9_-]+=*$')

class Subscription(BaseModel):
    endpoint:str=Field(max_length=3000)
    keys:PushKeys
    @field_validator('endpoint')
    @classmethod
    def trusted_provider(cls,value):
        p=urlsplit(value);host=p.hostname or ''
        allowed=host in ('fcm.googleapis.com','updates.push.services.mozilla.com','web.push.apple.com') or host.endswith('.push.apple.com') or host.endswith('.notify.windows.com')
        if p.scheme!='https' or not allowed or p.username or p.password or p.port not in (None,443):raise ValueError('Unsupported browser push provider endpoint')
        return value


def install_push(app,engine,Record,authorize,session,put):
    def configured():return all(os.getenv(k) for k in ('VAPID_PUBLIC_KEY','VAPID_PRIVATE_KEY','VAPID_SUBJECT'))
    @app.get('/push/config',dependencies=[Depends(authorize)])
    def config():return {'enabled':bool(configured()),'public_key':os.getenv('VAPID_PUBLIC_KEY','') if configured() else ''}

    @app.post('/push/subscriptions',dependencies=[Depends(authorize)])
    def subscribe(body:Subscription,principal=Depends(authorize),s:Session=Depends(session)):
        if not configured():raise HTTPException(503,'Browser push VAPID keys are not configured')
        rid='push:'+hashlib.sha256(body.endpoint.encode()).hexdigest()
        put(s,'push_subscriptions',{**body.model_dump(),'user_id':principal['user_id'] if principal else 'legacy-owner'},rid);s.commit();return {'subscribed':True}

    @app.delete('/push/subscriptions',dependencies=[Depends(authorize)])
    def unsubscribe(body:Subscription,principal=Depends(authorize),s:Session=Depends(session)):
        r=s.get(Record,'push:'+hashlib.sha256(body.endpoint.encode()).hexdigest())
        if r and r.data['user_id']==(principal['user_id'] if principal else 'legacy-owner'):s.delete(r);s.commit()
        return {'unsubscribed':True}

    def queue(s,notification):
        for subscription in s.scalars(select(Record).where(Record.kind=='push_subscriptions')):
            rid='push_delivery:'+hashlib.sha256((notification['id']+subscription.id).encode()).hexdigest()
            if not s.get(Record,rid):put(s,'push_delivery',{'subscription_id':subscription.id,'status':'pending','attempts':0},rid)
    app.state.queue_push=queue

    def flush():
        if not configured():return 0
        from pywebpush import webpush,WebPushException
        count=0
        with Session(engine) as s:
            for r in list(s.scalars(select(Record).where(Record.kind=='push_delivery',or_(Record.data['status'].as_string()=='pending',and_(Record.data['status'].as_string()=='sending',Record.data['lease_until'].as_string()<datetime.now(timezone.utc).isoformat()))).limit(100))):
                d=dict(r.data)
                if d['attempts']>=3:r.data={**d,'status':'failed'};s.commit();continue
                claimed={**d,'status':'sending','attempts':d['attempts']+1,'lease_until':(datetime.now(timezone.utc)+timedelta(minutes=3)).isoformat()}
                update_result=s.execute(update(Record).where(Record.id==r.id,Record.data['status'].as_string()==d['status'],Record.data['attempts'].as_integer()==d['attempts']).values(data=claimed));s.commit()
                if update_result.rowcount!=1:continue
                subscription=s.get(Record,d['subscription_id'])
                if not subscription:r.data={**d,'status':'skipped'};s.commit();continue
                try:
                    webpush(subscription_info={k:subscription.data[k] for k in ('endpoint','keys')},data=json.dumps({'title':'NotoChat','body':'Your workspace has an update. Open NotoChat to see the details.','url':'/'}),vapid_private_key=os.environ['VAPID_PRIVATE_KEY'],vapid_claims={'sub':os.environ['VAPID_SUBJECT']},ttl=60,timeout=10)
                    r.data={**d,'status':'sent','attempts':d['attempts']+1};count+=1
                except WebPushException as error:
                    status=error.response.status_code if error.response is not None else 0
                    if status in (404,410):s.delete(subscription)
                    attempts=d['attempts']+1;r.data={**d,'status':'failed' if attempts>=3 or status in (404,410) else 'pending','attempts':attempts}
                s.commit()
        return count
    app.state.flush_push=flush
