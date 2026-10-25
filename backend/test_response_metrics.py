from datetime import datetime,timezone,timedelta
from response_metrics import calculate
from test_completion import system,H,website,send_website

def test_metrics_count_verified_turns_ignore_drafts_and_report_oldest_wait():
    now=datetime.now(timezone.utc)
    def t(seconds):return (now-timedelta(seconds=seconds)).isoformat()
    inbound=[{'conversation_id':1,'received_at':t(100)},{'conversation_id':1,'received_at':t(80)},{'conversation_id':2,'received_at':t(50)},{'conversation_id':3,'received_at':t(40)},{'conversation_id':4}]
    replies=[{'conversation_id':1,'sent_at':t(60),'automated':False},{'conversation_id':2,'sent_at':t(30),'automated':True},{'conversation_id':1,'sent_at':t(20),'automated':False}]
    m=calculate(inbound,replies,now)
    assert m['human_response_seconds']==40 and m['human_response_samples']==1
    assert m['ai_handled_turn_percent']==50 and m['waiting']['3']['seconds']==40
    assert set(m['waiting'])=={'3'}

def test_real_widget_reply_clears_wait_once_without_counting_local_tests(system,monkeypatch):
    _,c,engine=system;cid,wh=website(c,monkeypatch)
    send_website(c,engine,wh,'Question')
    assert str(cid) in c.get('/analytics',headers=H).json()['waiting']
    c.patch(f'/conversations/{cid}/mode',headers=H,json={'mode':'human'})
    c.post(f'/conversations/{cid}/messages',headers=H,json={'text':'Response'})
    m=c.get('/analytics',headers=H).json();assert str(cid) not in m['waiting'] and m['human_response_samples']==1
    c.post(f'/conversations/{cid}/incoming',headers=H,json={'text':'Synthetic local test'})
    c.post(f'/conversations/{cid}/messages',headers=H,json={'text':'Another response'})
    assert c.get('/analytics',headers=H).json()['human_response_samples']==1
