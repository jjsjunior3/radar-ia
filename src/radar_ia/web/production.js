'use strict';
window.radarProduction=(()=>{
  const find=id=>document.querySelector('#production-'+id);
  const panel=find('panel');
  let current=null;
  const states={new:'Ainda não preparado',prepared:'Pauta preparada',no_content:'Sem conteúdo para esta edição',
    draft_in_progress:'Preparando o roteiro',draft_failed:'Geração do roteiro interrompida',
    awaiting_script_review:'Aguardando sua revisão',script_approved:'Roteiro aprovado',
    audio_in_progress:'Preparando o áudio',audio_failed:'Geração do áudio interrompida',
    awaiting_audio_review:'Áudio aguardando escuta',audio_approved:'Áudio aprovado',
    publish_in_progress:'Publicação em andamento',completed:'Publicado'};
  function today(){
    const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
    const value=type=>parts.find(part=>part.type===type).value;
    return `${value('year')}-${value('month')}-${value('day')}`;
  }
  async function request(path,options={}){
    const response=await fetch(window.radarAuth.url(path),{...options,cache:'no-store',headers:window.radarAuth.headers(options.headers||{})});
    const data=await response.json();
    if(!response.ok){const error=Error(data.error||'Não foi possível consultar a edição.');error.status=response.status;throw error;}
    return data;
  }
  function render(data){
    current=data;panel.hidden=false;
    find('date').textContent=new Date(data.date+'T12:00:00-03:00').toLocaleDateString('pt-BR',{day:'2-digit',month:'long',timeZone:'America/Sao_Paulo'});
    find('state').textContent=states[data.stage]||'Em preparação';
    find('theme').textContent=data.theme||'Seu próximo episódio';
    const notes={new:'A edição de hoje ainda não foi preparada.',no_content:'Nenhum conteúdo elegível foi selecionado para hoje.',
      awaiting_script_review:'Leia o texto e confira as fontes antes de aprovar. A aprovação não gera áudio nem publica o episódio.',
      script_approved:'Texto aprovado. A geração e a revisão do áudio são as próximas etapas.',
      awaiting_audio_review:'O áudio está pronto para a próxima etapa de escuta e aprovação pelo fluxo acompanhado.',
      completed:'O episódio já está disponível na sua biblioteca.'};
    find('note').textContent=notes[data.stage]||'Você pode atualizar este painel para acompanhar o andamento.';
    find('details').hidden=!data.narration;
    find('narration').textContent=data.narration||'';
    const sources=find('sources');sources.replaceChildren();
    for(const source of data.sources||[]){
      const item=document.createElement('li'),link=document.createElement('a');
      const url=new URL(source.url);
      if(url.protocol!=='https:'||url.username||url.password)continue;
      link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';
      link.textContent=`${source.source} — ${source.title}`;item.append(link);sources.append(item);
    }
    find('confirmation').hidden=!data.can_approve_script;
    find('confirm').checked=false;find('approve').disabled=true;
  }
  async function load(){
    find('refresh').disabled=true;find('feedback').textContent='';
    try{render(await request('/api/production/'+today()));}
    catch(error){
      if([401,403,404].includes(error.status)){panel.hidden=true;return;}
      panel.hidden=false;find('note').textContent='Não foi possível consultar a edição.';find('feedback').textContent=error.message;
    }finally{find('refresh').disabled=false;}
  }
  find('refresh').onclick=load;
  find('confirm').onchange=()=>{find('approve').disabled=!find('confirm').checked;};
  find('approve').onclick=async()=>{
    if(!current?.can_approve_script||!find('confirm').checked)return;
    find('approve').disabled=true;find('feedback').textContent='Registrando sua aprovação…';
    try{
      const result=await request('/api/production/'+current.date+'/approve-script',{method:'POST',
        headers:{'Content-Type':'application/json'},body:JSON.stringify({digest:current.digest,confirmed:true})});
      render(result);find('feedback').textContent='Roteiro aprovado. Nenhuma geração de voz ou publicação foi iniciada.';
    }catch(error){
      if(error.status===409)await load();
      find('feedback').textContent=error.message;
      find('approve').disabled=!find('confirm').checked;
    }
  };
  return {load};
})();
