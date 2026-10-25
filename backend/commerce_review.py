"""Reviewed operations; proposals never execute refunds, discounts or purchases."""
import hashlib,json
from datetime import datetime,timezone
from typing import Literal
from fastapi import Depends,HTTPException
from pydantic import BaseModel,Field
from sqlalchemy import select

def fingerprint(data):return hashlib.sha256(json.dumps(data,sort_keys=True,default=str).encode()).hexdigest()
def stamp():return datetime.now(timezone.utc).isoformat()
class Correction(BaseModel):
    expected_hash:str
    title:str=Field(min_length=1,max_length=200)
    text:str=Field(min_length=1,max_length=50000)
    source_note:str=Field(min_length=1,max_length=1000)
class Proposal(BaseModel):
    request_id:str=Field(min_length=8,max_length=100)
    conversation_id:int
    kind:Literal['discount','refund','unclear_order','policy_exception']
    detail:str=Field(min_length=1,max_length=2000)
class Decision(BaseModel):
    decision:Literal['approved','rejected']
    expected_source_hash:str
    note:str=Field(min_length=1,max_length=2000)
class Area(BaseModel):
    name:str=Field(min_length=1,max_length=100)
    fee:int=Field(ge=0,le=100000)
    minimum:int=Field(default=0,ge=0,le=10000000)
    slots:list[str]=Field(default_factory=list,max_length=20)
class DeliveryRules(BaseModel):
    enabled:bool=False
    areas:list[Area]=Field(default_factory=list,max_length=100)
class Reorder(BaseModel):
    request_id:str=Field(min_length=8,max_length=100)

def install_reviews(app,Record,Product,Conversation,Message,authorize,session,put,records,catalog):
    def lock(s):s.scalar(select(Record).where(Record.id=='agent:live').with_for_update())
    def require(s,rid,kind):
        r=s.get(Record,rid)
        if not r or r.kind!=kind:raise HTTPException(404,'Record not found in this workspace')
        return r
    def source(s,cid):
        c=s.get(Conversation,cid)
        if not c:raise HTTPException(404,'Conversation not found')
        return fingerprint({'messages':[(m.id,m.text) for m in s.scalars(select(Message).where(Message.conversation_id==cid,Message.role=='customer').order_by(Message.id))],'catalog':catalog('',s),'agent':s.get(Record,'agent:live').data,'knowledge':records(s,'knowledge')})
    @app.get('/knowledge/provenance',dependencies=[Depends(authorize)])
    def provenance(s=Depends(session)):
        return [{**d,'source_hash':fingerprint({'title':d['title'],'text':d['text']})} for d in records(s,'knowledge')]
    @app.put('/knowledge/{rid}/correction',dependencies=[Depends(authorize)])
    def correct(rid:str,body:Correction,principal=Depends(authorize),s=Depends(session)):
        lock(s);r=require(s,rid,'knowledge');old=fingerprint({'title':r.data['title'],'text':r.data['text']})
        if old!=body.expected_hash:raise HTTPException(409,'Source changed; reload and review the current document')
        put(s,'knowledge_revision',{'document_id':rid,'previous':r.data,'source_hash':old,'note':body.source_note,'actor':principal.get('user_id') if principal else 'legacy-owner','created_at':stamp()})
        r.data={**r.data,'title':body.title,'text':body.text,'source_note':body.source_note,'updated_at':stamp()}
        index=s.get(Record,'index:'+rid)
        if index:s.delete(index)
        s.commit();return {**r.data,'source_hash':fingerprint({'title':body.title,'text':body.text})}
    def queue(s,cid,kind,detail,key):
        rid='approval:'+key;old=s.get(Record,rid)
        if old:return old.data
        c=s.get(Conversation,cid)
        if not c:raise HTTPException(404,'Conversation not found')
        c.mode='human'
        return put(s,'approval',{'conversation_id':cid,'kind':kind,'detail':detail,'status':'pending','source_hash':source(s,cid),'created_at':stamp(),'execution':'none'},rid)
    app.state.queue_approval=queue
    @app.get('/approvals',dependencies=[Depends(authorize)])
    def approvals(s=Depends(session)):return records(s,'approval')
    @app.post('/approvals',dependencies=[Depends(authorize)])
    def propose(body:Proposal,s=Depends(session)):
        lock(s);rid='approval:'+body.request_id;old=s.get(Record,rid)
        if old and any(old.data[k]!=getattr(body,k) for k in ('conversation_id','kind','detail')):raise HTTPException(409,'Request ID reused for another proposal')
        result=queue(s,body.conversation_id,body.kind,body.detail,body.request_id);s.commit();return result
    @app.post('/approvals/{rid}/decision',dependencies=[Depends(authorize)])
    def decide(rid:str,body:Decision,principal=Depends(authorize),s=Depends(session)):
        lock(s);r=require(s,rid,'approval')
        if r.data['status']!='pending':
            if r.data['status']==body.decision and r.data.get('decision_note')==body.note:return r.data
            raise HTTPException(409,'Proposal already decided')
        if body.expected_source_hash!=r.data['source_hash'] or source(s,r.data['conversation_id'])!=r.data['source_hash']:raise HTTPException(409,'Conversation or source changed; create a new reviewed proposal')
        r.data={**r.data,'status':body.decision,'decision_note':body.note,'decided_at':stamp(),'decided_by':principal.get('user_id') if principal else 'legacy-owner','execution':'none'};s.commit();return r.data
    @app.get('/customers/{cid}/profile',dependencies=[Depends(authorize)])
    def profile(cid:int,s=Depends(session)):
        c=s.get(Conversation,cid)
        if not c:raise HTTPException(404,'Conversation not found')
        return {'conversation_id':cid,'name':c.customer,'orders':[o for o in records(s,'orders') if o['conversation_id']==cid],'sensitive_profile_collected':False}
    @app.post('/orders/{rid}/reorder-draft',dependencies=[Depends(authorize)])
    def reorder(rid:str,body:Reorder,s=Depends(session)):
        lock(s);old=require(s,rid,'orders');key='reorder:'+body.request_id;existing=s.get(Record,key)
        if existing:
            if existing.data['source_order_id']!=rid:raise HTTPException(409,'Request ID reused for another order')
            return {**existing.data,'note':'Saved draft only. Current catalog is revalidated on order submission.'}
        items=[];changes=[];available=True
        for item in old.data['items']:
            p=s.get(Product,item['product_id'])
            if not p or p.stock<item['quantity']:available=False;changes.append('Unavailable: '+item['name'])
            if p and p.price!=item['unit_price']:changes.append('Price changed: '+p.name)
            items.append({'product_id':item['product_id'],'quantity':item['quantity'],'expected_unit_price':p.price if p else None})
        result=put(s,'reorder_draft',{'source_order_id':rid,'conversation_id':old.data['conversation_id'],'customer':old.data['customer'],'phone':old.data['phone'],'address':old.data['address'],'items':items,'changes':changes,'available':available,'requires_customer_confirmation':True,'created_at':stamp(),'order_created':False},key);s.commit();return result
    @app.get('/delivery/rules',dependencies=[Depends(authorize)])
    def rules(s=Depends(session)):
        r=s.get(Record,'delivery:rules');return r.data if r else {'enabled':False,'areas':[]}
    @app.put('/delivery/rules',dependencies=[Depends(authorize)])
    def save_rules(body:DeliveryRules,s=Depends(session)):
        names=[a.name.strip().casefold() for a in body.areas]
        if len(set(names))!=len(names) or any(not n for n in names) or (body.enabled and not names):raise HTTPException(422,'Provide unique nonempty delivery areas')
        if any(any(not x.strip() or len(x)>100 for x in a.slots) for a in body.areas):raise HTTPException(422,'Use nonempty slot labels under 100 characters')
        lock(s);result=put(s,'delivery_rules',body.model_dump(),'delivery:rules');s.commit();return result
    def validate_delivery(s,area,slot,fee,subtotal):
        config=rules(s)
        if not config['enabled']:return
        chosen=next((a for a in config['areas'] if a['name']==area),None)
        if not chosen:raise HTTPException(409,'Select an explicitly supported delivery area')
        if fee!=chosen['fee'] or subtotal<chosen['minimum'] or (chosen['slots'] and slot not in chosen['slots']):raise HTTPException(409,'Delivery fee, minimum or slot changed; review current delivery rules')
    app.state.validate_delivery=validate_delivery
    @app.get('/commerce/report',dependencies=[Depends(authorize)])
    def report(s=Depends(session)):
        checkouts=records(s,'checkout');current=datetime.now(timezone.utc)
        expired=sum(bool(not x.get('order_id') and x.get('expires_at') and datetime.fromisoformat(x['expires_at'])<=current) for x in checkouts)
        orders=records(s,'orders');ledger=records(s,'ledger');drafts=records(s,'reorder_draft');approvals=records(s,'approval');usage=records(s,'usage')
        return {'confirmed_order_value_bdt':sum(o['total'] for o in orders if o['status']!='cancelled'),'verified_revenue_bdt':None,'actual_ai_cost_paisa':-sum(x['paisa'] for x in ledger if x.get('type')=='usage'),'unmetered_requests':sum(not any(l.get('usage_id')==u['id'] for l in ledger) for u in usage),'orders_by_status':{status:sum(o['status']==status for o in orders) for status in ('confirmed','shipped','delivered','cancelled')},'observed_stages':{'conversations':s.query(Conversation).count(),'reorder_drafts':len(drafts),'orders':len(orders),'pending_approvals':sum(p['status']=='pending' for p in approvals),'current_checkout_quotes':len(checkouts),'confirmed_checkout_quotes':sum(bool(x.get('order_id')) for x in checkouts),'expired_unconfirmed_quotes':expired},'dropoff_rate':None,'note':'Counts are observed stages/current quote snapshots, not a historical attribution funnel. Expired unconfirmed quotes are observed drop-offs, not inferred customer intent. No reliable abandonment rate or verified sales revenue is inferred. Unmetered AI requests have unknown cost.'}
