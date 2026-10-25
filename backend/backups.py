"""Streaming authenticated database backups. Keys never appear in archives or logs."""
import argparse
import base64
import io
import os
import secrets
import sqlite3
import struct
import subprocess
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy.engine import make_url
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

MAGIC=b'NOTOBAK1';CHUNK=65536

def key(master,salt):
    raw=base64.urlsafe_b64decode(master)
    if len(raw)!=32:raise ValueError('Backup key must encode 32 random bytes')
    return HKDF(algorithm=hashes.SHA256(),length=32,salt=salt,info=MAGIC).derive(raw)


def encrypt_stream(source,target,master):
    salt=secrets.token_bytes(16);prefix=secrets.token_bytes(8);header=MAGIC+salt+prefix
    cipher=AESGCM(key(master,salt));target.write(header);index=0
    while True:
        data=source.read(CHUNK);counter=struct.pack('!I',index)
        encrypted=cipher.encrypt(prefix+counter,data,header+counter)
        target.write(struct.pack('!I',len(encrypted)));target.write(encrypted);index+=1
        if not data:break


def decrypt_stream(source,target,master):
    header=source.read(32)
    if len(header)!=32 or not header.startswith(MAGIC):raise ValueError('Invalid backup header')
    salt=header[8:24];prefix=header[24:32];cipher=AESGCM(key(master,salt));index=0
    while True:
        length=source.read(4)
        if len(length)!=4:raise ValueError('Truncated backup')
        size=struct.unpack('!I',length)[0]
        if not 16<=size<=CHUNK+16:raise ValueError('Invalid chunk size')
        data=source.read(size)
        if len(data)!=size:raise ValueError('Truncated backup')
        counter=struct.pack('!I',index);plain=cipher.decrypt(prefix+counter,data,header+counter);index+=1
        if not plain:
            if source.read(1):raise ValueError('Unexpected trailing backup data')
            return
        target.write(plain)


class SQLiteDump(io.RawIOBase):
    def __init__(self,path):
        self.db=sqlite3.connect('file:'+str(Path(path).resolve())+'?mode=ro',uri=True);self.db.execute('BEGIN');self.lines=iter(self.db.iterdump());self.buffer=b'';self.finished=False
    def read(self,size=-1):
        if size<0:raise ValueError('Read backup in bounded chunks')
        while len(self.buffer)<size and not self.finished:
            try:self.buffer+=(next(self.lines)+'\n').encode()
            except StopIteration:self.finished=True
        result,self.buffer=self.buffer[:size],self.buffer[size:];return result
    def close(self):self.db.close();super().close()


def backup(database_url,output,master):
    url=make_url(database_url);output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise FileExistsError('Backup output already exists')
    temporary=output.with_name(output.name+'.partial-'+secrets.token_hex(6));process=None;source=None
    try:
        if url.drivername.startswith('postgresql'):
            env={**os.environ,'PGHOST':url.host or 'localhost','PGPORT':str(url.port or 5432),'PGUSER':url.username or '','PGPASSWORD':url.password or '','PGDATABASE':url.database or ''}
            # Connection credentials remain in the child environment, never process arguments.
            process=subprocess.Popen(['pg_dump','--format=custom','--no-owner','--no-acl'],env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL);source=process.stdout
        elif url.drivername.startswith('sqlite') and url.database and url.database!=':memory:':source=SQLiteDump(url.database)
        else:raise ValueError('A file-backed SQLite or PostgreSQL database is required')
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as target:encrypt_stream(source,target,master)
        if process and process.wait()!=0:raise RuntimeError('pg_dump failed; no completed backup was saved')
        os.link(temporary,output);temporary.unlink()
    finally:
        if source:source.close()
        if process and process.poll() is None:process.kill();process.wait()
        if temporary.exists():temporary.unlink()
    return output



def verify_archive(path,master):
    class Discard:
        def write(self,chunk):return len(chunk)
    with open(path,'rb') as source:decrypt_stream(source,Discard(),master)
    return {'authenticated':True,'plaintext_written':False}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output');p.add_argument('--verify',action='store_true');p.add_argument('--decrypt',action='store_true');p.add_argument('--input');args=p.parse_args()
    master=os.environ.get('BACKUP_ENCRYPTION_KEY','')
    if not master:raise SystemExit('Configure BACKUP_ENCRYPTION_KEY outside the database and backup directory')
    if args.verify:
        if not args.input:raise SystemExit("--input is required")
        print(verify_archive(args.input,master));raise SystemExit(0)
    if not args.output:raise SystemExit("--output is required")
    if args.decrypt:
        if not args.input:raise SystemExit('--input is required for decryption')
        path=Path(args.output)
        if path.exists():raise SystemExit('Decryption output already exists')
        temporary=path.with_name(path.name+'.partial-'+secrets.token_hex(6))
        try:
            with open(args.input,'rb') as source,os.fdopen(os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as target:decrypt_stream(source,target,master)
            os.link(temporary,path);temporary.unlink()
        finally:
            if temporary.exists():temporary.unlink()
        print('Backup authenticated and decrypted to the requested file. Restore using the appropriate database tool.')
    else:
        backup(os.environ['DATABASE_URL'],args.output,master);print('Encrypted database backup saved.')
