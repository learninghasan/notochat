"""Read-only, bounded public WooCommerce catalog snapshots; never local inventory."""
import html,json,re
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from html.parser import HTMLParser
import httpx
from fastapi import Depends,HTTPException
from pydantic import BaseModel
from sqlalchemy import select

SOURCES={'peoniara':'https://peoniara.com'}
MAX_BYTES=4_000_000
class Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.hidden=0
    def handle_starttag(self,t,a):
        if t in ('script','style'):self.hidden+=1
    def handle_endtag(self,t):
        if t in ('script','style'):self.hidden=max(0,self.hidden-1)
    def handle_data(self,d):
        if not self.hidden:self.parts.append(d)
def plain(v,limit):
    p=Text();p.feed(str(v));return ' '.join(' '.join(p.parts).split())[:limit]
def now():return datetime.now(timezone.utc)
def read(url):
    # Callers construct paths only from a fixed source and validated integer IDs.
    with httpx.Client(timeout=15,follow_redirects=False,trust_env=True) as c:
        with c.stream('GET',url,headers={'Accept':'application/json'}) as r:
            r.raise_for_status();b=bytearray()
            for chunk in r.iter_bytes():
                b.extend(chunk)
                if len(b)>MAX_BYTES:raise ValueError('Catalog response too large')
            return json.loads(b),dict(r.headers)
def normalize(p,base):
    if not isinstance(p,dict) or type(p.get('id')) is not int or p['id']<=0:raise ValueError('Invalid product ID')
    prices=p['prices'];unit=prices['currency_minor_unit']
    if type(unit)is not int or not 0<=unit<=4 or not re.fullmatch('[A-Z]{3}',prices['currency_code']):raise ValueError('Invalid currency')
    def price(key):
        v=prices.get(key)
        if v in ('',None):return None
        if not isinstance(v,str) or not re.fullmatch(r'\d{1,12}',v):raise ValueError('Invalid price')
        return str(Decimal(v)/(10**unit))
    link=p['permalink']
    if not link.startswith(base+'/product/') or any(x in link for x in ['\\','\n','\r']):raise ValueError('Invalid product URL')
    images=[i['src'] for i in p.get('images',[])[:8] if isinstance(i,dict) and isinstance(i.get('src'),str) and i['src'].startswith(base+'/wp-content/uploads/')][:8]
    availability=p.get('is_in_stock')
    if type(availability)is not bool:raise ValueError('Invalid availability')
    variants=p.get('variations',[])
    return {'source_id':p['id'],'name':plain(p['name'],300),'description':plain(p.get('description',''),4000),'sku':plain(p.get('sku',''),100),'type':plain(p.get('type',''),30),'url':link,'images':images,'currency':prices['currency_code'],'price':price('price'),'regular_price':price('regular_price'),'sale_price':price('sale_price'),'listed_available':availability,'stock_quantity':None,'purchasable':p.get('is_purchasable') is True,'grouped_product_ids':[x for x in p.get('grouped_products',[]) if type(x)is int and x>0][:100],'variants':[{'id':v['id'],'attributes':[{'name':plain(a.get('name',''),100),'value':plain(a.get('value',''),100)} for a in v.get('attributes',[])[:30]]} for v in variants[:100] if isinstance(v,dict) and type(v.get('id'))is int],'attributes':[{'name':plain(a.get('name',''),100),'terms':[plain(t.get('name',''),100) for t in a.get('terms',[])[:100]]} for a in p.get('attributes',[])[:30]],'shipping_quote':None}
def fetch_catalog(source):
    base=SOURCES[source];result={};total=None
    for page in range(1,11):
        rows,headers=read(f'{base}/wp-json/wc/store/v1/products?per_page=100&page={page}')
        pages=int(headers.get('x-wp-totalpages','1'));count=int(headers.get('x-wp-total','0'))
        if not 1<=pages<=10 or count>1000 or not isinstance(rows,list) or len(rows)>100:raise ValueError('Catalog exceeds bounded import limits')
        if total is None:total=count
        if total!=count:raise ValueError('Catalog changed during pagination; retry')
        for raw in rows:
            p=normalize(raw,base)
            if p['source_id'] in result:raise ValueError('Duplicate product across pages')
            result[p['source_id']]=p
        if page==pages:break
    if len(result)!=total:raise ValueError('Incomplete catalog snapshot')
    return list(result.values())
class Config(BaseModel):
    source:str

def install_website_catalog(app,Record,authorize,session,put):
    def lock(s):s.scalar(select(Record).where(Record.id=='agent:live').with_for_update())
    def config(s):
        r=s.get(Record,'website_catalog:config')
        if not r:raise HTTPException(409,'Choose a supported website source first')
        return r.data['source']
    @app.put('/website-catalog/config',dependencies=[Depends(authorize)])
    def configure(body:Config,s=Depends(session)):
        if body.source not in SOURCES:raise HTTPException(422,'Unsupported website source')
        lock(s);put(s,'website_catalog_config',{'source':body.source},'website_catalog:config');s.commit();return {'source':body.source}
    @app.get('/website-catalog',dependencies=[Depends(authorize)])
    def snapshot(s=Depends(session)):
        r=s.get(Record,'website_catalog:snapshot');status=s.get(Record,'website_catalog:status');cfg=s.get(Record,'website_catalog:config')
        data=r.data if r else {'products':[],'last_sync':None}
        stale=not data['last_sync'] or now()-datetime.fromisoformat(data['last_sync'])>timedelta(minutes=15) or bool(status and status.data.get('error'))
        return {**data,'source':cfg.data['source'] if cfg else None,'stale':stale,'status':status.data if status else {},'stock_quantity_available':False,'delivery_quote_available':False,'checkout_policy':'Website listings only. Recheck listing and confirm quantity and address-specific delivery with the store; no local purchase or stock reservation.'}
    @app.post('/website-catalog/sync',dependencies=[Depends(authorize)])
    def sync(s=Depends(session)):
        lock(s);source=config(s);status=s.get(Record,'website_catalog:status')
        if status and now()-datetime.fromisoformat(status.data['attempted_at'])<timedelta(seconds=60):raise HTTPException(429,'Wait one minute before syncing again')
        attempted=now().isoformat()
        try:products=fetch_catalog(source)
        except Exception:
            put(s,'website_catalog_status',{'attempted_at':attempted,'error':'Source unavailable or invalid; last good snapshot preserved.'},'website_catalog:status');s.commit();raise HTTPException(502,'Website sync failed; last good snapshot preserved') from None
        put(s,'website_catalog_snapshot',{'source':source,'source_url':SOURCES[source],'last_sync':now().isoformat(),'products':products},'website_catalog:snapshot')
        put(s,'website_catalog_status',{'attempted_at':attempted,'error':None},'website_catalog:status');s.commit();return snapshot(s)
    @app.post('/website-catalog/products/{pid}/recheck',dependencies=[Depends(authorize)])
    def recheck(pid:int,s=Depends(session)):
        lock(s);source=config(s)
        if pid<=0:raise HTTPException(422,'Invalid product ID')
        r=s.get(Record,'website_catalog:snapshot')
        if not r or not any(p['source_id']==pid for p in r.data['products']):raise HTTPException(404,'Product not present in this tenant snapshot')
        gate=s.get(Record,'website_catalog:recheck')
        if gate and now()-datetime.fromisoformat(gate.data['attempted_at'])<timedelta(seconds=5):raise HTTPException(429,'Wait five seconds before rechecking a listing')
        put(s,'website_catalog_recheck',{'attempted_at':now().isoformat()},'website_catalog:recheck');s.commit()
        try:raw,_=read(f'{SOURCES[source]}/wp-json/wc/store/v1/products/{pid}');p=normalize(raw,SOURCES[source])
        except Exception:raise HTTPException(502,'Cannot revalidate website listing; operator review required') from None
        if p['source_id']!=pid:raise HTTPException(502,'Source product identity mismatch')
        return {'product':p,'checked_at':now().isoformat(),'requires_operator_confirmation':True,'order_created':False,'shipping_quote':None}
