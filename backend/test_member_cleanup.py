import json
from sqlalchemy.orm import Session
from main import Base
from test_business import gateway,call,proof

def test_member_cleanup_requires_signed_service_event_and_is_tenant_bound(gateway):
    c,g=gateway
    for org in ('devices_A','devices_B'):
        app=g.workspace(org)
        with Session(app.state.engine) as s:
            s.add(Base.WorkspaceRecord(id='push:test',kind='push_subscriptions',data={'user_id':'removed','endpoint':'https://fcm.googleapis.com/fake'}));s.commit()
    path='/push/revoke-member';body={'user_id':'removed'}
    assert call(c,'devices_A','POST',path,body).status_code==403
    raw=json.dumps(body).encode();headers=proof('devices_A','POST',path,raw,role='admin',user_id='auth-membership-hook',service_event='member-removal')
    result=c.post(path,content=raw,headers=headers);assert result.status_code==200 and result.json()['revoked']==1
    with Session(g.workspace('devices_A').state.engine) as s:assert s.get(Base.WorkspaceRecord,'push:test') is None and s.get(Base.WorkspaceRecord,'push_revoked:removed') is not None
    with Session(g.workspace('devices_B').state.engine) as s:assert s.get(Base.WorkspaceRecord,'push:test') is not None

def test_org_removal_event_quarantines_without_purging(gateway):
    c,g=gateway
    call(c,'org_removal','POST','/conversations',{'customer':'Retained for recovery'})
    path='/push/revoke-organization';raw=b'{}'
    headers=proof('org_removal','POST',path,raw,role='admin',user_id='auth-membership-hook',service_event='organization-removal')
    assert c.post(path,content=raw,headers=headers).json()['permanently_deleted'] is False
    assert call(c,'org_removal','GET','/workspace').status_code==423
    assert len(call(c,'org_removal','GET','/workspace/export').json()['conversations'])==1
