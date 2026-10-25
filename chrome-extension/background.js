import {appOrigin,permittedRequest} from './contracts.mjs';
chrome.sidePanel.setPanelBehavior({openPanelOnActionClick:true});
chrome.runtime.onMessage.addListener((message,sender,respond)=>{
 if(sender.id!==chrome.runtime.id||sender.url!==chrome.runtime.getURL('panel.html'))return;
 handle(message).then(value=>respond({value}),error=>respond({error:error.message}));return true;
});
async function handle(message){
 const origin=appOrigin(message.origin);
 if(message.type!=='request'||!permittedRequest(message.path,message.method,message.body))throw Error('This action is not allowed by the copilot');
 const {appOrigin:configured}=await chrome.storage.local.get('appOrigin');
 if(origin!==configured)throw Error('Connect your NotoChat app first');
 if(!await chrome.permissions.contains({origins:[origin+'/*']}))throw Error('Allow access to your NotoChat app first');
 const tab=await chrome.tabs.get(message.tabId);
 if(!tab.url||new URL(tab.url).origin!==origin)throw Error('The connected NotoChat tab is closed or changed. Connect again.');
 if(message.path!=='/api/auth/organization/get-active-member'&&(!message.organizationId||message.organizationId.length>200))throw Error('Choose a business and connect again');
 const results=await chrome.scripting.executeScript({target:{tabId:tab.id},world:'MAIN',func:async (expectedOrigin,path,method,body,org)=>{
  if(location.origin!==expectedOrigin)return {error:'The app tab changed. Connect again.'};
  try{
   const r=await fetch(path,{method,credentials:'same-origin',redirect:'error',cache:'no-store',headers:{'Content-Type':'application/json',...(org?{'X-NotoChat-Expected-Organization':org}:{})},...(body?{body:JSON.stringify(body)}:{}),signal:AbortSignal.timeout(65000)});
   const d=await r.json();if(!r.ok)return {error:typeof d.detail==='string'?d.detail:'Sign in to NotoChat and select your business'};
   // Never return an auth session or token to extension storage.
   if(path==='/api/auth/organization/get-active-member')return {value:{organizationId:d.organizationId,role:d.role}};
   if(path==='/api/conversations')return {value:d.map(c=>({id:c.id,customer:c.customer,channel:c.channel}))};
   return {value:{text:d.text}};
  }catch{return {error:'Could not reach NotoChat. Check your app tab and connection.'};}
 },args:[origin,message.path,message.method,message.body,message.organizationId]});
 const result=results[0]?.result;
 if(!result||result.error)throw Error(result?.error||'Reconnect the NotoChat tab');
 return result.value;
}
