"""Versioned baseline for the current additive schema; unsupported drift fails closed."""
from sqlalchemy import inspect
CURRENT_VERSION=1
EXPECTED={'conversations':{'id','customer','channel','mode'},'messages':{'id','conversation_id','role','text'},'products':{'id','name','price','stock'},'workspace_records':{'id','kind','data'}}
def inspect_schema(engine):
    inspector=inspect(engine);schema=engine.get_execution_options().get('schema_translate_map',{}).get(None)
    missing={}
    for table,columns in EXPECTED.items():
        actual={c['name'] for c in inspector.get_columns(table,schema=schema)} if inspector.has_table(table,schema=schema) else set()
        if columns-actual:missing[table]=sorted(columns-actual)
    return {'version':CURRENT_VERSION,'compatible':not missing,'missing':missing}
def register_baseline(engine,Record):
    from sqlalchemy.orm import Session
    from sqlalchemy import select
    report=inspect_schema(engine)
    if not report['compatible']:raise RuntimeError('Unsupported schema drift; explicit migration and backup are required')
    with Session(engine) as s:
        s.scalar(select(Record).where(Record.id=='agent:live').with_for_update())
        r=s.get(Record,'schema:version')
        if r and r.data['version']>CURRENT_VERSION:raise RuntimeError('Database is newer than this application; restore compatible code, do not downgrade data')
        if not r:s.add(Record(id='schema:version',kind='schema_version',data={'version':CURRENT_VERSION}))
        s.commit()
    return report
