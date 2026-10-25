"""Observed reply-turn timing, never inferred resolution or ownership statistics."""
from datetime import datetime,timezone
from sqlalchemy import select

def calculate(inbounds,replies,now=None):
    now=now or datetime.now(timezone.utc)
    events=[]
    for inbound,data in [(True,d) for d in inbounds]+[(False,d) for d in replies]:
        try:
            at=datetime.fromisoformat(data['received_at' if inbound else 'sent_at'])
            if at.tzinfo is None or at>now:continue
            events.append((at,inbound,data))
        except (KeyError,ValueError,TypeError):continue
    pending={};human=[];ai=[]
    for at,inbound,d in sorted(events,key=lambda x:(x[0],not x[1])):
        cid=d['conversation_id']
        if inbound:pending.setdefault(cid,at)
        elif cid in pending:
            elapsed=(at-pending.pop(cid)).total_seconds()
            (ai if d['automated'] else human).append(elapsed)
    count=len(human)+len(ai)
    return {'human_response_seconds':sum(human)/len(human) if human else None,'human_response_samples':len(human),'ai_response_samples':len(ai),'ai_handled_turn_percent':round(100*len(ai)/count,1) if count else None,'waiting':{str(cid):{'since':at.isoformat(),'seconds':int((now-at).total_seconds())} for cid,at in pending.items()},'response_metrics_note':'Observed verified customer turns with confirmed replies since timing instrumentation was enabled. AI handled share is not resolution rate; historical messages without timestamps are excluded.'}

def install_metrics(app,Record,put):
    def reply(s,cid,mid,automated=False):
        key=f'reply_event:{mid}'
        if not s.get(Record,key):put(s,'reply_event',{'conversation_id':cid,'message_id':mid,'automated':automated,'sent_at':datetime.now(timezone.utc).isoformat()},key)
    def snapshot(s):
        return calculate([r.data for r in s.scalars(select(Record).where(Record.kind=='verified_message'))],[r.data for r in s.scalars(select(Record).where(Record.kind=='reply_event'))])
    app.state.record_reply=reply;app.state.response_metrics=snapshot
