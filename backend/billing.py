"""Verified hosted recharge and integer-paisa credit ledger (sandbox by default)."""
import hashlib
import os
import secrets
from datetime import datetime,timezone
from decimal import Decimal,ROUND_CEILING,InvalidOperation
from urllib.parse import parse_qs,urlsplit
from fastapi import Depends,HTTPException,Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.orm import Session

class Recharge(BaseModel):
    amount_bdt:int=Field(ge=10,le=50000)
    name:str=Field(min_length=1,max_length=100)
    email:str=Field(pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$',max_length=254)
    phone:str=Field(min_length=5,max_length=40)


def install_billing(app,engine,Record,authorize,session,put,notify,records):
    from billing_email import install_email
    install_email(app,engine,Record,authorize,session,put)
    def enabled():return os.getenv('AI_BILLING_ENABLED')=='1' or os.getenv('APP_ENV')=='production'
    def provider():
        if not os.getenv('SSLCOMMERZ_STORE_ID') or not os.getenv('SSLCOMMERZ_STORE_PASSWORD'):raise HTTPException(503,'Hosted recharge gateway is not configured')
        return 'https://securepay.sslcommerz.com' if os.getenv('SSLCOMMERZ_LIVE')=='1' else 'https://sandbox.sslcommerz.com'
    def wallet(s):
        r=s.scalar(select(Record).where(Record.id=='billing:wallet').with_for_update())
        if not r:
            r=Record(id='billing:wallet',kind='wallet',data={'balance_paisa':0,'sandbox_balance_paisa':0});s.add(r);s.flush()
        return r
    with Session(engine) as s:wallet(s);s.commit()

    def trial_policy():
        # No implied monetary offer: operator must explicitly select all terms.
        amount=os.getenv('PAGE_CONNECT_TRIAL_PAISA','')
        policy=os.getenv('PAGE_CONNECT_TRIAL_POLICY_ID','')
        scope=os.getenv('PAGE_CONNECT_TRIAL_SCOPE','')
        if not amount and not policy and not scope:return None
        if not amount.isascii() or not amount.isdigit() or not 0<int(amount)<=5_000_000 or not policy or len(policy)>100 or scope!='workspace':
            raise HTTPException(503,'Page-connect trial policy requires an explicit positive paisa amount, policy ID and workspace scope')
        return {'amount_paisa':int(amount),'policy_id':policy,'scope':scope}

    def grant_page_trial(s,page_id):
        # Called only after authenticated Meta subscription succeeds. Wallet row
        # serializes retries/concurrent connections, together with the ledger write.
        w=wallet(s)
        rid='ledger:page-connect-trial'
        prior=s.get(Record,rid)
        if prior:return {'granted':False,'already_granted':True}
        policy=trial_policy()
        if not policy:return {'granted':False,'configured':False}
        w.data={**w.data,'balance_paisa':w.data['balance_paisa']+policy['amount_paisa']}
        put(s,'ledger',{'type':'page_connect_trial','paisa':policy['amount_paisa'],'policy_id':policy['policy_id'],'scope':policy['scope'],'page_id':page_id,'created_at':datetime.now(timezone.utc).isoformat()},rid)
        return {'granted':True,**policy}

    app.state.grant_page_trial=grant_page_trial

    def require_credit(s,action='text'):
        if not enabled():return
        if action=='audio':
            try:
                rate=Decimal(os.getenv('AI_AUDIO_PAISA_PER_MINUTE','0'))
                if not rate.is_finite() or rate<=0:raise ValueError()
            except (InvalidOperation,ValueError):raise HTTPException(503,'Operator must configure and disclose audio pricing')
            if wallet(s).data['balance_paisa']<=0:raise HTTPException(402,'AI credit exhausted. Recharge to resume automatic processing.')
            return
        try:
            rates=[Decimal(os.getenv(key,'0')) for key in ['AI_INPUT_PAISA_PER_MILLION','AI_OUTPUT_PAISA_PER_MILLION']]
            if any(not rate.is_finite() or rate<=0 for rate in rates):raise ValueError()
        except (InvalidOperation,ValueError):raise HTTPException(503,'Operator must configure and disclose AI usage pricing')
        if wallet(s).data['balance_paisa']<=0:raise HTTPException(402,'AI credit exhausted. Recharge to resume automatic processing.')

    def charge(s,usage):
        if not enabled():return
        rid='ledger:usage:'+hashlib.sha256(usage['id'].encode()).hexdigest()
        w=wallet(s)  # Serialize before checking idempotency, including concurrent retries.
        if s.get(Record,rid):return
        if usage.get('action')=='audio':
            try:
                duration=Decimal(str(usage.get('duration_seconds','NaN')));rate=Decimal(os.getenv('AI_AUDIO_PAISA_PER_MINUTE','0'))
                if not duration.is_finite() or duration<=0 or not rate.is_finite() or rate<=0:raise ValueError()
            except (InvalidOperation,ValueError):raise HTTPException(502,'Provider duration and configured audio rate are required; no fabricated charge')
            cost=int((duration*rate/60).to_integral_value(rounding=ROUND_CEILING));input_rate=rate;output_rate=Decimal(0)
        else:
            tokens=usage.get('tokens',{})
            if any(not isinstance(tokens.get(k),int) or isinstance(tokens.get(k),bool) or tokens[k]<0 for k in ['input_tokens','output_tokens']):raise HTTPException(502,'Provider did not report billable token usage')
            input_rate=Decimal(os.getenv('AI_INPUT_PAISA_PER_MILLION','0'));output_rate=Decimal(os.getenv('AI_OUTPUT_PAISA_PER_MILLION','0'))
            if input_rate<=0 or output_rate<=0:raise HTTPException(503,'AI usage rates are not configured')
            cost=int(((Decimal(tokens['input_tokens'])*input_rate+Decimal(tokens['output_tokens'])*output_rate)/1000000).to_integral_value(rounding=ROUND_CEILING))
        w=wallet(s);previous=w.data['balance_paisa'];w.data={**w.data,'balance_paisa':previous-cost}
        put(s,'ledger',{'type':'usage','paisa':-cost,'usage_id':usage['id'],'action':usage.get('action','text'),'duration_seconds':usage.get('duration_seconds'),'input_rate':str(input_rate),'output_rate':str(output_rate),'created_at':datetime.now(timezone.utc).isoformat()},rid)
        if previous>100 and w.data['balance_paisa']<=100:
            notify(s,'AI credit is low','Recharge your workspace to keep automatic processing available.')
            app.state.queue_credit_email(s,hashlib.sha256(usage['id'].encode()).hexdigest())

    def snapshot(s):
        w=wallet(s)
        return {'currency':'BDT','balance':w.data['balance_paisa']/100,'balance_paisa':w.data['balance_paisa'],'sandbox_balance':w.data.get('sandbox_balance_paisa',0)/100,'metering_enabled':enabled(),'payments_connected':bool(os.getenv('SSLCOMMERZ_STORE_ID') and os.getenv('SSLCOMMERZ_STORE_PASSWORD')),'sandbox':os.getenv('SSLCOMMERZ_LIVE')!='1','usage':records(s,'usage'),'ledger':records(s,'ledger'),'trial_policy':trial_policy(),'pricing':{'audio_paisa_per_minute':os.getenv('AI_AUDIO_PAISA_PER_MINUTE'),'input_paisa_per_million':os.getenv('AI_INPUT_PAISA_PER_MILLION'),'output_paisa_per_million':os.getenv('AI_OUTPUT_PAISA_PER_MILLION')},'note':'Recharge credits are posted only after server-to-server validation. Sandbox payments are test credits. Usage metering is '+('enabled at the displayed operator-configured rates.' if enabled() else 'disabled; no AI credit deductions are applied.')}
    app.state.require_credit=require_credit;app.state.charge_usage=charge;app.state.billing_snapshot=snapshot

    @app.post('/billing/recharge',dependencies=[Depends(authorize)])
    async def recharge(body:Recharge,request:Request,principal=Depends(authorize),s:Session=Depends(session)):
        if principal and principal.get('role') not in ('owner','admin'):raise HTTPException(403,'Owner or admin permission required')
        base=provider();backend=os.getenv('PUBLIC_BACKEND_URL','').rstrip('/')
        if not backend.startswith('https://'):raise HTTPException(503,'Set PUBLIC_BACKEND_URL to the public HTTPS gateway origin')
        suffix='/business/'+principal['organization_id'] if principal else ''
        callback=backend+suffix+'/payments'
        tran_id='nc'+secrets.token_hex(13)
        put(s,'payments',{'tran_id':tran_id,'expected_paisa':body.amount_bdt*100,'status':'pending','sandbox':base.startswith('https://sandbox.'),'created_at':datetime.now(timezone.utc).isoformat()},'payment:'+tran_id);s.commit()
        form={'store_id':os.environ['SSLCOMMERZ_STORE_ID'],'store_passwd':os.environ['SSLCOMMERZ_STORE_PASSWORD'],'total_amount':str(body.amount_bdt),'currency':'BDT','tran_id':tran_id,'success_url':callback+'/return','fail_url':callback+'/return','cancel_url':callback+'/return','ipn_url':callback+'/ipn','shipping_method':'NO','product_name':'NotoChat AI credit','product_category':'top up','product_profile':'non-physical-goods','cus_name':body.name,'cus_email':body.email,'cus_phone':body.phone,'cus_add1':'Digital service','cus_city':'Dhaka','cus_country':'Bangladesh'}
        import httpx
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                r=await client.post(base+'/gwprocess/v4/api.php',data=form);r.raise_for_status();result=r.json()
            checkout=result.get('GatewayPageURL','');parsed=urlsplit(checkout)
            if result.get('status')!='SUCCESS' or parsed.scheme!='https' or parsed.hostname!=urlsplit(base).hostname:raise ValueError()
        except (httpx.HTTPError,ValueError):raise HTTPException(502,'Recharge session could not be created; no credit was added')
        return {'checkout_url':checkout,'tran_id':tran_id,'sandbox':base.startswith('https://sandbox.')}

    @app.post('/payments/ipn')
    async def ipn(request:Request,s:Session=Depends(session)):
        raw=await request.body()
        if len(raw)>20000:raise HTTPException(413,'Payment callback too large')
        values=parse_qs(raw.decode(errors='replace'));val=values.get('val_id',[''])[0]
        if not val or len(val)>200:raise HTTPException(422,'Validation reference is required')
        base=provider()
        import httpx
        try:
            async with httpx.AsyncClient(timeout=25) as client:
                response=await client.get(base+'/validator/api/validationserverAPI.php',params={'val_id':val,'store_id':os.environ['SSLCOMMERZ_STORE_ID'],'store_passwd':os.environ['SSLCOMMERZ_STORE_PASSWORD'],'format':'json'})
                response.raise_for_status();verified=response.json()
        except (httpx.HTTPError,ValueError):raise HTTPException(502,'Payment validation is temporarily unavailable')
        tid=verified.get('tran_id','');p=s.scalar(select(Record).where(Record.id=='payment:'+tid,Record.kind=='payments').with_for_update())
        if not p:raise HTTPException(404,'Payment does not belong to this workspace')
        if p.data['status']=='credited':return {'credited':True,'duplicate':True}
        try:paisa=Decimal(str(verified.get('amount','NaN')))*100
        except InvalidOperation:raise HTTPException(422,'Invalid provider amount')
        if verified.get('status') not in ('VALID','VALIDATED') or verified.get('currency')!='BDT' or not paisa.is_finite() or paisa!=p.data['expected_paisa'] or str(verified.get('risk_level','1'))!='0' or verified.get('val_id')!=val:raise HTTPException(409,'Payment amount, currency, status or risk check failed; no credit added')
        if p.data['sandbox']!=(base.startswith('https://sandbox.')):raise HTTPException(409,'Payment environment mismatch')
        rid='ledger:payment:'+hashlib.sha256(val.encode()).hexdigest()
        if s.get(Record,rid):return {'credited':True,'duplicate':True}
        w=wallet(s);balance_key='sandbox_balance_paisa' if p.data['sandbox'] else 'balance_paisa';w.data={**w.data,balance_key:w.data.get(balance_key,0)+int(paisa)}
        put(s,'ledger',{'type':'recharge','paisa':int(paisa),'tran_id':tid,'sandbox':p.data['sandbox'],'created_at':datetime.now(timezone.utc).isoformat()},rid)
        p.data={**p.data,'status':'credited','validation_reference':val}
        if not p.data['sandbox']:
            for job in s.scalars(select(Record).where(Record.kind=='jobs')):
                if job.data.get('status') in ('pending','failed') and 'credit exhausted' in job.data.get('error','').lower():job.data={**job.data,'status':'pending','attempts':0,'next_run_at':datetime.now(timezone.utc).isoformat(),'error':''}
        s.commit();return {'credited':True,'sandbox':p.data['sandbox']}

    @app.post('/payments/return',response_class=HTMLResponse)
    def payment_return():
        return HTMLResponse('<!doctype html><html><title>NotoChat payment</title><body><h1>Return to NotoChat</h1><p>Payment status is verified separately with the payment provider. Open your workspace billing page and refresh to see validated credits.</p></body></html>',headers={'Content-Security-Policy':"default-src 'none'",'Cache-Control':'no-store'})
