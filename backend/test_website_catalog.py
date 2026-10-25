import copy
import pytest
from test_business import gateway,call
import website_catalog as wc

def product(pid=1):
    return {'id':pid,'name':'A &amp; B','description':'<script>bad()</script><p>Merchant text</p>','permalink':f'https://peoniara.com/product/sample-{pid}/','prices':{'price':'43000','regular_price':'47000','sale_price':'43000','currency_code':'BDT','currency_minor_unit':2},'is_in_stock':True,'is_purchasable':True,'type':'simple','images':[{'src':'https://evil.test/a.png'}],'variations':[]}

def test_normalization_and_bounded_pages(monkeypatch):
    p=wc.normalize(product(),wc.SOURCES['peoniara'])
    assert p['price']=='430' and p['stock_quantity'] is None and p['shipping_quote'] is None
    assert p['description']=='Merchant text' and p['name']=='A & B' and not p['images']
    for patch in [{'id':True},{'permalink':'https://peoniara.com.evil.test/product/a'},{'is_in_stock':'yes'}]:
        with pytest.raises(ValueError):wc.normalize({**product(),**patch},wc.SOURCES['peoniara'])
    monkeypatch.setattr(wc,'read',lambda url:([product()],{'x-wp-totalpages':'11','x-wp-total':'1001'}))
    with pytest.raises(ValueError):wc.fetch_catalog('peoniara')
    monkeypatch.setattr(wc,'read',lambda url:([product()],{'x-wp-totalpages':'1','x-wp-total':'2'}))
    with pytest.raises(ValueError):wc.fetch_catalog('peoniara')

def test_tenant_sync_failure_recheck_and_roles(gateway,monkeypatch):
    c,g=gateway
    monkeypatch.setattr(wc,'fetch_catalog',lambda source:[wc.normalize(product(),wc.SOURCES[source])])
    assert call(c,'org_A','PUT','/website-catalog/config',{'source':'http://localhost'}).status_code==422
    assert call(c,'org_A','PUT','/website-catalog/config',{'source':'peoniara'},role='member').status_code==403
    assert call(c,'org_A','PUT','/website-catalog/config',{'source':'peoniara'}).status_code==200
    first=call(c,'org_A','POST','/website-catalog/sync',{});assert first.status_code==200,first.text
    assert first.json()['products'][0]['stock_quantity'] is None
    assert call(c,'org_A','POST','/website-catalog/sync',{}).status_code==429
    assert call(c,'org_B','GET','/website-catalog').json()['products']==[]
    assert call(c,'org_A','GET','/catalog').json()==[] # never invent reservable local inventory
    monkeypatch.setattr(wc,'read',lambda url:({**product(),'prices':{**product()['prices'],'price':'45000'}},{}))
    check=call(c,'org_A','POST','/website-catalog/products/1/recheck',{}).json()
    assert check['product']['price']=='450' and check['requires_operator_confirmation'] and not check['order_created']
    assert call(c,'org_A','POST','/website-catalog/products/2/recheck',{}).status_code==404
    original=wc.now;monkeypatch.setattr(wc,'now',lambda:original()+wc.timedelta(minutes=2))
    def fail(source):raise ValueError('upstream secret must not leak')
    monkeypatch.setattr(wc,'fetch_catalog',fail)
    failure=call(c,'org_A','POST','/website-catalog/sync',{});assert failure.status_code==502 and 'secret' not in failure.text
    last=call(c,'org_A','GET','/website-catalog').json();assert last['stale'] and last['products']==first.json()['products']
    monkeypatch.setattr(wc,'now',lambda:original()+wc.timedelta(minutes=4))
    monkeypatch.setattr(wc,'fetch_catalog',lambda source:[])
    assert call(c,'org_A','POST','/website-catalog/sync',{}).json()['products']==[]
