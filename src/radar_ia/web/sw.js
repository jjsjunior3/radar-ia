'use strict';
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('push',event=>{
  let data={};try{data=event.data?.json()||{};}catch{}
  const title='Radar IA';
  const body=typeof data.body==='string'?data.body.slice(0,160):'Há novidades na sua biblioteca privada.';
  event.waitUntil(self.registration.showNotification(title,{body,tag:typeof data.tag==='string'?data.tag:'radar-ia',
    icon:'/icon.svg',badge:'/icon.svg',renotify:false,data:{view:data.view==='review'?'review':'pending'}}));
});
self.addEventListener('notificationclick',event=>{
  event.notification.close();
  event.waitUntil((async()=>{
    const root=self.location.origin+'/';
    const review=event.notification.data?.view==='review';
    const target=root+(review?'#review':'');
    const windows=await self.clients.matchAll({type:'window',includeUncontrolled:true});
    for(const client of windows){if(client.url.startsWith(root)){await client.focus();client.postMessage(review?{type:'radar-notice-opened',view:'review'}:{type:'radar-notice-opened'});return;}}
    await self.clients.openWindow(target);
  })());
});
// Sem cache offline: audio, catalogo e sessao continuam privados.
