'use strict';
window.radarEpisodeNotes=(()=>{
  const panel=document.querySelector('#episode-details-panel');
  const content=document.querySelector('#episode-details-content');
  const status=document.querySelector('#episode-details-status');
  let revision=0;
  function el(tag,text){const element=document.createElement(tag);if(text!==undefined)element.textContent=text;return element;}
  function clear(){
    revision+=1;panel.hidden=true;content.replaceChildren();status.textContent='';
  }
  function safeLink(source){
    if(!source.url)return null;
    try{
      const url=new URL(source.url);
      if(url.protocol!=='https:'||url.username||url.password)return null;
      const link=el('a',source.name||source.title||'Abrir fonte');
      link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';return link;
    }catch{return null;}
  }
  function render(data){
    const transcript=el('details'),sources=el('details'),glossary=el('details');
    transcript.append(el('summary','Transcrição'));
    transcript.append(el('p',data.intro));
    const list=el('ol');list.className='episode-topic-list';
    const references=el('ul');
    for(const topic of data.topics){
      const item=el('li'),heading=el('h3',topic.title);
      item.append(heading,el('p',topic.summary));
      for(const turn of topic.turns){
        const paragraph=el('p');paragraph.className='transcript-turn';
        if(turn.speaker!=='Narração')paragraph.append(el('strong',turn.speaker+' '));
        paragraph.append(el('span',turn.text));item.append(paragraph);
      }
      list.append(item);
      const reference=el('li');reference.append(el('span',topic.title+' · '));
      const link=safeLink(topic.source);
      reference.append(link||el('span',topic.source.name||'Fonte indisponível'));
      if(topic.source.published){
        const date=new Date(topic.source.published);
        if(!Number.isNaN(date.getTime()))reference.append(el('small',' · '+date.toLocaleDateString('pt-BR',{timeZone:'America/Sao_Paulo'})));
      }
      references.append(reference);
    }
    transcript.append(list,el('p',data.outro));
    sources.append(el('summary','Fontes por assunto'),references);
    const terms=el('dl');
    for(const term of data.glossary){
      const name=el('dt',term.term);name.lang='en';
      terms.append(name,el('dd',term.explanation));
    }
    glossary.append(el('summary','Inglês do episódio'));
    glossary.append(data.glossary.length?terms:el('p','Esta edição não tem termos no glossário.'));
    content.replaceChildren(transcript,sources,glossary);
  }
  async function show(episode,scroll=false){
    const request=++revision;
    panel.hidden=false;content.replaceChildren();
    document.querySelector('#episode-details-title').textContent=episode.title;
    status.textContent='Carregando roteiro e fontes…';
    if(scroll)panel.scrollIntoView({behavior:'smooth',block:'start'});
    try{
      const response=await fetch(window.radarAuth.url('/api/episodes/'+encodeURIComponent(episode.id)),{
        cache:'no-store',headers:await window.radarAuth.headers(),signal:AbortSignal.timeout(15000)});
      const data=await response.json();
      if(request!==revision||!window.radarAuth.ready)return;
      if(!response.ok)throw Error(data.error||'Não foi possível carregar os detalhes.');
      if(data.episode_id!==episode.id)throw Error('O roteiro recebido pertence a outra edição.');
      render(data);status.textContent='';
    }catch(error){
      if(request!==revision||!window.radarAuth.ready)return;
      status.textContent='Não foi possível carregar o roteiro. Tente abrir os detalhes novamente.';
    }
  }
  return {show,clear};
})();
