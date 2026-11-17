const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../../src/radar_ia/web/episode-notes.js'),'utf8');
function setup(fetch){
  const elements={};
  function node(tag){return {tag,hidden:true,children:[],textContent:'',append(...items){this.children.push(...items);},replaceChildren(...items){this.children=items;},scrollIntoView(){}};}
  const element=id=>elements[id]||(elements[id]=node('div'));
  const sandbox={window:{radarAuth:{ready:true,url:p=>p,headers:async()=>({})}},
    document:{querySelector:element,createElement:node},fetch,AbortSignal,URL,Date,Number};
  vm.createContext(sandbox);vm.runInContext(source,sandbox);
  return {api:sandbox.window.radarEpisodeNotes,elements,sandbox};
}
function payload(id,url='https://example.org'){
 return {episode_id:id,intro:'Abertura.',outro:'Fim.',glossary:[],
   topics:[{title:'<script>alert(1)</script>',summary:'Resumo.',turns:[{speaker:'Narração',text:'Texto.'}],
     source:{name:'Fonte',url}}]};
}
function descendants(node){return [node,...node.children.flatMap(descendants)];}
test('notes render text safely and refuse unsafe links',async()=>{
 const {api,elements}=setup(async()=>({ok:true,json:async()=>payload('a','javascript:alert(1)')}));
 await api.show({id:'a',title:'Edição'});
 const nodes=descendants(elements['#episode-details-content']);
 assert.equal(nodes.some(n=>n.tag==='script'||n.tag==='a'),false);
 assert(nodes.some(n=>n.textContent==='<script>alert(1)</script>'));
});
test('stale episode response cannot replace a newer episode',async()=>{
 const pending={};
 const {api,elements}=setup(url=>new Promise(resolve=>pending[url]=resolve));
 const a=api.show({id:'a',title:'A'});
 await new Promise(resolve=>setImmediate(resolve));
 const b=api.show({id:'b',title:'B'});
 await new Promise(resolve=>setImmediate(resolve));
 pending['/api/episodes/b']({ok:true,json:async()=>payload('b')});await b;
 pending['/api/episodes/a']({ok:true,json:async()=>payload('a')});await a;
 assert.equal(elements['#episode-details-title'].textContent,'B');
});
test('logout clears private notes and blocks a late response',async()=>{
 let resolve;
 const {api,elements,sandbox}=setup(()=>new Promise(r=>resolve=r));
 const pending=api.show({id:'a',title:'A'});
 await new Promise(r=>setImmediate(r));
 sandbox.window.radarAuth.ready=false;api.clear();
 resolve({ok:true,json:async()=>payload('a')});await pending;
 assert.equal(elements['#episode-details-panel'].hidden,true);
 assert.equal(elements['#episode-details-content'].children.length,0);
});
