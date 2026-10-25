"""Explicit public/private Facebook comment replies, tied to signed comment evidence."""
from datetime import datetime,timezone,timedelta
import re
from fastapi import Depends,HTTPException
from pydantic import BaseModel
from typing import Literal
from sqlalchemy.exc import IntegrityError

class CommentReply(BaseModel):
    message_id:int
    comment_message_id:int
    kind:Literal['public','private']

def install_comment_replies(app,Record,Conversation,Message,authorize,session,configuration):
    @app.post('/conversations/{cid}/comment-replies',dependencies=[Depends(authorize)])
    async def reply(cid:int,body:CommentReply,s=Depends(session)):
        c=s.get(Conversation,cid);m=s.get(Message,body.message_id);proof=s.get(Record,f'verified_message:{body.comment_message_id}')
        if not c or c.channel!='Facebook comments' or not m or m.conversation_id!=cid or m.role!='team' or not proof or proof.data.get('conversation_id')!=cid or proof.data.get('channel')!='Facebook comments':raise HTTPException(404,'Verified comment and team reply required')
        if c.mode!='human':raise HTTPException(409,'Take over before replying to a comment')
        if configuration().get('ENABLE_LIVE_SEND')!='1':raise HTTPException(503,'Live delivery is disabled')
        d=proof.data;cfg=app.state.channel_account('Facebook comments',d.get('account',''))
        if not cfg:raise HTTPException(409,'Page is disconnected or paused')
        version=cfg.get('META_GRAPH_VERSION','');token=cfg.get('META_PAGE_ACCESS_TOKEN')
        if not token or not re.fullmatch(r'v\d+\.\d+',version):raise HTTPException(503,'Page transport configuration missing')
        comment=d.get('provider_id','')
        if not re.fullmatch(r'[0-9_]{1,150}',comment):raise HTTPException(409,'Comment identifier is unavailable')
        try:age=datetime.now(timezone.utc)-datetime.fromisoformat(d['received_at'])
        except (ValueError,KeyError):raise HTTPException(409,'Comment timestamp unavailable')
        if not timedelta(0)<=age<timedelta(days=7):raise HTTPException(409,'Comment is outside the conservative seven-day reply limit')
        # One private reply per verified comment; public message retries share their own key.
        rid=f"comment-reply:{body.comment_message_id}:private" if body.kind=='private' else f'comment-reply:{m.id}:public'
        old=s.get(Record,rid)
        if old:
            if old.data['message_id']!=m.id or old.data['comment_message_id']!=body.comment_message_id:raise HTTPException(409,'A private reply was already attempted for this comment')
            if old.data['status']=='sent':return old.data
            raise HTTPException(409,'Delivery was attempted; verify the original channel before any further action')
        claim={'id':rid,'conversation_id':cid,'message_id':m.id,'comment_message_id':body.comment_message_id,'kind':body.kind,'status':'attempting'}
        s.add(Record(id=rid,kind='comment_replies',data=claim))
        try:s.commit()
        except IntegrityError:s.rollback();raise HTTPException(409,'Another reply attempt is in progress')
        if body.kind=='public':path=comment+'/comments';payload={'message':m.text}
        else:path=d['account']+'/messages';payload={'recipient':{'comment_id':comment},'message':{'text':m.text}}
        import httpx
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                r=await client.post('https://graph.facebook.com/'+version+'/'+path,headers={'Authorization':'Bearer '+token},json=payload)
                r.raise_for_status();result=r.json()
            provider_id=result.get('id') or result.get('message_id')
            if not provider_id:raise ValueError('Missing provider receipt')
        except (httpx.HTTPError,ValueError):
            record=s.get(Record,rid);record.data={**claim,'status':'unconfirmed'};s.commit()
            raise HTTPException(502,'Comment reply outcome is unconfirmed; inspect the original channel, do not resend blindly')
        record=s.get(Record,rid);record.data={**claim,'status':'sent','provider_id':provider_id,'sent_at':datetime.now(timezone.utc).isoformat()};app.state.record_reply(s,cid,m.id);s.commit();return record.data
