"""Deterministic, configurable booking questions for verified customer chat."""
import hashlib,secrets
from datetime import datetime,timezone,timedelta
from fastapi import Depends,HTTPException
from pydantic import BaseModel,Field,model_validator
from sqlalchemy import select

class Service(BaseModel):
    name:str=Field(min_length=1,max_length=200)
    resource:str=Field(default='Main',min_length=1,max_length=100)
    duration_minutes:int=Field(default=60,ge=15,le=1440)
class Configuration(BaseModel):
    enabled:bool=False
    services:list[Service]=Field(default_factory=list,max_length=10)
    questions:list[str]=Field(default_factory=list,max_length=10)
    @model_validator(mode='after')
    def validate_questions(self):
        if self.enabled and not self.services:raise ValueError('Add a service before enabling intake')
        if any(not q.strip() or len(q)>300 for q in self.questions):raise ValueError('Questions must contain 1–300 characters')
        if any(not x.name.strip() or not x.resource.strip() for x in self.services):raise ValueError('Service and resource names cannot be blank')
        return self

def install_booking_intake(app,Record,Conversation,BookingInput,booking,authorize,session,put):
    @app.get('/booking-intake',dependencies=[Depends(authorize)])
    def configuration(s=Depends(session)):
        r=s.get(Record,'booking-intake:settings');return r.data if r else Configuration().model_dump()
    @app.put('/booking-intake',dependencies=[Depends(authorize)])
    def configure(body:Configuration,s=Depends(session)):
        d=put(s,'booking_intake_settings',body.model_dump(),'booking-intake:settings');s.commit();return d
    def respond(s,cid,text):
        config=s.get(Record,'booking-intake:settings')
        if not config or not config.data.get('enabled'):return None
        c=s.scalar(select(Conversation).where(Conversation.id==cid).with_for_update())
        key=f'booking-intake:{cid}';r=s.get(Record,key);word=text.strip();now=datetime.now(timezone.utc)
        if word.casefold() in ('book','বুকিং'):
            settings=Configuration.model_validate(config.data).model_dump()
            d={'conversation_id':cid,'code':secrets.token_hex(3).upper(),'step':'service','settings':settings,'answers':[],'expires_at':(now+timedelta(minutes=30)).isoformat()}
            put(s,'booking_intake',d,key)
            return 'Choose service number / সেবার নম্বর লিখুন:\n'+'\n'.join(f"{i+1}. {x['name']} ({x['duration_minutes']} min)" for i,x in enumerate(settings['services']))+'\nCANCEL to exit / বাতিল করতে CANCEL'
        if not r:return None
        d=dict(r.data)
        if word.upper()=='CANCEL':s.delete(r);return 'Booking questions cancelled. / বুকিং প্রশ্ন বাতিল করা হয়েছে।'
        if d.get('booking_id'):
            if word.upper()=='REQUEST '+d['code']:
                existing=s.get(Record,d['booking_id']);return 'Booking request already recorded: '+d['booking_id']+' · '+(existing.data['status'] if existing else 'unavailable')
            return None
        if datetime.fromisoformat(d['expires_at'])<=now:s.delete(r);return 'Booking questions expired. Send BOOK to restart. / আবার BOOK লিখুন।'
        if word.upper() in ('HUMAN','TEAM'):
            s.delete(r);c.mode='human';return 'Our team will help with your booking. / টিম আপনার বুকিংয়ে সাহায্য করবে।'
        if d['step']=='service':
            if not word.isascii() or not word.isdigit() or not 1<=int(word)<=len(d['settings']['services']):return 'Please send one of the service numbers above, or CANCEL.'
            d.update(service=d['settings']['services'][int(word)-1],step='name');answer='Your full name? / আপনার পুরো নাম?'
        elif d['step']=='name':
            if not word or len(word)>160:return 'Use a name between 1 and 160 characters, or CANCEL.'
            d.update(customer=word,step='time');answer='Requested date/time with timezone, e.g. 2026-12-01T14:00:00+06:00. The owner must confirm availability. / সময় ও টাইমজোন লিখুন।'
        elif d['step']=='time':
            try:
                at=datetime.fromisoformat(word)
                if at.tzinfo is None or at<=now:raise ValueError()
            except ValueError:return 'Use a future date/time including timezone, e.g. 2026-12-01T14:00:00+06:00, or CANCEL.'
            d.update(starts_at=at.isoformat(),answers=[],step='questions' if d['settings']['questions'] else 'confirm');answer=''
        elif d['step']=='questions':
            if not word or len(word)>1000:return 'Answer using 1–1000 characters, or CANCEL.'
            d['answers']=[*d['answers'],word]
            if len(d['answers'])==len(d['settings']['questions']):d['step']='confirm'
            answer=''
        else:
            if word.upper()!='REQUEST '+d['code']:return 'Review the summary and type REQUEST '+d['code']+' to request owner confirmation, or CANCEL.'
            request_id='intake-'+hashlib.sha256((str(cid)+d['code']).encode()).hexdigest()
            existing=s.get(Record,'bookings:'+str(cid)+':'+request_id)
            try:result=existing.data if existing else booking(BookingInput(conversation_id=cid,customer=d['customer'],service=d['service']['name'],resource=d['service']['resource'],duration_minutes=d['service']['duration_minutes'],starts_at=d['starts_at'],request_id=request_id),s)
            except (HTTPException,ValueError) as error:
                if isinstance(error,HTTPException) and error.status_code!=409:raise
                s.rollback();r=s.get(Record,key);r.data={**d,'step':'time'};return 'That resource is no longer available. Please choose another date/time with timezone, or CANCEL.'
            record=s.get(Record,result['id']);record.data={**record.data,'intake_answers':[{'question':q,'answer':a} for q,a in zip(d['settings']['questions'],d['answers'])]}
            r=s.get(Record,key);r.data={**d,'booking_id':result['id']}
            return 'Booking requested, pending owner confirmation. No payment verified. / মালিকের অনুমোদনের অপেক্ষায়: '+result['id']
        if d['step']=='questions':answer=d['settings']['questions'][len(d['answers'])]
        if d['step']=='confirm':answer=f"Review booking / বুকিং মিলিয়ে দেখুন:\n{d['service']['name']} · {d['customer']}\n{d['starts_at']} · {d['service']['duration_minutes']} min\n"+'\n'.join(q+': '+a for q,a in zip(d['settings']['questions'],d['answers']))+'\nNo payment taken. Owner approval required. Reply REQUEST '+d['code']+' or CANCEL.'
        r=s.get(Record,key);r.data=d;return answer
    app.state.booking_intake_response=respond
