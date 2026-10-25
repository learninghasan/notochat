"""Explicit courier booking and authenticated status reconciliation.

Contracts follow published SDKs; merchant credentials and live verification required.
"""
import hashlib
from typing import Literal
from urllib.parse import quote
from fastapi import Depends,HTTPException,Request
from pydantic import BaseModel,Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

class Booking(BaseModel):
    provider:Literal['Steadfast','Pathao']
    store_id:int=Field(default=0,ge=0)
    city_id:int=Field(default=0,ge=0)
    zone_id:int=Field(default=0,ge=0)
    area_id:int=Field(default=0,ge=0)
    weight:float=Field(default=0.5,ge=0.1,le=50)


def install_couriers(app,Record,authorize,session,put,notify):
    async def pathao_auth(config,client):
        keys=['PATHAO_CLIENT_ID','PATHAO_CLIENT_SECRET','PATHAO_USERNAME','PATHAO_PASSWORD']
        if not all(config.get(k) for k in keys):raise HTTPException(503,'Pathao merchant credentials are not configured')
        base='https://api-hermes.pathao.com' if config.get('PATHAO_SANDBOX')=='0' else 'https://courier-api-sandbox.pathao.com'
        r=await client.post(base+'/aladdin/api/v1/issue-token',json={'client_id':config[keys[0]],'client_secret':config[keys[1]],'username':config[keys[2]],'password':config[keys[3]],'grant_type':'password'})
        r.raise_for_status();token=r.json().get('access_token')
        if not token:raise ValueError('No Pathao token')
        return base,{'Authorization':'Bearer '+token,'Accept':'application/json'}

    def steadfast(config):
        if not config.get('STEADFAST_API_KEY') or not config.get('STEADFAST_SECRET_KEY'):raise HTTPException(503,'Steadfast merchant credentials are not configured')
        return 'https://portal.packzy.com/api/v1',{'Api-Key':config['STEADFAST_API_KEY'],'Secret-Key':config['STEADFAST_SECRET_KEY']}

    @app.post('/orders/{rid}/courier',dependencies=[Depends(authorize)])
    async def book(rid:str,body:Booking,s:Session=Depends(session)):
        order=s.get(Record,rid)
        if not order or order.kind!='orders':raise HTTPException(404,'Order not found')
        d=order.data;config=app.state.channel_configuration()
        if d['status']!='confirmed':raise HTTPException(409,'Only confirmed orders can be booked')
        if d['payment_method']!='COD' and d.get('payment_status')!='verified':raise HTTPException(409,'Prepaid orders require verified payment before booking; COD is available')
        sandbox=body.provider=='Pathao' and config.get('PATHAO_SANDBOX')!='0'
        if not sandbox and config.get('COURIER_LIVE_ENABLED')!='1':raise HTTPException(503,'Live courier booking is disabled in Connections')
        if body.provider=='Pathao' and not all([body.store_id,body.city_id,body.zone_id]):raise HTTPException(422,'Pathao store, city and zone IDs are required')
        shipment_id='shipment:'+hashlib.sha256(rid.encode()).hexdigest()
        existing=s.get(Record,shipment_id)
        if existing:
            if existing.data['status']=='booked':return existing.data
            raise HTTPException(409,'A courier booking was already attempted. Reconcile with the merchant dashboard before retrying.')
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                base,headers=await pathao_auth(config,client) if body.provider=='Pathao' else steadfast(config)
            except (httpx.HTTPError,ValueError):raise HTTPException(502,'Courier authentication failed')
            invoice='NC-'+hashlib.sha256(rid.encode()).hexdigest()[:24]
            put(s,'shipments',{'order_id':rid,'provider':body.provider,'status':'attempting','invoice':invoice,'sandbox':sandbox},shipment_id)
            try:s.commit()
            except IntegrityError:s.rollback();raise HTTPException(409,'Courier booking already in progress')
            try:
                if body.provider=='Steadfast':
                    payload={'invoice':invoice,'recipient_name':d['customer'],'recipient_phone':d['phone'],'recipient_address':d['address'],'cod_amount':d['total'] if d['payment_method']=='COD' else 0,'note':'NotoChat order'}
                    response=await client.post(base+'/create_order',headers=headers,json=payload);response.raise_for_status();result=response.json()
                    consignment=result.get('consignment',{});provider_id=str(consignment.get('consignment_id',''));tracking=consignment.get('tracking_code','')
                    if result.get('status')!=200:raise ValueError('Booking rejected')
                else:
                    payload={'store_id':body.store_id,'merchant_order_id':invoice,'recipient_name':d['customer'],'recipient_phone':d['phone'],'recipient_address':d['address'],'recipient_city':body.city_id,'recipient_zone':body.zone_id,'recipient_area':body.area_id,'delivery_type':48,'item_type':2,'item_quantity':sum(i['quantity'] for i in d['items']),'item_weight':body.weight,'amount_to_collect':d['total'] if d['payment_method']=='COD' else 0,'item_description':'; '.join(i['name'] for i in d['items'])[:500]}
                    response=await client.post(base+'/aladdin/api/v1/orders',headers=headers,json=payload);response.raise_for_status();result=response.json();consignment=result.get('data',{});provider_id=str(consignment.get('consignment_id',''));tracking=provider_id
                if not provider_id or not tracking:raise ValueError('No consignment reference')
            except (httpx.HTTPError,ValueError):
                r=s.get(Record,shipment_id);r.data={**r.data,'status':'unconfirmed'};s.commit();raise HTTPException(502,'Courier booking could not be confirmed. Check the merchant dashboard; do not book a duplicate.')
        shipment=s.get(Record,shipment_id);shipment.data={**shipment.data,'status':'booked','provider_id':provider_id,'tracking':tracking}
        order=s.get(Record,rid);order.data={**order.data,'status':order.data['status'] if sandbox else 'shipped','tracking':tracking,'courier_status':'sandbox-booked' if sandbox else 'booked','courier':body.provider}
        if not sandbox:app.state.schedule_lifecycle(s,order)
        notify(s,'Courier sandbox booking' if sandbox else 'Courier booked',d['customer'],d['conversation_id']);s.commit();return shipment.data

    async def sync(rid,s):
        shipment=s.get(Record,'shipment:'+hashlib.sha256(rid.encode()).hexdigest())
        if not shipment or shipment.data.get('status')!='booked':raise HTTPException(409,'Confirmed courier booking required')
        config=app.state.channel_configuration();data=shipment.data;provider_id=quote(data['provider_id'],safe='')
        import httpx
        async with httpx.AsyncClient(timeout=25) as client:
            try:
                if data['provider']=='Steadfast':
                    base,headers=steadfast(config);r=await client.get(base+'/status_by_cid/'+provider_id,headers=headers);r.raise_for_status();status=r.json().get('delivery_status')
                else:
                    base,headers=await pathao_auth(config,client);r=await client.get(base+'/aladdin/api/v1/orders/'+provider_id,headers=headers);r.raise_for_status();status=r.json().get('data',{}).get('order_status')
                if not isinstance(status,str) or not status:raise ValueError('Missing status')
            except (httpx.HTTPError,ValueError):raise HTTPException(502,'Courier status could not be verified')
        order=s.get(Record,rid);previous=order.data.get('courier_status')
        new={**order.data,'courier_status':status}
        if not data['sandbox'] and status.casefold()=='delivered' and new['status']=='shipped':new['status']='delivered'
        order.data=new
        if not data['sandbox']:app.state.schedule_lifecycle(s,order)
        if status!=previous:notify(s,'Courier status updated',status,order.data['conversation_id'])
        s.commit();return {'provider_status':status,'verified_with_provider':True,'sandbox':data['sandbox']}

    @app.post('/orders/{rid}/courier/sync',dependencies=[Depends(authorize)])
    async def sync_route(rid:str,s:Session=Depends(session)):return await sync(rid,s)

    @app.post('/webhooks/courier')
    async def webhook(request:Request,s:Session=Depends(session)):
        import hmac
        expected=app.state.channel_configuration().get('COURIER_WEBHOOK_TOKEN')
        if not expected or not hmac.compare_digest(request.headers.get('authorization',''),'Bearer '+expected):raise HTTPException(403,'Invalid courier webhook token')
        raw=await request.body()
        if len(raw)>20000:raise HTTPException(413,'Callback too large')
        import json
        try:payload=json.loads(raw)
        except ValueError:raise HTTPException(422,'Invalid callback')
        cid=str(payload.get('consignment_id',''))
        match=next((r for r in s.scalars(select(Record).where(Record.kind=='shipments')) if r.data.get('provider_id')==cid),None)
        if not match:raise HTTPException(404,'Consignment not found')
        # Status from the callback is never trusted; the authenticated provider API is queried.
        return await sync(match.data['order_id'],s)
