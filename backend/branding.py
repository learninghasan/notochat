"""Tenant-owned presentation; platform-owned host mappings and sender verification."""
import base64,binascii,io,re
from fastapi import Depends
from pydantic import BaseModel,Field,field_validator
from PIL import Image

DEFAULT={'name':'NotoChat','primary_color':'#176b5b','logo_data_url':'','widget_greeting':'Send a message to our team','receipt_footer':'Thank you for shopping with us.','requested_domain':''}

def contrast_white(color):
    rgb=[int(color[i:i+2],16)/255 for i in (1,3,5)]
    lum=sum(w*(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4) for v,w in zip(rgb,(.2126,.7152,.0722)))
    return 1.05/(lum+.05)

class Branding(BaseModel):
    name:str=Field(default='NotoChat',min_length=1,max_length=100)
    primary_color:str=Field(default='#176b5b',pattern=r'^#[0-9a-fA-F]{6}$')
    logo_data_url:str=Field(default='',max_length=280000)
    widget_greeting:str=Field(default=DEFAULT['widget_greeting'],min_length=1,max_length=300)
    receipt_footer:str=Field(default=DEFAULT['receipt_footer'],max_length=500)
    requested_domain:str=Field(default='',max_length=253)
    @field_validator('name','widget_greeting','receipt_footer')
    @classmethod
    def plain(cls,v):
        if any(ord(c)<32 for c in v) or not v.strip():raise ValueError('Use nonempty plain text without control characters')
        return v.strip()
    @field_validator('primary_color')
    @classmethod
    def color(cls,v):
        if contrast_white(v)<4.5:raise ValueError('Choose a darker color with at least 4.5:1 contrast against white')
        return v.lower()
    @field_validator('requested_domain')
    @classmethod
    def domain(cls,v):
        v=v.lower().strip()
        if v and not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}',v):raise ValueError('Use a domain name, not a URL, wildcard or IP')
        return v
    @field_validator('logo_data_url')
    @classmethod
    def logo(cls,v):
        if not v:return v
        match=re.fullmatch(r'data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)',v)
        if not match:raise ValueError('Upload a PNG, JPEG or WebP logo; remote URLs and SVG are not accepted')
        try:
            raw=base64.b64decode(match[2],validate=True)
            if len(raw)>200000:raise ValueError()
            with Image.open(io.BytesIO(raw)) as im:
                if im.width*im.height>1_000_000 or im.format!={'png':'PNG','jpeg':'JPEG','webp':'WEBP'}[match[1]] or getattr(im,'n_frames',1)!=1:raise ValueError()
                im.verify()
        except Exception:raise ValueError('Use a valid single-frame logo under 200 KB and 1 megapixel') from None
        return v

def install_branding(app,Record,authorize,session,put):
    def get(s):
        r=s.get(Record,'branding:settings')
        return {**DEFAULT,**(r.data if r else {})}
    app.state.branding=get
    @app.get('/branding',dependencies=[Depends(authorize)])
    def read(s=Depends(session)):
        return {**get(s),'domain_status':'pending_platform_verification' if get(s)['requested_domain'] else 'not_requested','sender_status':'platform_verified_sender_required'}
    @app.put('/branding',dependencies=[Depends(authorize)])
    def save(body:Branding,s=Depends(session)):
        put(s,'branding',body.model_dump(),'branding:settings');s.commit();return get(s)
