"""Account-bound Meta onboarding; candidate page tokens never leave the server."""
import hashlib,json,os,re,secrets,time
from urllib.parse import urlencode,urlsplit
from fastapi import Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import delete,update

class Complete(BaseModel):
    state:str=Field(min_length=32,max_length=200)
    code:str=Field(min_length=1,max_length=4000)
class Selection(BaseModel):
    page_id:str=Field(pattern=r'^\d{1,100}$')

def install_meta_oauth(app,Record,authorize,session):
    def owner(p):
        if not p or p.get('role') not in ('owner','admin'):raise HTTPException(403,'Sign in as business owner or admin')
    def config():
        values={k:os.getenv(k,'') for k in ('META_OAUTH_APP_ID','META_OAUTH_APP_SECRET','META_OAUTH_GRAPH_VERSION','META_OAUTH_VERIFY_TOKEN','PUBLIC_FRONTEND_URL')}
        u=urlsplit(values['PUBLIC_FRONTEND_URL'])
        if not all(values.values()) or not re.fullmatch(r'v\d+\.\d+',values['META_OAUTH_GRAPH_VERSION']) or u.scheme!='https' or not u.netloc or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):
            raise HTTPException(503,'Configure Meta OAuth app ID, secret, Graph version, webhook verify token and HTTPS PUBLIC_FRONTEND_URL')
        values['redirect']=values['PUBLIC_FRONTEND_URL'].rstrip('/')+'/api/oauth/meta/callback';return values
    def cipher():return app.state.credential_cipher()
    def save(s,rid,kind,data):
        r=s.get(Record,rid)
        if r:r.data=data
        else:s.add(Record(id=rid,kind=kind,data=data))
    def pending(s,user):
        r=s.get(Record,'oauth-pages:'+user)
        if not r or r.data['expires_at']<time.time():raise HTTPException(409,'Connect Meta again; page selection expired')
        try:return json.loads(cipher().decrypt(r.data['ciphertext'].encode()))
        except Exception:raise HTTPException(503,'Could not decrypt pending page selection')

    @app.post('/oauth/meta/start')
    def start(p=Depends(authorize),s=Depends(session)):
        owner(p);cfg=config();cipher()
        # Expired one-time states and encrypted page candidates have no further use.
        # Keep cleanup tenant-local and preserve any authorization still in progress.
        s.execute(delete(Record).where(Record.kind=='private_oauth',Record.data['expires_at'].as_float()<time.time()))
        state=secrets.token_urlsafe(40)
        save(s,'oauth-state:'+hashlib.sha256(state.encode()).hexdigest(),'private_oauth',{'user_id':p['user_id'],'organization_id':p['organization_id'],'expires_at':time.time()+600,'status':'pending'});s.commit()
        params={'client_id':cfg['META_OAUTH_APP_ID'],'redirect_uri':cfg['redirect'],'state':state,'response_type':'code','scope':'pages_show_list,pages_messaging,pages_manage_metadata,pages_read_engagement,instagram_basic,instagram_manage_messages'}
        return {'url':'https://www.facebook.com/'+cfg['META_OAUTH_GRAPH_VERSION']+'/dialog/oauth?'+urlencode(params)}

    @app.post('/oauth/meta/complete')
    async def complete(body:Complete,p=Depends(authorize),s=Depends(session)):
        owner(p);cfg=config();rid='oauth-state:'+hashlib.sha256(body.state.encode()).hexdigest()
        r=s.get(Record,rid)
        if not r or r.data.get('status')!='pending' or r.data['expires_at']<time.time() or r.data['user_id']!=p['user_id'] or r.data['organization_id']!=p['organization_id']:raise HTTPException(400,'OAuth state is invalid, expired or belongs to a different account')
        claimed=s.execute(update(Record).where(Record.id==rid,Record.data['status'].as_string()=='pending').values(data={**r.data,'status':'consumed'}));s.commit()
        if claimed.rowcount!=1:raise HTTPException(400,'OAuth state was already used')
        import httpx
        root='https://graph.facebook.com/'+cfg['META_OAUTH_GRAPH_VERSION']
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                response=await client.get(root+'/oauth/access_token',params={'client_id':cfg['META_OAUTH_APP_ID'],'client_secret':cfg['META_OAUTH_APP_SECRET'],'redirect_uri':cfg['redirect'],'code':body.code});response.raise_for_status();token=response.json()['access_token']
                response=await client.get(root+'/oauth/access_token',params={'grant_type':'fb_exchange_token','client_id':cfg['META_OAUTH_APP_ID'],'client_secret':cfg['META_OAUTH_APP_SECRET'],'fb_exchange_token':token});response.raise_for_status();token=response.json()['access_token']
                pages=[];after=None
                for _ in range(10):
                    params={'fields':'id,name,access_token,instagram_business_account','limit':100}
                    if after:params['after']=after
                    response=await client.get(root+'/me/accounts',headers={'Authorization':'Bearer '+token},params=params);response.raise_for_status();data=response.json()
                    pages.extend(x for x in data.get('data',[]) if x.get('access_token') and re.fullmatch(r'\d{1,100}',str(x.get('id',''))))
                    if not data.get('paging',{}).get('next'):break
                    after=data.get('paging',{}).get('cursors',{}).get('after')
                    if not after:break
            save(s,'oauth-pages:'+p['user_id'],'private_oauth',{'expires_at':time.time()+900,'ciphertext':cipher().encrypt(json.dumps(pages).encode()).decode()});s.commit()
        except (httpx.HTTPError,ValueError,KeyError):raise HTTPException(502,'Meta authorization could not be completed. Check app permissions and reconnect.')
        return {'connected':True,'pages':len(pages),'live_send':False}

    @app.get('/oauth/meta/pages')
    def pages(p=Depends(authorize),s=Depends(session)):
        owner(p)
        return [{'id':x['id'],'name':x.get('name','Facebook page'),'instagram_account_id':x.get('instagram_business_account',{}).get('id','')} for x in pending(s,p['user_id'])]

    @app.post('/oauth/meta/select')
    async def select_page(body:Selection,p=Depends(authorize),s=Depends(session)):
        owner(p);cfg=config();pages=pending(s,p['user_id']);page=next((x for x in pages if x['id']==body.page_id),None)
        if not page:raise HTTPException(404,'Page is not available in this authorization')
        ig=str(page.get('instagram_business_account',{}).get('id',''))
        if ig and not re.fullmatch(r'\d{1,100}',ig):raise HTTPException(502,'Invalid Instagram account from provider')
        if not hasattr(app.state,'bind_meta_accounts'):raise HTTPException(503,'Business gateway is required')
        # Unique ownership protects shared-app webhook routing across businesses.
        app.state.bind_meta_accounts([body.page_id]+([ig] if ig else []))
        import httpx
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                r=await client.post('https://graph.facebook.com/'+cfg['META_OAUTH_GRAPH_VERSION']+'/'+body.page_id+'/subscribed_apps',headers={'Authorization':'Bearer '+page['access_token']},data={'subscribed_fields':'messages,messaging_postbacks'});r.raise_for_status()
                if not r.json().get('success'):raise ValueError('Subscription rejected')
        except (httpx.HTTPError,ValueError):raise HTTPException(502,'Meta page subscription failed. Verify approved permissions and reconnect.')
        d=app.state.channel_configuration();d.update(META_APP_SECRET=cfg['META_OAUTH_APP_SECRET'],META_GRAPH_VERSION=cfg['META_OAUTH_GRAPH_VERSION'],META_PAGE_ID=body.page_id,META_PAGE_ACCESS_TOKEN=page['access_token'],INSTAGRAM_ACCOUNT_ID=ig,INSTAGRAM_ACCESS_TOKEN=page['access_token'] if ig else '',ENABLE_LIVE_SEND='0')
        save(s,'connections:private','private_credentials',{'ciphertext':cipher().encrypt(json.dumps(d).encode()).decode()})
        s.delete(s.get(Record,'oauth-pages:'+p['user_id']));s.commit()
        return {'connected':True,'page_id':body.page_id,'instagram_account_id':ig,'live_send':False,'note':'Verify inbound webhooks before explicitly enabling live sending in connection settings.'}
