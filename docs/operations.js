(function(){
'use strict';
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels={preparazione:'In preparazione',pronto:'Pronto al ritiro',ritirato:'Ritirato',consegnato:'Consegnato'};
const fmt=n=>new Intl.NumberFormat('it-IT').format(n);
const day=s=>s?new Intl.DateTimeFormat('it-IT',{day:'2-digit',month:'short',year:'numeric'}).format(new Date(s+'T12:00:00')):'—';
const time=s=>new Intl.DateTimeFormat('it-IT',{dateStyle:'short',timeStyle:'short',timeZone:'Europe/Rome'}).format(new Date(s));
const service=r=>r.service==='piana'?'Biancheria piana':'Ospiti e divise';
class Operations{
 constructor(api,notify){this.api=api;this.notify=notify;this.generation=0;this.routes=[];this.rows=[];this.filter='';this.dialog=document.querySelector('#preparation-dialog');
  this.dialog.addEventListener('click',e=>this.click(e));this.dialog.addEventListener('submit',e=>this.submit(e));
  this.dialog.addEventListener('cancel',e=>{if(this.busy)e.preventDefault();});
 }
 leave(){this.generation++;clearInterval(this.timer);this.root=null;this.rows=[];this.routes=[];if(this.dialog.open)this.dialog.close();this.dialog.innerHTML='';this.edit=null;this.user=null;this.busy=false;}
 async open(root,user){this.root=root;this.user=user;root.innerHTML='<p class="private-loading">Caricamento delle distinte condivise…</p>';const generation=this.generation;
  root.onclick=e=>this.click(e);root.onchange=e=>{if(e.target.id==='op-filter'){this.filter=e.target.value;this.render();}};
  await this.load();if(generation===this.generation&&this.root)this.timer=setInterval(()=>{if(!this.dialog.open&&!document.hidden)this.load(false);},20000);
 }
 async load(showError=true){const gen=this.generation;try{
  const [routes,rows]=await Promise.all([this.api.routes(),this.api.preparations()]);if(gen!==this.generation||!this.root||!this.api.token)return;
  this.routes=routes;this.rows=rows;this.render();
 }catch(e){if(gen!==this.generation||!this.root)return;if(showError)this.root.innerHTML='<section class="panel"><div class="panel-head"><h2>Distinte non disponibili</h2></div><div class="panel-body"><p>'+esc(e.message)+'</p><button class="button secondary" data-op="refresh">Riprova</button></div></section>';else{const s=this.root.querySelector('#op-sync');if(s)s.textContent='Aggiornamento non riuscito. Riprova con Aggiorna.';}}
 }
 route(id){return this.routes.find(r=>r.id===id);}
 render(){const rows=this.rows.filter(r=>!this.filter||r.route_id===this.filter);
  this.root.innerHTML='<div class="page-heading"><div><span class="eyebrow">GESTIONE OPERATIVA</span><h1>Consegne e preparazione</h1><p>Una registrazione condivisa con l’ufficio, una distinta per ogni origine.</p></div><button class="button primary" data-op="new" '+(!this.routes.length?'disabled':'')+'>＋ Nuova distinta</button></div>'+
   '<div class="notice neutral">Le distinte registrano la preparazione e i passaggi della partita. L’emissione del DDT sarà un’operazione distinta.</div>'+
   '<section class="panel"><div class="panel-head"><div><h2>Partite di consegna</h2><p>Ospiti e divise, piana del terzista: preparazioni indipendenti per la stessa destinazione.</p></div><button class="button small secondary" data-op="refresh">Aggiorna</button></div><div class="toolbar"><select id="op-filter" aria-label="Filtra per servizio e origine"><option value="">Tutti i servizi e le origini</option>'+this.routes.map(r=>'<option value="'+esc(r.id)+'" '+(this.filter===r.id?'selected':'')+'>'+esc(service(r)+' · '+r.origin_name)+'</option>').join('')+'</select><span class="hint" id="op-sync">Aggiornato alle '+esc(new Intl.DateTimeFormat('it-IT',{hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(new Date()))+' · verifica automatica ogni 20 secondi</span></div><div class="table-wrap"><table><thead><tr><th>Destinazione / servizio</th><th>Origine</th><th>Data prevista</th><th>Stato</th><th>Distinta</th></tr></thead><tbody>'+rows.map(p=>{const r=this.route(p.route_id);return '<tr><td><strong>'+esc(r?r.client_name+' · '+r.site_name:'Percorso non disponibile')+'</strong><span class="secondary-line">'+esc(r?service(r):'')+' · '+p.lines.length+' articoli · v'+p.revision+'</span></td><td>'+esc(r?.origin_name||'—')+'</td><td>'+esc(day(p.delivery_on))+'</td><td><span class="tag '+({preparazione:'amber',pronto:'good',ritirato:'blue'}[p.status]||'')+'">'+esc(labels[p.status])+'</span></td><td><button class="button small secondary" data-op="open" data-id="'+esc(p.id)+'">Apri</button></td></tr>';}).join('')+'</tbody></table>'+(rows.length?'':'<p class="empty">Nessuna distinta presente. Crea la prima preparazione per cliente e data.</p>')+'</div><div class="page-count">'+rows.length+' distinte visualizzate · elenco delle ultime 200</div></section>';
 }
 lineRow(line={article:'',quantity:1,unit:'pezzi'}){return '<div class="op-line" data-line><label>Articolo<input name="article" maxlength="120" required value="'+esc(line.article)+'"></label><label>Quantità<input name="quantity" type="number" min="0.001" max="1000000" step="0.001" required value="'+esc(line.quantity)+'"></label><label>Unità<select name="unit"><option value="pezzi" '+(line.unit==='pezzi'?'selected':'')+'>Pezzi</option><option value="kg" '+(line.unit==='kg'?'selected':'')+'>Kg</option></select></label><button type="button" class="icon-button" data-op="remove" aria-label="Rimuovi articolo">×</button></div>';}
 containerRow(c={kind:'roll',quantity:1}){return '<div class="op-container" data-container><label>Contenitore<select name="kind">'+['roll','sacco','collo'].map(k=>'<option '+(k===c.kind?'selected':'')+'>'+k+'</option>').join('')+'</select></label><label>Numero<input name="quantity" type="number" min="1" max="1000000" step="1" required value="'+esc(c.quantity)+'"></label><button type="button" class="icon-button" data-op="remove" aria-label="Rimuovi contenitore">×</button></div>';}
 show(id){this.edit=id?this.rows.find(p=>p.id===id):{id:crypto.randomUUID(),revision:0,status:'preparazione',lines:[{article:'',quantity:1,unit:'pezzi'}],containers:[],notes:''};if(!this.edit)return;
  const p=this.edit,r=this.route(p.route_id),editable=p.status==='preparazione',today=new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Rome'});
  this.dialog.innerHTML='<div class="dialog-heading"><div><span class="eyebrow">DISTINTA DI PREPARAZIONE</span><h2>'+esc(p.revision?'Partita · versione '+p.revision:'Nuova distinta')+'</h2></div><button type="button" class="icon-button" data-op="close" aria-label="Chiudi">×</button></div>'+
   '<p class="hint">'+esc(r?r.client_name+' · '+r.site_name+' · '+service(r)+' · '+r.origin_name:'Scegli servizio e origine della preparazione.')+'</p><form id="op-form"><fieldset '+(!editable?'disabled':'')+'><div class="form-grid"><label>Servizio e origine<select name="route_id" '+(p.revision?'disabled':'')+' required><option value="">Scegli un percorso</option>'+this.routes.map(r=>'<option value="'+esc(r.id)+'" '+(r.id===p.route_id?'selected':'')+'>'+esc(r.client_name+' · '+r.site_name+' · '+service(r)+' · '+r.origin_name)+'</option>').join('')+'</select></label><label>Consegna prevista<input type="date" name="delivery_on" required value="'+esc(p.delivery_on||today)+'" '+(p.revision?'disabled':'')+'></label></div><h3>Articoli preparati</h3><div id="op-lines">'+p.lines.map(l=>this.lineRow(l)).join('')+'</div><button type="button" class="button small secondary" data-op="add-line">＋ Aggiungi articolo</button><h3>Contenitori</h3><p class="hint">Roll, sacchi e colli restano separati dalle quantità degli articoli.</p><div id="op-containers">'+p.containers.map(c=>this.containerRow(c)).join('')+'</div><button type="button" class="button small secondary" data-op="add-container">＋ Aggiungi contenitore</button><label class="op-notes">Note operative<textarea name="notes" rows="3" maxlength="2000">'+esc(p.notes)+'</textarea></label></fieldset><p id="op-message" class="login-message" role="status"></p><div class="dialog-actions">'+(editable?'<button class="button primary" type="submit">Salva distinta</button>':'')+'</div></form>'+
   (p.revision?'<div class="op-state-actions"><span class="tag">'+esc(labels[p.status])+'</span>'+({preparazione:'<button class="button secondary" data-op="status" data-status="pronto">Segna pronto al ritiro</button>',pronto:'<button class="button secondary" data-op="status" data-status="preparazione">Riapri preparazione</button><button class="button primary" data-op="status" data-status="ritirato">Conferma ritiro</button>',ritirato:'<button class="button primary" data-op="status" data-status="consegnato">Conferma consegna</button>'}[p.status]||'')+'</div><button class="button link" data-op="history">Mostra storico delle versioni</button><div id="op-history"></div>':'');
  this.snapshot=this.signature();
  if(!this.dialog.open)this.dialog.showModal();
 }
 signature(){return JSON.stringify([...this.dialog.querySelectorAll('[data-line] input,[data-line] select,[data-container] input,[data-container] select,textarea')].map(e=>e.value));}
 setBusy(busy){this.busy=busy;this.dialog.querySelectorAll('button').forEach(b=>b.disabled=busy);}
 async save(record){if(this.busy)return;this.setBusy(true);const generation=this.generation;
  try{await this.api.savePreparation({...record,revision:record.revision+1,recorded_by:this.user.id});if(generation!==this.generation)return;this.dialog.close();await this.load();this.notify('Distinta salvata nel database condiviso.');}
  catch(e){if(generation!==this.generation)return;this.dialog.querySelector('#op-message').textContent=e.message+' Se l’invio è stato interrotto, chiudi e aggiorna l’elenco prima di riprovare.';}
  finally{if(generation===this.generation)this.setBusy(false);}
 }
 async click(e){const b=e.target.closest('[data-op]');if(!b||this.busy)return;const action=b.dataset.op;
  if(action==='refresh'){await this.load();return;}if(action==='new'){this.show();return;}if(action==='open'){this.show(b.dataset.id);return;}if(action==='close'){this.dialog.close();return;}
  if(action==='add-line'){this.dialog.querySelector('#op-lines').insertAdjacentHTML('beforeend',this.lineRow());return;}
  if(action==='add-container'){this.dialog.querySelector('#op-containers').insertAdjacentHTML('beforeend',this.containerRow());return;}
  if(action==='remove'){b.closest('[data-line],[data-container]').remove();return;}
  if(action==='status'){if(this.signature()!==this.snapshot){this.dialog.querySelector('#op-message').textContent='Salva le modifiche prima di cambiare lo stato.';return;}await this.save({...this.edit,status:b.dataset.status});return;}
  if(action==='history'){const id=this.edit.id,gen=this.generation;try{const rows=await this.api.preparationHistory(id);if(gen!==this.generation||this.edit?.id!==id||!this.dialog.open)return;this.dialog.querySelector('#op-history').innerHTML=rows.map(p=>'<details class="op-version"><summary>v'+p.revision+' · '+esc(labels[p.status])+' · '+esc(time(p.recorded_at))+'</summary><ul>'+p.lines.map(l=>'<li>'+esc(l.article)+' · '+fmt(l.quantity)+' '+esc(l.unit)+'</li>').join('')+'</ul><p>'+esc(p.containers.map(c=>fmt(c.quantity)+' '+c.kind).join(' · '))+'</p><p>'+esc(p.notes)+'</p></details>').join('');}catch(error){this.notify(error.message);}}
 }
 async submit(e){if(e.target.id!=='op-form')return;e.preventDefault();const form=e.target,p=this.edit,lines=[...form.querySelectorAll('[data-line]')].map(row=>({article:row.querySelector('[name=article]').value.trim(),quantity:Number(row.querySelector('[name=quantity]').value),unit:row.querySelector('[name=unit]').value}));
  if(!lines.length){form.querySelector('#op-message').textContent='Inserisci almeno un articolo.';return;}
  if(lines.some(l=>l.unit==='pezzi'&&!Number.isInteger(l.quantity))){form.querySelector('#op-message').textContent='La quantità in pezzi deve essere intera.';return;}
  const containers=[...form.querySelectorAll('[data-container]')].map(row=>({kind:row.querySelector('[name=kind]').value,quantity:Number(row.querySelector('[name=quantity]').value)}));
  await this.save({...p,route_id:p.route_id||form.elements.route_id.value,delivery_on:p.delivery_on||form.elements.delivery_on.value,lines,containers,notes:form.elements.notes.value});
 }
}
window.LaundryOperations=Operations;
})();
