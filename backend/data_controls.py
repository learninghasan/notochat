"""Scoped operator export; private credentials and auth tokens are excluded."""
from datetime import datetime,timezone
from fastapi import Depends,HTTPException
from sqlalchemy import select


def install_data_controls(app,Record,Conversation,Message,Product,authorize,session,tenant):
    @app.get('/workspace/export',dependencies=[Depends(authorize)])
    def export(principal=Depends(authorize),s=Depends(session)):
        if tenant and (not principal or principal.get('role') not in ('owner','admin')):raise HTTPException(403,'Owner or admin permission required')
        kinds=['orders','leads','bookings','knowledge','automations','agent','agent_versions','notifications','product_details']
        return {'format':'notochat-export-v1','created_at':datetime.now(timezone.utc).isoformat(),'conversations':[{'id':c.id,'customer':c.customer,'channel':c.channel,'mode':c.mode} for c in s.scalars(select(Conversation))],'messages':[{'conversation_id':m.conversation_id,'role':m.role,'text':m.text} for m in s.scalars(select(Message))],'products':[{'id':p.id,'name':p.name,'price':p.price,'stock':p.stock} for p in s.scalars(select(Product))],'records':[{'kind':r.kind,'data':r.data} for r in s.scalars(select(Record).where(Record.kind.in_(kinds)))],'excluded':['private credentials','session tokens','push subscriptions','raw customer media','authentication password hashes']}

    @app.get('/audit',dependencies=[Depends(authorize)])
    def audit(principal=Depends(authorize)):
        if tenant and (not principal or principal.get('role') not in ('owner','admin')):raise HTTPException(403,'Owner or admin permission required')
        return app.state.audit_events() if hasattr(app.state,'audit_events') else []
