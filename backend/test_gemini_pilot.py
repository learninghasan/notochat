from test_business import gateway,call
def mock_client(monkeypatch,post_result,status=200):
 calls=[]
 class Response:
  status_code=status
  def raise_for_status(self):pass
  def json(self):return post_result
 class Client:
  def __init__(self,**kw):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*a):pass
  async def post(self,url,**kw):calls.append((url,kw));return Response()
 monkeypatch.setattr('httpx.AsyncClient',Client)
 return calls

def test_pilot_config_scope_and_no_actions(gateway,monkeypatch):
 c,g=gateway
 assert call(c,'org_A','POST','/ai/pilot/draft',{'question':'hello','public_or_redacted':True}).status_code==503
 monkeypatch.setenv('GEMINI_API_KEY','synthetic-key');monkeypatch.setenv('GEMINI_MODEL','test-model');monkeypatch.setenv('GEMINI_PILOT_ENABLED','1')
 assert call(c,'org_A','POST','/ai/pilot/draft',{'question':'hello'}).status_code==422
 assert call(c,'org_A','POST','/ai/pilot/draft',{'question':'hello','public_or_redacted':True},role='member').status_code==403
 calls=mock_client(monkeypatch,post_result={'candidates':[{'content':{'parts':[{'text':'Ask the team for current delivery fees.'}]}}],'usageMetadata':{'totalTokenCount':20}})
 before=call(c,'org_A','GET','/workspace').json()
 r=call(c,'org_A','POST','/ai/pilot/draft',{'question':'delivery fee?','public_or_redacted':True});assert r.status_code==200,r.text
 assert r.json()['sent'] is False and r.json()['requires_review'] and r.json()['cost'] is None
 after=call(c,'org_A','GET','/workspace').json()
 for key in ['orders','deliveries','jobs']:assert before[key]==after[key]
 assert call(c,'org_A','POST','/ai/pilot/draft',{'question':'again','public_or_redacted':True}).status_code==429
 assert call(c,'org_B','POST','/ai/pilot/draft',{'question':'hello','public_or_redacted':True}).status_code==200
 assert calls
 assert all('customer' not in c[1]['json']['contents'][0]['parts'][0]['text'] for c in calls)


def test_gemini_quota_has_no_paid_fallback(gateway,monkeypatch):
 c,g=gateway
 for k,v in {'GEMINI_API_KEY':'test','GEMINI_MODEL':'test-model','GEMINI_PILOT_ENABLED':'1'}.items():monkeypatch.setenv(k,v)
 calls=mock_client(monkeypatch,{},status=429)
 r=call(c,'org_A','POST','/ai/pilot/draft',{'question':'Public product question','public_or_redacted':True})
 assert r.status_code==429 and 'no paid fallback' in r.text
 assert len(calls)==1 and calls[0][0].startswith('https://generativelanguage.googleapis.com/')
 assert call(c,'org_A','POST','/ai/pilot/draft',{'question':'retry','public_or_redacted':True}).status_code==429
 assert len(calls)==1


def test_flash_reserves_output_for_visible_draft(gateway,monkeypatch):
 c,g=gateway
 for k,v in {'GEMINI_API_KEY':'test','GEMINI_MODEL':'gemini-2.5-flash','GEMINI_PILOT_ENABLED':'1'}.items():monkeypatch.setenv(k,v)
 calls=mock_client(monkeypatch,{'candidates':[{'content':{'parts':[{'text':'Welcome!'}]}}]})
 r=call(c,'org_A','POST','/ai/pilot/draft',{'question':'hello','public_or_redacted':True})
 assert r.status_code==200
 assert calls[0][1]['json']['generationConfig']=={'maxOutputTokens':800,'thinkingConfig':{'thinkingBudget':0}}


def test_provider_errors_do_not_expose_secrets(gateway,monkeypatch):
 c,g=gateway
 for k,v in {'GEMINI_API_KEY':'secret-fixture','GEMINI_MODEL':'test-model','GEMINI_PILOT_ENABLED':'1'}.items():monkeypatch.setenv(k,v)
 for status in [400,401,403,404,500]:
  calls=mock_client(monkeypatch,{'error':{'message':'secret-fixture private question'}},status=status)
  r=call(c,'org_'+str(status),'POST','/ai/pilot/draft',{'question':'hello','public_or_redacted':True})
  assert r.status_code==502 and str(status) in r.text
  assert 'secret-fixture' not in r.text and 'private question' not in r.text
  assert len(calls)==1


def test_empty_output_is_actionable_without_exposing_provider_content(gateway,monkeypatch):
 c,g=gateway
 for k,v in {'GEMINI_API_KEY':'test','GEMINI_MODEL':'test-model','GEMINI_PILOT_ENABLED':'1'}.items():monkeypatch.setenv(k,v)
 mock_client(monkeypatch,{'candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':[{'thought':True,'text':'private thought'}]}}]})
 r=call(c,'org_A','POST','/ai/pilot/draft',{'question':'hello','public_or_redacted':True})
 assert r.status_code==502 and 'output limit' in r.text and 'private thought' not in r.text
