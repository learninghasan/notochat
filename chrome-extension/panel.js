import {appOrigin} from './contracts.mjs';
const $=id=>document.getElementById(id);
let connection=null;
const stored=await chrome.storage.local.get('appOrigin');$('origin').value=stored.appOrigin||'';
function status(message){$('status').textContent=message;}
async function request(path,method='GET',body){
 if(!connection)throw Error('Connect your workspace first');
 const r=await chrome.runtime.sendMessage({type:'request',...connection,path,method,body});
 if(r.error)throw Error(r.error);return r.value;
}
async function run(action){
 for(const b of document.querySelectorAll('button'))b.disabled=true;
 try{await action()}catch(e){status(e.message)}finally{for(const b of document.querySelectorAll('button'))b.disabled=false;$('copy').disabled=!$('output').textContent;}
}
$('connect').addEventListener('click',()=>run(async()=>{
 connection=null;$('workspace').hidden=true;$('output').textContent='';
 const origin=appOrigin($('origin').value.trim());
 if(!await chrome.permissions.request({origins:[origin+'/*']}))throw Error('App access was not granted');
 await chrome.storage.local.set({appOrigin:origin});
 const tabs=await chrome.tabs.query({url:origin+'/*'});
 const tab=tabs.find(t=>t.active)||tabs[0];if(!tab)throw Error('Open your NotoChat app in a tab, sign in and select a business');
 connection={origin,tabId:tab.id};
 const member=await request('/api/auth/organization/get-active-member');
 if(!member.organizationId)throw Error('Select a business in NotoChat first');
 connection.organizationId=member.organizationId;
 const customers=await request('/api/conversations');$('customer').replaceChildren();
 for(const c of customers){const option=document.createElement('option');option.value=c.id;option.textContent=c.customer+' · '+c.channel;$('customer').append(option);}
 $('workspace').hidden=false;status('Connected · '+member.role+' · '+member.organizationId);
}));
async function ask(action){
 if(!$('customer').value)throw Error('Choose a customer first');
 const question=$('question').value.trim();if(action==='question'&&!question)throw Error('Enter your question first');
 $('output').textContent='';status('Preparing a reviewable answer…');
 const result=await request('/api/conversations/'+$('customer').value+'/assistant','POST',{action,question});
 $('output').textContent=result.text||'';status('Answer ready for review');
}
$('summary').onclick=()=>run(()=>ask('summary'));$('draft').onclick=()=>run(()=>ask('draft'));$('ask').onclick=()=>run(()=>ask('question'));
$('customer').onchange=()=>{$('output').textContent='';$('question').value='';$('copy').disabled=true;};
$('selection').onclick=()=>run(async()=>{
 const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
 if(!tab?.id)throw Error('Activate the customer conversation tab first');
 const results=await chrome.scripting.executeScript({target:{tabId:tab.id},func:()=>window.getSelection()?.toString().slice(0,4000)||''});
 const text=results[0]?.result;if(!text)throw Error('Select customer text on the page first. Click the extension icon on that tab to grant access.');
 $('question').value=text;status('Selected text copied. Check the customer and text, then ask AI.');
});
$('copy').onclick=()=>run(async()=>{await navigator.clipboard.writeText($('output').textContent);status('Copied. Review before sending in your messaging app.');});
