// Deterministic browser simulation. Never calls a backend or a model.
export const scenarioChannels=['WhatsApp','Website','Instagram','Messenger','Facebook comments'];
export const scenarioSteps=['Customer inquiry','Simulated AI response','Photo / voice / comment context','Human handover','Review order','Confirm sample order','Ship & deliver','Follow-up & rating'];
export function scenarioApi(s,path,method,body,save,check){
 if(!path.startsWith('/demo/scenarios'))return undefined;
 s.demo_scenarios??={};
 if(method==='GET')return s.demo_scenarios;
 const channel=body.channel;check(scenarioChannels.includes(channel),'Choose a supported sample channel');
 let run=s.demo_scenarios[channel];
 if(path==='/demo/scenarios/start'){
  if(run)return run;
  const cid=Math.max(0,...s.conversations.map(c=>c.id))+1;
  s.conversations.push({id:cid,customer:channel+' demo visitor',channel,mode:'ai'});s.messages[cid]=[];
  run={channel,cid,step:0,events:[],order_id:null};s.demo_scenarios[channel]=run;save(s);return run;
 }
 check(run,'Start this scenario first');check(Number.isInteger(body.step),'Step is required');
 if(path==='/demo/scenarios/requote'){
  check(run.step===5,'A pending quote is required');
  const p=s.products.find(p=>p.id===run.quote.product_id);check(p&&p.stock>0,'Sample item is out of stock');
  run.quote.price=p.price;s.messages[run.cid].push({id:crypto.randomUUID(),role:'team',text:'[Updated sample quote] BDT '+p.price+'. Synthetic pickup: BDT 0. Review and confirm again.'});save(s);return run;
 }
 if(body.step<run.step)return run;
 check(body.step===run.step&&run.step<scenarioSteps.length,'Run the next step in order');
 const c=s.conversations.find(c=>c.id===run.cid);check(c,'Sample conversation is missing');
 const now=new Date().toISOString();const id='scenario:'+channel.replaceAll(' ','-');
 const msg=(role,text)=>s.messages[run.cid].push({id:crypto.randomUUID(),role,text,created_at:now});
 const product=s.products.find(p=>p.sku==='JOURNEY-SAMPLE');
 if(run.step===0){
  if(!product)s.products.push({id:Math.max(0,...s.products.map(p=>p.id))+1,sku:'JOURNEY-SAMPLE',name:'Journey sample cleanser — fictional',price:100,stock:50,description:'Fictional demo product. Not a real Peoniara price, stock or efficacy claim.',category:'Demo',image:''});
  msg('customer',channel==='Facebook comments'?'[Simulated public comment] Price please?':'[Simulated customer] Do you have the sample cleanser?');
  s.conversation_meta[run.cid]={last_inbound:now,source:'browser simulation'};
 }
 if(run.step===1){msg('assistant','[SIMULATED AI · no model call] The fictional sample cleanser is BDT 100. Would you like one? Actual delivery terms need review.');s.leads.push({id:id+':lead',conversation_id:c.id,customer:c.customer,stage:'Qualified',temperature:'Warm',note:'Synthetic product inquiry',created_at:now});}
 if(run.step===2){msg('customer',channel==='Instagram'?'[Sample photo fixture] A cleanser bottle. Suggested match requires human review.':channel==='WhatsApp'?'[Sample voice transcript fixture] Please order one sample cleanser. No audio was uploaded or transcribed.':channel==='Facebook comments'?'[Simulated private-reply request] Please send the details privately.':'[Sample document fixture] Delivery question extracted for review. No actual parser was run.');msg('assistant','[SIMULATED REVIEW] Suggested item: Journey sample cleanser. Confirm the item before checkout; media interpretation alone cannot create an order.');}
 if(run.step===3){c.mode='human';s.conversation_meta[c.id]={...s.conversation_meta[c.id],assignee:'Demo operator',reason:'Review delivery and product match',handover_until:''};msg('team','[Simulated staff] I am reviewing your item and delivery details.');s.approvals??=[];s.approvals.push({id:id+':approval',conversation_id:c.id,kind:'policy_exception',detail:'Synthetic delivery-policy review',status:'pending',source_hash:JSON.stringify([s.messages[c.id]?.filter(m=>m.role==='customer'),s.products,s.agent,s.knowledge]),execution:'none'});}
 if(run.step===4){check(product&&product.stock>0,'Sample product is unavailable');run.quote={product_id:product.id,price:product.price};msg('team','[Sample quote] One fictional item: BDT '+product.price+'. Synthetic pickup: BDT 0. Confirm sample order to continue. No real shipping fee is claimed.');}
 if(run.step===5){check(body.confirm===true,'Explicitly confirm this fictional order');check(product&&product.id===run.quote.product_id&&product.price===run.quote.price&&product.stock>0,'Price or stock changed. Review this scenario with current catalog data.');product.stock-=1;run.order_id=id+':order';s.orders.push({id:run.order_id,conversation_id:c.id,customer:c.customer,phone:'TEST-ONLY',address:'Synthetic pickup location',items:[{product_id:product.id,name:product.name,quantity:1,unit_price:product.price}],subtotal:product.price,delivery_charge:0,total:product.price,status:'confirmed',payment_method:'COD',payment_status:'unverified',courier_status:'not booked',created_at:now});msg('customer','[Simulated customer confirmation] Confirm this fictional order.');msg('team','[Demo order saved] No payment or real purchase occurred.');}
 if(run.step===6){const o=s.orders.find(o=>o.id===run.order_id);check(o,'Sample order is missing');o.status='delivered';o.tracking='DEMO-TRACKING';o.courier_status='simulated delivery — no courier booked';msg('team','[SIMULATED SHIPMENT → DELIVERY] Your fictional parcel is marked delivered.');}
 if(run.step===7){s.automations.push({id:id+':followup',conversation_id:c.id,kind:'review',text:'Synthetic review request — not sent',due_at:now,status:'draft',delivery:'not sent'});msg('customer','[Simulated rating] 5/5 for this fictional order.');s.notifications.push({id:id+':done',title:channel+' demo complete',detail:'Explore Orders, Leads, Commerce review and Follow-ups for these sample records.',done:false,created_at:now});}
 run.events.push({title:scenarioSteps[run.step],at:now});run.step+=1;save(s);return run;
}
