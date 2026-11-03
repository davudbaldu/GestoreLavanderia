(function () {
"use strict";
const C = window.LaundryCore, $ = s => document.querySelector(s);
const esc = v => String(v == null ? "" : v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const nf = new Intl.NumberFormat("it-IT");
const fmt = n => nf.format(n);
const today = new Date(), localISO = d => [d.getFullYear(),String(d.getMonth()+1).padStart(2,"0"),String(d.getDate()).padStart(2,"0")].join("-");
const dateAt = offset => { const d = new Date(today); d.setDate(d.getDate()+offset); return localISO(d); };
const niceDate = s => s ? new Intl.DateTimeFormat("it-IT",{day:"2-digit",month:"short",year:"numeric"}).format(new Date(s+"T12:00:00")) : "—";
const people = [
{id:"p1",name:"Ospite Demo 01",kind:"ospite",area:"Reparto A"},{id:"p2",name:"Ospite Demo 02",kind:"ospite",area:"Reparto A"},
{id:"p3",name:"Ospite Demo 03",kind:"ospite",area:"Reparto B"},{id:"p4",name:"Ospite Demo 04",kind:"ospite",area:"Reparto B"},
{id:"p5",name:"Operatore Demo 01",kind:"operatore",area:"Assistenza"},{id:"p6",name:"Operatore Demo 02",kind:"operatore",area:"Assistenza"},
{id:"p7",name:"Operatore Demo 03",kind:"operatore",area:"Servizi"},{id:"s1",name:"Scorta divise M",kind:"scorta",area:"Magazzino"},
{id:"s2",name:"Dotazione reparto",kind:"dotazione",area:"Reparto A"}
];
const articles = ["Maglia","Pantalone","Felpa","Canotta","Casacca","Pantalone lavoro"];
const garmentStates = ["da lavorare","da lavorare","da ricomporre","pronto"];
const garments = Array.from({length:48},(_,i)=>({id:"g"+(i+1),tag:"DEMO"+String(i+1).padStart(8,"0"),personId:people[i%people.length].id,article:articles[i%articles.length],color:["Bianco","Blu","Grigio","Verde"][i%4],status:garmentStates[i%4],lastDate:dateAt(-(i%4)),washes:3+(i*7)%65}));
const labels={preparazione:"In preparazione",pronto:"Pronto al ritiro",ritirato:"Ritirato",consegnato:"Consegnato"};
const statusClass={preparazione:"amber",pronto:"good",ritirato:"blue",consegnato:""};
const seedDeliveries = () => [
{id:"DEMO-001",origin:"interno",service:"Ospiti e divise",date:dateAt(0),client:"Struttura Demo · Sede A",article:"Biancheria ospiti",quantity:2,unit:"roll",status:"pronto",history:[{status:"preparazione",at:"Preparazione dimostrativa"},{status:"pronto",at:"Distinta verificata"}]},
{id:"DEMO-002",origin:"terzista",service:"Piana",date:dateAt(0),client:"Struttura Demo · Sede A",article:"Teli viso",quantity:80,unit:"pezzi",status:"preparazione",history:[{status:"preparazione",at:"Preparazione dimostrativa"}]},
{id:"DEMO-003",origin:"interno",service:"Ospiti e divise",date:dateAt(1),client:"Struttura Demo · Sede A",article:"Divise",quantity:24,unit:"pezzi",status:"preparazione",history:[{status:"preparazione",at:"Preparazione dimostrativa"}]},
{id:"DEMO-004",origin:"terzista",service:"Piana",date:dateAt(-1),client:"Struttura Demo · Sede A",article:"Lenzuola",quantity:60,unit:"pezzi",status:"consegnato",history:[{status:"preparazione",at:"Partita dimostrativa"},{status:"pronto",at:"Pronto"},{status:"ritirato",at:"Ritiro demo"},{status:"consegnato",at:"Consegna demo"}]}
];
function readDemo() {
try { const value=JSON.parse(localStorage.getItem("laundry-demo-v1")); if(Array.isArray(value)&&value.every(d=>typeof d.id==="string"&&Object.hasOwn(labels,d.status)&&/^\d{4}-\d{2}-\d{2}$/.test(d.date)&&typeof d.article==="string"&&Number.isFinite(d.quantity)&&d.quantity>0&&Array.isArray(d.history))) return value; } catch(_) {}
return seedDeliveries();
}
const state={page:"panoramica",search:"",filter:"tutti",deliveries:readDemo(),imports:[],reports:null,busy:false};
function saveDemo(){try{localStorage.setItem("laundry-demo-v1",JSON.stringify(state.deliveries));}catch(_){toast("Memoria del browser non disponibile: la demo resta in questa sessione.");}}
const titles={panoramica:"Panoramica",persone:"Persone e dotazioni",capi:"Capi e tag",movimenti:"Movimenti",consegne:"Consegne e documenti",importazioni:"Importazioni CSV"};
function toast(text){$("#toast").textContent=text;$("#toast").classList.add("visible");setTimeout(()=>$("#toast").classList.remove("visible"),3500);}
function heading(title,desc,action=""){return '<div class="page-heading"><div><span class="eyebrow">GESTIONE OPERATIVA</span><h1>'+esc(title)+'</h1><p>'+esc(desc)+'</p></div>'+action+'</div>';}
function badge(status){return '<span class="tag '+esc(statusClass[status]||"")+'">'+esc(labels[status]||status)+'</span>';}
function kpi(label,value,foot,featured=false){return '<article class="kpi '+(featured?"featured":"")+'"><div class="kpi-label"><span>'+esc(label)+'</span><span class="kpi-icon" aria-hidden="true">↗</span></div><div class="kpi-number">'+esc(value)+'</div><div class="kpi-foot">'+esc(foot)+'</div></article>';}
function deliveryTable(rows,short=false){return '<div class="table-wrap"><table><thead><tr><th>Partita / destinazione</th><th>Origine</th><th>Consegna</th><th>Stato</th><th><span class="secondary-line">Dettaglio</span></th></tr></thead><tbody>'+rows.map(d=>'<tr><td><span class="primary-cell">'+esc(d.client)+'</span><span class="secondary-line">'+esc(d.id)+' · '+esc(d.service)+' · '+fmt(d.quantity)+' '+esc(d.unit)+'</span></td><td>'+esc(d.origin==="interno"?"Laboratorio interno":"Terzista demo")+'</td><td>'+niceDate(d.date)+'</td><td>'+badge(d.status)+'</td><td><button class="button small secondary" data-delivery="'+esc(d.id)+'">'+(short?"Apri":"Documento")+'</button></td></tr>').join("")+'</tbody></table>'+(rows.length?"":'<div class="empty">Nessuna consegna corrisponde ai filtri.</div>')+'</div>';}
function dashboard(){
 const dayDeliveries=state.deliveries.filter(d=>d.date===dateAt(0));
 const ready=garments.filter(g=>g.status==="pronto").length;
 const processing=garments.filter(g=>g.status!=="pronto").length;
 const queue=state.deliveries.filter(d=>d.status!=="consegnato").sort((a,b)=>a.date.localeCompare(b.date)).slice(0,5);
 return heading("Il lavoro, a colpo d’occhio.","Preparazione, tracciabilità e consegne in un’unica vista.",'<button class="button primary" data-new-delivery><span aria-hidden="true">＋</span> Nuova distinta</button>')+
 '<section class="kpi-grid" aria-label="Indicatori demo">'+kpi("Capi registrati",fmt(garments.length),"Solo capi dimostrativi",true)+kpi("In lavorazione",fmt(processing),"Ultimo stato del capo")+kpi("Pronti alla consegna",fmt(ready),"Ricomposizione completata")+kpi("Consegne di oggi",fmt(dayDeliveries.length),"Partite da origini indipendenti")+'</section>'+
 '<div class="dashboard-grid"><div><section class="panel"><div class="panel-head"><div><h2>Le prossime consegne</h2><p>Una destinazione, più partite di lavorazione.</p></div><a class="button link" href="#consegne">Vedi tutte ↗</a></div>'+deliveryTable(queue,true)+'</section>'+
 '<section class="panel"><div class="panel-head"><div><h2>Due letture certe, un percorso completo</h2><p>La demo distingue ciò che viene letto da ciò che è ancora da confermare.</p></div><span class="tag">Tracciabilità</span></div><div class="panel-body"><div class="activity"><span class="activity-dot" aria-hidden="true">↥</span><div><strong>Ingresso sporco</strong><small>Lettura RFID in ingresso · origine della lavorazione</small></div></div><div class="activity"><span class="activity-dot" aria-hidden="true">⇄</span><div><strong>Ricomposizione del pulito</strong><small>Lettura del capo e assegnazione alla persona</small></div></div><div class="activity"><span class="activity-dot" aria-hidden="true">✓</span><div><strong>Ritiro e consegna</strong><small>Conferme distinte dalla lettura del pulito</small></div></div></div></section></div>'+
 '<div><section class="panel"><div class="panel-head"><div><h2>Avanzamento preparazione</h2><p>Distribuzione dei capi della demo</p></div></div><div class="panel-body"><div class="progress-list">'+[["Da lavorare",24],["Da ricomporre",12],["Pronti",12]].map(([l,n],i)=>'<div><div class="progress-label"><span>'+l+'</span><span>'+n+' / 48</span></div><progress class="production-progress p'+i+'" value="'+n+'" max="48">'+n+' su 48</progress></div>').join("")+'</div><div class="panel-callout"><strong>Partiamo dai tuoi report</strong><p>Puoi già verificare i CSV NewPod direttamente sul tuo dispositivo.</p><a href="#importazioni" class="button small secondary">Analizza i CSV ↗</a></div></div></section>'+
 '<section class="panel"><div class="panel-head"><div><h2>Perimetro del pilota</h2></div><span class="count-chip">01</span></div><div class="panel-body"><div class="activity"><div><strong>Una struttura, due servizi</strong><small>Ospiti/divise e piana restano distinti.</small></div></div><div class="activity"><div><strong>Un documento per partita</strong><small>Il laboratorio e il terzista preparano senza aspettarsi.</small></div></div><div class="activity"><div><strong>Storico conservato</strong><small>Identificativi e assegnazioni mantengono la provenienza.</small></div></div></div></section></div></div>';
}
function toolbar(placeholder,options){return '<div class="toolbar"><label class="search" aria-label="Cerca"><input id="view-search" type="search" placeholder="'+esc(placeholder)+'" value="'+esc(state.search)+'"></label><label aria-label="Filtra" class="filter-label"><select id="view-filter">'+options.map(([v,l])=>'<option value="'+esc(v)+'" '+(state.filter===v?"selected":"")+'>'+esc(l)+'</option>').join("")+'</select></label></div>';}
const match=(s)=>s.toLowerCase().includes(state.search.toLowerCase());
function personsView(){const rows=people.filter(p=>match(p.name+" "+p.area)&&(state.filter==="tutti"||p.kind===state.filter));return heading("Persone e dotazioni","Ospiti, personale e scorte hanno ruoli distinti.")+'<section class="panel"><div class="panel-head"><div><h2>Anagrafiche dimostrative</h2><p>Struttura Demo · Sede A</p></div><span class="tag">Dati fittizi</span></div>'+toolbar("Cerca persona, scorta o reparto",[["tutti","Tutte le voci"],["ospite","Ospiti"],["operatore","Personale"],["scorta","Scorte"],["dotazione","Dotazioni"]])+'<div class="table-wrap"><table><thead><tr><th>Nome / assegnazione</th><th>Tipo</th><th>Reparto</th><th>Capi associati</th></tr></thead><tbody>'+rows.map(p=>'<tr><td class="primary-cell">'+esc(p.name)+'</td><td><span class="tag">'+esc({ospite:"Ospite",operatore:"Operatore",scorta:"Scorta",dotazione:"Dotazione"}[p.kind])+'</span></td><td>'+esc(p.area)+'</td><td>'+garments.filter(g=>g.personId===p.id).length+'</td></tr>').join("")+'</tbody></table></div><div class="page-count">'+rows.length+' voci visualizzate</div></section>';}
function garmentsView(){const rows=garments.filter(g=>{const p=people.find(p=>p.id===g.personId);return match(g.tag+" "+g.article+" "+p.name)&&(state.filter==="tutti"||g.status===state.filter)});return heading("Capi e tag","Trova un capo e consulta il suo ultimo passaggio registrato.")+'<section class="panel"><div class="panel-head"><div><h2>Archivio capi</h2><p>Il codice tag resta distinto dall’identità del capo.</p></div><span class="tag">Dati fittizi</span></div>'+toolbar("Cerca tag, articolo o assegnatario",[["tutti","Tutti gli stati"],["da lavorare","Da lavorare"],["da ricomporre","Da ricomporre"],["pronto","Pronti"]])+'<div class="table-wrap"><table><thead><tr><th>Tag / capo</th><th>Assegnazione</th><th>Ultimo stato</th><th>Lavaggi demo</th><th>Storico</th></tr></thead><tbody>'+rows.map(g=>'<tr><td><span class="primary-cell">'+esc(g.article)+'</span><span class="secondary-line mono">'+esc(g.tag)+'</span></td><td>'+esc(people.find(p=>p.id===g.personId).name)+'</td><td><span class="tag '+(g.status==="pronto"?"good":"amber")+'">'+esc(g.status)+'</span></td><td>'+g.washes+'</td><td><button class="button small secondary" data-garment="'+g.id+'">Apri</button></td></tr>').join("")+'</tbody></table></div><div class="page-count">'+rows.length+' capi visualizzati</div></section>';}
function movementsView(){const rows=garments.filter(g=>match(g.tag+" "+g.article));return heading("Movimenti","Ingressi e uscite registrati, senza inventare passaggi intermedi.")+'<div class="notice neutral">Questa vista mostra movimenti dimostrativi. Per verificare lo storico reale usa Importazioni CSV.</div><section class="panel"><div class="panel-head"><h2>Ultime registrazioni demo</h2><span class="tag">RFID</span></div><div class="toolbar"><label class="search" aria-label="Cerca movimento"><input id="view-search" type="search" placeholder="Cerca tag o articolo" value="'+esc(state.search)+'"></label></div><div class="table-wrap"><table><thead><tr><th>Capo</th><th>Registrazione</th><th>Data</th><th>Precisione</th></tr></thead><tbody>'+rows.slice(0,30).map(g=>'<tr><td><span class="mono">'+esc(g.tag)+'</span><span class="secondary-line">'+esc(g.article)+'</span></td><td>'+esc(g.status==="da lavorare"?"Ingresso sporco":"Uscita pulito / ricomposizione")+'</td><td>'+niceDate(g.lastDate)+'</td><td><span class="tag">Solo giorno</span></td></tr>').join("")+'</tbody></table></div><div class="page-count">'+Math.min(rows.length,30)+' registrazioni dimostrative visualizzate</div></section>';}
function deliveriesView(){const rows=state.deliveries.filter(d=>match(d.client+" "+d.id+" "+d.service)&&(state.filter==="tutti"||d.status===state.filter)).sort((a,b)=>b.date.localeCompare(a.date));return heading("Consegne e documenti","Distinte indipendenti per origine, riunite per destinazione.",'<button class="button primary" data-new-delivery>＋ Nuova distinta</button>')+'<div class="notice">Le distinte di questa demo non costituiscono DDT validi. La numerazione fiscale e l’emissione definitiva saranno collegate al gestionale operativo.</div><section class="panel"><div class="panel-head"><div><h2>Partite di consegna</h2><p>Apri una partita per consultare il documento e registrare il passaggio successivo.</p></div><button class="button small secondary" data-reset-demo>Ripristina demo</button></div>'+toolbar("Cerca destinazione, partita o servizio",[["tutti","Tutti gli stati"],["preparazione","In preparazione"],["pronto","Pronti"],["ritirato","Ritirati"],["consegnato","Consegnati"]])+deliveryTable(rows)+'</section>';}
function resultsHTML(){
if(!state.reports)return "";
const totals=state.reports.files.reduce((s,f)=>{s.rows+=f.audit.rows;s.entries+=f.audit.entries;s.exits+=f.audit.exits;return s},{rows:0,entries:0,exits:0});
const issues=state.reports.files.flatMap(f=>f.audit.issues.map(i=>({label:f.name+": "+i.label,count:i.count})));
const r=state.reports.reconciliation;
return '<section class="panel"><div class="panel-head"><div><h2>Esito della verifica</h2><p>I dati sono stati analizzati, non importati in un database condiviso.</p></div><button class="button small secondary" data-export-audit>Scarica riepilogo</button></div><div class="panel-body"><div class="result-grid"><div class="result-card"><b>'+fmt(totals.rows)+'</b><span>Righe analizzate</span></div><div class="result-card"><b>'+fmt(totals.entries)+'</b><span>Ingressi con data valida</span></div><div class="result-card"><b>'+fmt(totals.exits)+'</b><span>Uscite con data valida</span></div></div><ul class="result-list">'+state.reports.files.map(f=>'<li><b>'+esc(f.name)+'</b><span class="secondary-line">'+esc(f.audit.archive)+' · '+esc(f.audit.kind)+' · '+fmt(f.audit.rows)+' righe'+(f.audit.minDate?" · "+niceDate(f.audit.minDate)+" – "+niceDate(f.audit.maxDate):"")+'</span></li>').join("")+'</ul><h3>Controlli fra archivi</h3><ul class="result-list"><li>Tag storici assenti dai file di tag attivi caricati: <b>'+fmt(r.absentActiveTags)+'</b></li><li>Tag con assegnazione storica diversa dall’attuale: <b>'+fmt(r.assignmentDifferences)+'</b></li><li>Codici persona presenti in entrambi gli archivi: <b>'+fmt(r.crossArchivePersonIds)+'</b></li></ul><p class="hint">I confronti con i tag attivi sono disponibili soltanto per gli archivi di cui hai caricato anche quel report. Le righe senza uscita non sono un conteggio dei capi mancanti.</p><h3>Segnalazioni sui file</h3>'+(issues.length?'<ul class="result-list">'+issues.map(i=>'<li>'+esc(i.label)+' <b>('+fmt(i.count)+')</b></li>').join("")+'</ul>':'<p class="hint">Nessuna anomalia rilevata dai controlli eseguiti.</p>')+'</div></section>';
}
function importsView(){return heading("Importazioni CSV","Verifica i report NewPod prima di trasferirli nel nuovo sistema.")+'<section class="panel"><div class="panel-head"><div><h2>Carica i report da verificare</h2><p>Tag attivi, anagrafiche e movimenti · archivi ospiti e divise</p></div><span class="tag good">Analisi sul dispositivo</span></div><div class="panel-body"><div class="import-zone"><span class="eyebrow">REPORT NEWPOD</span><h3>Scegli uno o più file CSV</h3><p>Indica per ogni file l’archivio di provenienza.</p><input id="csv-files" type="file" accept=".csv,text/csv" multiple aria-label="Seleziona i report CSV"><p>I file restano in memoria durante questa sessione. Nessun caricamento online.</p></div><div id="file-list">'+state.imports.map((f,i)=>'<div class="file-row"><div><strong>'+esc(f.name)+'</strong><small>'+esc(f.kind)+' · '+fmt(f.dataset.rows.length)+' righe · '+esc(f.encoding)+'</small></div><select data-archive-index="'+i+'" aria-label="Archivio per '+esc(f.name)+'"><option value="">Scegli archivio</option><option value="ospiti" '+(f.archive==="ospiti"?"selected":"")+'>Ospiti</option><option value="divise" '+(f.archive==="divise"?"selected":"")+'>Divise</option></select></div>').join("")+'</div><div class="import-actions"><button class="button primary" data-analyze '+(!state.imports.length||state.busy?"disabled":"")+'>'+(state.busy?"Analisi in corso…":"Analizza i report")+'</button><button class="button secondary" data-clear-imports '+(!state.imports.length?"disabled":"")+'>Svuota</button><span class="hint">Non modifica NewPod né i file originali.</span></div></div></section>'+resultsHTML();}
function render(){
const active=document.activeElement,id=active&&active.id,selection=active&&active.selectionStart;
$("#crumb").textContent=titles[state.page];document.title=titles[state.page]+" · Gestore Lavanderia";
document.querySelectorAll("[data-page]").forEach(a=>{a.classList.toggle("active",a.dataset.page===state.page);if(a.dataset.page===state.page)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current")});
const views={panoramica:dashboard,persone:personsView,capi:garmentsView,movimenti:movementsView,consegne:deliveriesView,importazioni:importsView};
$("#content").innerHTML=views[state.page]();
if(id==="view-search"&&$("#view-search")){const input=$("#view-search");input.focus();try{input.setSelectionRange(selection,selection)}catch(_){}}
}
function route(){const key=location.hash.slice(1);state.page=Object.hasOwn(titles,key)?key:"panoramica";state.search="";state.filter="tutti";render();}
function showDelivery(id){
const d=state.deliveries.find(x=>x.id===id);if(!d)return;const next={preparazione:"Segna pronto al ritiro",pronto:"Conferma ritiro demo",ritirato:"Conferma consegna demo"}[d.status];
$("#detail-content").innerHTML='<div class="dialog-heading"><div><span class="eyebrow">DOCUMENTO DIMOSTRATIVO</span><h2 id="detail-title">'+esc(d.id)+'</h2></div><button class="icon-button" data-close-dialog aria-label="Chiudi">×</button></div><div class="document-header"><strong>Gestore Lavanderia · Demo</strong><p>Distinta di preparazione · non valida come DDT</p></div><div class="document-meta"><div><small>Destinazione</small>'+esc(d.client)+'</div><div><small>Consegna prevista</small>'+niceDate(d.date)+'</div><div><small>Origine</small>'+esc(d.origin==="interno"?"Laboratorio interno":"Terzista demo")+'</div><div><small>Avanzamento</small>'+esc(labels[d.status])+'</div></div><table><thead><tr><th>Articolo</th><th>Quantità</th><th>Unità</th></tr></thead><tbody><tr><td>'+esc(d.article)+'</td><td>'+fmt(d.quantity)+'</td><td>'+esc(d.unit)+'</td></tr></tbody></table><h3>Passaggi della partita</h3>'+d.history.map(h=>'<div class="timeline-item">'+esc(labels[h.status]||h.status)+'<small>'+esc(h.at)+'</small></div>').join("")+'<div class="dialog-actions"><button class="button secondary" data-print>Stampa / salva PDF</button>'+(next?'<button class="button primary" data-advance="'+esc(d.id)+'">'+esc(next)+'</button>':"")+'</div>';
if(!$("#detail-dialog").open)$("#detail-dialog").showModal();
}
function showGarment(id){
const g=garments.find(x=>x.id===id);if(!g)return;const p=people.find(x=>x.id===g.personId);
$("#detail-content").innerHTML='<div class="dialog-heading"><div><span class="eyebrow">SCHEDA CAPO DEMO</span><h2 id="detail-title">'+esc(g.article)+'</h2></div><button class="icon-button" data-close-dialog aria-label="Chiudi">×</button></div><div class="document-meta"><div><small>Tag</small><span class="mono">'+esc(g.tag)+'</span></div><div><small>Assegnazione</small>'+esc(p.name)+'</div><div><small>Colore</small>'+esc(g.color)+'</div><div><small>Contatore demo</small>'+g.washes+' lavaggi</div></div><h3>Ultimo passaggio dimostrativo</h3><div class="timeline-item">'+esc(g.status==="da lavorare"?"Ingresso sporco":"Uscita pulito / ricomposizione")+'<small>'+niceDate(g.lastDate)+' · precisione: solo giorno</small></div><p class="hint">La scheda conserva separatamente il capo, il tag e l’assegnatario. I passaggi senza lettura non vengono ricostruiti automaticamente.</p>';
$("#detail-dialog").showModal();
}
async function loadFiles(fileList){
state.busy=true;state.reports=null;state.imports=[];render();
try{
const files=Array.from(fileList);if(files.length>12)throw new Error("Seleziona al massimo 12 report per volta.");
for(const file of files){
 if(file.size>25*1024*1024)throw new Error("Il file "+file.name+" supera 25 MB. Dividilo per periodo.");
 const bytes=await file.arrayBuffer();let text,encoding="UTF-8";const a=new Uint8Array(bytes);
 if(a[0]===255&&a[1]===254){text=new TextDecoder("utf-16le",{fatal:true}).decode(bytes);encoding="UTF-16 LE";}
 else if(a[0]===254&&a[1]===255){text=new TextDecoder("utf-16be",{fatal:true}).decode(bytes);encoding="UTF-16 BE";}
 else{try{text=new TextDecoder("utf-8",{fatal:true}).decode(bytes);}catch(_){text=new TextDecoder("windows-1252").decode(bytes);encoding="Windows-1252";}}
 const dataset=C.parseCSV(text),kind=C.classify(dataset.headers);
 state.imports.push({name:file.name,encoding,dataset,kind,archive:""});
 await new Promise(resolve=>setTimeout(resolve,0));
}
}catch(e){toast(e.message||"Non riesco a leggere il CSV.");}
finally{state.busy=false;render();}
}
document.addEventListener("input",e=>{if(e.target.id==="view-search"){state.search=e.target.value;render();}});
document.addEventListener("change",e=>{
 if(e.target.id==="view-filter"){state.filter=e.target.value;render();}
 if(e.target.id==="csv-files")loadFiles(e.target.files);
 if(e.target.matches("[data-archive-index]")){const i=Number(e.target.dataset.archiveIndex);if(state.imports[i])state.imports[i].archive=e.target.value;state.reports=null;}
});
document.addEventListener("click",async e=>{
const button=e.target.closest("button");if(!button)return;
if(button.matches("[data-close-dialog]")){button.closest("dialog").close();return;}
if(button.matches("[data-new-delivery]")){$("#delivery-form").reset();$("#delivery-form [name=date]").value=dateAt(0);$("#delivery-dialog").showModal();}
if(button.dataset.delivery)showDelivery(button.dataset.delivery);
if(button.dataset.garment)showGarment(button.dataset.garment);
if(button.matches("[data-print]"))window.print();
if(button.dataset.advance){const i=state.deliveries.findIndex(x=>x.id===button.dataset.advance);if(i>=0){try{const updated=C.advanceDelivery(state.deliveries[i]);updated.history=[...state.deliveries[i].history,{status:updated.status,at:new Date().toLocaleString("it-IT")}];state.deliveries[i]=updated;saveDemo();render();showDelivery(updated.id);toast("Passaggio dimostrativo registrato.");}catch(error){toast(error.message);}}}
if(button.matches("[data-reset-demo]")){state.deliveries=seedDeliveries();saveDemo();render();toast("Dati dimostrativi ripristinati.");}
if(button.matches("[data-clear-imports]")){state.imports=[];state.reports=null;render();}
if(button.matches("[data-analyze]")){
 if(state.imports.some(f=>!f.archive)){toast("Scegli Ospiti o Divise per ciascun file.");return;}
 state.busy=true;render();await new Promise(resolve=>setTimeout(resolve,0));
 try{const reports=state.imports.map(f=>({name:f.name,audit:C.analyzeDataset(f.dataset,f.archive)}));state.reports={files:reports,reconciliation:C.reconcile(state.imports),createdAt:new Date().toISOString()};}catch(error){toast(error.message);}
 finally{state.busy=false;render();}
}
if(button.matches("[data-export-audit]")&&state.reports){const blob=new Blob([JSON.stringify(state.reports,null,2)],{type:"application/json"});const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="verifica-newpod-"+dateAt(0)+".json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
});
$("#delivery-form").addEventListener("submit",e=>{
e.preventDefault();const form=e.currentTarget;if(!form.reportValidity())return;const v=new FormData(form),quantity=Number(v.get("quantity")),date=String(v.get("date"));
if(!Number.isInteger(quantity)||quantity<1||!C.isoDate(date)){toast("Verifica data e quantità.");return;}
const origin=String(v.get("origin")),id="DEMO-"+Date.now().toString(36).toUpperCase();
state.deliveries.unshift({id,origin,service:origin==="interno"?"Ospiti e divise":"Piana",date,client:"Struttura Demo · Sede A",article:String(v.get("article")),quantity,unit:String(v.get("unit")),status:"preparazione",history:[{status:"preparazione",at:new Date().toLocaleString("it-IT")}]});
saveDemo();$("#delivery-dialog").close();if(location.hash!=="#consegne")location.hash="#consegne";else render();toast("Distinta dimostrativa creata.");
});
$("#today").textContent=new Intl.DateTimeFormat("it-IT",{weekday:"short",day:"numeric",month:"short"}).format(today);
window.addEventListener("hashchange",route);route();
})();