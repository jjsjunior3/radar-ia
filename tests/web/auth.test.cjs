const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../../src/radar_ia/web/auth.js'),'utf8');
function setup(created,state='expected',options={}){
 const elements={};
 const element=id=>elements[id]||(elements[id]={hidden:false,textContent:''});
 const storage={'radar-pkce':JSON.stringify({state,verifier:'test-verifier',created})};
 const persistent=options.persistent||{};const listeners={};
 const sandbox={window:{addEventListener:(name,callback)=>listeners[name]=callback},AbortSignal,localStorage:{getItem:k=>persistent[k]||null,setItem:(k,v)=>persistent[k]=v,removeItem:k=>delete persistent[k]},document:{querySelector:element},location:{hostname:'radar.example',search:'?code=test-code&state=expected',pathname:'/',origin:'https://radar.example',assign:url=>sandbox.destination=url},history:{replaceState(){}},sessionStorage:{getItem:k=>storage[k],removeItem:k=>delete storage[k]},URLSearchParams,URL,Date,Number,fetch:async()=>({ok:true,json:async()=>({apiBase:'https://api.example',authDomain:'https://login.example',clientId:'test'})})};
 if(options.search!==undefined)sandbox.location.search=options.search;
 if(options.fetch)sandbox.fetch=options.fetch;
 vm.createContext(sandbox);vm.runInContext(source,sandbox);
 return {auth:sandbox.window.radarAuth,elements,storage,persistent,sandbox,listeners};
}
test('expired callback leaves login button accessible and keeps library hidden',async()=>{
 const {auth,elements}=setup(Date.now()-601000);
 await assert.rejects(auth.initialize(),/expirou/);
 assert.equal(elements['#auth-panel'].hidden,false);
 assert.equal(elements['#library-section'].hidden,true);
 assert.equal(typeof elements['#sign-in'].onclick,'function');
 assert.equal(auth.token,null);
});
test('incorrect OAuth state remains rejected',async()=>{
 const {auth,elements}=setup(Date.now(),'wrong');
 await assert.rejects(auth.initialize(),/inválido/);
 assert.equal(elements['#auth-panel'].hidden,false);
});
test('future state timestamp is rejected',async()=>{
 const {auth}=setup(Date.now()+60000);
 await assert.rejects(auth.initialize(),/inválido/);
});

const config={apiBase:'https://api.example',authDomain:'https://login.example',clientId:'test'};
const sessionKey='radar-session-v1';
function savedSession(){return {[sessionKey]:JSON.stringify({clientId:'test',refreshToken:'test-refresh',expiresAt:Date.now()+86400000})};}
const response=(data,status=200)=>({ok:status>=200&&status<300,status,json:async()=>data});

test('new login persists refresh token without password or access token',async()=>{
 const env=setup(Date.now(),'expected',{fetch:async url=>url==='/config.json'?response(config):response({access_token:'test-access',refresh_token:'test-refresh',expires_in:3600})});
 assert.equal(await env.auth.initialize(),true);
 const saved=JSON.parse(env.persistent[sessionKey]);
 assert.equal(saved.refreshToken,'test-refresh');assert.equal(saved.access_token,undefined);
 assert.equal(env.auth.token,'test-access');
});

test('reopening app restores session without password and only refreshes once for concurrent requests',async()=>{
 const persistent=savedSession();let refreshes=0;
 const env=setup(Date.now(),'expected',{persistent,search:'',fetch:async(url,options)=>{
  if(url==='/config.json')return response(config);
  refreshes++;assert.equal(options.body.get('grant_type'),'refresh_token');
  assert.equal(options.body.get('refresh_token'),'test-refresh');
  return response({access_token:'renewed-access',expires_in:3600});
 }});
 assert.equal(await env.auth.initialize(),true);assert.equal(refreshes,1);
 assert.equal(env.elements['#auth-panel'].hidden,true);
 env.auth.expiresAt=0;
 const headers=await Promise.all([env.auth.headers(),env.auth.headers()]);
 assert.equal(refreshes,2);assert.equal(headers[0].Authorization,'Bearer renewed-access');
 assert.equal(headers[1].Authorization,headers[0].Authorization);
});

test('expired or revoked refresh token clears persisted session and offers sign in',async()=>{
 const env=setup(Date.now(),'expected',{persistent:savedSession(),search:'',fetch:async url=>url==='/config.json'?response(config):response({error:'invalid_grant'},400)});
 assert.equal(await env.auth.initialize(),false);assert.equal(env.persistent[sessionKey],undefined);
 assert.equal(env.auth.token,null);assert.equal(env.elements['#auth-panel'].hidden,false);
});

test('temporary service failure preserves session for a later retry',async()=>{
 const env=setup(Date.now(),'expected',{persistent:savedSession(),search:'',fetch:async url=>url==='/config.json'?response(config):response({},503)});
 await assert.rejects(env.auth.initialize(),/renovar/);assert.ok(env.persistent[sessionKey]);
});

test('logout clears local access and revokes refresh token before Cognito logout',async()=>{
 let revocations=0;
 const env=setup(Date.now(),'expected',{persistent:savedSession(),search:'',fetch:async(url,options)=>{
  if(url==='/config.json')return response(config);
  if(url.endsWith('/revoke')){revocations++;assert.equal(options.body.get('token'),'test-refresh');return response({});}
  return response({access_token:'renewed-access',expires_in:3600});
 }});
 await env.auth.initialize();await env.auth.logout();
 assert.equal(env.persistent[sessionKey],undefined);assert.equal(env.auth.token,null);
 assert.equal(revocations,1);assert.match(env.sandbox.destination,/login.example\/logout/);
});

test('logout in another tab cannot be undone by an in-flight refresh',async()=>{
 let finish;
 const env=setup(Date.now(),'expected',{persistent:savedSession(),search:'',fetch:async url=>url==='/config.json'?response(config):new Promise(resolve=>finish=resolve)});
 const initialized=env.auth.initialize();
 while(!finish)await new Promise(resolve=>setImmediate(resolve));
 delete env.persistent[sessionKey];env.listeners.storage({key:sessionKey,newValue:null});
 finish(response({access_token:'late-access',expires_in:3600}));
 assert.equal(await initialized,false);assert.equal(env.auth.token,null);
});

test('expired local persistence is discarded without a refresh call',async()=>{
 const persistent=savedSession();const saved=JSON.parse(persistent[sessionKey]);saved.expiresAt=Date.now()-1;persistent[sessionKey]=JSON.stringify(saved);
 let calls=0;const env=setup(Date.now(),'expected',{persistent,search:'',fetch:async()=>{calls++;return response(config);}});
 assert.equal(await env.auth.initialize(),false);assert.equal(calls,1);assert.equal(persistent[sessionKey],undefined);
});
