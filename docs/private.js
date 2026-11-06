(function(){
"use strict";
const $=s=>document.querySelector(s),esc=v=>String(v==null?"":v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const api=new window.LaundryPrivateClient(window.LaundryBackendConfig);
const operations=new window.LaundryOperations(api,toast);
const catalogue=new window.LaundryCatalogue(api,toast);
const rfid=new window.LaundryRFID(api,toast);
const fmt=n=>new Intl.NumberFormat("it-IT").format(n||0);
const niceDate=s=>s?new Intl.DateTimeFormat("it-IT",{day:"2-digit",month:"short",year:"numeric"}).format(new Date(s.slice(0,10)+"T12:00:00")):"—";
let activation=new URLSearchParams(location.hash.slice(1)).get("attiva")||"";
if(!/^[0-9a-f]{64}$/.test(activation))activation="";
const state={section:"panoramica",archive:"ospiti",offset:0,total:0,search:"",field:"person_name_key",rows:[],batches:[],overview:null,user:null,request:0};
const titles={letture:"Letture sporco e pulito",ospiti:"Ospiti e capi personali",operatori:"Operatori e divise",qualita:"Qualità dati",panoramica:"Panoramica",persone:"Persone e dotazioni",tag:"Capi e tag",movimenti:"Movimenti",consegne:"Consegne e preparazione",flusso:"Flusso lavanderia",report:"Report e verifiche"};
function icon(name){const paths={tag:'<path d="M20 13 13 20a2 2 0 0 1-3 0L3 13V4h9l8 7a2 2 0 0 1 0 2Z"/><circle cx="7.5" cy="8" r="1"/>',people:'<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3M16 5a3 3 0 0 1 0 6m2 4a5 5 0 0 1 3 4v2"/>',flow:'<path d="M4 7h16m-4-4 4 4-4 4M20 17H4m4-4-4 4 4 4"/>',shield:'<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-6"/>',arrow:'<path d="M5 12h14m-6-6 6 6-6 6"/>',clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',grid:'<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',report:'<path d="M14 3H5v18h14V8Zm0 0v5h5M8 12h8m-8 4h6"/>'};return '<svg class="ui-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(paths[name]||paths.flow)+'</svg>';}
function latestImport(){return state.batches.reduce((latest,b)=>b.imported_at>latest?b.imported_at:latest,"");}
function archiveStats(archive){const rows=state.overview.batches||[],sum=kind=>rows.filter(b=>b.archive===archive&&b.kind===kind).reduce((n,b)=>n+Number(b.records||0),0);return {people:sum("persone"),tags:sum("tag"),movements:sum("movimenti")};}
function toast(s){$("#private-toast").textContent=s;$("#private-toast").classList.add("visible");setTimeout(()=>$("#private-toast").classList.remove("visible"),3500);}
function heading(title,description){return '<div class="page-heading"><div><span class="eyebrow">ARCHIVIO IMPORTATO</span><h1>'+esc(title)+'</h1><p>'+esc(description)+'</p></div><span class="tag good">Sola consultazione</span></div>';}
function message(s,error=false){const e=$("#login-message");if(e){e.textContent=s;e.classList.toggle("error",error);}else toast(s);}
function renderLogin(mode=activation?"signup":"login"){
 operations.leave();catalogue.leave();rfid.leave();
 state.request++;state.rows=[];state.batches=[];state.overview=null;state.user=null;
 $("#private-nav").hidden=true;$("#logout").hidden=true;$("#private-crumb").textContent="Accesso personale";$("#private-account").innerHTML='Accesso personale<small>Consultazione protetta</small>';
 $("#private-content").innerHTML='<section class="login-wrap"><span class="eyebrow">GESTORE LAVANDERIA</span><h1>Il tuo archivio, riservato.</h1><p>Accedi per consultare anagrafiche, capi e movimenti importati da NewPod.</p><div class="panel"><div class="panel-head"><h2>'+esc(mode==="signup"?"Crea il tuo accesso":"Accedi all’archivio")+'</h2><span class="tag">Personale</span></div><div class="panel-body"><div class="login-tabs" role="tablist" aria-label="Accesso"><button class="button secondary" data-auth-mode="login" role="tab" aria-selected="'+(mode==="login")+'">Accedi</button><button class="button secondary" data-auth-mode="signup" role="tab" aria-selected="'+(mode==="signup")+'">Primo accesso</button></div><form id="auth-form" data-mode="'+mode+'"><label>Email<input id="auth-email" name="email" type="email" autocomplete="username" required></label><label>Password<input id="auth-password" name="password" type="password" autocomplete="'+(mode==="signup"?"new-password":"current-password")+'" minlength="'+(mode==="signup"?"12":"1")+'" required></label>'+(mode==="signup"?'<p class="hint">Per il pilota usa l’email del tuo account Supabase. Scegli una password di almeno 12 caratteri e conferma l’indirizzo dal messaggio ricevuto. Poi torna qui e accedi.</p>':'')+'<button class="button primary" id="auth-submit" type="submit">'+(mode==="signup"?"Crea accesso":"Accedi")+'</button><p class="login-message" id="login-message" role="status"></p></form>'+(activation?'<p class="hint">Il collegamento personale di attivazione è stato riconosciuto. L’accesso ai dati si abilita dopo la verifica dell’email.</p>':'<p class="hint">La registrazione da sola non concede accesso ai dati. Serve un account abilitato.</p>')+'</div></div></section>';
 styleLogin();
}
function styleLogin(){
 const content=$("#private-content"),form=content.querySelector(".login-wrap"),layout=document.createElement("div");
 layout.className="login-layout";
 layout.innerHTML='<section class="login-story"><span class="eyebrow">IL FILO CHE COLLEGA TUTTO</span><h2>Ogni capo.<br> Ogni persona.<br> <span>Un’unica vista.</span></h2><p>Dallo sporco alla ricomposizione, ritrova la storia dei capi e delle persone a cui appartengono.</p><div class="laundry-visual" aria-hidden="true"><div class="visual-thread"></div><div class="visual-tag">'+icon("tag")+'<span>Un’identità per ogni capo</span></div><div class="visual-cabinet">'+Array.from({length:6},()=>'<span></span>').join("")+'</div><div class="visual-label">OSPITI & DIVISE</div></div><div class="login-assurance">'+icon("shield")+'<span>Archivio privato · accesso personale</span></div></section>';
 form.querySelector("h1").textContent=form.querySelector("[data-mode]").dataset.mode==="signup"?"Iniziamo da qui.":"Bentornato.";
 layout.appendChild(form);content.appendChild(layout);
}
function renderActivation(){
 $("#private-content").innerHTML='<section class="login-wrap"><span class="eyebrow">PRIMO ACCESSO</span><h1>Attiva il tuo archivio.</h1><p>L’email è stata verificata. Inserisci il codice personale ricevuto con il collegamento di attivazione.</p><section class="panel"><div class="panel-body"><form id="activation-form"><label>Codice di attivazione<input name="code" type="password" class="activation-code" minlength="64" maxlength="64" autocomplete="off" required></label><button class="button primary" type="submit">Attiva accesso</button><p class="login-message" id="login-message" role="status"></p></form></div></section></section>';
}
async function afterLogin(){
 state.user=await api.user();$("#logout").hidden=false;
 if(activation){await api.claim(activation);activation="";history.replaceState(null,"",location.pathname+location.search);}
 const members=await api.membership();if(!members.length){renderActivation();return;}
 const [batches,overview]=await Promise.all([api.batches(),api.overview()]);
 state.batches=batches;state.overview=overview;$("#private-nav").hidden=false;$("#logout").hidden=false;
 $("#private-account").innerHTML=esc(state.user.email||"Account abilitato")+'<small>Proprietario · archivio riservato</small>';render();
}
function kpi(label,n,detail,symbol){return '<article class="kpi"><div class="kpi-label">'+esc(label)+'<span class="metric-icon '+esc(symbol)+'">'+icon(symbol)+'</span></div><div class="kpi-number">'+fmt(n)+'</div><div class="kpi-foot">'+esc(detail)+'</div></article>';}
function dashboard(){
 const b=state.overview.batches||[],sum=(kind,field)=>b.filter(x=>x.kind===kind).reduce((s,x)=>s+Number(x[field]||0),0);
 $("#private-content").innerHTML=heading("La lavanderia, a colpo d’occhio.","Persone, capi e tracciabilità. Tutto parte da qui.")+
 '<section class="archive-hero"><div><span class="eyebrow">IL TUO PATRIMONIO DI DATI</span><h2>Ogni capo ha una storia.<br>Ora puoi ritrovarla.</h2><p>Esplora gli archivi ospiti e divise, cerca un tag<br class="desktop-break"> e consulta i movimenti originali.</p><button class="button hero-button" data-section="ospiti">Cerca un capo '+icon("arrow")+'</button></div><div class="hero-emblem" aria-hidden="true"><div class="emblem-orbit"></div><div class="emblem-tag">'+icon("tag")+'</div><span class="emblem-label">TRACCIABILITÀ, IN ORDINE.</span></div></section>'+
 '<section class="kpi-grid private-kpis" aria-label="Totali dei report importati">'+kpi("Tag attivi registrati",sum("tag","records"),"Negli ultimi report importati","tag")+kpi("Voci anagrafiche",sum("persone","records"),"Persone, scorte e voci generiche","people")+kpi("Righe di movimento",sum("movimenti","records"),"Storico importato · ingresso e/o uscita","flow")+'</section>'+
 '<div class="archive-layout"><section class="panel"><div class="panel-head"><div><h2>Due archivi, una visione chiara.</h2><p>Consulta i dati per servizio.</p></div>'+icon("grid")+'</div><div class="panel-body archive-cards">'+archiveCard("ospiti")+archiveCard("divise")+'</div></section><section class="panel sync-card"><div class="panel-head"><h2>Postazioni di lavanderia</h2>'+icon("flow")+'</div><div class="panel-body"><span class="tag amber">Tempo reale da attivare</span><p>I dati disponibili sono quelli dei report caricati. Le nuove letture non arrivano ancora automaticamente.</p><div class="import-stamp">'+icon("clock")+'<div><small>Ultimo caricamento</small><strong>'+esc(niceDate(latestImport()))+'</strong></div></div><button class="button secondary" data-section="flusso">Il nostro sistema '+icon("arrow")+'</button></div></section></div>'+
 '<section class="panel"><div class="panel-head"><div><h2>Le fonti del tuo archivio</h2><p>Report originali e data di caricamento.</p></div><button class="button link" data-section="report">Vedi verifiche '+icon("arrow")+'</button></div>'+batchTable()+'</section>';
}
function archiveCard(archive){const s=archiveStats(archive),guests=archive==="ospiti";return '<article class="archive-card"><div class="archive-card-title"><span class="archive-symbol '+(guests?"guests":"uniforms")+'">'+icon(guests?"people":"tag")+'</span><div><h3>'+esc(guests?"Capi degli ospiti":"Divise del personale")+'</h3><p>'+esc(guests?"Ospiti, dotazioni e scorte":"Operatori, assegnazioni e scorte")+'</p></div></div><div class="archive-card-numbers"><div><strong>'+fmt(s.tags)+'</strong><small>Tag attivi</small></div><div><strong>'+fmt(s.people)+'</strong><small>Voci anagrafiche</small></div></div><button class="button link" data-section="'+(guests?"ospiti":"operatori")+'" data-archive="'+archive+'">Esplora i capi '+icon("arrow")+'</button></article>';}
function renderFlow(){
 $("#private-content").innerHTML=heading("Un software, tutta la lavanderia.","Dalle antenne ai documenti di consegna: il sistema da costruire insieme.")+
 '<section class="panel flow-intro"><div class="panel-head"><div><h2>Le nostre postazioni, il nostro gestionale</h2><p>Tunnel e armadi invieranno eventi indipendenti allo stesso sistema centrale.</p></div><span class="tag amber">Software postazioni da realizzare</span></div><div class="panel-body"><ol class="flow-steps"><li><span class="flow-number">INGRESSO</span>'+icon("tag")+'<h3>Tunnel dello sporco</h3><p>Il nostro programma acquisirà i tag dall’antenna esistente e registrerà l’ingresso dei capi.</p></li><li><span class="flow-number">RICOMPOSIZIONE</span>'+icon("grid")+'<h3>Quattro armadi</h3><p>Il nostro programma riconoscerà il capo e guiderà la ricomposizione per ospite o operatore.</p></li><li><span class="flow-number">GESTIONE CENTRALE</span>'+icon("flow")+'<h3>Un unico database</h3><p>Letture, capi, assegnazioni e lavorazioni aggiornati automaticamente per tutta la lavanderia.</p></li><li><span class="flow-number">USCITA E CONTROLLO</span>'+icon("report")+'<h3>Consegne e report</h3><p>Distinte, bolle per i trasportatori, uscite, conferme di consegna e report per cliente.</p></li></ol><div class="notice neutral">La lettura del pulito e la consegna sono due eventi distinti. Il gestionale dovrà registrare e mostrare entrambi.</div></div></section>'+
 '<div class="flow-detail-grid"><section class="panel"><div class="panel-head"><h2>Il punto di partenza: i tuoi dati</h2></div><div class="panel-body"><p>Sono disponibili '+fmt(state.batches.length)+' report importati da NewPod. Ultimo caricamento: <strong>'+esc(niceDate(latestImport()))+'</strong>. Sono lo storico iniziale; non costituiscono ancora un sistema di produzione.</p><button class="button secondary" data-section="ospiti">Consulta lo storico '+icon("arrow")+'</button></div></section><section class="panel"><div class="panel-head"><h2>Il prossimo passo: comandare le postazioni</h2></div><div class="panel-body"><p>Servono i modelli e i protocolli delle antenne e delle centraline degli armadi per realizzare i nostri programmi di lettura e ricomposizione.</p><p class="hint">Obiettivo: una sola lettura, aggiornamento entro pochi secondi, recupero dopo interruzioni di rete. Il software esistente sarà sostituito dopo il collaudo sul campo.</p></div></section></div>';
}
function batchTable(){return '<div class="table-wrap"><table><thead><tr><th>Report</th><th>Archivio</th><th>Righe</th><th>Caricamento</th></tr></thead><tbody>'+state.batches.map(b=>'<tr><td class="primary-cell">'+esc(b.file_name)+'</td><td>'+esc(b.archive==="ospiti"?"Ospiti":"Divise")+'</td><td>'+fmt(b.summary.rows)+'</td><td>'+niceDate(b.imported_at)+'</td></tr>').join("")+'</tbody></table></div>';}
function render(){
 operations.leave();catalogue.leave();rfid.leave();
 $("#private-crumb").textContent=titles[state.section];document.title=titles[state.section]+" · Archivio riservato";
 document.querySelectorAll("#private-nav [data-section]").forEach(a=>{a.classList.toggle("active",a.dataset.section===state.section);if(a.dataset.section===state.section)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current")});
 if(state.section==="panoramica"){dashboard();return;}
 if(["ospiti","operatori","qualita"].includes(state.section)){catalogue.open($("#private-content"),state.section==="operatori"?"divise":state.section==="ospiti"?"ospiti":state.archive,state.user,state.section==="qualita");return;}
 if(state.section==="letture"){rfid.open($("#private-content"));return;}
 if(state.section==="consegne"){operations.open($("#private-content"),state.user);return;}
 if(state.section==="flusso"){renderFlow();return;}
 if(state.section==="report"){renderReports();return;}
 const kind=state.section,description={persone:"Anagrafiche originali, comprese le assegnazioni generiche.",tag:"Tag, articoli, assegnazioni e contatori conservati dal report.",movimenti:"Righe originali con ingresso e/o uscita del capo."}[kind];
 $("#private-content").innerHTML=heading(titles[kind],description)+'<section class="panel"><div class="panel-head"><h2 id="report-title">Archivio '+esc(state.archive)+'</h2><span class="tag">Dati originali</span></div><form class="toolbar private-tools" id="records-filter"><select name="archive" aria-label="Archivio"><option value="ospiti" '+(state.archive==="ospiti"?"selected":"")+'>Ospiti</option><option value="divise" '+(state.archive==="divise"?"selected":"")+'>Divise</option></select><select name="field" aria-label="Campo di ricerca"><option value="person_name_key" '+(state.field==="person_name_key"?"selected":"")+'>Nominativo</option>'+(kind!=="persone"?'<option value="tag_id" '+(state.field==="tag_id"?"selected":"")+'>Tag</option>':"")+'</select><input name="search" type="search" placeholder="Cerca nell’intero report" value="'+esc(state.search)+'" aria-label="Testo da cercare"><button class="button secondary" type="submit">Cerca</button></form><div id="records-content" class="private-loading">Caricamento dei dati…</div><div class="private-paging"><span id="records-count"></span><div class="action-row"><button class="button small secondary" id="previous-page" disabled>Precedenti</button><button class="button small secondary" id="next-page" disabled>Successivi</button></div></div></section>';loadRows();
}
async function loadRows(){
 const seq=++state.request,section=state.section,batch=state.batches.find(b=>b.archive===state.archive&&b.kind===section);
 if(!batch){$("#records-content").innerHTML='<div class="empty">Nessun report disponibile per questo archivio.</div>';return;}
 try{
  const result=await api.records(batch.id,{offset:state.offset,limit:50,search:state.search,field:state.field});
  if(seq!==state.request||!api.token)return;state.rows=result.data;state.total=result.total;
  $("#report-title").textContent=batch.file_name;
  const columns=section==="persone"?[["Cognome","Cognome"],["Nome","Nome"],["Area","Area / reparto"],["Piano","Piano"],["Ingresso","Ingresso"],["Uscita","Uscita"]]:
   section==="tag"?[["Tag ID","Tag"],["Classe merceologica","Articolo"],["Cognome","Cognome"],["Nome","Nome"],["Area","Area"],["Nr. lavaggi","Lavaggi"],["Ult. lavaggio","Ult. lavaggio"]]:
   [["TAGID","Tag"],["Cognome","Cognome"],["Nome","Nome"],["Reparto","Reparto"],["DataIngresso","Ingresso sporco"],["DataUscita","Uscita pulito"]];
  $("#records-content").className="table-wrap";
  $("#records-content").innerHTML='<table><thead><tr>'+columns.map(c=>'<th>'+esc(c[1])+'</th>').join("")+'<th>Originale</th></tr></thead><tbody>'+state.rows.map((r,i)=>'<tr>'+columns.map(c=>'<td'+(c[0].toUpperCase().includes("TAG")?' class="mono"':"")+'>'+esc(r.raw_json[c[0]]||"—")+'</td>').join("")+'<td><button class="button small secondary" data-raw-index="'+i+'">Dettaglio</button></td></tr>').join("")+'</tbody></table>'+(state.rows.length?"":'<div class="empty">Nessuna riga corrisponde alla ricerca.</div>');
  $("#records-count").textContent=(state.rows.length?fmt(state.offset+1)+"–"+fmt(state.offset+state.rows.length):"0")+" di "+fmt(state.total);
  $("#previous-page").disabled=state.offset===0;$("#next-page").disabled=state.offset+50>=state.total;
 }catch(e){if(seq!==state.request)return;$("#records-content").className="private-error";$("#records-content").textContent=e.message;}
}
async function renderReports(){
 state.request++;$("#private-content").innerHTML=heading("Report e verifiche","Versioni dei dati importati e segnalazioni da riconciliare.")+'<section class="panel"><div class="panel-head"><h2>I sei report importati</h2></div>'+batchTable()+'</section><section class="panel"><div class="panel-head"><h2>Segnalazioni conservate</h2></div><div class="panel-body" id="issues-content"><p class="hint">Caricamento…</p></div></section>';
 try{const issues=await api.issues();if(state.section!=="report"||!api.token)return;const counts={};for(const i of issues)counts[i.code]=(counts[i.code]||0)+1;
 const labels={flags:"Indicatori sporco/pulito da verificare",historical_tag_not_current:"Tag storici assenti dall’elenco attivo",assignment_changed:"Tag con assegnazione storica diversa dall’attuale",cross_archive_person_id:"Codici persona riutilizzati fra archivi",same_name_multiple_ids:"Nominativi associati a più codici tecnici"};
 $("#issues-content").innerHTML='<div class="issue-grid">'+Object.entries(counts).map(([code,n])=>'<div class="issue-line"><span>'+esc(labels[code]||code)+'</span><b>'+fmt(n)+'</b></div>').join("")+'</div><p class="hint">Le differenze di assegnazione e i tag assenti dall’elenco attivo possono dipendere dalla storia del capo. Non sono automaticamente errori o capi mancanti.</p>';
 }catch(e){if($("#issues-content"))$("#issues-content").textContent=e.message;}
}
document.addEventListener("click",async e=>{
 const mode=e.target.closest("[data-auth-mode]");if(mode){renderLogin(mode.dataset.authMode);return;}
 const nav=e.target.closest("[data-section]");if(nav){e.preventDefault();state.request++;state.section=nav.dataset.section;if(nav.dataset.archive)state.archive=nav.dataset.archive;state.offset=0;state.search="";state.field="person_name_key";render();return;}
 if(e.target.closest("#logout")){state.request++;try{await api.logout();}catch(_){toast("Sessione locale chiusa.");}finally{activation="";$("#raw-dialog").close();$("#raw-content").textContent="";renderLogin("login");}return;}
 if(e.target.closest("#previous-page")){state.offset=Math.max(0,state.offset-50);loadRows();}
 if(e.target.closest("#next-page")){state.offset+=50;loadRows();}
 const detail=e.target.closest("[data-raw-index]");if(detail){const r=state.rows[Number(detail.dataset.rawIndex)];if(!r)return;$("#raw-content").innerHTML='<p class="hint">Riga '+esc(r.source_row)+' del report originale.</p><div class="raw-grid">'+Object.entries(r.raw_json).map(([k,v])=>'<div class="raw-field"><small>'+esc(k)+'</small><div>'+esc(v||"—")+'</div></div>').join("")+'</div>';$("#raw-dialog").showModal();}
 if(e.target.closest("#close-raw"))$("#raw-dialog").close();
});
document.addEventListener("submit",async e=>{
 if(e.target.id==="auth-form"){
  e.preventDefault();const form=e.target,button=$("#auth-submit"),email=form.email.value.trim(),password=form.password.value,mode=form.dataset.mode;button.disabled=true;message("Richiesta in corso…");
  try{
   if(mode==="signup"){const data=await api.signup(email,password,location.origin+location.pathname);form.reset();if(data.access_token){await afterLogin();}else{renderLogin("login");$("#auth-email").value=email;message("Controlla la tua email e conferma l’indirizzo. Poi torna a questa pagina e accedi. Se il collegamento di conferma non apre il sito, puoi tornare qui manualmente.");}}
   else{await api.login(email,password);form.reset();await afterLogin();}
  }catch(error){message(error.message,true);}finally{if($("#auth-submit"))$("#auth-submit").disabled=false;}
 }
 if(e.target.id==="activation-form"){
  e.preventDefault();const button=e.target.querySelector("button");button.disabled=true;
  try{await api.claim(e.target.code.value.trim());activation="";history.replaceState(null,"",location.pathname+location.search);await afterLogin();}catch(error){message(error.message,true);button.disabled=false;}
 }
 if(e.target.id==="records-filter"){
  e.preventDefault();state.request++;state.archive=e.target.archive.value;state.field=e.target.field.value;state.search=e.target.search.value;state.offset=0;loadRows();
 }
});
const navIcons={letture:"flow",ospiti:"people",operatori:"tag",qualita:"shield",panoramica:"grid",persone:"people",tag:"tag",movimenti:"flow",consegne:"report",flusso:"flow",report:"report"};
document.querySelectorAll("#private-nav [data-section] span").forEach(span=>{span.innerHTML=icon(navIcons[span.parentElement.dataset.section]);});
renderLogin();
})();
