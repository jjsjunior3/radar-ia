'use strict';
let episodes=[],filter='pending',view='pending',libraryFilter='all',active=null,lastSaved=0;
const audio=document.querySelector('#audio'),message=document.querySelector('#message');
const state=e=>e.progress.heard?'heard':e.progress.position>0?'progress':'new';
const labels={heard:'Ouvido',progress:'Em andamento',new:'Não ouvido'};
function time(seconds){return `${Math.floor(seconds/60)}:${String(Math.floor(seconds%60)).padStart(2,'0')}`;}
async function api(path,options={}){const response=await fetch(window.radarAuth.url(path),{...options,headers:await window.radarAuth.headers(options.headers||{})});const result=await response.json();if(!response.ok)throw Error(result.error||'Não foi possível concluir.');return result;}
function node(tag,text,cls){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;}
function setView(next){
 if(!['pending','library','review'].includes(next)||!window.radarAuth.ready)return;
 view=next;history.replaceState(null,'',location.pathname+(view==='pending'?'':'#'+view));filter=view==='pending'?'pending':libraryFilter;
 document.querySelector('#library-section').hidden=view==='review';
 document.querySelector('#review-section').hidden=view!=='review';
 document.querySelector('#library-title').textContent=view==='pending'?'Para ouvir':'Sua biblioteca';
 document.querySelector('.filters').hidden=view!=='library';
 document.querySelectorAll('[data-view]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.view===view)));
 document.querySelectorAll('[data-filter]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.filter===filter)));
 render();
}
document.querySelectorAll('[data-view]').forEach(button=>button.onclick=()=>{setView(button.dataset.view);document.querySelector('#app-nav').scrollIntoView({block:'start',behavior:'smooth'});});
window.addEventListener('radar-production-state',event=>{
 const attention=['awaiting_human_review','awaiting_script_review','awaiting_audio_review','audio_approved','draft_failed','audio_failed'].includes(event.detail.stage);
 document.querySelector('#review-attention').hidden=!attention;
 document.querySelector('[data-view="review"]').setAttribute('aria-label',attention?'Análise e aprovação: requer sua atenção':'Análise e aprovação');
});
function render(){
 const list=document.querySelector('#episodes');list.replaceChildren();
 document.querySelector('#pending-count').textContent=String(episodes.filter(e=>!e.progress.heard).length);
 document.querySelector('#library-count').textContent=String(episodes.length);
 const selected=episodes.filter(e=>filter==='pending'?!e.progress.heard:filter==='all'||state(e)===filter);
 if(view==='pending')selected.sort((a,b)=>Number(state(b)==='progress')-Number(state(a)==='progress'));
 document.querySelector('#count').textContent=`${selected.length} episódio${selected.length===1?'':'s'}`;
 if(!selected.length){
  const empty=node('div',undefined,'empty-state');
  empty.append(node('h3',view==='pending'?'Nenhum episódio pendente':'Nada por aqui ainda.'),node('p',view==='pending'?'Os próximos episódios publicados aparecerão aqui. Consulte o histórico na biblioteca.':'Escolha outro filtro ou aguarde a publicação de um episódio.','small'));
  if(view==='pending'){const button=node('button','Explorar biblioteca');button.onclick=()=>setView('library');empty.append(button);}
  list.append(empty);
 }

for(const e of selected){const card=node('article',undefined,'episode');const cover=node('div','◉','cover');cover.setAttribute('aria-hidden','true');const body=node('div');const date=new Date(e.date+'T12:00:00').toLocaleDateString('pt-BR',{day:'2-digit',month:'long'});body.append(node('div',`${date} · ${time(e.duration_seconds)} min`,'meta'),node('h3',e.title),node('span',labels[state(e)],'status'));const track=node('div',undefined,'track'),fill=node('div',undefined,'track-fill');fill.style.width=`${Math.min(100,100*e.progress.position/e.duration_seconds)}%`;track.append(fill);body.append(track);const actions=node('div',undefined,'actions');const listen=node('button',e.progress.position>0&&!e.progress.heard?'▶ Continuar':'▶ Ouvir','listen');if(e.demo){listen.textContent='Exemplo sem áudio';listen.disabled=true;listen.title='Demonstração sem áudio real ou chamadas pagas.';}else listen.addEventListener('click',()=>play(e,listen));const mark=node('button',e.progress.heard?'Marcar não ouvido':'Marcar como ouvido','mark');mark.addEventListener('click',async()=>{mark.disabled=true;try{await save(e,{heard:!e.progress.heard});}catch(err){message.textContent=err.message;}finally{mark.disabled=false;}});actions.append(listen,mark);card.append(cover,body,actions);list.append(card);}}
let saveChain=Promise.resolve();
function save(e,change){const task=saveChain.catch(()=>{}).then(async()=>{const result=await api('/api/progress',{method:'POST',headers:{'Content-Type':'application/json','X-Radar-Client':'web'},body:JSON.stringify({episode_id:e.id,...change}),keepalive:true});e.progress=result;render();});saveChain=task;return task;}
async function play(e,button){button.disabled=true;message.textContent='Preparando reprodução privada…';try{audio.pause();await saveChain.catch(()=>{});const result=await api('/api/audio/'+encodeURIComponent(e.id));active=e;document.querySelector('#playing-title').textContent=e.title;document.querySelector('#player-panel').hidden=false;audio.src=result.url;const position=e.progress.heard?0:e.progress.position;audio.addEventListener('loadedmetadata',()=>{audio.currentTime=Math.min(position,audio.duration||position);},{once:true});audio.playbackRate=Number(document.querySelector('#speed').value);await audio.play();document.querySelector('#player-panel').scrollIntoView({behavior:'smooth',block:'nearest'});lastSaved=performance.now();message.textContent='';if('mediaSession' in navigator)navigator.mediaSession.metadata=new MediaMetadata({title:e.title,artist:'Radar IA'});}catch(err){message.textContent=err.message;}finally{button.disabled=false;}}
function savePosition(){if(!window.radarAuth.ready)return;const e=active;if(!e||!Number.isFinite(audio.currentTime))return;const position=Math.min(e.duration_seconds,Math.max(0,audio.currentTime));save(e,{position}).catch(err=>message.textContent=err.message);}
audio.addEventListener('timeupdate',()=>{if(performance.now()-lastSaved>10000){lastSaved=performance.now();savePosition();}});audio.addEventListener('pause',savePosition);audio.addEventListener('seeked',savePosition);audio.addEventListener('ended',()=>{if(active)save(active,{position:active.duration_seconds,heard:true}).catch(err=>message.textContent=err.message);});audio.addEventListener('error',()=>{if(active)message.textContent='O link pode ter expirado ou a reprodução falhou. Clique em Continuar para obter novo acesso.';});document.addEventListener('visibilitychange',()=>{if(document.hidden)savePosition();});window.addEventListener('pagehide',savePosition);
document.querySelector('#back').onclick=()=>audio.currentTime=Math.max(0,audio.currentTime-15);document.querySelector('#forward').onclick=()=>audio.currentTime=Math.min(audio.duration||0,audio.currentTime+15);document.querySelector('#speed').onchange=e=>audio.playbackRate=Number(e.target.value);document.querySelectorAll('[data-filter]').forEach(button=>button.onclick=()=>{filter=button.dataset.filter;libraryFilter=filter;document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));render();});
const weekday=new Date().getDay();document.querySelectorAll('.schedule span').forEach((el,index)=>el.classList.toggle('today',index===weekday-1));
window.radarAuth.initialize().then(ready=>{if(!ready)return null;return api('/api/episodes');}).then(data=>{if(!data||!window.radarAuth.ready){document.querySelector('#count').textContent='Entre para acessar';return;}episodes=data.episodes;if(data.mode==='demo')message.textContent='DEMONSTRAÇÃO · dados fictícios, sem áudio real, AWS ou chamadas pagas.';document.querySelector('#app-nav').hidden=false;setView(location.hash==='#review'?'review':location.hash==='#library'?'library':'pending');document.querySelector('#mode').textContent=data.mode==='demo'?'Demonstração local · sem conexão AWS':data.mode==='cloud'?'Acesso privado · progresso na sua conta':'Prévia local · catálogo privado S3';render();window.radarProduction.load();window.radarNotifications.initialize();}).catch(err=>{message.textContent=err.message;document.querySelector('#count').textContent='Indisponível';});

window.addEventListener("radar-episode-published",async event=>{try{await saveChain.catch(()=>{});const data=await api("/api/episodes");episodes=data.episodes;if(event.detail?.navigate)setView('pending');else render();}catch(error){message.textContent=error.message;}});

window.addEventListener("radar-review-opened",()=>{setView("review");window.radarProduction.load();document.querySelector("#app-nav").scrollIntoView({block:"start"});});

window.addEventListener('hashchange',()=>{if(window.radarAuth.ready)setView(location.hash==='#review'?'review':location.hash==='#library'?'library':'pending');});
