// Run only against a disposable local frontend + gateway + databases.
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
assert.equal(process.env.NOTOCHAT_DISPOSABLE_STACK,'1','Explicit disposable stack opt-in required');
const origin=process.env.NOTOCHAT_QA_ORIGIN||'http://localhost:18030';
assert.ok(['localhost','127.0.0.1'].includes(new URL(origin).hostname),'Only local disposable stacks are allowed');
const cookies=new Map();let organization='';
async function request(path,method='GET',body,expected=200,org=organization){
 const response=await fetch(origin+'/api'+path,{method,headers:{Origin:origin,'Content-Type':'application/json',Cookie:[...cookies].map(([k,v])=>k+'='+v).join('; '),...(org?{'X-NotoChat-Expected-Organization':org}:{})},...(body?{body:JSON.stringify(body)}:{})});
 for(const entry of response.headers.getSetCookie()){const pair=entry.split(';')[0],i=pair.indexOf('=');cookies.set(pair.slice(0,i),pair.slice(i+1));}
 const data=await response.json();assert.equal(response.status,expected,method+' '+path+': '+JSON.stringify(data));return data;
}
const id=randomUUID().replaceAll('-','');
await request('/auth/sign-up/email','POST',{name:'HTTP QA owner',email:`qa-${id}@example.test`,password:'temporary-test-password-123'});
const a=await request('/auth/organization/create','POST',{name:'HTTP QA business A',slug:'http-a-'+id});organization=a.id;
const product=await request('/products','POST',{name:'HTTP QA product',price:100,stock:3});
const customer=await request('/conversations','POST',{customer:'HTTP QA customer',channel:'Website'});
await request(`/conversations/${customer.id}/mode`,'PATCH',{mode:'human'});
await request(`/conversations/${customer.id}/messages`,'POST',{text:'A local support reply'});
assert.equal((await request(`/conversations/${customer.id}/messages`)).at(-1).text,'A local support reply');
const order={conversation_id:customer.id,customer:'HTTP QA customer',phone:'01700000000',address:'Synthetic QA address, Dhaka',items:[{product_id:product.id,quantity:2}],delivery_charge:70,request_id:id};
const first=await request('/orders','POST',order);
assert.equal(first.total,270);assert.equal((await request('/orders','POST',order)).id,first.id);
assert.equal((await request('/catalog'))[0].stock,1);
await request('/orders','POST',{...order,request_id:id+'2'},409);
const exported=await request('/workspace/export');assert.equal(exported.products.length,1);assert.equal(exported.messages.length,1);
const b=await request('/auth/organization/create','POST',{name:'HTTP QA business B',slug:'http-b-'+id});organization=b.id;
assert.deepEqual(await request('/catalog'),[]);
assert.deepEqual(await request('/conversations'),[]);
await request('/catalog','GET',undefined,409,a.id);
await request(`/conversations/${customer.id}/messages`,'GET',undefined,404);
await request('/auth/sign-out','POST',{});
await request('/catalog','GET',undefined,401);
console.log('PASS: real local HTTP signup, organization selection, signed API proxy, support reply, order/stock/idempotency, export, business isolation, stale-context rejection and logout');
