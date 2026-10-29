'use strict';
window.radarNotifications=(()=>{
  const el=id=>document.querySelector('#notifications-'+id);
  let registration=null,config=null,currentId=null;
  const supported=()=>('serviceWorker' in navigator&&'PushManager' in window&&'Notification' in window);
  async function request(path,data){
    const response=await fetch(window.radarAuth.url(path),{method:data?'POST':'GET',cache:'no-store',
      headers:await window.radarAuth.headers(data?{'Content-Type':'application/json'}:{}),
      body:data?JSON.stringify(data):undefined,signal:AbortSignal.timeout(10000)});
    const result=await response.json();if(!response.ok)throw Error(result.error||'Não foi possível configurar os avisos.');return result;
  }
  async function synchronize(){
    const subscription=await registration.pushManager.getSubscription();
    if(subscription&&Notification.permission==='granted'){
      const result=await request('/api/push/subscribe',subscription.toJSON());currentId=result.id;
    }else currentId=null;
    el('enable').hidden=Boolean(currentId)||Notification.permission==='denied';
    el('disable').hidden=!currentId;el('test').hidden=!currentId;
    el('status').textContent=currentId?'Avisos ativados neste dispositivo.':Notification.permission==='denied'?
      'Avisos bloqueados pelo navegador. Você pode permitir nas configurações do site.':'Ative para receber um aviso quando um episódio estiver publicado.';
  }
  async function initialize(){
    if(!window.radarAuth.ready||!window.radarAuth.config)return;
    el('panel').hidden=false;
    navigator.serviceWorker?.addEventListener('message',event=>{if(event.data?.type==='radar-notice-opened'&&window.radarAuth.ready)window.dispatchEvent(new Event('radar-episode-published'));});
    if(!supported()){el('status').textContent='Este navegador não oferece avisos Web Push. Use o Chrome atualizado no Android.';el('enable').hidden=true;return;}
    try{
      config=await request('/api/push/config');
      if(!config.public_key){el('status').textContent='Avisos ainda não configurados neste ambiente.';el('enable').hidden=true;return;}
      registration=await navigator.serviceWorker.register('/sw.js',{scope:'/',updateViaCache:'none'});
      await navigator.serviceWorker.ready;await synchronize();
    }catch(error){el('status').textContent=error.message;el('enable').hidden=true;}
  }
  async function enable(){
    // A permissao so e solicitada por um clique explicito do usuario.
    const permission=await Notification.requestPermission();
    if(permission!=='granted'){await synchronize();return;}
    const encoded=config.public_key.replace(/-/g,'+').replace(/_/g,'/');
    const key=Uint8Array.from(atob(encoded+'='.repeat((4-encoded.length%4)%4)),char=>char.charCodeAt(0));
    await registration.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:key});await synchronize();
  }
  async function disable(){
    if(!supported())return;
    const active=registration||await navigator.serviceWorker.getRegistration('/');
    const subscription=await active?.pushManager.getSubscription();
    try{if(currentId)await request('/api/push/unsubscribe',{id:currentId});}
    finally{if(subscription)await subscription.unsubscribe();currentId=null;}
    if(registration)await synchronize();
  }
  for(const [button,action] of [['enable',enable],['disable',disable],['test',async()=>{
    if(!currentId)return;await request('/api/push/test',{id:currentId});el('status').textContent='Aviso de teste solicitado. Confira as notificações do dispositivo.';
  }]])el(button).onclick=async()=>{
    el(button).disabled=true;try{await action();}catch(error){el('status').textContent=error.message;}finally{el(button).disabled=false;}
  };
  return {initialize,disable};
})();
