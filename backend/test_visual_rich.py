import base64,io
from PIL import Image
from test_completion import system,H
from test_attachments import media_shop,provider,incoming,event

def picture(color):
    b=io.BytesIO();Image.new('RGB',(32,32),color).save(b,format='PNG');return base64.b64encode(b.getvalue()).decode()
def test_visual_exact_and_top_three_are_bounded_and_review_only(system):
    _,c,_=system
    raw=picture('blue')
    assert c.put('/products/1/visual-image',headers=H,json={'content_base64':raw}).status_code==200
    assert c.put('/products/2/visual-image',headers=H,json={'content_base64':picture('red')}).status_code==200
    r=c.post('/conversations/1/visual-match',headers=H,json={'content_base64':raw}).json()
    assert r['matches'][0]['product']['id']==1 and r['matches'][0]['exact_pixels'] is True
    assert r['order_created'] is False
    assert c.put('/products/1/visual-image',headers=H,json={'content_base64':base64.b64encode(b'<script>bad</script>').decode()}).status_code==422

def test_catalog_cards_idempotence_and_current_prices(media_shop,monkeypatch):
    _,c,_=media_shop;incoming(c,event(kind='image'))
    cid=c.get('/conversations',headers=H).json()[-1]['id'];path=f'/conversations/{cid}/catalog-cards'
    body={'request_id':'test-card-request','product_ids':[1,2]}
    r=c.post(path,headers=H,json=body);assert r.status_code==200,r.text
    assert c.post(path,headers=H,json=body).json()['message_id']==r.json()['message_id']
    monkeypatch.setenv('ENABLE_LIVE_SEND','1')
    from test_completion import mock_client
    calls=mock_client(monkeypatch,post_result={'message_id':'fake-card'})
    sent=c.post(f'/conversations/{cid}/deliver',headers=H,json={'message_id':r.json()['message_id']});assert sent.status_code==200,sent.text
    assert calls[0][2]['json']['message']['attachment']['payload']['template_type']=='generic'
    fresh=c.post(path,headers=H,json={**body,'request_id':'test-card-fresh'}).json()
    c.put('/products/1',headers=H,json={'name':'Changed','price':1,'stock':1})
    assert c.post(f'/conversations/{cid}/deliver',headers=H,json={'message_id':fresh['message_id']}).status_code==409

from test_business import gateway,call

def test_visual_indexes_and_cards_do_not_cross_businesses(gateway):
    c,_=gateway
    for org in ('visual_A','visual_B'):call(c,org,'POST','/conversations',{'customer':org})
    p=call(c,'visual_A','POST','/products',{'name':'Private catalog','price':123,'stock':3}).json()
    assert call(c,'visual_A','PUT',f"/products/{p['id']}/visual-image",{'content_base64':picture('blue')}).status_code==200
    assert call(c,'visual_B','POST','/conversations/1/visual-match',{'content_base64':picture('blue')}).json()['matches']==[]
    assert call(c,'visual_B','POST','/conversations/1/catalog-cards',{'request_id':'cross-tenant-cards','product_ids':[p['id']]}).status_code==409
