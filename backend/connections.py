"""Per-business secrets encrypted at rest; never returned to clients."""
import json
import os
from fastapi import Depends,HTTPException
from pydantic import BaseModel,Field,field_validator
from sqlalchemy.orm import Session


class ChannelConfiguration(BaseModel):
    app_secret: str = Field(default='',max_length=4000)
    verify_token: str = Field(default='',max_length=4000)
    graph_version: str = Field(default='',pattern=r'^$|^v\d+\.\d+$')
    page_id: str = Field(default='',max_length=100,pattern=r'^[A-Za-z0-9_-]*$')
    page_access_token: str = Field(default='',max_length=8000)
    instagram_account_id: str = Field(default='',max_length=100,pattern=r'^[A-Za-z0-9_-]*$')
    instagram_access_token: str = Field(default='',max_length=8000)
    whatsapp_phone_id: str = Field(default='',max_length=100,pattern=r'^[A-Za-z0-9_-]*$')
    whatsapp_access_token: str = Field(default='',max_length=8000)
    steadfast_api_key:str=Field(default='',max_length=8000)
    steadfast_secret_key:str=Field(default='',max_length=8000)
    pathao_client_id:str=Field(default='',max_length=1000)
    pathao_client_secret:str=Field(default='',max_length=8000)
    pathao_username:str=Field(default='',max_length=1000)
    pathao_password:str=Field(default='',max_length=8000)
    courier_webhook_token:str=Field(default='',max_length=4000)
    courier_live:bool=False
    pathao_sandbox:bool=True
    live_send: bool = False
    widget_enabled: bool = False
    widget_origins: list[str] = Field(default_factory=list,max_length=20)

    @field_validator('widget_origins')
    @classmethod
    def origins(cls,values):
        from urllib.parse import urlsplit
        for origin in values:
            p=urlsplit(origin)
            if p.scheme!='https' or not p.netloc or p.path or p.query or p.fragment or p.username or p.password or any(x in origin for x in [';',"'",'"',' ']):raise ValueError('Use exact HTTPS origins, without paths or wildcards')
        return values


MAPPING={'steadfast_api_key':'STEADFAST_API_KEY','steadfast_secret_key':'STEADFAST_SECRET_KEY','pathao_client_id':'PATHAO_CLIENT_ID','pathao_client_secret':'PATHAO_CLIENT_SECRET','pathao_username':'PATHAO_USERNAME','pathao_password':'PATHAO_PASSWORD','courier_webhook_token':'COURIER_WEBHOOK_TOKEN','app_secret':'META_APP_SECRET','verify_token':'META_VERIFY_TOKEN','graph_version':'META_GRAPH_VERSION','page_id':'META_PAGE_ID','page_access_token':'META_PAGE_ACCESS_TOKEN','instagram_account_id':'INSTAGRAM_ACCOUNT_ID','instagram_access_token':'INSTAGRAM_ACCESS_TOKEN','whatsapp_phone_id':'WHATSAPP_PHONE_NUMBER_ID','whatsapp_access_token':'WHATSAPP_ACCESS_TOKEN'}


def install_connections(app,engine,Record,authorize,session,tenant):
    def cipher():
        from cryptography.fernet import Fernet
        key=os.getenv('CREDENTIAL_ENCRYPTION_KEY','')
        if not key:raise HTTPException(503,'Set CREDENTIAL_ENCRYPTION_KEY before saving business credentials')
        try:return Fernet(key.encode())
        except ValueError:raise HTTPException(503,'Credential encryption key is invalid')

    def read():
        with Session(engine) as s:
            r=s.get(Record,'connections:private')
            if not r:
                if tenant:return {}
                d={k:os.getenv(k,'') for k in [*MAPPING.values(),'ENABLE_LIVE_SEND','WIDGET_ENABLED','COURIER_LIVE_ENABLED','PATHAO_SANDBOX']}
                d['WIDGET_FRAME_ANCESTORS']=os.getenv('WIDGET_FRAME_ANCESTORS',"'self'");return d
            try:return json.loads(cipher().decrypt(r.data['ciphertext'].encode()))
            except HTTPException:raise
            except Exception:raise HTTPException(503,'Stored connection credentials could not be decrypted')

    def manager(principal):
        if tenant and (not principal or principal.get('role') not in ('owner','admin')):raise HTTPException(403,'Owner or admin permission required')

    @app.get('/connections/configuration',dependencies=[Depends(authorize)])
    def status(principal=Depends(authorize)):
        manager(principal);d=read()
        return {**{key:bool(d.get(env)) for key,env in MAPPING.items()},'graph_version_value':d.get('META_GRAPH_VERSION',''),'page_id_value':d.get('META_PAGE_ID',''),'instagram_account_id_value':d.get('INSTAGRAM_ACCOUNT_ID',''),'whatsapp_phone_id_value':d.get('WHATSAPP_PHONE_NUMBER_ID',''),'courier_live':d.get('COURIER_LIVE_ENABLED')=='1','pathao_sandbox':d.get('PATHAO_SANDBOX')!='0','live_send':d.get('ENABLE_LIVE_SEND')=='1','widget_enabled':d.get('WIDGET_ENABLED')=='1','widget_origins':d.get('WIDGET_ORIGINS',[]),'encrypted_at_rest':bool(d) if tenant else False,'note':'Blank secret inputs preserve existing values. Secrets are never returned.'}

    @app.put('/connections/configuration',dependencies=[Depends(authorize)])
    def save(body:ChannelConfiguration,principal=Depends(authorize),s:Session=Depends(session)):
        manager(principal);fernet=cipher();d=read()
        for key,env in MAPPING.items():
            if getattr(body,key):d[env]=getattr(body,key)
        d['COURIER_LIVE_ENABLED']='1' if body.courier_live else '0'
        d['PATHAO_SANDBOX']='1' if body.pathao_sandbox else '0'
        d['ENABLE_LIVE_SEND']='1' if body.live_send else '0'
        d['WIDGET_ENABLED']='1' if body.widget_enabled else '0'
        d['WIDGET_ORIGINS']=body.widget_origins
        d['WIDGET_FRAME_ANCESTORS']=' '.join(body.widget_origins) if body.widget_origins else "'self'"
        r=s.get(Record,'connections:private');payload={'ciphertext':fernet.encrypt(json.dumps(d).encode()).decode()}
        if r:r.data=payload
        else:s.add(Record(id='connections:private',kind='private_credentials',data=payload))
        s.commit();return {'saved':True,'secrets_returned':False}

    @app.delete('/connections/configuration',dependencies=[Depends(authorize)])
    def remove(principal=Depends(authorize),s:Session=Depends(session)):
        manager(principal);r=s.get(Record,'connections:private')
        if r:s.delete(r);s.commit()
        return {'removed':True,'note':'Provider tokens are removed locally; revoke access at Meta separately if necessary.'}

    app.state.credential_cipher=cipher
    app.state.channel_configuration=read
    return read
