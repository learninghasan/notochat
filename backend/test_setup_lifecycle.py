from datetime import datetime,timezone,timedelta
import pytest
from sqlalchemy.orm import Session
from main import Base,Conversation,Message,Product
from test_completion import system,H
from workspace_lifecycle import purge_quarantined

def test_setup_resume_is_not_live_verification(system):
    _,c,_=system
    assert c.put('/onboarding/profile',headers=H,json={'name':'QA','timezone':'Bad/Zone'}).status_code==422
    assert c.put('/onboarding/profile',headers=H,json={'name':'QA','timezone':'Asia/Dhaka'}).status_code==200
    c.put('/onboarding/progress',headers=H,json={'step':'test'})
    d=c.get('/onboarding',headers=H).json();assert d['resume_step']=='test' and d['checks']['business'] and not d['live_verified']

def test_quarantine_restore_and_purge_only_synthetic_database(system):
    app,c,engine=system
    token=c.post('/workspace/deletion/request',headers=H).json()['token']
    assert c.get('/workspace',headers=H).status_code==200
    assert c.post('/workspace/deletion/confirm',headers=H,json={'token':token,'confirmation':'delete'}).status_code==409
    assert c.post('/workspace/deletion/confirm',headers=H,json={'token':token,'confirmation':'QUARANTINE THIS WORKSPACE'}).status_code==200
    assert c.get('/workspace',headers=H).status_code==423
    assert c.get('/workspace/export',headers=H).status_code==200
    with Session(engine) as s:
        with pytest.raises(ValueError):purge_quarantined(s,Base.WorkspaceRecord,Conversation,Message,Product,'PERMANENTLY PURGE QUARANTINED WORKSPACE',True)
    assert c.post('/workspace/deletion/restore',headers=H,json={'token':'','confirmation':'RESTORE THIS WORKSPACE'}).status_code==200
    assert all(x['mode']=='human' for x in c.get('/conversations',headers=H).json())
    token=c.post('/workspace/deletion/request',headers=H).json()['token'];c.post('/workspace/deletion/confirm',headers=H,json={'token':token,'confirmation':'QUARANTINE THIS WORKSPACE'})
    with Session(engine) as s:
        r=s.get(Base.WorkspaceRecord,'workspace:lifecycle');r.data={**r.data,'purge_after':(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()};s.commit()
        assert purge_quarantined(s,Base.WorkspaceRecord,Conversation,Message,Product,'PERMANENTLY PURGE QUARANTINED WORKSPACE')['dry_run']
        assert s.get(Product,1) is not None
        assert purge_quarantined(s,Base.WorkspaceRecord,Conversation,Message,Product,'PERMANENTLY PURGE QUARANTINED WORKSPACE',True)['purged']
        assert s.get(Product,1) is None
    assert c.get('/workspace',headers=H).status_code==423

def test_schema_baseline_and_backup_authentication(system,tmp_path):
    import io,base64,os
    from migrations import inspect_schema,register_baseline
    from backups import encrypt_stream,verify_archive
    _,_,engine=system
    assert inspect_schema(engine)['compatible']
    register_baseline(engine,Base.WorkspaceRecord)
    with Session(engine) as s:assert s.get(Base.WorkspaceRecord,'schema:version').data['version']==1
    key=base64.urlsafe_b64encode(os.urandom(32)).decode();path=tmp_path/'synthetic.ncb'
    with path.open('wb') as f:encrypt_stream(io.BytesIO(b'SYNTHETIC QA DATABASE'),f,key)
    assert verify_archive(path,key)['plaintext_written'] is False
    raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw)
    with pytest.raises(Exception):verify_archive(path,key)
