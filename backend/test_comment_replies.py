import time
from test_completion import system,H,mock_client
from test_attachments import media_shop,incoming
from test_business import gateway,call

def comment(c,mid='12345_9988',sender='customer'):
    return incoming(c,{'object':'page','entry':[{'id':'12345','changes':[{'field':'feed','value':{'item':'comment','verb':'add','from':{'id':sender},'comment_id':mid,'message':'How much?','created_time':int(time.time())}}]}]})
def prepare(c):
    comment(c);cid=c.get('/conversations',headers=H).json()[-1]['id']
    c.post(f'/conversations/{cid}/messages',headers=H,json={'text':'Please check your inbox'})
    messages=c.get(f'/conversations/{cid}/messages',headers=H).json()
    return cid,{'comment_message_id':messages[0]['id'],'message_id':messages[-1]['id'],'kind':'private'}
def test_verified_public_private_comment_transports_are_explicit_and_idempotent(media_shop,monkeypatch):
    _,c,_=media_shop;cid,body=prepare(c)
    assert c.post(f'/conversations/{cid}/comment-replies',headers=H,json=body).status_code==503
    monkeypatch.setenv('ENABLE_LIVE_SEND','1');calls=mock_client(monkeypatch,post_result={'message_id':'fake-receipt'})
    path=f'/conversations/{cid}/comment-replies'
    assert c.post(path,headers=H,json=body).status_code==200
    assert calls[0][2]['json']['recipient']=={'comment_id':'12345_9988'}
    assert c.post(path,headers=H,json=body).status_code==200 and len(calls)==1
    assert c.post(path,headers=H,json={**body,'kind':'public'}).status_code==200
    assert calls[-1][1].endswith('/12345_9988/comments')
    c.post(f'/conversations/{cid}/messages',headers=H,json={'text':'Second private reply'})
    mid=c.get(f'/conversations/{cid}/messages',headers=H).json()[-1]['id']
    assert c.post(path,headers=H,json={**body,'message_id':mid}).status_code==409
    assert len(calls)==2

def test_comment_uncertain_receipt_never_blindly_retries_and_page_echo_ignored(media_shop,monkeypatch):
    _,c,_=media_shop;assert comment(c,sender='12345').json()['stored']==0
    cid,body=prepare(c);monkeypatch.setenv('ENABLE_LIVE_SEND','1');calls=mock_client(monkeypatch,post_result={})
    path=f'/conversations/{cid}/comment-replies'
    assert c.post(path,headers=H,json=body).status_code==502
    assert c.post(path,headers=H,json=body).status_code==409 and len(calls)==1
    c.patch(f'/conversations/{cid}/mode',headers=H,json={'mode':'ai'})
    assert c.post(path,headers=H,json={**body,'kind':'public'}).status_code==409

def test_local_test_message_cannot_authorize_comment_reply(media_shop,monkeypatch):
    _,c,_=media_shop;cid,body=prepare(c)
    c.post(f'/conversations/{cid}/incoming',headers=H,json={'text':'not a signed comment'})
    mid=c.get(f'/conversations/{cid}/messages',headers=H).json()[-1]['id']
    assert c.post(f'/conversations/{cid}/comment-replies',headers=H,json={**body,'comment_message_id':mid}).status_code==404

def test_expired_comment_and_other_business_cannot_be_replied_to(media_shop,monkeypatch,gateway):
    from sqlalchemy.orm import Session
    from main import Base
    from datetime import datetime,timezone,timedelta
    _,c,engine=media_shop;cid,body=prepare(c);monkeypatch.setenv('ENABLE_LIVE_SEND','1')
    calls=mock_client(monkeypatch,post_result={'id':'fake'})
    with Session(engine) as s:
        p=s.get(Base.WorkspaceRecord,f"verified_message:{body['comment_message_id']}");p.data={**p.data,'received_at':(datetime.now(timezone.utc)-timedelta(days=8)).isoformat()};s.commit()
    assert c.post(f'/conversations/{cid}/comment-replies',headers=H,json=body).status_code==409 and calls==[]
    gc,_=gateway
    assert call(gc,'other_org','POST',f'/conversations/{cid}/comment-replies',body).status_code==404
