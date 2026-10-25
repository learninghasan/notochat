"""Operator-owned verified public widget routing. Host never grants authentication."""
import json,os,re

def organization_for_host(host):
    raw=os.getenv('VERIFIED_TENANT_DOMAINS_JSON','{}')
    mapping=json.loads(raw)
    if not isinstance(mapping,dict):raise ValueError('Invalid verified domain configuration')
    for domain,org in mapping.items():
        if not isinstance(domain,str) or not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}',domain) or not isinstance(org,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',org):raise ValueError('Invalid verified domain mapping')
    return mapping.get(host.lower().split(':')[0])
