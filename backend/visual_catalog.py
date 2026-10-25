"""Uploaded catalog images only: no arbitrary URL fetching; similarity requires review."""
import base64,binascii,math
from fastapi import Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select
from media_extract import extract

class ImageInput(BaseModel):
    content_base64:str=Field(max_length=5_400_000)

def decode(body):
    try:raw=base64.b64decode(body.content_base64,validate=True)
    except (ValueError,binascii.Error):raise HTTPException(422,'Invalid image encoding')
    if not raw or len(raw)>4_000_000:raise HTTPException(422,'Use an image under 4 MB')
    return raw

def install_visual(app,Record,Product,Conversation,authorize,session,put,catalog):
    def match(s,raw):
        query=extract(raw,'image','image');products={p['id']:p for p in catalog('',s)};found=[]
        for r in s.scalars(select(Record).where(Record.kind=='visual_catalog').limit(500)):
            d=r.data;p=products.get(d['product_id'])
            if not p:continue
            exact=query['exact']==d['exact'];distance=(int(query['dhash'],16)^int(d['dhash'],16)).bit_count()
            a=query['histogram'];b=d['histogram'];den=math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
            color=sum(x*y for x,y in zip(a,b))/den if den else 0
            score=1 if exact else .5*(1-distance/64)+.5*color
            found.append({'product':p,'exact_pixels':exact,'similarity':round(score,4),'requires_review':not exact})
        return sorted(found,key=lambda x:(x['exact_pixels'],x['similarity']),reverse=True)[:3]
    @app.put('/products/{pid}/visual-image',dependencies=[Depends(authorize)])
    def index(pid:int,body:ImageInput,s=Depends(session)):
        if not s.get(Product,pid):raise HTTPException(404,'Product not found')
        parsed=extract(decode(body),'image','image');put(s,'visual_catalog',{'product_id':pid,**parsed},f'visual_catalog:{pid}');s.commit()
        return {'indexed':True,'product_id':pid,'exact_pixels':parsed['exact'],'similarity_is_not_identity':True}
    @app.post('/conversations/{cid}/visual-match',dependencies=[Depends(authorize)])
    def compare(cid:int,body:ImageInput,s=Depends(session)):
        if not s.get(Conversation,cid):raise HTTPException(404,'Conversation not found')
        return {'matches':match(s,decode(body)),'order_created':False,'note':'Top-three visual similarity suggestions, not semantic identity or a purchase confirmation.'}
    app.state.visual_match=match
