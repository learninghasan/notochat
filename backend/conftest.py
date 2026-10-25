"""Set test storage before any module imports the application factory."""
import atexit
import os
import tempfile

_directory=tempfile.TemporaryDirectory(prefix='notochat-tests-')
atexit.register(_directory.cleanup)
os.environ['DATABASE_URL']='sqlite:///'+_directory.name+'/legacy.db'
os.environ['APP_TOKEN']='test-token'
os.environ['SEED_SAMPLE_DATA']='1'
os.environ['TENANT_SQLITE_DIR']=_directory.name+'/businesses'
