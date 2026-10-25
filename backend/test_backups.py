import base64,io,secrets,sqlite3
import pytest
from cryptography.exceptions import InvalidTag
from backups import encrypt_stream,decrypt_stream,backup


def test_encrypted_backup_roundtrip_and_truncation_tamper_detection():
    key=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode();plain=b'private customer data'*10000
    out=io.BytesIO();encrypt_stream(io.BytesIO(plain),out,key);encrypted=out.getvalue()
    assert b'private customer data' not in encrypted
    recovered=io.BytesIO();decrypt_stream(io.BytesIO(encrypted),recovered,key);assert recovered.getvalue()==plain
    for corrupted in [encrypted[:-16],encrypted[:50]+bytes([encrypted[50]^1])+encrypted[51:]]:
        with pytest.raises((ValueError,InvalidTag)):decrypt_stream(io.BytesIO(corrupted),io.BytesIO(),key)


def test_sqlite_backup_is_consistent_sql_and_file_is_private(tmp_path):
    source=tmp_path/'source.db';connection=sqlite3.connect(source);connection.execute('CREATE TABLE sample (name TEXT)');connection.execute('INSERT INTO sample VALUES (?)',('Customer',));connection.commit();connection.close()
    key=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode();output=tmp_path/'backup.ncb'
    backup('sqlite:///'+str(source),output,key)
    assert output.stat().st_mode&0o777==0o600
    sql=io.BytesIO()
    with output.open('rb') as f:decrypt_stream(f,sql,key)
    restored=sqlite3.connect(':memory:');restored.executescript(sql.getvalue().decode())
    assert restored.execute('SELECT name FROM sample').fetchone()[0]=='Customer'
