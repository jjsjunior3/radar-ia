const {test}=require('node:test');const assert=require('node:assert/strict');const vm=require('node:vm');const fs=require('node:fs');const path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'../../src/radar_ia/web/sw.js'),'utf8');
function environment(){const listeners={};const show=()=>{};const sandbox={self:{location:{origin:'https://radar.example'},addEventListener:(name,fn)=>listeners[name]=fn,registration:{showNotification:show},clients:{},skipWaiting:()=>{}},URL};vm.createContext(sandbox);vm.runInContext(code,sandbox);return {sandbox,listeners};}

test('notification click ignores arbitrary payload URL and opens only app origin',async()=>{
 const {sandbox,listeners}=environment();let opened;
 sandbox.self.clients.matchAll=async()=>[];sandbox.self.clients.openWindow=async url=>opened=url;
 let pending;listeners.notificationclick({notification:{data:{url:'https://evil.example'},close(){}},waitUntil:p=>pending=p});await pending;
 assert.equal(opened,'https://radar.example/');
});

test('push shows visible notification without exposing source URLs or credentials',async()=>{
 const {sandbox,listeners}=environment();let received,pending;
 sandbox.self.registration.showNotification=async(title,options)=>received={title,options};
 listeners.push({data:{json:()=>({title:'Untrusted title',body:'Um episódio está pronto.',url:'https://signed.example/?secret=yes',tag:'episode'})},waitUntil:p=>pending=p});await pending;
 assert.equal(received.title,'Radar IA');assert.equal(received.options.body,'Um episódio está pronto.');assert.equal(received.options.url,undefined);assert.equal(received.options.renotify,false);
});

test('existing app window is focused and told to refresh its library',async()=>{
 const {sandbox,listeners}=environment();let focused=false,message,pending;
 sandbox.self.clients.matchAll=async()=>[{url:'https://radar.example/',focus:async()=>focused=true,postMessage:data=>message=data}];
 listeners.notificationclick({notification:{close(){}},waitUntil:p=>pending=p});await pending;
 assert.equal(focused,true);assert.equal(message.type,'radar-notice-opened');
});
