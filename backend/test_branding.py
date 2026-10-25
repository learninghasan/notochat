import pytest
from test_business import gateway,call

def test_branding_isolation_roles_and_injection(gateway,monkeypatch):
    c,g=gateway
    body={'name':'Peoniara <sample>','primary_color':'#176b5b','widget_greeting':'Hello <script>sample</script>','receipt_footer':'Synthetic only','requested_domain':'chat.example.test'}
    assert call(c,'org_A','PUT','/branding',body,role='member').status_code==403
    assert call(c,'org_A','PUT','/branding',body).status_code==200
    assert call(c,'org_B','GET','/branding').json()['name']=='NotoChat'
    assert call(c,'org_A','GET','/branding').json()['domain_status']=='pending_platform_verification'
    for changes in ({'primary_color':'#ffffff'},{'logo_data_url':'https://example.test/logo.svg'},{'logo_data_url':'data:image/svg+xml;base64,AAAA'},{'name':'bad\nHeader'},{'requested_domain':'https://other.test/path'}):
        assert call(c,'org_A','PUT','/branding',{**body,**changes}).status_code==422
    monkeypatch.setenv('WIDGET_ENABLED','1')
    # Tenant config is intentionally distinct from legacy environment defaults.
    g.workspace('org_A').state.channel_configuration=lambda:{'WIDGET_ENABLED':'1'}
    from cryptography.fernet import Fernet
    monkeypatch.setenv('CREDENTIAL_ENCRYPTION_KEY',Fernet.generate_key().decode())
    assert call(c,'org_A','PUT','/connections/configuration',{'widget_enabled':True}).status_code==200
    r=c.get('/business/org_A/widget');assert r.status_code==200,r.text
    assert 'Peoniara &lt;sample&gt;' in r.text and '<script>sample</script>' not in r.text
    monkeypatch.setenv('VERIFIED_TENANT_DOMAINS_JSON','{"chat.example.test":"org_A"}')
    assert 'Peoniara &lt;sample&gt;' in c.get('/widget',headers={'host':'chat.example.test'}).text
    assert c.get('/business/org_B/widget',headers={'host':'chat.example.test'}).status_code==404
