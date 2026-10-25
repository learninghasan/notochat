"""Consent-aware, idempotent, window-bound customer outreach."""
from datetime import datetime,timezone,timedelta
from typing import Literal
from fastapi import Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

class Consent(BaseModel):
    allowed:bool
    evidence:str=Field(default='',max_length=2000)

class ConfirmBroadcast(BaseModel):
    confirm:Literal['SEND ELIGIBLE RECIPIENTS']


def install_outreach(app,Record,Conversation,Message,authorize,session,put,notify):
    def now():return datetime.now(timezone.utc)
    def eligibility(s,cid,marketing=False):
        if not app.state.workspace_active():return False,'Workspace is paused'
        c=s.get(Conversation,cid);m=s.get(Record,f'conversation:{cid}')
        if not c or not m:return False,'Verified customer source is required'
        d=m.data
        if d.get('source') not in ('website-widget','signed-meta-webhook'):return False,'Verified customer source is required'
        if c.channel not in ('Website','Messenger','Instagram','WhatsApp'):return False,'No supported message transport'
        if c.mode!='ai':return False,'Human takeover pauses automated outreach'
        try:age=now()-datetime.fromisoformat(d.get('last_verified_inbound',''))
        except (ValueError,TypeError):return False,'Recent inbound timestamp is required'
        if not timedelta(0)<=age<timedelta(hours=23):return False,'Reply window has expired; template sending is not implemented'
        if marketing and not d.get('marketing_opt_in'):return False,'Recorded marketing consent is required'
        if c.channel!='Website' and not app.state.channel_account(c.channel,d.get('account','')):return False,'Channel account is disconnected or disabled'
        if c.channel!='Website' and app.state.channel_configuration().get('ENABLE_LIVE_SEND')!='1':return False,'Live channel sending is disabled'
        return True,'Eligible now; eligibility will be checked again before sending'

    @app.put('/conversations/{cid}/marketing-consent',dependencies=[Depends(authorize)])
    def consent(cid:int,body:Consent,s=Depends(session)):
        if not s.get(Conversation,cid):raise HTTPException(404,'Conversation not found')
        if body.allowed and len(body.evidence.strip())<5:raise HTTPException(422,'Record when/how this customer opted in')
        r=s.get(Record,f'conversation:{cid}');d=r.data if r else {}
        put(s,'conversation',{**d,'marketing_opt_in':body.allowed,'consent_evidence':body.evidence.strip(),'consent_recorded_at':now().isoformat()},f'conversation:{cid}');s.commit();return {'marketing_opt_in':body.allowed}

    @app.post('/broadcasts/{rid}/send',dependencies=[Depends(authorize)])
    def send_broadcast(rid:str,body:ConfirmBroadcast,s=Depends(session)):
        b=s.scalar(select(Record).where(Record.id==rid,Record.kind=='broadcasts').with_for_update())
        if not b:raise HTTPException(404,'Broadcast preview not found')
        if b.data['status'] in ('queued','completed'):return b.data
        if now()-datetime.fromisoformat(b.data['created_at'])>timedelta(minutes=15):raise HTTPException(409,'Create a fresh audience preview before sending')
        ids=[];blocked=[]
        for cid in b.data['eligible_ids']:
            allowed,reason=eligibility(s,cid,True)
            if allowed:
                app.state.enqueue(s,'outreach',{'conversation_id':cid,'text':b.data['text'],'marketing':True,'broadcast_id':rid},key='broadcast-'+rid+'-'+str(cid));ids.append(cid)
            else:blocked.append({'conversation_id':cid,'reason':reason})
        b.data={**b.data,'status':'queued' if ids else 'completed','queued_ids':ids,'blocked':blocked};s.commit();return b.data

    async def deliver(s,cid,text,key,marketing=False,tracking_url=None):
        allowed,reason=eligibility(s,cid,marketing)
        if not allowed:return {'sent':False,'blocked':reason}
        r=s.get(Record,'outreach:'+key)
        if r:message_id=r.data['message_id']
        else:
            message=Message(conversation_id=cid,role='team',text=text);s.add(message);s.flush();message_id=message.id
            put(s,'outreach',{'conversation_id':cid,'message_id':message_id,'marketing':marketing},'outreach:'+key)
            if tracking_url:put(s,'rich_message',{'conversation_id':cid,'message_id':message_id,'kind':'link','tracking_url':tracking_url,'products':[],'categories':[]},f'rich_message:{message_id}')
            try:s.commit()
            except IntegrityError:
                s.rollback();existing=s.get(Record,'outreach:'+key)
                if not existing:raise
                message_id=existing.data['message_id']
        c=s.get(Conversation,cid)
        if c.channel=='Website':return {'sent':True,'message_id':message_id,'channel':'Website'}
        result=await app.state.deliver_automated(cid,message_id,s)
        return {'sent':result.get('status')=='sent','message_id':message_id,'channel':c.channel}

    app.state.outreach_eligibility=eligibility
    app.state.deliver_outreach=deliver
