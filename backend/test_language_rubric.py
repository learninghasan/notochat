"""Synthetic safety/grounding rubric, not native-human linguistic review."""
import pytest
from natural_reply import acceptable

@pytest.mark.parametrize('candidate,facts,expected',[
 ('জি, এই শার্টটি ৳১৩৯০। সাইজটি বলবেন?','Navy Shirt · ৳1390 · 8 in stock',True),
 ('Ji vai, shirt er dam 1390. Kon size lagbe?','Navy Shirt · ৳1390 · 8 in stock',True),
 ('The shirt is BDT 1390. Which size would you like?','Navy Shirt · ৳1390 · 8 in stock',True),
 ('মাত্র ৳৯৯৯!','Navy Shirt · ৳1390 · 8 in stock',False),
 ('Apnar order confirmed','Please share delivery details',False),
 ('ফ্রি ডেলিভারি পাবেন','Delivery BDT 130',False),
 ('Pay at https://evil.example','Delivery BDT 130',False),
 ('অর্ডার কনফার্ম হয়ে গেছে','Please share delivery details',False),
])
def test_synthetic_grounding_rubric(candidate,facts,expected):assert acceptable(candidate,facts) is expected

import asyncio,json
from test_completion import system,H,website,send_website,mock_client

@pytest.mark.parametrize('question,reply',[('এই শার্টের দাম কত?','জি, সাইজটি বলবেন?'),('Shirt er dam koto vai?','Ji vai, kon size lagbe?'),('What does the shirt cost?','Which size would you prefer?')])
def test_synthetic_language_pipeline_preserves_verified_facts(system,monkeypatch,question,reply):
    app,c,engine=system
    v=c.post('/agent/versions',headers=H,json={'auto_reply':True,'natural_replies':True}).json();c.post('/agent/versions/'+v['id']+'/publish',headers=H)
    cid,wh=website(c,monkeypatch);monkeypatch.setenv('OPENAI_API_KEY','fake');monkeypatch.setenv('OPENAI_MODEL','fake')
    intent={'intent':'product','product_ids':[2],'items':[],'customer':'','phone':'','address':''}
    def response(url,args):
        content={'text':reply} if args['json']['text']['format']['name']=='customer_phrasing' else intent
        return {'output':[{'content':[{'type':'output_text','text':json.dumps(content,ensure_ascii=False)}]}],'usage':{'input_tokens':10,'output_tokens':10}}
    calls=mock_client(monkeypatch,post_result=response)
    send_website(c,engine,wh,question);asyncio.run(app.state.run_jobs())
    text=c.get(f'/conversations/{cid}/messages',headers=H).json()[-1]['text']
    assert text.startswith(reply) and '1390' in text and 'Navy Linen Shirt' in text and len(calls)==2
    assert c.get('/workspace',headers=H).json()['orders']==[]
