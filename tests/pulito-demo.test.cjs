const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

// Execute the actual inline demo script against a small event/DOM fixture.
// No antenna, backend, browser printer or network is involved.
function demo(){
  class Element {
    constructor(){this.children=[];this.dataset={};this.style={};this.events={};this.attributes={};this.classes=new Set();this.classList={add:(s)=>this.classes.add(s)};}
    set textContent(s){this.text=String(s);this.children=[];}
    get textContent(){return (this.text||'')+this.children.map(c=>c.textContent).join('');}
    append(...children){this.children.push(...children);}
    setAttribute(k,v){this.attributes[k]=v;}
    addEventListener(k,fn){this.events[k]=fn;}
    click(){if(!this.disabled)this.events.click?.();}
    select(){}
    showModal(){this.open=true;}
    close(){this.open=false;}
  }
  const html=fs.readFileSync(path.join(__dirname,'../docs/pulito-demo.html'),'utf8');
  const elements=new Map();
  for(const match of html.matchAll(/\bid="([^"]+)"/g)){
    assert.ok(!elements.has(match[1]),'Duplicate HTML id '+match[1]);
    elements.set(match[1],new Element());
  }
  elements.get('management').hidden=true;
  let prints=0;
  const document={getElementById:(id)=>{assert.ok(elements.has(id),id);return elements.get(id);},createElement:()=>new Element()};
  vm.runInNewContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],{document,window:{confirm:()=>true,print:()=>prints++},setTimeout:()=>{}});
  const get=(id)=>elements.get(id);
  const scan=(tag)=>{get('tagInput').value=tag;get('scanBtn').click();};
  const cells=()=>get('modules').children.flatMap(bank=>bank.children.at(-1).children);
  return {get,scan,cells,prints:()=>prints};
}

test('Explicit red errors clear active guidance without assigning unknown or foreign tags',()=>{
  const d=demo();
  for(const [button,title,owner] of [
    ['unknownBtn','TAG NON PRESENTE\nNEGLI ARCHIVI','Proprietario non identificabile'],
    ['wrongClientBtn','CLIENTE ERRATO','Altra struttura (demo)'],
    ['wrongArchiveBtn','ARCHIVIO ERRATO','DIVISE OPERATORI']
  ]){
    d.scan('E004000000000001');
    assert.equal(d.cells().filter(c=>c.classes.has('active')).length,1);
    d.get(button).click();
    assert.equal(d.get('hero').dataset.mode,'bad');
    assert.equal(d.get('heroNumber').textContent,title);
    assert.ok((d.get('heroPerson').textContent+d.get('heroDetail').textContent).includes(owner));
    assert.equal(d.cells().filter(c=>c.classes.has('active')).length,0);
    assert.equal(d.cells().filter(c=>c.classes.has('used')).length,1);
    assert.equal(d.get('statItems').textContent,'1');
    assert.equal(d.get('management').hidden,true);
  }
  d.scan('E004000000000004');
  assert.equal(d.get('hero').dataset.mode,'ok');
  assert.equal(d.get('heroNumber').textContent,'CASELLA 02');
});

test('Closure produces one label per occupied slot; re-preview and printing do not recount movements',()=>{
  const d=demo();
  for(const tag of ['E004000000000001','E004000000000002','E004000000000001','E004000000000004'])d.scan(tag);
  d.get('closeBtn').click();
  assert.equal(d.get('statItems').textContent,'3');
  assert.equal(d.get('statMovement').textContent,'3 ricomposizioni');
  assert.equal(d.get('labelPreview').children.length,2);
  assert.ok(d.get('labelPreview').children[0].textContent.includes('CASELLA 01'));
  assert.ok(d.get('labelPreview').children[0].textContent.includes('2 capi'));
  assert.equal(d.prints(),0);
  d.get('closeBtn').click();
  d.get('printBtn').click();
  assert.equal(d.prints(),1);
  assert.equal(d.get('statMovement').textContent,'3 ricomposizioni');
  assert.equal(d.get('labelPreview').children.length,2);
});

test('Management is hidden by default; a scan restores the operator view and all 90 slots remain visible',()=>{
  const d=demo();
  assert.equal(d.get('management').hidden,true);
  assert.equal(d.cells().length,90);
  d.get('menuBtn').click();
  assert.equal(d.get('management').hidden,false);
  assert.equal(d.get('menuBtn').attributes['aria-expanded'],'true');
  d.scan('E004000000000001');
  assert.equal(d.get('management').hidden,true);
  // Occupied cells cannot replace a blocking warning with stale slot guidance.
  assert.ok(d.cells().every(c=>c.disabled));
});
