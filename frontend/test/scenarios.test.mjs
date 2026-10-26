import {test,beforeEach} from 'node:test';
import assert from 'node:assert/strict';
import {demoApi as api} from '../app/demo.js';
import {scenarioChannels} from '../app/demo-scenarios.js';
let store;
beforeEach(()=>{store=new Map();globalThis.localStorage={getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v)}});
const post=(p,b)=>api(p,{method:'POST',body:JSON.stringify(b)});
test('all five channel journeys persist once without touching existing records',async()=>{
 const original=await api('/conversations');
 for(const channel of scenarioChannels){
  const run=await post('/demo/scenarios/start',{channel});
  assert.equal((await post('/demo/scenarios/start',{channel})).cid,run.cid);
  for(let step=0;step<8;step++){
   if(step===5)await assert.rejects(()=>post('/demo/scenarios/step',{channel,step}),/confirm/i);
   await post('/demo/scenarios/step',{channel,step,confirm:true});
   await post('/demo/scenarios/step',{channel,step,confirm:true});
  }
  const messages=await api('/conversations/'+run.cid+'/messages');
  assert(messages.some(m=>m.text.includes('SIMULATED AI')));
  assert.equal((await api('/demo/scenarios'))[channel].step,8);
 }
 const s=await api('/workspace');
 assert.deepEqual(s.conversations.slice(0,original.length),original);
 assert.equal(s.orders.length,5);assert.equal(s.products.find(p=>p.sku==='JOURNEY-SAMPLE').stock,45);
 assert(s.orders.every(o=>o.payment_status==='unverified'&&o.status==='delivered'));
 assert.equal(s.automations.length,5);
});
test('scenario rejects skipped steps and changed prices without stock/order mutation',async()=>{
 const channel='Website';await post('/demo/scenarios/start',{channel});
 await assert.rejects(()=>post('/demo/scenarios/step',{channel,step:5,confirm:true}),/order/);
 for(let step=0;step<5;step++)await post('/demo/scenarios/step',{channel,step});
 const p=(await api('/catalog')).find(p=>p.sku==='JOURNEY-SAMPLE');
 await api('/products/'+p.id,{method:'PUT',body:JSON.stringify({...p,price:101})});
 await assert.rejects(()=>post('/demo/scenarios/step',{channel,step:5,confirm:true}),/changed/);
 const s=await api('/workspace');assert.equal(s.orders.length,0);assert.equal(s.products.find(p=>p.sku==='JOURNEY-SAMPLE').stock,50);
 await post('/demo/scenarios/requote',{channel,step:5});
 await post('/demo/scenarios/step',{channel,step:5,confirm:true});
 assert.equal((await api('/workspace')).orders[0].total,101);
});
