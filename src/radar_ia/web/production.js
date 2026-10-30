'use strict';
window.radarProduction=(()=>{
  const find=id=>document.querySelector('#production-'+id);
  const panel=find('panel');
  let current=null, activeJob=null, timer=null;
  const states={new:'Ainda não preparado',prepared:'Pauta preparada',no_content:'Sem conteúdo para esta edição',
    draft_in_progress:'Preparando o roteiro',draft_failed:'Geração do roteiro interrompida',
    awaiting_human_review:'Duas reprovações: aguardando sua decisão',awaiting_script_review:'Aguardando sua revisão',script_approved:'Roteiro aprovado',
    audio_in_progress:'Preparando o áudio',audio_failed:'Geração do áudio interrompida',
    awaiting_audio_review:'Áudio aguardando escuta',audio_approved:'Áudio aprovado',
    publish_in_progress:'Publicação em andamento',completed:'Publicado'};
  function today(){
    const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
    const value=type=>parts.find(part=>part.type===type).value;
    return `${value('year')}-${value('month')}-${value('day')}`;
  }
  async function request(path,options={}){
    const response=await fetch(window.radarAuth.url(path),{...options,cache:'no-store',headers:await window.radarAuth.headers({'X-Radar-Client':'web',...(options.headers||{})})});
    const data=await response.json();
    if(!response.ok){const error=Error(data.error||'Não foi possível consultar a edição.');error.status=response.status;throw error;}
    return data;
  }
  function render(data){
    const oldDigest=current?.audio_digest;current=data;panel.hidden=false;
    window.dispatchEvent(new CustomEvent('radar-production-state',{detail:{stage:data.stage}}));
    find('editorial-reviews').open=data.stage==='awaiting_human_review';
    if(oldDigest!==data.audio_digest){find('player').pause();find('player').removeAttribute('src');find('player').hidden=true;}
    find('date').textContent=new Date(data.date+'T12:00:00-03:00').toLocaleDateString('pt-BR',{day:'2-digit',month:'long',timeZone:'America/Sao_Paulo'});
    const operation=data.last_editorial_job;
    find('schedule').textContent=data.schedule_enabled?'Seg–sex, 8h30 · São Paulo':'Disparo diário desativado';
    find('last-run').textContent=operation?.started_at||operation?.updated_at?new Date(operation.started_at||operation.updated_at).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo',dateStyle:'short',timeStyle:'short'}):'Aguardando primeira execução';
    const operations={queued:'Na fila',running:'Preparando pauta e roteiro',succeeded:'Execução concluída',failed:'Execução interrompida',needs_review:'Resultado incerto'};
    const recovered=operation?.date===data.date&&['failed','needs_review'].includes(operation.status)&&['awaiting_script_review','script_approved','audio_in_progress','awaiting_audio_review','audio_approved','publish_in_progress','completed'].includes(data.stage);
    find('operation-result').textContent=recovered?'Edição recuperada após interrupção':operation?operations[operation.status]||'Consultar edição':'Ainda sem execução registrada';
    const warning=operation&&['failed','needs_review'].includes(operation.status)&&!recovered&&data.stage!=='completed';
    find('operation-alert').hidden=!warning;
    find('operation-alert').textContent=warning?'A produção encontrou um problema. A tentativa foi preservada e não haverá repetição automática de uma chamada paga.':'';
    find('state').textContent=states[data.stage]||'Em preparação';
    find('theme').textContent=data.theme||'Seu próximo episódio';
    const notes={new:'A edição de hoje ainda não foi preparada.',no_content:'Nenhum conteúdo elegível foi selecionado para hoje.',
      awaiting_human_review:'O avaliador reprovou duas versões. Confira os pareceres e o roteiro; sua aprovação retoma automaticamente Polly e publicação, com custos AWS. As observações orientarão futuras edições.',
      awaiting_script_review:'Leia o texto e confira as fontes antes de aprovar. A aprovação não gera áudio nem publica o episódio.',
      script_approved:'Texto aprovado. A geração e a revisão do áudio são as próximas etapas.',
      awaiting_audio_review:'O áudio está pronto para a próxima etapa de escuta e aprovação pelo fluxo acompanhado.',
      completed:'O episódio já está disponível na sua biblioteca.'};
    find('note').textContent=data.automatic_publication&&!['completed','no_content','awaiting_human_review'].includes(data.stage)?'Modo automático: verificações de roteiro, áudio e duração antes da publicação. Você receberá um aviso quando o episódio estiver disponível.':notes[data.stage]||'Você pode atualizar este painel para acompanhar o andamento.';
    if(data.demo)find('note').textContent='Demonstração com dados fictícios. Aprovar simula a conclusão, sem gerar áudio ou chamar AWS/LLM.';
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
    find('editorial-reviews').hidden=!(data.editorial_reviews||[]).length;
    const findings=find('review-findings');findings.replaceChildren();
    for(const [index,review] of (data.editorial_reviews||[]).entries()){
      const heading=document.createElement('p');heading.textContent=`Versão ${index+1}: ${review.approved?'aprovada':'reprovada'} · qualidade ${review.quality}/5`;findings.append(heading);
      for(const item of review.findings||[]){const line=document.createElement('p');line.textContent=`${item.news_id?'Notícia '+item.news_id+': ':''}${item.issue} Correção sugerida: ${item.correction}`;findings.append(line);}
    }
    find('approve').textContent=data.demo?'Simular aprovação':data.human_escalated&&data.automatic_publication?'Aprovar e continuar automaticamente':'Aprovar roteiro';
    const refinement=data.refinement||{versions:[],examples:[],changes:''};
    find('refinement').hidden=!data.narration;
    find('learning-summary').textContent=`${refinement.examples.length} referência(s) de aprovação humana consultada(s) nesta edição. ${refinement.versions.length} versão(ões) de roteiro preservada(s).`;
    const examples=find('learning-examples');examples.replaceChildren();
    for(const item of refinement.examples){const line=document.createElement('p');line.className='small';line.textContent=`${item.date} · ${item.feedback||'Texto aprovado sem observação adicional.'}`;examples.append(line);}
    const versions=find('script-versions');versions.replaceChildren();
    for(const item of refinement.versions){const details=document.createElement('details'),summary=document.createElement('summary'),text=document.createElement('p');summary.textContent=`Ler versão ${item.version}`;text.className='production-narration';text.textContent=item.narration;details.append(summary,text);versions.append(details);}
    find('diff-section').hidden=!refinement.changes;find('script-diff').textContent=refinement.changes||'';
    find('confirmation').hidden=!data.can_approve_script;
    find('confirm').checked=false;find('approve').disabled=true;
    activeJob=[...(data.jobs||[]),...(['queued','running'].includes(data.editorial_job?.status)?[data.editorial_job]:[])].filter(Boolean).find(job=>job.status!=='succeeded')||null;
    const busy=activeJob&&['queued','running','needs_review'].includes(activeJob.status);
    find('audio-action').hidden=!data.can_generate_audio||Boolean(activeJob);
    find('listen').hidden=!data.audio_digest||data.stage==='completed';
    find('audio-confirmation').hidden=!data.can_approve_audio||Boolean(busy);
    find('publish-action').hidden=!data.can_publish||Boolean(activeJob?.action==='publish');
    for(const [check,button] of [['cost','generate'],['audio-confirm','approve-audio'],['publish-confirm','publish']]){
      find(check).checked=false;find(button).disabled=true;
    }
    showJob(activeJob);

  }
  function showJob(job){
    clearTimeout(timer);activeJob=job;find('job').hidden=!job;
    if(!job)return;
    const labels={queued:'Na fila. Você pode fechar o app.',running:'Processando em segundo plano.',succeeded:'Tarefa concluída.',failed:'A tarefa falhou.',needs_review:'Resultado incerto. A repetição foi bloqueada; precisamos revisar o checkpoint.'};
    const progress=job.total_chunks?` Trechos: ${job.completed_chunks}/${job.total_chunks}.`:'';
    find('job-state').textContent=(labels[job.status]||'Consultando tarefa.')+progress;
    find('retry').hidden=!job.can_retry||!['audio','publish'].includes(job.action);
    if(['queued','running'].includes(job.status)&&!document.hidden)timer=setTimeout(poll,5000);
  }
  async function poll(){
    if(!activeJob||document.hidden||panel.hidden)return;
    try{const job=await request('/api/jobs/'+activeJob.id);showJob(job);
      if(job.status==='succeeded'){await load();if(job.action==='publish')window.dispatchEvent(new Event('radar-episode-published'));}
    }catch(error){find('feedback').textContent=error.message;}
  }
  async function action(path,digest){
    return request('/api/production/'+current.date+'/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({digest,confirmed:true})});
  }
  async function start(actionName){
    const path=actionName==='audio'?'generate-audio':'publish';
    find(actionName==='audio'?'generate':'publish').disabled=true;
    try{const job=await action(path,actionName==='audio'?current.digest:current.audio_digest);await load();showJob(job);}
    catch(error){find('feedback').textContent=error.message;await load();}
  }
  for(const [check,button] of [['cost','generate'],['audio-confirm','approve-audio'],['publish-confirm','publish']]){
    find(check).onchange=()=>{find(button).disabled=!find(check).checked;};
  }
  find('generate').onclick=()=>{if(current?.can_generate_audio&&find('cost').checked)start('audio');};
  find('publish').onclick=()=>{if(current?.can_publish&&find('publish-confirm').checked)start('publish');};
  find('retry').onclick=()=>{if(activeJob?.can_retry)start(activeJob.action);};
  find('preview').onclick=async()=>{
    find('preview').disabled=true;
    try{const data=await request('/api/production/'+current.date+'/preview');find('player').src=data.url;find('player').hidden=false;}
    catch(error){find('feedback').textContent=error.message;}
    finally{find('preview').disabled=false;}
  };
  find('approve-audio').onclick=async()=>{
    if(!current?.can_approve_audio||!find('audio-confirm').checked)return;
    find('approve-audio').disabled=true;
    try{render(await action('approve-audio',current.audio_digest));find('feedback').textContent='Áudio aprovado. Agora você pode publicar na biblioteca privada.';}
    catch(error){await load();find('feedback').textContent=error.message;}
  };
  document.addEventListener('visibilitychange',()=>{if(document.hidden)clearTimeout(timer);else if(!panel.hidden)load();});
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
        headers:{'Content-Type':'application/json'},body:JSON.stringify({digest:current.digest,confirmed:true,feedback:find('editorial-feedback').value.trim()})});
      render(result);find('editorial-feedback').value='';find('feedback').textContent=result.demo?'Aprovação simulada. Nenhum episódio ou chamada paga foi gerado.':result.human_escalated&&result.automatic_publication?'Decisão registrada. O fluxo automático foi retomado; suas observações orientarão as próximas edições.':'Roteiro aprovado e preferência editorial registrada. Nenhuma geração de voz ou publicação foi iniciada.';
    }catch(error){
      if(error.status===409)await load();
      find('feedback').textContent=error.message;
      find('approve').disabled=!find('confirm').checked;
    }
  };
  return {load};
})();
