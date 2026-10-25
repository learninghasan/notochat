"""Embeddable, capability-authenticated website chat. No admin token in the browser."""
import hashlib
import os
import secrets
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, Request, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session


class Start(BaseModel):
    name: str = Field(min_length=1,max_length=100)


class CustomerMessage(BaseModel):
    text: str = Field(min_length=1,max_length=4000)


WIDGET_HTML=r'''<!doctype html><html lang="bn"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NotoChat · Chat with us</title><style>*{box-sizing:border-box}body{margin:0;font:14px Arial;background:#f5f7fd;color:#293650;display:flex;flex-direction:column;height:100dvh}header{padding:20px;background:#315cde;color:white}header strong{font-size:19px}header p{font-size:12px;margin-bottom:0;color:#dbe6ff}main{padding:15px;flex:1;overflow:auto}form{padding:15px;display:flex;gap:8px;background:white}input{min-width:0;flex:1;padding:12px;border:1px solid #dce4f2;border-radius:8px}button{background:#315cde;color:white;border:0;padding:12px;border-radius:8px;cursor:pointer}button:disabled{opacity:.5}article{padding:12px 15px;border-radius:12px;background:white;line-height:1.8;margin-bottom:12px;white-space:pre-wrap;overflow-wrap:anywhere}.mine{background:#e4ebff;margin-left:28px}.note{font-size:11px;color:#8592aa;line-height:1.8;padding:0 15px}#error{font-size:12px;color:#b14343;padding:8px 15px}label{display:block;margin-bottom:12px}</style></head><body><header><strong>NotoChat</strong><p>Send a message to our team</p></header><main id="history"><p class="note">আপনার প্রশ্ন লিখুন। টিম এখানেই উত্তর দিতে পারবে।</p></main><div id="error" role="alert"></div><form id="start"><input aria-label="Your name" id="name" placeholder="আপনার নাম" maxlength="100" required><button>Start chat</button></form><form id="send" hidden style="display:none"><input aria-label="Your message" id="text" placeholder="আপনার মেসেজ…" maxlength="4000" required><button>Send</button></form><p class="note">No guaranteed response time. Avoid sharing passwords or payment card details.</p><script>
let token='';let sending=false;const $=id=>document.getElementById(id);
async function request(path,options={}){const r=await fetch(location.pathname.replace(/\/widget$/,'')+'/widget/'+path,{...options,headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})}});const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'Request failed');return d;}
async function refresh(){if(!token)return;try{const data=await request('messages');const fragment=document.createDocumentFragment();for(const m of data){const article=document.createElement('article');article.textContent=m.text;if(m.role==='customer')article.className='mine';fragment.append(article)}$('history').replaceChildren(fragment);}catch(e){$('error').textContent=e.message}}
$('start').addEventListener('submit',async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;try{const d=await request('sessions',{method:'POST',body:JSON.stringify({name:$('name').value})});token=d.token;$('start').style.display='none';$('send').style.display='flex';$('text').focus();await refresh();}catch(e){$('error').textContent=e.message}finally{b.disabled=false}});
$('send').addEventListener('submit',async e=>{e.preventDefault();if(sending)return;sending=true;const b=e.target.querySelector('button');b.disabled=true;try{await request('messages',{method:'POST',body:JSON.stringify({text:$('text').value})});$('text').value='';$('error').textContent='';await refresh()}catch(e){$('error').textContent=e.message}finally{sending=false;b.disabled=false}});setInterval(refresh,6000);
</script></body></html>'''


def install_widget(app,engine,Record,Conversation,Message,session,configuration=None):
    configuration=configuration or (lambda:dict(os.environ))
    def enabled():
        if configuration().get('WIDGET_ENABLED')!='1':raise HTTPException(503,'Website chat is not enabled')

    def valid_session(request,s):
        enabled()
        auth=request.headers.get('authorization','')
        if not auth.startswith('Bearer '):raise HTTPException(401,'Chat session required')
        hashed=hashlib.sha256(auth[7:].encode()).hexdigest()
        r=s.get(Record,'widget:'+hashed)
        if not r or datetime.fromisoformat(r.data['expires_at'])<=datetime.now(timezone.utc):raise HTTPException(401,'Session expired. Start a new chat.')
        return r

    @app.get('/widget',response_class=HTMLResponse)
    def widget():
        enabled()
        origins=configuration().get('WIDGET_FRAME_ANCESTORS',"'self'")
        return HTMLResponse(WIDGET_HTML,headers={'Content-Security-Policy':"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; frame-ancestors "+origins,'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer'})

    @app.post('/widget/sessions')
    def start(body:Start,request:Request,s:Session=Depends(session)):
        enabled()
        if not body.name.strip():raise HTTPException(422,'Name required')
        now=datetime.now(timezone.utc)
        # Shared DB row locks serialize session creation/rate checks across server instances.
        s.scalar(select(Record).where(Record.id=='agent:live').with_for_update())
        ip=request.client.host if request.client else 'unknown'
        bucket='widget-rate:'+hashlib.sha256((ip+now.strftime('%Y-%m-%d-%H')).encode()).hexdigest()
        rate=s.get(Record,bucket)
        count=rate.data['count'] if rate else 0
        if count>=20:raise HTTPException(429,'Too many new chats. Please try again later.')
        if rate:rate.data={'count':count+1}
        else:s.add(Record(id=bucket,kind='widget_rate',data={'count':1}))
        c=Conversation(customer=body.name.strip(),channel='Website',mode='ai' if (s.get(Record,'agent:live') and s.get(Record,'agent:live').data.get('auto_reply')) else 'human');s.add(c);s.flush()
        token=secrets.token_urlsafe(32)
        s.add(Record(id='widget:'+hashlib.sha256(token.encode()).hexdigest(),kind='widget',data={'conversation_id':c.id,'expires_at':(now+timedelta(hours=24)).isoformat(),'count':0}))
        s.add(Record(id=f'conversation:{c.id}',kind='conversation',data={'source':'website-widget','last_inbound':'','assignee':'','reason':'Website customer','handover_until':''}))
        s.commit();return {'token':token,'expires_in':86400}

    @app.get('/widget/messages')
    def widget_messages(request:Request,s:Session=Depends(session)):
        r=valid_session(request,s)
        rows=list(s.scalars(select(Message).where(Message.conversation_id==r.data['conversation_id']).order_by(Message.id.desc()).limit(100)))
        return [{'id':m.id,'role':m.role,'text':m.text} for m in reversed(rows)]

    @app.post('/widget/messages')
    def send(body:CustomerMessage,request:Request,s:Session=Depends(session)):
        r=valid_session(request,s)
        r=s.scalar(select(Record).where(Record.id==r.id).with_for_update())
        if r.data['count']>=100:raise HTTPException(429,'Message limit reached for this session. Contact the shop directly.')
        if not body.text.strip():raise HTTPException(422,'Message cannot be blank')
        now=datetime.now(timezone.utc)
        if r.data.get('last_sent') and (now-datetime.fromisoformat(r.data['last_sent'])).total_seconds()<2:raise HTTPException(429,'Please wait a moment before sending again')
        cid=r.data['conversation_id']
        message=Message(conversation_id=cid,role='customer',text=body.text.strip());s.add(message);s.flush()
        s.add(Record(id=f'verified_message:{message.id}',kind='verified_message',data={'conversation_id':cid,'message_id':message.id,'source':'website-widget','received_at':now.isoformat()}))
        app.state.queue_auto_draft(s,cid,message.id)
        r.data={**r.data,'count':r.data['count']+1,'last_sent':now.isoformat()}
        meta=s.get(Record,f'conversation:{cid}');meta.data={**meta.data,'last_inbound':now.isoformat(),'last_verified_inbound':now.isoformat()}
        s.commit();return {'saved':True}
