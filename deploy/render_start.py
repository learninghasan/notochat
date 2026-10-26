"""Fail closed before imports can create an ephemeral SQLite database."""
import os
import sys
from sqlalchemy.engine import make_url


def validate(env):
    try:
        url = make_url(env.get('DATABASE_URL', ''))
    except Exception:
        raise ValueError('Set DATABASE_URL to a durable PostgreSQL database') from None
    if url.drivername != 'postgresql+psycopg':
        raise ValueError('DATABASE_URL must use postgresql+psycopg://; SQLite is not supported on Render')
    for name in ('APP_TOKEN', 'INTERNAL_API_SECRET'):
        if len(env.get(name, '')) < 32:
            raise ValueError(f'Set {name} to an approved secret of at least 32 characters')
    from cryptography.fernet import Fernet
    try:
        Fernet(env.get('CREDENTIAL_ENCRYPTION_KEY', '').encode())
    except Exception:
        raise ValueError('Set CREDENTIAL_ENCRYPTION_KEY to an approved Fernet key') from None
    for name in ('ENABLE_LIVE_SEND', 'ENABLE_EMAIL_SEND', 'SSLCOMMERZ_LIVE'):
        if env.get(name, '0') != '0':
            raise ValueError(f'{name} must remain 0 for the free testing deployment')
    if env.get('WIDGET_ENABLED','0')!='0' and env.get('PILOT_WEBSITE_CHAT')!='1':
        raise ValueError('Website chat requires explicit PILOT_WEBSITE_CHAT=1')
    if env.get('APP_ENV') != 'production' or env.get('SEED_SAMPLE_DATA') != '0':
        raise ValueError('Require APP_ENV=production and SEED_SAMPLE_DATA=0')


if __name__ == '__main__':
    try:
        validate(os.environ)
    except ValueError as error:
        sys.exit(str(error))
    os.execvp('uvicorn', ['uvicorn', 'server:app', '--host', '0.0.0.0', '--port', os.getenv('PORT', '10000'), '--workers', '1'])
