"""Signed-channel media ingestion and bounded, review-only analysis."""
import base64,hashlib,json,re,time
from urllib.parse import urlsplit
from fastapi import Depends,HTTPException
from pydantic import BaseModel
from sqlalchemy import select,update,delete

LIMIT=8_000_000
MIMES={'image/jpeg':'image','image/png':'image','image/webp':'image','audio/mpeg':'audio','audio/wav':'audio','audio/webm':'audio','audio/mp4':'audio','audio/ogg':'audio'}

def media_url(value,whatsapp=False):
    try:
        p=urlsplit(value);host=p.hostname or ''
        allowed=host=='lookaside.fbsbx.com' if whatsapp else host=='lookaside.fbsbx.com' or any(host.endswith('.'+suffix) for suffix in ('fbcdn.net','cdninstagram.com','fbsbx.com'))
        return bool(allowed and p.scheme=='https' and p.port in (None,443) and not p.username and not p.password and not p.fragment and len(value)<=8000)
    except (ValueError,TypeError):return False

def signature_matches(raw,mime):
    if mime=='image/jpeg':return raw.startswith(b'\xff\xd8\xff')
    if mime=='image/png':return raw.startswith(b'\x89PNG\r\n\x1a\n')
    if mime in ('image/webp','audio/wav'):return raw.startswith(b'RIFF') and raw[8:12]==(b'WEBP' if mime=='image/webp' else b'WAVE')
    if mime=='audio/ogg':return raw.startswith(b'OggS')
    if mime=='audio/webm':return raw.startswith(b'\x1a\x45\xdf\xa3')
    if mime=='audio/mp4':return raw[4:8]==b'ftyp'
    if mime=='audio/mpeg':return raw.startswith(b'ID3') or len(raw)>1 and raw[0]==255 and raw[1]&224==224
    return False

class Analyze(BaseModel):
    retry:bool=False

def install_attachments(app,Record,Conversation,Message,authorize,session,put,notify,media,MediaInput):
    def ingest(s,cid,mid,event):
        s.execute(delete(Record).where(Record.kind=='private_attachment',Record.data['expires_at'].as_float()<time.time()))
        for index,item in enumerate(event.get('attachments',[])[:3]):
            rid=f'attachment:{mid}:{index}'
            if s.get(Record,rid):continue
            kind=item.get('type','unknown');source={'url':item.get('payload',{}).get('url','')} if event['channel']!='WhatsApp' else item
            supported=kind in ('image','audio') and (bool(re.fullmatch(r'\d{1,100}',str(source.get('id','')))) if event['channel']=='WhatsApp' else media_url(source['url']))
            d={'conversation_id':cid,'message_id':mid,'channel':event['channel'],'account':event['account'],'kind':kind if kind in ('image','audio') else 'unsupported','status':'ready' if supported else 'unsupported','received_at':time.time(),'attempts':0}
            if supported:
                try:encrypted=app.state.credential_cipher().encrypt(json.dumps(source).encode()).decode()
                except HTTPException:d['status']='unavailable';d['error']='Credential encryption must be configured before receiving media'
                else:put(s,'private_attachment',{'conversation_id':cid,'ciphertext':encrypted,'expires_at':time.time()+86400},'source:'+rid)
            put(s,'attachments',d,rid)
        if event.get('attachments'):notify(s,'Customer attachment needs review','Open the conversation to review received media.',cid)

    @app.post('/conversations/{cid}/attachments/{rid}/analyze',dependencies=[Depends(authorize)])
    def queue(cid:int,rid:str,body:Analyze, s=Depends(session)):
        if not s.get(Conversation,cid):raise HTTPException(404,'Conversation not found')
        r=s.scalar(select(Record).where(Record.id==rid,Record.kind=='attachments').with_for_update())
        if not r or r.data['conversation_id']!=cid:raise HTTPException(404,'Attachment not found')
        d=r.data
        if d['status']=='complete':return {'status':'complete','draft_id':d['draft_id']}
        if d['status'] in ('unsupported','unavailable'):raise HTTPException(409,'This attachment cannot be analyzed; use the original channel')
        if d['status']=='processing' and time.time()-d.get('started_at',0)<300:raise HTTPException(409,'Analysis is in progress')
        if d['status'] in ('failed','processing') and not body.retry:raise HTTPException(409,'Previous attempt failed or was interrupted. Explicit retry is required and may incur AI usage again.')
        if time.time()-d['received_at']>86400:raise HTTPException(409,'Media reference expired; ask the customer to send it again')
        r.data={**d,'status':'ready','error':''}
        job=app.state.enqueue(s,'media_analyze',{'conversation_id':cid,'attachment_id':rid,'automatic':False},key=f"media-manual-{rid}-{d['attempts']}");s.commit();return job

    async def download(d,source):
        import httpx
        cfg=app.state.channel_account(d['channel'],d['account'])
        if not cfg:raise HTTPException(409,'Channel account is disconnected or disabled')
        whatsapp=d['channel']=='WhatsApp';headers={};expected_mime=source.get('mime_type');expected_hash=source.get('sha256')
        async with httpx.AsyncClient(timeout=20,follow_redirects=False) as client:
            if whatsapp:
                version=cfg.get('META_GRAPH_VERSION','')
                if not re.fullmatch(r'v\d+\.\d+',version):raise HTTPException(503,'Graph version is not configured')
                token=cfg.get('WHATSAPP_ACCESS_TOKEN')
                if not token:raise HTTPException(503,'WhatsApp credentials are missing')
                headers={'Authorization':'Bearer '+token}
                response=await client.get('https://graph.facebook.com/'+version+'/'+source['id'],headers=headers)
                if response.status_code!=200:raise HTTPException(502,'Media lookup failed')
                metadata=response.json();url=metadata.get('url','')
                if metadata.get('file_size',0)>LIMIT:raise HTTPException(422,'Media exceeds 8 MB')
                expected_mime=expected_mime or metadata.get('mime_type');expected_hash=expected_hash or metadata.get('sha256')
            else:url=source['url']
            if not media_url(url,whatsapp):raise HTTPException(422,'Untrusted media location')
            async with client.stream('GET',url,headers=headers) as response:
                if response.status_code!=200:raise HTTPException(502,'Media download failed or redirected')
                mime=response.headers.get('content-type','').split(';')[0].strip().lower()
                if mime not in MIMES or MIMES[mime]!=d['kind'] or (expected_mime and expected_mime.split(';')[0]!=mime):raise HTTPException(422,'Unsupported or mismatched media type')
                if int(response.headers.get('content-length','0'))>LIMIT:raise HTTPException(422,'Media exceeds 8 MB')
                raw=bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw)>LIMIT:raise HTTPException(422,'Media exceeds 8 MB')
            if not raw or not signature_matches(raw,mime):raise HTTPException(422,'Media bytes do not match the declared format')
            if expected_hash and base64.b64encode(hashlib.sha256(raw).digest()).decode()!=expected_hash:raise HTTPException(422,'Media integrity check failed')
            return bytes(raw),mime

    async def analyze(s,cid,rid,automatic=False):
        r=s.get(Record,rid);c=s.get(Conversation,cid)
        if not r or r.kind!='attachments' or r.data['conversation_id']!=cid or not c:raise HTTPException(404,'Attachment not found')
        d=dict(r.data)
        if d['status']=='complete':return {'sent':False,'draft_id':d['draft_id']}
        if automatic and (c.mode!='ai' or not s.get(Record,'agent:live').data.get('auto_media_analysis')):return {'sent':False,'skipped':'Automatic media analysis disabled or human takeover'}
        if d['status']!='ready':return {'sent':False,'blocked':'Explicit retry or original-channel review required'}
        attempt=d['attempts']+1
        claimed=s.execute(update(Record).where(Record.id==rid,Record.data['status'].as_string()=='ready',Record.data['attempts'].as_integer()==d['attempts']).values(data={**d,'status':'processing','attempts':attempt,'started_at':time.time()}));s.commit()
        if claimed.rowcount!=1:return {'sent':False,'skipped':'Another worker claimed this analysis'}
        try:
            if time.time()-d['received_at']>86400:raise HTTPException(409,'Media reference expired')
            proof=s.get(Record,f"verified_message:{d['message_id']}")
            if not proof:raise HTTPException(409,'Verified inbound event required')
            source=s.get(Record,'source:'+rid)
            if not source:raise HTTPException(409,'Media source is unavailable')
            decoded=json.loads(app.state.credential_cipher().decrypt(source.data['ciphertext'].encode()))
            app.state.require_credit(s,d['kind'])
            raw,mime=await download(d,decoded)
            result=await media(cid,MediaInput(kind=d['kind'],mime_type=mime,content_base64=base64.b64encode(raw).decode()),s)
            r=s.get(Record,rid);s.refresh(r)
            if r.data['attempts']!=attempt:return {'sent':False,'skipped':'A newer analysis attempt superseded this result'}
            draft=put(s,'assistant_drafts',{'conversation_id':cid,'text':result['text'][:8000],'status':'review','attachment_id':rid,'message_id':d['message_id']},'assistant_drafts:'+rid)
            r.data={**r.data,'status':'complete','draft_id':draft['id'],'error':''}
            # Drop signed media locations after successful analysis; retain review text only.
            source=s.get(Record,'source:'+rid)
            if source:s.delete(source)
            notify(s,'Attachment analysis ready','Review the analysis before replying.',cid);s.commit()
            return {'sent':False,'draft_id':draft['id']}
        except Exception:
            s.rollback();r=s.get(Record,rid)
            if r and r.data['attempts']==attempt:r.data={**r.data,'status':'failed','error':'Analysis could not be completed. Check media expiry, format, provider and billing settings before retrying.'};s.commit()
            return {'sent':False,'failed':True}

    app.state.ingest_attachments=ingest
    app.state.analyze_attachment=analyze
