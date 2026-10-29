'use strict';
// Tokens ficam apenas em memória. sessionStorage guarda somente state/PKCE temporários.
window.radarAuth={ready:false,config:null,token:null,expiresAt:0,
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
      if(!tokens.access_token)throw Error('Login não retornou autorização de acesso.');
      this.token=tokens.access_token;this.expiresAt=Date.now()+Number(tokens.expires_in)*1000;
    }
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
  logout(){this.token=null;this.expiresAt=0;sessionStorage.removeItem('radar-pkce');const url=new URL(this.config.authDomain+'/logout');url.search=new URLSearchParams({client_id:this.config.clientId,logout_uri:location.origin+'/'});location.assign(url.href);},
  url(path){return this.config?this.config.apiBase+path:path;},
  headers(headers={}){if(!this.config)return headers;if(!this.token||Date.now()>=this.expiresAt)throw Error('Sua sessão expirou. Recarregue a página e entre novamente.');return {...headers,Authorization:'Bearer '+this.token};}
};
