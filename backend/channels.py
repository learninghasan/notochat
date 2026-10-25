"""Official Meta webhook ingestion and an explicitly enabled text transport."""
import copy
import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone, timedelta

from fastapi import Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class DeliveryInput(BaseModel):
    message_id: int


def install_channels(app,engine,Record,Conversation,Message,authorize,session,configuration=None):
    configuration=configuration or (lambda:dict(os.environ))
    def put(s,kind,rid,data):
        r=s.get(Record,rid)
        if r:r.data={**data,"id":rid}
        else:s.add(Record(id=rid,kind=kind,data={**data,"id":rid}))

    @app.get('/webhooks/meta')
    def verify(request:Request):
        expected=configuration().get('META_VERIFY_TOKEN')
        if not expected:raise HTTPException(503,'Meta verification is not configured')
        token=request.query_params.get('hub.verify_token','')
        if request.query_params.get('hub.mode')!='subscribe' or not hmac.compare_digest(token,expected):raise HTTPException(403,'Verification failed')
        return PlainTextResponse(request.query_params.get('hub.challenge',''))

    @app.post('/webhooks/meta')
    async def receive(request:Request,s:Session=Depends(session)):
        secret=configuration().get('META_APP_SECRET')
        if not secret:raise HTTPException(503,'Meta app secret is not configured')
        if int(request.headers.get('content-length','0'))>2_000_000:raise HTTPException(413,'Webhook too large')
        raw=await request.body()
        if len(raw)>2_000_000:raise HTTPException(413,'Webhook too large')
        expected='sha256='+hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
        if not hmac.compare_digest(request.headers.get('x-hub-signature-256',''),expected):raise HTTPException(403,'Invalid webhook signature')
        try:payload=json.loads(raw)
        except ValueError:raise HTTPException(400,'Invalid JSON')
        if not isinstance(payload,dict):raise HTTPException(400,'Object payload is required')
        events=[]
        for entry in payload.get('entry',[])[:100]:
            for event in entry.get('messaging',[])[:100]:
                page=str(event.get('recipient',{}).get('id',''))
                channel='Instagram' if payload.get('object')=='instagram' else 'Messenger'
                if not app.state.channel_account(channel,page):continue
                message=event.get('message',{})
                if message.get('is_echo') or not message.get('mid'):continue
                events.append({'channel':'Instagram' if payload.get('object')=='instagram' else 'Messenger','sender':str(event.get('sender',{}).get('id','')),'account':page,'message_id':message['mid'],'text':message.get('text') or '[Attachment received; open in the original channel]','timestamp':event.get('timestamp',0)/1000,'attachments':message.get('attachments',[])[:3]})
            for change in entry.get('changes',[])[:100]:
                value=change.get('value',{})
                if change.get('field')=='messages':
                    phone=str(value.get('metadata',{}).get('phone_number_id',''))
                    if not app.state.channel_account('WhatsApp',phone):continue
                    for m in value.get('messages',[])[:100]:
                        events.append({'channel':'WhatsApp','sender':str(m.get('from','')),'account':phone,'message_id':m.get('id',''),'text':m.get('text',{}).get('body') or '[Media received; open in WhatsApp]','timestamp':float(m.get('timestamp',0)),'attachments':[{**m.get(m.get('type'),{}),'type':m.get('type')}] if m.get('type') in ('image','audio','video','document') else []})
                if change.get('field')=='feed' and value.get('item')=='comment' and value.get('verb')=='add':
                    page=str(entry.get('id',''))
                    if app.state.channel_account('Facebook comments',page) and str(value.get('from',{}).get('id',''))!=page:
                        events.append({'channel':'Facebook comments','sender':str(value.get('from',{}).get('id','')),'account':page,'message_id':value.get('comment_id',''),'text':value.get('message','[Comment]'),'timestamp':value.get('created_time',0)})
        count=0
        for e in events:
            if not e['sender'] or not e['message_id']:continue
            dedup='inbound:'+hashlib.sha256(json.dumps([e['channel'],e['account'],e['message_id']],separators=(',',':')).encode()).hexdigest()
            legacy=s.get(Record,'inbound:'+hashlib.sha256((e['channel']+e['message_id']).encode()).hexdigest())
            if legacy:
                oldmeta=s.get(Record,f"conversation:{legacy.data['conversation_id']}")
                if oldmeta and oldmeta.data.get('account')==e['account']:continue
            if s.get(Record,dedup):continue
            mapping='channel:'+hashlib.sha256(json.dumps([e['channel'],e['account'],e['sender']],separators=(',',':')).encode()).hexdigest()
            r=s.get(Record,mapping)
            if not r:
                previous=s.get(Record,'channel:'+hashlib.sha256((e['channel']+e['account']+e['sender']).encode()).hexdigest())
                if previous and all(previous.data.get(k)==e[k] for k in ('channel','account','sender')):r=previous
            if r:c=s.get(Conversation,r.data['conversation_id'])
            else:
                c=Conversation(customer=e['channel']+' customer '+e['sender'][-6:],channel=e['channel'],mode='ai' if (s.get(Record,'agent:live') and s.get(Record,'agent:live').data.get('auto_reply')) else 'human');s.add(c);s.flush()
                put(s,'channel',mapping,{'conversation_id':c.id,'sender':e['sender'],'account':e['account'],'channel':e['channel']})
            try:t=datetime.fromtimestamp(float(e['timestamp']),timezone.utc)
            except (ValueError,OverflowError,OSError):t=datetime.now(timezone.utc)-timedelta(days=2)
            # Never let an upstream future timestamp open an unbounded reply window.
            if t>datetime.now(timezone.utc)+timedelta(minutes=1):t=datetime.now(timezone.utc)-timedelta(days=2)
            meta=s.get(Record,f'conversation:{c.id}')
            d=copy.deepcopy(meta.data) if meta else {}
            old=d.get('last_verified_inbound','')
            if not old or t.isoformat()>old:
                d.update(last_inbound=t.isoformat(),last_verified_inbound=t.isoformat(),source='signed-meta-webhook',sender=e['sender'],account=e['account'],channel=e['channel'],account_name=(app.state.channel_account(e['channel'],e['account']) or {}).get('account_name',e['account']))
                put(s,'conversation',f'conversation:{c.id}',d)
            message=Message(conversation_id=c.id,role='customer',text=str(e['text'])[:8000]);s.add(message);s.flush()
            put(s,'verified_message',f'verified_message:{message.id}',{'conversation_id':c.id,'message_id':message.id,'source':'signed-meta-webhook','channel':e['channel'],'account':e['account'],'provider_id':e['message_id'],'received_at':t.isoformat()})
            app.state.ingest_attachments(s,c.id,message.id,e)
            app.state.queue_auto_draft(s,c.id,message.id)
            put(s,'inbound',dedup,{'conversation_id':c.id,'provider_id':e['message_id'],'created_at':datetime.now(timezone.utc).isoformat()})
            try:s.commit();count+=1
            except IntegrityError:s.rollback()  # Concurrent webhook retry; unique provider event wins once.
        return {'received':True,'stored':count,'auto_replied':False}

    async def send_message(cid,body,s,automated=False):
        if configuration().get('ENABLE_LIVE_SEND')!='1':raise HTTPException(503,'Live delivery is disabled. Configure and verify the official channel, then explicitly enable it.')
        c=s.get(Conversation,cid)
        if not c:raise HTTPException(404,'Conversation not found')
        if automated and c.mode!='ai':raise HTTPException(409,'Human takeover stopped automatic delivery')
        if c.mode!='human' and not automated:raise HTTPException(409,'Take over before delivering a team reply')
        message=s.get(Message,body.message_id)
        if not message or message.conversation_id!=cid or message.role!='team':raise HTTPException(404,'Team message not found')
        record=s.get(Record,f'conversation:{cid}')
        if not record or not record.data.get('last_verified_inbound'):raise HTTPException(409,'A verified inbound channel message is required; local test messages do not qualify')
        d=record.data
        age=datetime.now(timezone.utc)-datetime.fromisoformat(d['last_verified_inbound'])
        if not timedelta(0)<=age<timedelta(hours=23):raise HTTPException(409,'Outside the conservative reply window. Template messaging is not implemented.')
        account_configuration=app.state.channel_account(c.channel,d.get('account',''))
        if not account_configuration:raise HTTPException(409,'This conversation’s channel account is disconnected or disabled')
        version=account_configuration.get('META_GRAPH_VERSION','')
        if not re.fullmatch(r'v\d+\.\d+',version):raise HTTPException(503,'Set a supported META_GRAPH_VERSION, for example the version configured on your Meta app')
        if c.channel not in ['Messenger','Instagram','WhatsApp']:raise HTTPException(409,'This channel does not support this text transport')
        token=account_configuration.get('WHATSAPP_ACCESS_TOKEN') if c.channel=='WhatsApp' else (account_configuration.get('INSTAGRAM_ACCESS_TOKEN') or account_configuration.get('META_PAGE_ACCESS_TOKEN')) if c.channel=='Instagram' else account_configuration.get('META_PAGE_ACCESS_TOKEN')
        if not token:raise HTTPException(503,'Channel access token is missing')
        if c.channel=='WhatsApp':payload={'messaging_product':'whatsapp','recipient_type':'individual','to':d['sender'],'type':'text','text':{'body':message.text}}
        else:payload={'recipient':{'id':d['sender']},'messaging_type':'RESPONSE','message':{'text':message.text}}
        rid=f'delivery:{message.id}'
        existing=s.get(Record,rid)
        if existing:
            if existing.data.get('status')=='sent':return existing.data
            raise HTTPException(409,'This delivery was already attempted. Check the original channel before retrying to avoid a duplicate.')
        put(s,'delivery',rid,{'status':'attempting','message_id':message.id,'conversation_id':cid});
        try:s.commit()
        except IntegrityError:s.rollback();raise HTTPException(409,'Delivery already in progress')
        import httpx
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                r=await client.post(f"https://graph.facebook.com/{version}/{d['account']}/messages",headers={'Authorization':'Bearer '+token},json=payload)
                r.raise_for_status();result=r.json()
            provider_id=result.get('message_id') or next(iter(result.get('messages',[])),{}).get('id')
            if not provider_id:raise ValueError('No provider message ID')
        except (httpx.HTTPError,ValueError):
            put(s,'delivery',rid,{'status':'unconfirmed','message_id':message.id,'conversation_id':cid});s.commit()
            raise HTTPException(502,'Delivery could not be confirmed. Check the original channel before retrying.')
        put(s,'delivery',rid,{'status':'sent','message_id':message.id,'conversation_id':cid,'provider_id':provider_id});app.state.record_reply(s,cid,message.id,automated);s.commit()
        return s.get(Record,rid).data

    @app.post('/conversations/{cid}/deliver',dependencies=[Depends(authorize)])
    async def deliver(cid:int,body:DeliveryInput,s:Session=Depends(session)):
        return await send_message(cid,body,s)

    async def automated(cid,mid,s):
        return await send_message(cid,DeliveryInput(message_id=mid),s,automated=True)
    app.state.deliver_automated=automated
    from comment_replies import install_comment_replies
    install_comment_replies(app,Record,Conversation,Message,authorize,session,configuration)
