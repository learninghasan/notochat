"""Operator-supplied delivery dates, safe tracking links and verified customer ratings."""
import hashlib,re,secrets
from datetime import datetime,timezone,timedelta
from urllib.parse import urlsplit
from fastapi import Depends,HTTPException
from pydantic import BaseModel,Field,field_validator
from sqlalchemy import select

class Plan(BaseModel):
    expected_at:datetime
    tracking_url:str=Field(max_length=2000)
    @field_validator('expected_at')
    @classmethod
    def future(cls,value):
        if not value.tzinfo or not datetime.now(timezone.utc)<value<datetime.now(timezone.utc)+timedelta(days=90):raise ValueError('Choose a future delivery update time within 90 days, with timezone')
        return value
    @field_validator('tracking_url')
    @classmethod
    def safe(cls,value):
        p=urlsplit(value);host=p.hostname or ''
        if p.scheme!='https' or p.username or p.password or p.port not in (None,443) or not(host=='steadfast.com.bd' or host.endswith('.steadfast.com.bd') or host=='pathao.com' or host.endswith('.pathao.com')):raise ValueError('Use an official HTTPS Steadfast or Pathao tracking link')
        return value

def install_delivery_experience(app,Record,authorize,session,put):
    @app.put('/orders/{rid}/delivery-plan',dependencies=[Depends(authorize)])
    def plan(rid:str,body:Plan,s=Depends(session)):
        order=s.scalar(select(Record).where(Record.id==rid,Record.kind=='orders').with_for_update())
        if not order:raise HTTPException(404,'Order not found')
        if order.data['status']!='shipped':raise HTTPException(409,'A shipped order is required; no delivery date is inferred')
        stamp=body.expected_at.isoformat();order.data={**order.data,'expected_delivery_at':stamp,'tracking_url':body.tracking_url}
        key='automations:delivery-day:'+hashlib.sha256((rid+stamp+body.tracking_url).encode()).hexdigest()
        existing=s.get(Record,key)
        if existing:s.commit();return existing.data
        automatic=bool(s.get(Record,'agent:live').data.get('auto_lifecycle'))
        d=put(s,'automations',{'conversation_id':order.data['conversation_id'],'kind':'delivery','text':'আজ ডেলিভারি প্রত্যাশিত / Delivery is expected today; timing may change. Tracking: '+body.tracking_url,'due_at':stamp,'status':'scheduled' if automatic else 'draft','delivery':'not sent','auto_send':automatic,'source_id':rid,'source_kind':'orders','source_state':'shipped','expected_delivery_at':stamp,'tracking_url':body.tracking_url},key)
        if automatic:app.state.enqueue(s,'reminder_prepare',{'automation_id':key,'conversation_id':order.data['conversation_id']},due=body.expected_at,key='reminder-'+key)
        s.commit();return d
    def rating_prompt(s,order):
        key='rating_request:'+order.id;r=s.get(Record,key)
        if r:return r.data
        return put(s,'rating_request',{'conversation_id':order.data['conversation_id'],'order_id':order.id,'code':secrets.token_hex(4).upper(),'expires_at':(datetime.now(timezone.utc)+timedelta(days=7)).isoformat()},key)
    def rating(s,cid,text):
        m=re.fullmatch(r'RATE\s+([A-F0-9]{8})\s+([1-5])',text.strip(),re.I)
        if not m:return None
        r=s.scalar(select(Record).where(Record.kind=='rating_request',Record.data['conversation_id'].as_integer()==cid,Record.data['code'].as_string()==m[1].upper()).with_for_update())
        if not r:return 'No matching rating request. / রেটিং অনুরোধ পাওয়া যায়নি।'
        order=s.get(Record,r.data['order_id'])
        if not order or order.data['status']=='cancelled' or datetime.fromisoformat(r.data['expires_at'])<=datetime.now(timezone.utc):return 'This rating request has expired or was cancelled.'
        if r.data.get('rating'):return 'Your rating was already recorded. Thank you! / ধন্যবাদ, রেটিংটি আগে রেকর্ড হয়েছে।'
        r.data={**r.data,'rating':int(m[2]),'rated_at':datetime.now(timezone.utc).isoformat()}
        return 'Thank you for your rating! / আপনার রেটিংয়ের জন্য ধন্যবাদ!'
    app.state.rating_prompt=rating_prompt;app.state.capture_rating=rating
