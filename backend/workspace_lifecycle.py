"""Recoverable quarantine. Irreversible purge is an offline, explicitly gated operation."""
import secrets
from datetime import datetime,timezone,timedelta
from fastapi import Depends,HTTPException
from pydantic import BaseModel
from sqlalchemy import select,delete,update
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

class Confirmation(BaseModel):
    token:str
    confirmation:str

def purge_quarantined(s,Record,Conversation,Message,Product,confirmation,execute=False):
    r=s.scalar(select(Record).where(Record.id=='workspace:lifecycle').with_for_update())
    if not r or r.data.get('status')!='quarantined':raise ValueError('Quarantine is required')
    if datetime.fromisoformat(r.data['purge_after'])>datetime.now(timezone.utc):raise ValueError('Recovery period has not elapsed')
    if confirmation!='PERMANENTLY PURGE QUARANTINED WORKSPACE':raise ValueError('Exact permanent-purge confirmation required')
    if not execute:return {'dry_run':True,'eligible':True,'scope':'Only this tenant database/schema; auth account and offsite backups are separate'}
    for model in (Message,Conversation,Product):s.execute(delete(model))
    s.execute(delete(Record).where(Record.id!='workspace:lifecycle'))
    r.data={'status':'purged','purged_at':datetime.now(timezone.utc).isoformat()};s.commit()
    return {'purged':True,'auth_account_deleted':False,'offsite_backups_deleted':False}

def install_lifecycle_controls(app,engine,Record,Conversation,Message,Product,authorize,session,put,tenant):
    def owner(principal):
        if tenant and (not principal or principal.get('role')!='owner'):raise HTTPException(403,'Business owner required')
    def status(s):
        r=s.get(Record,'workspace:lifecycle');return r.data.get('status','active') if r else 'active'
    def active():
        with Session(engine) as s:return status(s) not in ('quarantined','purged')
    app.state.workspace_active=active
    @app.middleware('http')
    async def gate(request,call_next):
        if not request.url.path.startswith('/workspace/deletion') and request.url.path not in ('/health','/workspace/export','/push/revoke-member','/push/restore-member','/push/revoke-organization') and not active():return JSONResponse({'detail':'Workspace is quarantined or purged. Owner may inspect deletion status or restore during quarantine.'},status_code=423)
        return await call_next(request)
    @app.get('/workspace/deletion',dependencies=[Depends(authorize)])
    def read(principal=Depends(authorize),s=Depends(session)):
        owner(principal);r=s.get(Record,'workspace:lifecycle');return {k:v for k,v in (r.data if r else {'status':'active'}).items() if k!='token'}
    @app.post('/workspace/deletion/request',dependencies=[Depends(authorize)])
    def request(principal=Depends(authorize),s=Depends(session)):
        owner(principal);s.scalar(select(Record).where(Record.id=='agent:live').with_for_update())
        r=s.get(Record,'workspace:lifecycle')
        if r and r.data.get('status') in ('quarantined','purged'):raise HTTPException(409,'Workspace is already quarantined or purged')
        if r and r.data.get('status')=='requested' and datetime.fromisoformat(r.data['expires_at'])>datetime.now(timezone.utc):return r.data
        d=put(s,'workspace_lifecycle',{'status':'requested','token':secrets.token_urlsafe(24),'expires_at':(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat()},'workspace:lifecycle');s.commit();return d
    @app.post('/workspace/deletion/confirm',dependencies=[Depends(authorize)])
    def confirm(body:Confirmation,principal=Depends(authorize),s=Depends(session)):
        owner(principal);r=s.scalar(select(Record).where(Record.id=='workspace:lifecycle').with_for_update())
        if not r or body.confirmation!='QUARANTINE THIS WORKSPACE' or not secrets.compare_digest(body.token,r.data.get('token','')):raise HTTPException(409,'Exact confirmation and current token required')
        if r.data['status']=='quarantined':return {'status':'quarantined','purge_after':r.data['purge_after']}
        if r.data['status']!='requested' or datetime.fromisoformat(r.data['expires_at'])<=datetime.now(timezone.utc):raise HTTPException(409,'Deletion request expired')
        r.data={**r.data,'status':'quarantined','quarantined_at':datetime.now(timezone.utc).isoformat(),'purge_after':(datetime.now(timezone.utc)+timedelta(days=7)).isoformat()}
        s.execute(update(Conversation).values(mode='human'));s.commit()
        return {'status':'quarantined','purge_after':r.data['purge_after'],'permanently_deleted':False}
    @app.post('/workspace/deletion/restore',dependencies=[Depends(authorize)])
    def restore(body:Confirmation,principal=Depends(authorize),s=Depends(session)):
        owner(principal);r=s.scalar(select(Record).where(Record.id=='workspace:lifecycle').with_for_update())
        if not r or r.data['status']=='purged':raise HTTPException(409,'Workspace cannot be restored here')
        if body.confirmation!='RESTORE THIS WORKSPACE':raise HTTPException(409,'Exact restore confirmation required')
        r.data={'status':'active','restored_at':datetime.now(timezone.utc).isoformat()};s.commit()
        return {'status':'active','conversation_mode':'human; return chats to AI explicitly'}
