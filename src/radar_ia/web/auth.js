'use strict';
// Access token só em memória; refresh token persistente por até 30 dias, sem armazenar senha.
window.radarAuth={ready:false,config:null,token:null,expiresAt:0,refreshing:null,generation:0,sessionKey:'radar-session-v1',
  async initialize(){
    if(['127.0.0.1','localhost'].includes(location.hostname)){this.ready=true;return true;}
    const response=await fetch('/config.json',{cache:'no-store'});
    if(!response.ok)throw Error('Configuração do aplicativo indisponível.');
    this.config=await response.json();
    const config=this.config;
    // Preparar recuperação antes de analisar o retorno: falhas não escondem Entrar.
    this.showSignedOut();
    document.querySelector('#sign-in').onclick=()=>this.login().catch(error=>document.querySelector('#message').textContent=error.message);
    document.querySelector('#sign-out').onclick=()=>this.logout();
    window.addEventListener('storage',event=>{if((event.key===this.sessionKey||event.key===null)&&!event.newValue){this.generation++;this.showSignedOut();}});
    document.querySelector('#mode').textContent='Acesso privado · entre para ouvir';
    if(!config.apiBase.startsWith('https://')||!config.authDomain.startsWith('https://'))throw Error('Configuração HTTPS inválida.');
    const query=new URLSearchParams(location.search);
    const code=query.get('code');
    if(query.has('error')){history.replaceState({},'',location.pathname);throw Error('O login não foi concluído. Tente entrar novamente.');}
    if(code){
      const saved=sessionStorage.getItem('radar-pkce');sessionStorage.removeItem('radar-pkce');
      history.replaceState({},'',location.pathname);
      if(!saved)throw Error('Este acesso de login expirou. Clique em Entrar para iniciar novamente.');
      const state=JSON.parse(saved);
      if(state.state!==query.get('state')||!Number.isFinite(state.created)||Date.now()-state.created>600000||Date.now()<state.created)throw Error('Este retorno de login é inválido ou expirou. Clique em Entrar para iniciar um novo acesso.');
      const tokenResponse=await fetch(config.authDomain+'/oauth2/token',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({grant_type:'authorization_code',client_id:config.clientId,code,redirect_uri:location.origin+'/',code_verifier:state.verifier})});
      if(!tokenResponse.ok)throw Error('Não foi possível concluir a autenticação. Entre novamente.');
      const tokens=await tokenResponse.json();
      this.acceptTokens(tokens);
      if(tokens.refresh_token)this.saveSession({clientId:config.clientId,refreshToken:tokens.refresh_token,expiresAt:Date.now()+30*86400000});
    }
    if(!code&&this.readSession())await this.refresh();
    this.ready=Boolean(this.token);
    const panel=document.querySelector('#auth-panel');panel.hidden=this.ready;
    document.querySelector('#sign-in').onclick=()=>this.login().catch(error=>document.querySelector('#message').textContent=error.message);
    const logout=document.querySelector('#sign-out');logout.hidden=!this.ready;logout.onclick=()=>this.logout();
    document.querySelector('#library-section').hidden=!this.ready;
    if(this.ready){document.querySelector('#privacy-note').textContent='Seu ponto de escuta é salvo na sua conta. Narração por voz sintética.';}
    return this.ready;
  },
  showSignedOut(){
    this.ready=false;this.token=null;this.expiresAt=0;
    const audio=document.querySelector('#audio');if(audio&&typeof audio.pause==='function'){audio.pause();audio.removeAttribute('src');}
    const preview=document.querySelector('#production-player');if(preview&&typeof preview.pause==='function'){preview.pause();preview.removeAttribute('src');}
    const notices=document.querySelector('#notifications-panel');if(notices)notices.hidden=true;
    const production=document.querySelector('#production-panel');if(production)production.hidden=true;
    document.querySelector('#auth-panel').hidden=false;
    document.querySelector('#library-section').hidden=true;
    document.querySelector('#player-panel').hidden=true;
    document.querySelector('#sign-out').hidden=true;
  },
  async login(){
    const encode=bytes=>btoa(String.fromCharCode(...bytes)).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
    const verifier=encode(crypto.getRandomValues(new Uint8Array(32)));
    const state=encode(crypto.getRandomValues(new Uint8Array(24)));
    const challenge=encode(new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(verifier))));
    sessionStorage.setItem('radar-pkce',JSON.stringify({verifier,state,created:Date.now()}));
    const url=new URL(this.config.authDomain+'/oauth2/authorize');
    url.search=new URLSearchParams({client_id:this.config.clientId,response_type:'code',scope:'openid email',redirect_uri:location.origin+'/',state,code_challenge:challenge,code_challenge_method:'S256'});
    location.assign(url.href);
  },
  clearSession(){try{localStorage.removeItem(this.sessionKey);}catch{}},
  readSession(){
    try{
      const saved=JSON.parse(localStorage.getItem(this.sessionKey)||'null');
      if(!saved)return null;
      if(saved.clientId!==this.config.clientId||typeof saved.refreshToken!=='string'||!saved.refreshToken||!Number.isFinite(saved.expiresAt)||saved.expiresAt<=Date.now()){
        localStorage.removeItem(this.sessionKey);return null;
      }
      return saved;
    }catch{try{localStorage.removeItem(this.sessionKey);}catch{}return null;}
  },
  saveSession(session){
    try{localStorage.setItem(this.sessionKey,JSON.stringify(session));}
    catch{document.querySelector('#message').textContent='Login concluído. O navegador bloqueou salvar a sessão; será necessário entrar novamente ao fechar o app.';}
  },
  acceptTokens(tokens){
    const seconds=Number(tokens.expires_in);
    if(typeof tokens.access_token!=='string'||!tokens.access_token||!Number.isFinite(seconds)||seconds<=0)throw Error('Login não retornou autorização de acesso válida.');
    this.token=tokens.access_token;this.expiresAt=Date.now()+seconds*1000;
  },
  async refresh(){
    if(this.refreshing)return this.refreshing;
    const saved=this.readSession(),generation=this.generation;
    if(!saved){this.showSignedOut();return false;}
    const task=(async()=>{
      const response=await fetch(this.config.authDomain+'/oauth2/token',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
        body:new URLSearchParams({grant_type:'refresh_token',client_id:this.config.clientId,refresh_token:saved.refreshToken})});
      // Sair em outra aba ou durante a requisição nunca ressuscita a sessão.
      if(generation!==this.generation||this.readSession()?.refreshToken!==saved.refreshToken)return false;
      if(!response.ok){
        if([400,401].includes(response.status)){this.clearSession();this.showSignedOut();return false;}
        throw Error('Não foi possível renovar a sessão agora. Confira a conexão e tente novamente.');
      }
      const tokens=await response.json();
      if(generation!==this.generation||this.readSession()?.refreshToken!==saved.refreshToken)return false;
      this.acceptTokens(tokens);this.ready=true;
      if(tokens.refresh_token)this.saveSession({...saved,refreshToken:tokens.refresh_token});
      return true;
    })();
    this.refreshing=task;
    try{return await task;}finally{if(this.refreshing===task)this.refreshing=null;}
  },
  async logout(){
    try{await window.radarNotifications?.disable();}catch{}
    const saved=this.readSession();this.generation++;
    this.clearSession();sessionStorage.removeItem('radar-pkce');this.showSignedOut();
    if(saved){
      try{await fetch(this.config.authDomain+'/oauth2/revoke',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},
        body:new URLSearchParams({client_id:this.config.clientId,token:saved.refreshToken}),signal:AbortSignal.timeout(5000)});}catch{}
    }
    const url=new URL(this.config.authDomain+'/logout');url.search=new URLSearchParams({client_id:this.config.clientId,logout_uri:location.origin+'/'});location.assign(url.href);
  },
  url(path){return this.config?this.config.apiBase+path:path;},
  async headers(headers={}){
    if(!this.config)return headers;
    if(!this.token||Date.now()>=this.expiresAt-60000){if(!await this.refresh())throw Error('Sua sessão expirou. Clique em Entrar para continuar.');}
    return {...headers,Authorization:'Bearer '+this.token};
  }
};
