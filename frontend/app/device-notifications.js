'use client';
import {useEffect,useState} from 'react';
export function PWARegistration(){useEffect(()=>{if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{})},[]);return null}
export default function DeviceNotifications({api,demo,onError}){
 const [enabled,setEnabled]=useState(false),[busy,setBusy]=useState(false);
 function decode(base64){const s=atob(base64.replaceAll('-','+').replaceAll('_','/')+'='.repeat((4-base64.length%4)%4));return Uint8Array.from(s,c=>c.charCodeAt(0))}
 async function subscribe(){setBusy(true);try{if(!('serviceWorker'in navigator)||!('PushManager'in window)||!('Notification'in window))throw Error('This browser does not support web push.');const config=await api('/push/config');if(!config.enabled)throw Error('Push is not configured on the backend.');if(await Notification.requestPermission()!=='granted')throw Error('Notification permission was not granted.');const registration=await navigator.serviceWorker.ready;const subscription=await registration.pushManager.getSubscription()||await registration.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:decode(config.public_key)});await api('/push/subscriptions',{method:'POST',body:JSON.stringify(subscription.toJSON())});setEnabled(true)}catch(e){onError(e.message)}finally{setBusy(false)}}
 async function unsubscribe(){setBusy(true);try{const registration=await navigator.serviceWorker.ready;const subscription=await registration.pushManager.getSubscription();if(subscription){await api('/push/subscriptions',{method:'DELETE',body:JSON.stringify(subscription.toJSON())});await subscription.unsubscribe()}setEnabled(false)}catch(e){onError(e.message)}finally{setBusy(false)}}
 return <button className="secondary" disabled={demo||busy} onClick={enabled?unsubscribe:subscribe}>{enabled?'Disable device notifications':'Enable device notifications'}</button>
}
