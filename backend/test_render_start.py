"""The free hosting entrypoint must never silently fall back to ephemeral data."""
import importlib.util
from pathlib import Path
import pytest
from cryptography.fernet import Fernet

spec = importlib.util.spec_from_file_location('render_start', Path(__file__).resolve().parents[1] / 'deploy/render_start.py')
startup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(startup)

@pytest.fixture
def config():
    return {'DATABASE_URL': 'postgresql+psycopg://test:test@localhost/test',
            'APP_TOKEN': 'x'*32, 'INTERNAL_API_SECRET': 'y'*32,
            'CREDENTIAL_ENCRYPTION_KEY': Fernet.generate_key().decode(),
            'APP_ENV': 'production', 'SEED_SAMPLE_DATA': '0'}

def test_valid_config(config):
    startup.validate(config)

@pytest.mark.parametrize('key,value', [
    ('DATABASE_URL', 'sqlite:///tmp.db'), ('DATABASE_URL', ''),
    ('APP_TOKEN', ''), ('INTERNAL_API_SECRET', 'short'),
    ('CREDENTIAL_ENCRYPTION_KEY', 'invalid'), ('ENABLE_LIVE_SEND', '1'),
    ('ENABLE_EMAIL_SEND', '1'), ('SSLCOMMERZ_LIVE', '1'),
    ('WIDGET_ENABLED', '1'), ('APP_ENV', 'development'), ('SEED_SAMPLE_DATA', '1'),
])
def test_reject_unsafe_startup_without_disclosing_secrets(config, key, value):
    with pytest.raises(ValueError) as error:
        startup.validate({**config, key: value})
    for secret in (config['APP_TOKEN'], config['INTERNAL_API_SECRET'], config['CREDENTIAL_ENCRYPTION_KEY']):
        assert secret not in str(error.value)


def test_explicit_website_pilot_keeps_external_sends_blocked(config):
    enabled={**config,'WIDGET_ENABLED':'1','PILOT_WEBSITE_CHAT':'1'}
    startup.validate(enabled)
    with pytest.raises(ValueError):startup.validate({**enabled,'ENABLE_LIVE_SEND':'1'})
