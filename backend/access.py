"""Owner-managed channel/assignment scopes applied to every request session."""
from fastapi import Depends,HTTPException
from pydantic import BaseModel,Field
from typing import Literal,Annotated
from sqlalchemy import select,event,or_,and_
from sqlalchemy.orm import with_loader_criteria

class Policy(BaseModel):
    channels:list[Literal['Messenger','Instagram','WhatsApp','Facebook comments','Website']]=Field(default_factory=list)
    assigned_only:bool=False
    accounts:list[Annotated[str,Field(min_length=1,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')]]|None=Field(default=None,max_length=100)


def install_access(app,Record,Conversation,Message,authorize,session,put,tenant):
    def manager(principal):
        if tenant and (not principal or principal.get('role') not in ('owner','admin')):raise HTTPException(403,'Owner or admin permission required')

    @app.get('/access/policies',dependencies=[Depends(authorize)])
    def policies(principal=Depends(authorize),s=Depends(session)):
        manager(principal)
        return [r.data for r in s.scalars(select(Record).where(Record.kind=='access_policy'))]

    @app.put('/access/policies/{user_id}',dependencies=[Depends(authorize)])
    def save(user_id:str,body:Policy,principal=Depends(authorize),s=Depends(session)):
        manager(principal)
        if len(user_id)>200:raise HTTPException(422,'Invalid user ID')
        d=put(s,'access_policy',{**body.model_dump(),'user_id':user_id},'access:'+user_id);s.commit();return d

    def configure(s,principal):
        if not principal or principal.get('role') in ('owner','admin'):return None
        policy=s.get(Record,'access:'+principal['user_id'])
        if not policy:return None  # Existing members retain organization-wide access until explicitly scoped.
        p=policy.data
        ids=list(s.scalars(select(Conversation.id).where(Conversation.channel.in_(p['channels']))))
        if p.get('accounts') is not None:
            ids=[cid for cid in ids if s.get(Conversation,cid).channel=='Website' or (s.get(Record,f'conversation:{cid}') and s.get(Record,f'conversation:{cid}').data.get('account') in p['accounts'])]
        if p['assigned_only']:
            ids=[cid for cid in ids if (s.get(Record,f'conversation:{cid}') and s.get(Record,f'conversation:{cid}').data.get('assignee_user_id')==principal['user_id'])]
        order_ids=[r.id for r in s.scalars(select(Record).where(Record.kind=='orders')) if r.data['conversation_id'] in ids]
        scoped=['orders','leads','bookings','automations','assistant_drafts','sales','usage','delivery','channel','inbound','outreach','verified_message','checkout','attachments','private_attachment']
        condition=or_(
            and_(Record.kind.in_(scoped),Record.data['conversation_id'].as_integer().in_(ids)),
            and_(Record.kind=='conversation',Record.id.in_([f'conversation:{cid}' for cid in ids])),
            and_(Record.kind=='notifications',or_(Record.data['conversation_id'].as_integer().in_(ids),Record.data['conversation_id'].as_integer().is_(None))),
            and_(Record.kind=='jobs',Record.data['payload']['conversation_id'].as_integer().in_(ids)),
            and_(Record.kind=='shipments',Record.data['order_id'].as_string().in_(order_ids)),
            ~Record.kind.in_([*scoped,'conversation','notifications','jobs','shipments'])
        )
        def scope(execute):
            if execute.is_select:
                execute.statement=execute.statement.options(with_loader_criteria(Conversation,Conversation.id.in_(ids),include_aliases=True),with_loader_criteria(Message,Message.conversation_id.in_(ids),include_aliases=True),with_loader_criteria(Record,condition,include_aliases=True))
        event.listen(s,'do_orm_execute',scope)
        return lambda:event.remove(s,'do_orm_execute',scope)
    app.state.configure_access=configure
