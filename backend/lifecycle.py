"""Source-bound draft reminders; explicit published opt-in enables existing safe delivery."""
from datetime import datetime,timezone,timedelta
from sqlalchemy import select

def install_lifecycle(app,Record,put):
    def schedule(s,source):
        data=source.data;cid=data['conversation_id'];live=s.get(Record,'agent:live').data
        kind=source.kind;status=data.get('status','');now=datetime.now(timezone.utc)
        meta=s.get(Record,f'conversation:{cid}');last=(meta.data if meta else {}).get('last_verified_inbound','')
        if kind=='leads':
            if data.get('temperature') not in live.get('followup_temperatures',['Hot','Warm']) or data.get('stage') in ('Won','Lost'):return
            try:base=datetime.fromisoformat(last)
            except (ValueError,TypeError):return
            due=base+timedelta(hours=1 if data['temperature']=='Hot' else 4)
            if due<=now:return
            label='followup';text='আপনার পছন্দের পণ্য নিয়ে কোনো প্রশ্ন আছে? / Any questions about the products you were interested in?';state='followup'
        elif kind=='orders' and status=='shipped':
            label='delivery';text='আপনার অর্ডার পাঠানো হয়েছে। / Your order has shipped. Tracking reference: '+data.get('tracking','');due=now;state='shipped'
        elif kind=='orders' and status=='delivered':
            if not live.get('review_url'):return
            label='review';text='আপনার অভিজ্ঞতা জানাবেন? / Please share your experience: '+live['review_url'];due=now+timedelta(hours=1);state='delivered'
        else:return
        key=f'automations:lifecycle:{source.id}:{state}'
        if s.get(Record,key):return
        automatic=bool(live.get('auto_lifecycle'))
        d=put(s,'automations',{'conversation_id':cid,'kind':label,'text':text,'due_at':due.isoformat(),'status':'scheduled' if automatic else 'draft','delivery':'not sent','auto_send':automatic,'source_id':source.id,'source_kind':kind,'source_state':state,'source_inbound':last},key)
        if automatic:app.state.enqueue(s,'reminder_prepare',{'automation_id':key,'conversation_id':cid},due=due,key='reminder-'+key)
        return d
    def valid(s,data):
        if not data.get('source_id'):return True
        live=s.get(Record,'agent:live').data
        if data.get('auto_send') and data['source_kind'] in ('leads','orders') and not live.get('auto_lifecycle'):return False
        source=s.get(Record,data['source_id'])
        if not source or source.kind!=data['source_kind'] or source.data.get('conversation_id')!=data['conversation_id']:return False
        current=source.data
        if source.kind=='leads':
            meta=s.get(Record,f"conversation:{data['conversation_id']}")
            return bool(current.get('stage') not in ('Won','Lost') and current.get('temperature') in live.get('followup_temperatures',['Hot','Warm']) and meta and meta.data.get('last_verified_inbound')==data.get('source_inbound'))
        if source.kind=='orders':return current.get('status')==data['source_state']
        if source.kind=='bookings':return current.get('status')=='confirmed'
        return False
    app.state.schedule_lifecycle=schedule;app.state.lifecycle_source_valid=valid
