"""Offline tenant-scoped purge. Defaults to read-only planning, never auto-runs."""
import argparse,os
from sqlalchemy.orm import Session
from sqlalchemy import delete,select
from server import app as gateway,meta_accounts,registry
from main import Base,Conversation,Message,Product
from workspace_lifecycle import purge_quarantined

def main():
    p=argparse.ArgumentParser();p.add_argument('--organization',required=True);p.add_argument('--execute',action='store_true');p.add_argument('--confirm',required=True);args=p.parse_args()
    if args.execute and os.getenv('NOTOCHAT_ALLOW_PURGE')!='1':raise SystemExit('Explicit operator enablement NOTOCHAT_ALLOW_PURGE=1 required; production deletion needs separate authorization')
    if args.confirm!='PURGE '+args.organization:raise SystemExit('Confirmation must identify the exact organization')
    with gateway.engine.connect() as c:
        if not c.execute(select(registry.c.organization_id).where(registry.c.organization_id==args.organization)).first():raise SystemExit('Unknown organization; no workspace created')
    app=gateway.workspace(args.organization)
    with Session(app.state.engine) as s:result=purge_quarantined(s,Base.WorkspaceRecord,Conversation,Message,Product,'PERMANENTLY PURGE QUARANTINED WORKSPACE',args.execute)
    if args.execute:
        with gateway.engine.begin() as c:c.execute(delete(meta_accounts).where(meta_accounts.c.organization_id==args.organization))
    print(result)
if __name__=='__main__':main()
