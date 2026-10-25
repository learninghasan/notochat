"""Catalog-grounded cards and category buttons; selections are inquiries, not orders."""
import hashlib,json
from typing import Literal
from fastapi import Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select
from urllib.parse import urlsplit

class Cards(BaseModel):
    request_id:str=Field(min_length=8,max_length=100)
    product_ids:list[int]=Field(default_factory=list,max_length=10)
    category:str=Field(default='',max_length=80)
    kind:Literal['products','categories']='products'

def public_image(url):
    try:
        p=urlsplit(url)
        return url if p.scheme=='https' and p.hostname and not p.username and not p.password else ''
    except ValueError:return ''

def install_rich_catalog(app,Record,Conversation,Message,authorize,session,put,catalog):
    def attach(s,cid,mid,ids=None,kind='products',category=''):
        products=catalog('',s)
        if ids:
            selected=[p for p in products if p['id'] in ids]
            if len(selected)!=len(set(ids)):raise HTTPException(409,'A selected product is unavailable')
        else:selected=[p for p in products if not category or p.get('category')==category][:10]
        data={'conversation_id':cid,'message_id':mid,'kind':kind,'products':[{k:p.get(k,'') for k in ('id','name','price','stock','sku','image','size')} for p in selected], 'categories':sorted({p.get('category') for p in products if p.get('category')})[:10]}
        if not (data['categories'] if kind=='categories' else selected):raise HTTPException(409,'No catalog items to display')
        return put(s,'rich_message',data,f'rich_message:{mid}')
    def payload(s,cid,mid,channel,sender):
        record=s.get(Record,f'rich_message:{mid}')
        if not record:return None
        d=record.data
        if d['conversation_id']!=cid:raise HTTPException(404,'Catalog message not found')
        if d['kind']=='link':
            url=public_image(d['tracking_url'])
            if not url:raise HTTPException(409,'Tracking link is invalid')
            if channel=='WhatsApp':return {'messaging_product':'whatsapp','to':sender,'type':'text','text':{'body':'Track your parcel: '+url}}
            if channel=='Instagram':return {'recipient':{'id':sender},'message':{'text':'Track your parcel: '+url}}
            return {'recipient':{'id':sender},'messaging_type':'RESPONSE','message':{'attachment':{'type':'template','payload':{'template_type':'button','text':'Track your parcel / পার্সেল ট্র্যাক করুন','buttons':[{'type':'web_url','title':'Track parcel','url':url}]}}}}
        current={p['id']:p for p in catalog('',s)}
        if any(p['id'] not in current or any(current[p['id']].get(k)!=p[k] for k in ('price','stock','name')) for p in d['products']):raise HTTPException(409,'Catalog changed; prepare a fresh card before sending')
        if d['kind']=='categories':
            if channel=='WhatsApp':
                rows=[{'id':'CATEGORY:'+x,'title':x[:24]} for x in d['categories']]
                return {'messaging_product':'whatsapp','to':sender,'type':'interactive','interactive':{'type':'list','body':{'text':'Choose a category / ক্যাটাগরি বাছুন'},'action':{'button':'Categories','sections':[{'rows':rows}]}}}
            return {'recipient':{'id':sender},'messaging_type':'RESPONSE','message':{'text':'Choose a category / ক্যাটাগরি বাছুন','quick_replies':[{'content_type':'text','title':x[:20],'payload':'CATEGORY:'+x} for x in d['categories']]}}
        if channel=='WhatsApp':
            return {'messaging_product':'whatsapp','to':sender,'type':'interactive','interactive':{'type':'list','body':{'text':'Choose a product to ask about. This does not place an order.'},'action':{'button':'Products','sections':[{'rows':[{'id':'PRODUCT:'+str(p['id']),'title':p['name'][:24],'description':f"BDT {p['price']} · {p['stock']} in stock · {p['sku']}"[:72]} for p in d['products']]}]}}}
        elements=[]
        for p in d['products']:
            element={'title':p['name'][:80],'subtitle':f"৳{p['price']} · {p['stock']} in stock · {p['sku']}"[:80],'buttons':[{'type':'postback','title':'Ask about this','payload':'PRODUCT:'+str(p['id'])}]}
            if public_image(p['image']):element['image_url']=p['image']
            elements.append(element)
        return {'recipient':{'id':sender},'messaging_type':'RESPONSE','message':{'attachment':{'type':'template','payload':{'template_type':'generic','elements':elements}}}}
    @app.post('/conversations/{cid}/catalog-cards',dependencies=[Depends(authorize)])
    def prepare(cid:int,body:Cards,s=Depends(session)):
        c=s.scalar(select(Conversation).where(Conversation.id==cid).with_for_update())
        if not c:raise HTTPException(404,'Conversation not found')
        if c.channel not in ('Website','Messenger','Instagram','WhatsApp'):raise HTTPException(409,'Channel does not support catalog cards')
        key='catalog-request:'+hashlib.sha256((str(cid)+body.request_id).encode()).hexdigest();fingerprint=json.dumps(body.model_dump(),sort_keys=True)
        old=s.get(Record,key)
        if old:
            if old.data['fingerprint']!=fingerprint:raise HTTPException(409,'Request ID was used for different cards')
            return old.data
        if c.mode!='human':raise HTTPException(409,'Take over before preparing a team catalog reply')
        m=Message(conversation_id=cid,role='team',text='Catalog selection / পণ্য দেখুন — selecting an item does not place an order.');s.add(m);s.flush()
        attach(s,cid,m.id,body.product_ids,body.kind,body.category)
        d=put(s,'catalog_request',{'conversation_id':cid,'message_id':m.id,'fingerprint':fingerprint,'sent':c.channel=='Website'},key)
        if c.channel=='Website':app.state.record_reply(s,cid,m.id)
        s.commit();return d
    app.state.attach_catalog=attach;app.state.rich_payload=payload
