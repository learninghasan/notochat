"""Durable preparation and explicitly enabled, bounded automatic sales jobs."""
import copy
from datetime import datetime,timezone,timedelta
from fastapi import Depends,HTTPException
from sqlalchemy import select,update
from sqlalchemy.orm import Session


def install_jobs(app,engine,Record,Conversation,Message,authorize,session,put,notify,expire,within_window,assistant,AssistantInput):
    def now():return datetime.now(timezone.utc)
    def enqueue(s,kind,payload,due=None,key=None):
        if key:
            existing=s.get(Record,'jobs:'+key)
            if existing:return existing.data
        return put(s,'jobs',{'kind':kind,'payload':payload,'status':'pending','attempts':0,'next_run_at':(due or now()).isoformat(),'created_at':now().isoformat(),'lease_until':'','error':''},'jobs:'+key if key else None)

    def update_broadcast(s,bid):
        if not bid:return
        b=s.scalar(select(Record).where(Record.id==bid,Record.kind=='broadcasts').with_for_update().execution_options(populate_existing=True))
        if not b:return
        jobs=[j.data for j in s.scalars(select(Record).where(Record.kind=='jobs').execution_options(populate_existing=True)) if j.data['payload'].get('broadcast_id')==bid]
        b.data={**b.data,'sent':sum(bool(j.get('output',{}).get('sent')) for j in jobs),'status':'completed' if all(j['status'] in ('done','failed','cancelled') for j in jobs) else 'queued'}
        s.commit()

    def queue_auto(s,cid,mid):
        c=s.get(Conversation,cid);live=s.get(Record,'agent:live')
        attachments=list(s.scalars(select(Record).where(Record.kind=='attachments',Record.data['message_id'].as_integer()==mid)))
        if attachments:
            if c and c.mode=='ai' and live and live.data.get('auto_media_analysis'):
                for item in attachments:
                    if item.data['status']=='ready':enqueue(s,'media_analyze',{'conversation_id':cid,'attachment_id':item.id,'automatic':True},key='media-auto-'+item.id)
            return None
        if c and c.mode=='ai' and live and (live.data.get('auto_draft',False) or live.data.get('auto_reply',False)):
            return enqueue(s,'sales_agent' if live.data.get('auto_reply') else 'ai_draft',{'conversation_id':cid,'message_id':mid,'automatic':True},key='message-'+str(mid))

    app.state.enqueue=enqueue
    app.state.queue_auto_draft=queue_auto

    @app.get('/jobs',dependencies=[Depends(authorize)])
    def list_jobs(s:Session=Depends(session)):
        return [r.data for r in s.scalars(select(Record).where(Record.kind=='jobs').order_by(Record.id))]

    @app.post('/automations/{rid}/activate',dependencies=[Depends(authorize)])
    def activate(rid:str,s:Session=Depends(session)):
        r=s.get(Record,rid)
        if not r or r.kind!='automations':raise HTTPException(404,'Reminder not found')
        if r.data['status'] in ('scheduled','ready'):return r.data
        if r.data['status']!='draft':raise HTTPException(409,'Only reminder drafts can be scheduled')
        due=datetime.fromisoformat(r.data['due_at'])
        enqueue(s,'reminder_prepare',{'automation_id':rid,'conversation_id':r.data['conversation_id']},due=due,key='reminder-'+rid)
        r.data={**r.data,'status':'scheduled'};s.commit();return r.data

    @app.post('/conversations/{cid}/assistant/jobs',dependencies=[Depends(authorize)])
    def queue_assistant(cid:int,s:Session=Depends(session)):
        if not s.get(Conversation,cid):raise HTTPException(404,'Conversation not found')
        latest=s.scalar(select(Message).where(Message.conversation_id==cid,Message.role=='customer').order_by(Message.id.desc()).limit(1))
        d=enqueue(s,'ai_draft',{'conversation_id':cid,'message_id':latest.id if latest else None})
        s.commit();return d

    @app.post('/jobs/{rid}/cancel',dependencies=[Depends(authorize)])
    def cancel(rid:str,s:Session=Depends(session)):
        r=s.scalar(select(Record).where(Record.id==rid,Record.kind=='jobs').with_for_update())
        if not r:raise HTTPException(404,'Job not found')
        if r.data['status'] not in ('pending','failed'):raise HTTPException(409,'This job cannot be cancelled')
        r.data={**r.data,'status':'cancelled'};s.commit();update_broadcast(s,r.data['payload'].get('broadcast_id'));return r.data

    def claim(s):
        timestamp=now().isoformat()
        candidates=list(s.scalars(select(Record).where(Record.kind=='jobs').order_by(Record.id)))
        for record in candidates:
            d=copy.deepcopy(record.data)
            due=d['status']=='pending' and d['next_run_at']<=timestamp
            expired=d['status']=='running' and d.get('lease_until','')<=timestamp
            if not due and not expired:continue
            if d['attempts']>=3:
                record.data={**d,'status':'failed','error':'Maximum attempts reached; inspect before requeueing'};s.commit();update_broadcast(s,d['payload'].get('broadcast_id'));continue
            new={**d,'status':'running','attempts':d['attempts']+1,'lease_until':(now()+timedelta(minutes=3)).isoformat()}
            # Conditional atomic update is the claim; only one worker can win the old state.
            updated=s.execute(update(Record).where(Record.id==record.id,Record.data['status'].as_string()==d['status'],Record.data['attempts'].as_integer()==d['attempts']).values(data=new))
            s.commit()
            if updated.rowcount==1:return record.id,new
        return None

    async def run_jobs(limit=20):
        if hasattr(app.state,'workspace_active') and not app.state.workspace_active():return []
        processed=[]
        with Session(engine) as s:expire(s)
        for _ in range(limit):
            with Session(engine) as s:
                claimed=claim(s)
                if not claimed:break
                rid,data=claimed
                try:
                    payload=data['payload'];c=s.get(Conversation,payload['conversation_id'])
                    if not c:raise ValueError('Conversation no longer exists')
                    if data['kind']=='media_analyze':
                        output=await app.state.analyze_attachment(s,c.id,payload['attachment_id'],payload.get('automatic',False))
                    elif data['kind']=='outreach':
                        output=await app.state.deliver_outreach(s,c.id,payload['text'],rid,payload.get('marketing',False))
                    elif data['kind']=='sales_agent':
                        output=await app.state.sales_respond(c.id,payload['message_id'],s)
                    elif data['kind']=='reminder_prepare':
                        a=s.get(Record,payload['automation_id'])
                        if not a or a.kind!='automations':raise ValueError('Reminder no longer exists')
                        if not app.state.lifecycle_source_valid(s,a.data):
                            a.data={**a.data,'status':'blocked','delivery':'Source changed; reminder cancelled'}
                            record=s.get(Record,rid);record.data={**data,'status':'done','output':{'sent':False,'blocked':'Source changed'},'finished_at':now().isoformat(),'lease_until':''};s.commit();processed.append(rid);continue
                        eligible=within_window(s,c.id)
                        a.data={**a.data,'status':'ready' if eligible else 'blocked','delivery':'not sent','eligibility_checked_at':now().isoformat()}
                        notify(s,'Reminder ready for review' if eligible else 'Reminder blocked by reply window',a.data['text'],c.id)
                        output={'prepared':eligible,'sent':False}
                        if a.data.get('auto_send'):
                            output=await app.state.deliver_outreach(s,c.id,a.data['text'],rid,a.data['kind'] in ('followup','review'),a.data.get('tracking_url'))
                            a=s.get(Record,payload['automation_id']);a.data={**a.data,'status':'sent' if output.get('sent') else 'blocked','delivery':'sent' if output.get('sent') else output.get('blocked','not sent')}
                    elif data['kind']=='ai_draft':
                        latest=s.scalar(select(Message).where(Message.conversation_id==c.id,Message.role=='customer').order_by(Message.id.desc()).limit(1))
                        expected=payload.get('message_id')
                        if payload.get('automatic') and c.mode!='ai':output={'skipped':'Human took over','sent':False}
                        elif expected and latest and latest.id!=expected:output={'skipped':'Newer customer message exists','sent':False}
                        else:
                            result=await assistant(c.id,AssistantInput(action='draft'),s)
                            s.refresh(c)
                            current=s.scalar(select(Message).where(Message.conversation_id==c.id,Message.role=='customer').order_by(Message.id.desc()).limit(1))
                            if payload.get('automatic') and (c.mode!='ai' or (expected and current and current.id!=expected)):
                                output={'skipped':'Conversation changed while generating','sent':False}
                            else:
                                draft=put(s,'assistant_drafts',{'conversation_id':c.id,'text':result['text'],'created_at':now().isoformat(),'status':'review','job_id':rid},'assistant_drafts:'+rid)
                                notify(s,'AI draft ready for review',c.customer,c.id)
                                output={'draft_id':draft['id'],'sent':False}
                    else:raise ValueError('Unknown job kind')
                    record=s.get(Record,rid);record.data={**data,'status':'done','output':output,'finished_at':now().isoformat(),'lease_until':''};s.commit();processed.append(rid)
                    update_broadcast(s,payload.get('broadcast_id'))
                except Exception as error:
                    s.rollback();record=s.get(Record,rid)
                    detail=error.detail if isinstance(error,HTTPException) else str(error)
                    # Keep provider payloads/keys out of persisted diagnostic text.
                    record.data={**data,'status':'failed' if data['attempts']>=3 else 'pending','next_run_at':(now()+timedelta(seconds=30*2**data['attempts'])).isoformat(),'lease_until':'','error':str(detail)[:300]};s.commit()
                    update_broadcast(s,data['payload'].get('broadcast_id'))
        return processed

    app.state.run_jobs=run_jobs
