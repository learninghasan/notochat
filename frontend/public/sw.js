const CACHE='notochat-shell-v1';
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(['/offline.html','/icon.svg'])));self.skipWaiting()});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key.startsWith('notochat-shell-')&&key!==CACHE).map(key=>caches.delete(key)))));self.clients.claim()});
// No authenticated pages, API responses, tokens or customer data are cached.
self.addEventListener('fetch',event=>{if(event.request.mode==='navigate')event.respondWith(fetch(event.request).catch(()=>caches.match('/offline.html')))});
self.addEventListener('push',event=>{let data={};try{data=event.data?.json()||{}}catch{}event.waitUntil(self.registration.showNotification('NotoChat',{body:typeof data.body==='string'?data.body:'Your workspace has an update.',icon:'/icon.svg',badge:'/icon.svg',tag:'notochat-workspace-update',data:{url:'/'}}))});
self.addEventListener('notificationclick',event=>{event.notification.close();event.waitUntil(self.clients.matchAll({type:'window',includeUncontrolled:true}).then(windows=>{const existing=windows.find(w=>new URL(w.url).origin===self.location.origin);return existing?existing.focus():self.clients.openWindow('/')}))});
