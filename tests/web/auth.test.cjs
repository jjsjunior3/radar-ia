const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../../src/radar_ia/web/auth.js'),'utf8');
function setup(created,state='expected'){
 const elements={};
 const element=id=>elements[id]||(elements[id]={hidden:false,textContent:''});
 const storage={'radar-pkce':JSON.stringify({state,verifier:'test-verifier',created})};
 const sandbox={window:{},document:{querySelector:element},location:{hostname:'radar.example',search:'?code=test-code&state=expected',pathname:'/',origin:'https://radar.example'},history:{replaceState(){}},sessionStorage:{getItem:k=>storage[k],removeItem:k=>delete storage[k]},URLSearchParams,URL,Date,Number,fetch:async()=>({ok:true,json:async()=>({apiBase:'https://api.example',authDomain:'https://login.example',clientId:'test'})})};
 vm.createContext(sandbox);vm.runInContext(source,sandbox);
 return {auth:sandbox.window.radarAuth,elements,storage};
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
