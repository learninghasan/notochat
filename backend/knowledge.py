"""Bounded PDF import and optional embedding-based passage retrieval."""
import base64
import binascii
import hashlib
import io
import math
import os
from fastapi import Depends,HTTPException,Query
from pydantic import BaseModel,Field
from sqlalchemy import select

class PDFInput(BaseModel):
    title:str=Field(min_length=1,max_length=200)
    content_base64:str=Field(min_length=4,max_length=7000000)


def install_knowledge(app,Record,authorize,session,put):
    @app.post('/knowledge/import/pdf',dependencies=[Depends(authorize)])
    def import_pdf(body:PDFInput,s=Depends(session)):
        try:raw=base64.b64decode(body.content_base64,validate=True)
        except (binascii.Error,ValueError):raise HTTPException(422,'Invalid PDF encoding')
        if len(raw)>5_000_000 or not raw.startswith(b'%PDF-'):raise HTTPException(422,'Use a PDF under 5 MB')
        from media_extract import extract
        text=extract(raw,'application/pdf','document')['text']
        d=put(s,'knowledge',{'title':body.title,'text':text,'source':'PDF'});s.commit();return d

    async def embed(texts,s):
        app.state.require_credit(s)
        key=os.getenv('OPENAI_API_KEY');model=os.getenv('OPENAI_EMBEDDING_MODEL')
        if not key or not model:raise HTTPException(503,'Configure OPENAI_EMBEDDING_MODEL and the API key for semantic search')
        import httpx
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response=await client.post('https://api.openai.com/v1/embeddings',headers={'Authorization':'Bearer '+key},json={'model':model,'input':texts});response.raise_for_status();result=response.json()
            data=sorted(result['data'],key=lambda x:x['index']);vectors=[d['embedding'] for d in data]
            if len(vectors)!=len(texts) or any(not v or len(v)>8192 or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in v) for v in vectors):raise ValueError()
        except (httpx.HTTPError,ValueError,KeyError,TypeError):raise HTTPException(502,'Embedding response could not be validated')
        usage=result.get('usage',{})
        put(s,'usage',{'model':model,'action':'embedding','tokens':{'input_tokens':usage.get('prompt_tokens',usage.get('total_tokens',0)),'output_tokens':0},'cost_bdt':None})
        return model,vectors

    @app.post('/knowledge/{rid}/index',dependencies=[Depends(authorize)])
    async def index(rid:str,s=Depends(session)):
        d=s.get(Record,rid)
        if not d or d.kind!='knowledge':raise HTTPException(404,'Document not found')
        text=d.data['text'];passages=[text[i:i+1100] for i in range(0,len(text),900)]
        model,vectors=await embed([d.data['title']+'\n'+p for p in passages],s)
        put(s,'knowledge_index',{'document_id':rid,'model':model,'source_hash':hashlib.sha256(text.encode()).hexdigest(),'passages':passages,'vectors':vectors},'index:'+rid);s.commit();return {'indexed':True,'passages':len(passages),'model':model}

    @app.get('/knowledge/semantic/search',dependencies=[Depends(authorize)])
    async def semantic(q:str=Query(min_length=1,max_length=1000),s=Depends(session)):
        model,vectors=await embed([q],s);query=vectors[0];found=[]
        docs={r.id:r.data for r in s.scalars(select(Record).where(Record.kind=='knowledge'))}
        for index in s.scalars(select(Record).where(Record.kind=='knowledge_index')):
            d=index.data;document=docs.get(d['document_id'])
            if not document or d['model']!=model or d['source_hash']!=hashlib.sha256(document['text'].encode()).hexdigest():continue
            for passage,v in zip(d['passages'],d['vectors']):
                if len(v)!=len(query):continue
                denominator=math.sqrt(sum(x*x for x in query))*math.sqrt(sum(x*x for x in v))
                score=sum(x*y for x,y in zip(query,v))/denominator if denominator else 0
                found.append({'id':d['document_id'],'title':document['title'],'text':passage,'score':score,'match_type':'semantic'})
        s.commit();return sorted(found,key=lambda x:x['score'],reverse=True)[:5]
