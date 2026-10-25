from test_business import gateway,call

def setup(c):
    p=call(c,'org_A','POST','/products',{'name':'Synthetic cleanser','price':100,'stock':5}).json()
    chat=call(c,'org_A','POST','/conversations',{'customer':'Synthetic customer','channel':'Website'}).json()
    return p,chat

def test_corrections_sources_and_approval_retries(gateway):
    c,g=gateway;p,chat=setup(c)
    doc=call(c,'org_A','POST','/knowledge',{'title':'Synthetic returns','text':'Ask team before returning.'}).json()
    source=call(c,'org_A','GET','/knowledge/provenance').json()[0]
    edit={'expected_hash':source['source_hash'],'title':source['title'],'text':'Contact team with order ID.','source_note':'Synthetic merchant policy v2'}
    assert call(c,'org_B','PUT','/knowledge/'+doc['id']+'/correction',edit).status_code==404
    assert call(c,'org_A','PUT','/knowledge/'+doc['id']+'/correction',edit).status_code==200
    assert call(c,'org_A','PUT','/knowledge/'+doc['id']+'/correction',edit).status_code==409
    proposal={'request_id':'synthetic-review','conversation_id':chat['id'],'kind':'refund','detail':'Review request only'}
    a=call(c,'org_A','POST','/approvals',proposal).json()
    assert call(c,'org_A','POST','/approvals',proposal).json()['id']==a['id']
    decision={'decision':'approved','expected_source_hash':a['source_hash'],'note':'Proposal approved; no refund executed'}
    assert call(c,'org_B','POST','/approvals/'+a['id']+'/decision',decision).status_code==404
    assert call(c,'org_A','POST','/approvals/'+a['id']+'/decision',decision,role='member').status_code==403
    assert call(c,'org_A','POST','/approvals/'+a['id']+'/decision',decision).json()['execution']=='none'
    assert call(c,'org_A','POST','/approvals/'+a['id']+'/decision',decision).status_code==200
    b=call(c,'org_A','POST','/approvals',{**proposal,'request_id':'another-review'}).json()
    call(c,'org_A','PUT','/products/'+str(p['id']),{'name':p['name'],'price':101,'stock':5})
    assert call(c,'org_A','POST','/approvals/'+b['id']+'/decision',{**decision,'expected_source_hash':b['source_hash']}).status_code==409

def test_delivery_reorder_current_prices_and_no_purchase(gateway):
    c,g=gateway;p,chat=setup(c)
    rule={'enabled':True,'areas':[{'name':'Synthetic area','fee':20,'minimum':100,'slots':['Synthetic slot']}]}
    assert call(c,'org_A','PUT','/delivery/rules',rule).status_code==200
    order={'request_id':'synthetic-order','conversation_id':chat['id'],'customer':chat['customer'],'phone':'01700000000','address':'Synthetic address','items':[{'product_id':p['id'],'quantity':1,'expected_unit_price':100}],'delivery_charge':20,'delivery_area':'Synthetic area','delivery_slot':'Synthetic slot'}
    assert call(c,'org_A','POST','/orders',{**order,'delivery_charge':0}).status_code==409
    assert call(c,'org_A','POST','/orders',{**order,'delivery_slot':'invented'}).status_code==409
    created=call(c,'org_A','POST','/orders',order);assert created.status_code==200,created.text
    rid=created.json()['id']
    call(c,'org_A','PUT','/products/'+str(p['id']),{'name':p['name'],'price':150,'stock':0})
    draft=call(c,'org_A','POST','/orders/'+rid+'/reorder-draft',{'request_id':'synthetic-reorder'}).json()
    assert not draft['available'] and not draft['order_created'] and draft['requires_customer_confirmation']
    assert draft['items'][0]['expected_unit_price']==150 and len(draft['changes'])==2
    assert call(c,'org_A','POST','/orders/'+rid+'/reorder-draft',{'request_id':'synthetic-reorder'}).json()['id']==draft['id']
    assert call(c,'org_B','POST','/orders/'+rid+'/reorder-draft',{'request_id':'synthetic-reorder'}).status_code==404
    assert len(call(c,'org_A','GET','/customers/'+str(chat['id'])+'/profile').json()['orders'])==1
    assert call(c,'org_B','GET','/customers/'+str(chat['id'])+'/profile').status_code==404
    assert call(c,'org_A','POST','/orders',{**order,'request_id':'stale-reorder'}).status_code==409
    report=call(c,'org_A','GET','/commerce/report').json()
    assert report['confirmed_order_value_bdt']==120 and report['verified_revenue_bdt'] is None and report['dropoff_rate'] is None


def test_review_records_obey_channel_scopes_and_no_default_delivery_price(gateway):
    c,g=gateway;p,chat=setup(c)
    assert call(c,'org_A','GET','/workspace').json()['agent']['delivery_outside'] is None
    call(c,'org_A','POST','/approvals',{'request_id':'scoped-approval','conversation_id':chat['id'],'kind':'discount','detail':'Synthetic proposal'})
    call(c,'org_A','PUT','/access/policies/user_test',{'channels':['Messenger'],'assigned_only':False})
    assert call(c,'org_A','GET','/approvals',role='member').json()==[]
    assert call(c,'org_A','GET','/customers/'+str(chat['id'])+'/profile',role='member').status_code==404
