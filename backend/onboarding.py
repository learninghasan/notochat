"""Resumable setup evidence; configuration is not a live-provider verification."""
import os
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from fastapi import Depends
from pydantic import BaseModel,Field,field_validator
from typing import Literal
from sqlalchemy import select

class Profile(BaseModel):
    name:str=Field(min_length=1,max_length=160)
    timezone:str=Field(default='Asia/Dhaka',max_length=100)
    description:str=Field(default='',max_length=2000)
    @field_validator('timezone')
    @classmethod
    def zone(cls,v):
        try:ZoneInfo(v)
        except ZoneInfoNotFoundError:raise ValueError('Choose a valid timezone')
        return v
class Progress(BaseModel):
    step:Literal['business','channels','catalog','rules','test','launch']

def install_onboarding(app,Record,Product,authorize,session,put):
    @app.get('/onboarding',dependencies=[Depends(authorize)])
    def read(principal=Depends(authorize),s=Depends(session)):
        profile=s.get(Record,'onboarding:profile');progress=s.get(Record,'onboarding:progress');test=s.get(Record,'onboarding:test');cfg=app.state.channel_configuration()
        return {'profile':profile.data if profile else None,'resume_step':progress.data['step'] if progress else 'business','checks':{'account':bool(principal),'business':bool(profile),'channel_configured':bool(cfg.get('META_PAGE_ID') or cfg.get('META_PAGES') or cfg.get('WHATSAPP_PHONE_NUMBER_ID') or cfg.get('WIDGET_ENABLED')=='1'),'catalog':bool(s.scalar(select(Product).limit(1))),'rules_published':s.get(Record,'agent:live').data.get('version',1)>1,'test_preview':bool(test),'live_send_enabled':cfg.get('ENABLE_LIVE_SEND')=='1'},'test':test.data if test else None,'live_verified':False,'note':'Configured and preview-tested are separate from live verification. This checklist does not enable sending or create credentials.'}
    @app.put('/onboarding/profile',dependencies=[Depends(authorize)])
    def profile(body:Profile,s=Depends(session)):
        d=put(s,'business_profile',body.model_dump(),'onboarding:profile');s.commit();return d
    @app.put('/onboarding/progress',dependencies=[Depends(authorize)])
    def progress(body:Progress,s=Depends(session)):
        d=put(s,'onboarding_progress',body.model_dump(),'onboarding:progress');s.commit();return d
