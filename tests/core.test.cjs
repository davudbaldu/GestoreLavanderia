const test = require("node:test");
const assert = require("node:assert/strict");
const C = require("../docs/core.js");
test("CSV con BOM, campi quotati e delimitatori nel testo",()=>{
 const d=C.parseCSV('\uFEFFStruttura;Tag ID;Nome;Cognome\nDemo;00001234;"Uno; Due";Demo\n');
 assert.equal(d.rows[0].data["Tag ID"],"00001234");
 assert.equal(d.rows[0].data.Nome,"Uno; Due");
});
test("Date valide e precisione solo giorno",()=>{
 assert.equal(C.isoDate("29/02/2024"),"2024-02-29");
 assert.equal(C.isoDate("31/02/2026"),null);
 assert.equal(C.isoDate("03/11/2026 10:41:00"),"2026-11-03");
});
test("Identificativi persona distinti per archivio",()=>{
 assert.notEqual(C.externalPersonKey("ospiti","10.001"),C.externalPersonKey("divise","10.001"));
});
test("Righe con entrata e uscita contate come ciclo e due registrazioni",()=>{
 const d=C.parseCSV("TAGID;DataIngresso;DataUscita;CLIEID;Nome;Cognome;Sporco;Pulito\nD1;02/06/2026;03/06/2026;10.001;Uno;Demo;1;1\nD2;03/06/2026;;10.002;Due;Demo;1;0");
 const r=C.analyzeDataset(d,"ospiti");
 assert.equal(r.rows,2);assert.equal(r.entries,2);assert.equal(r.exits,1);assert.equal(r.paired,1);assert.equal(r.entryOnly,1);
});
test("Footer e conteggi del report esclusi dalle persone",()=>{
 const d=C.parseCSV("Tit.;Cognome;Nome;Area;Ingresso\n.;Demo;Uno;A;01-gen-2026\n1;0;;;\n1;;;;\nLavanderia;Elenco ospiti;Pagina 1;;");
 assert.equal(d.rows.length,1);
});
test("Storico e assegnazione attuale conservano significati diversi",()=>{
 const current=C.parseCSV("Struttura;Tag ID;Cognome;Nome\nDemo;D1;Demo;Nuovo");
 const old=C.parseCSV("TAGID;DataIngresso;DataUscita;CLIEID;Cognome;Nome;Pulito;Sporco\nD1;02/06/2026;03/06/2026;10.001;Demo;Precedente;1;1\nD2;03/06/2026;;10.002;Demo;Due;0;1");
 const r=C.reconcile([{archive:"ospiti",dataset:current},{archive:"ospiti",dataset:old}]);
 assert.equal(r.assignmentDifferences,1);assert.equal(r.absentActiveTags,1);
 assert.equal(current.rows[0].data.Nome,"Nuovo");
});
test("Il confronto non segnala tag assenti quando manca l'elenco attivo",()=>{
 const old=C.parseCSV("TAGID;DataIngresso;DataUscita\nD1;02/06/2026;03/06/2026");
 assert.equal(C.reconcile([{archive:"ospiti",dataset:old}]).absentActiveTags,0);
});
test("Date e indicatori incoerenti producono una segnalazione",()=>{
 const d=C.parseCSV("TAGID;DataIngresso;DataUscita;Sporco;Pulito\nD1;02/06/2026;;0;0");
 assert.equal(C.analyzeDataset(d,"ospiti").issues[0].code,"flags");
});
test("I passaggi della consegna non saltano direttamente alla consegna",()=>{
 const a=C.advanceDelivery({id:"D1",status:"preparazione"});
 assert.equal(a.status,"pronto");
 const b=C.advanceDelivery(a);assert.equal(b.status,"ritirato");
 const c=C.advanceDelivery(b);assert.equal(c.status,"consegnato");
 assert.throws(()=>C.advanceDelivery(c));
});
test("CSV troncati o colonne incoerenti vengono rifiutati",()=>{
 assert.throws(()=>C.parseCSV('A;B\n"non chiuso;X'));
 assert.throws(()=>C.parseCSV("A;B\nuno;due;tre"));
});

test("Un tag solo numerico non viene scambiato per il totale del report",()=>{
 const d=C.parseCSV("TAGID;DataIngresso;DataUscita\n00001234;02/06/2026;");
 assert.equal(d.rows.length,1);assert.equal(d.rows[0].data.TAGID,"00001234");
});
