import {test,beforeEach} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const {demoApi:api}=await import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync(new URL('../app/demo.js',import.meta.url),'utf8')).toString('base64'));
const store=new Map();
beforeEach(()=>{store.clear();globalThis.localStorage={getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v)}});
const post=(p,b)=>api(p,{method:'POST',body:JSON.stringify(b)});
const patch=(p,b)=>api(p,{method:'PATCH',body:JSON.stringify(b)});
const order=()=>({conversation_id:1,customer:'Test customer',phone:'01700000000',address:'House 1, Dhaka',items:[{product_id:1,quantity:2}],delivery_charge:70,payment_method:'COD',request_id:crypto.randomUUID()});

test('human takeover is required, then replies and ownership persist',async()=>{
 await assert.rejects(()=>post('/conversations/1/messages',{text:'Hello'}),/Take over/);
 await post('/conversations/1/handover',{assignee:'Agent',reason:'Exchange',duration_minutes:60});
 await post('/conversations/1/messages',{text:'ধন্যবাদ'});
 assert.equal((await api('/conversations/1/messages')).at(-1).text,'ধন্যবাদ');
 assert.equal((await api('/workspace')).conversation_meta[1].assignee,'Agent');
 await patch('/conversations/1/mode',{mode:'ai'});
 assert.equal((await api('/workspace')).conversation_meta[1].handover_until,'');
});
test('orders use catalog totals, retry once and restore stock exactly once',async()=>{
 const body=order(),o=await post('/orders',body);
 assert.equal(o.total,4970);
 assert.equal((await api('/catalog'))[0].stock,10);
 assert.equal((await post('/orders',body)).id,o.id);
 assert.equal((await api('/catalog'))[0].stock,10);
 await patch('/orders/'+o.id,{status:'cancelled'});
 await patch('/orders/'+o.id,{status:'cancelled'});
 assert.equal((await api('/catalog'))[0].stock,12);
 await assert.rejects(()=>patch('/orders/'+o.id,{status:'shipped',tracking:'x'}),/Invalid/);
});
test('invalid multi-product orders do not partially reduce inventory',async()=>{
 const body=order();body.items.push({product_id:2,quantity:100});
 await assert.rejects(()=>post('/orders',body),/Insufficient/);
 assert.equal((await api('/catalog'))[0].stock,12);
});
test('booking overlap blocked and repeat confirmation does not duplicate reminders',async()=>{
 const body={conversation_id:1,customer:'Test',service:'Consultation',resource:'Room 1',starts_at:new Date(Date.now()+5*86400000).toISOString(),duration_minutes:60,advance:0};
 const b=await post('/bookings',body);
 await assert.rejects(()=>post('/bookings',body),/already booked/);
 await patch('/bookings/'+b.id,{status:'confirmed'});
 await patch('/bookings/'+b.id,{status:'confirmed'});
 assert.equal((await api('/workspace')).automations.length,2);
});
test('agent drafts do not overwrite live settings until publication',async()=>{
 const w=await api('/workspace');const d=await post('/agent/versions',{...w.agent,delivery_inside:99});
 assert.equal((await api('/workspace')).agent.delivery_inside,70);
 await post('/agent/versions/'+d.id+'/publish',{});
 assert.equal((await api('/workspace')).agent.delivery_inside,99);
 assert.equal((await api('/workspace')).agent_versions.filter(v=>v.state==='previous').length,1);
});
test('broadcast preview blocks stale customers and never marks messages sent',async()=>{
 let r=await post('/broadcasts/preview',{text:'Offer',channel:'All'});assert.equal(r.eligible_ids.length,0);
 await post('/conversations/1/incoming',{text:'New inquiry'});
 r=await post('/broadcasts/preview',{text:'Offer',channel:'All'});assert.deepEqual(r.eligible_ids,[1]);assert.equal(r.sent,0);
});
test('Bengali knowledge is searchable and no demo AI is fabricated',async()=>{
 await post('/knowledge',{title:'রিটার্ন নীতি',text:'এক্সচেঞ্জ করতে যোগাযোগ করুন'});
 const result=await api('/knowledge/search?q='+encodeURIComponent('এক্সচেঞ্জ'));
 assert.equal(result.length,1);assert.equal(result[0].match_type,'keyword');
 await assert.rejects(()=>post('/conversations/1/assistant',{action:'summary'}),/not connected/);
});
test('team directory is explicit about profiles rather than access enforcement',async()=>{
 const t=await post('/team',{name:'Agent',email:'agent@example.com',role:'Agent',channels:['Messenger']});
 assert.match(t.access,/no invitation/);
 await assert.rejects(()=>post('/team',{name:'Agent 2',email:'agent@example.com',role:'Agent',channels:[]}),/already/);
});
