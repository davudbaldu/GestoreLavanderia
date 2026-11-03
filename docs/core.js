/* Shared data checks. No dependencies and no network requests. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.LaundryCore = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const clean = value => String(value == null ? "" : value).trim();
  function personKey(row) { return [row.Cognome, row.Nome].map(v => clean(v).replace(/\s+/g, " ").toUpperCase()).join("|"); }
  function externalPersonKey(archive, id) { return clean(archive) + "::" + clean(id); }
  function detectDelimiter(text) {
    const first = text.replace(/^\uFEFF/, "").split(/\r?\n/, 1)[0];
    let quoted = false, semi = 0, comma = 0, tab = 0;
    for (let i = 0; i < first.length; i++) {
      if (first[i] === '"') { if (quoted && first[i+1] === '"') i++; else quoted = !quoted; }
      else if (!quoted) { if (first[i] === ";") semi++; if (first[i] === ",") comma++; if (first[i] === "\t") tab++; }
    }
    return tab > semi && tab > comma ? "\t" : semi >= comma ? ";" : ",";
  }
  function parseCSV(text) {
    const input = String(text).replace(/^\uFEFF/, ""), delimiter = detectDelimiter(input);
    let row = [], field = "", quoted = false; const rows = [];
    const finish = () => { row.push(field.replace(/\r$/, "")); if (row.some(v => v !== "")) rows.push(row); row = []; field = ""; };
    for (let i = 0; i < input.length; i++) {
      const c = input[i];
      if (c === '"') { if (quoted && input[i+1] === '"') { field += '"'; i++; } else quoted = !quoted; }
      else if (c === delimiter && !quoted) { row.push(field); field = ""; }
      else if (c === "\n" && !quoted) finish();
      else field += c;
    }
    if (quoted) throw new Error("Virgolette non chiuse nel CSV.");
    if (field || row.length) finish();
    if (!rows.length) throw new Error("Il CSV è vuoto.");
    const headers = rows.shift().map(clean);
    if (new Set(headers).size !== headers.length) throw new Error("Il CSV contiene intestazioni duplicate.");
    const footer = r => headers[0] === "Tit." && (clean(r[0]).toLowerCase() === "lavanderia" || (/^\d+$/.test(clean(r[0])) && r.slice(2).every(v => !clean(v))));
    const dataRows = rows.filter(r => !footer(r));
    const malformed = dataRows.filter(r => r.length !== headers.length).length;
    if (malformed) throw new Error(malformed + " righe hanno un numero di colonne diverso dall'intestazione.");
    return { headers, delimiter, rows: dataRows.map((r, index) => ({ line: index + 2, data: Object.fromEntries(headers.map((h, i) => [h, r[i]])) })) };
  }
  function isoDate(value) {
    const s = clean(value); if (!s) return null;
    let match = s.match(/^(\d{2})\/(\d{2})\/(\d{4})(?:\s.*)?$/);
    if (match) { const result = match[3]+"-"+match[2]+"-"+match[1]; const d = new Date(result+"T00:00:00Z"); return !Number.isNaN(d.valueOf()) && d.toISOString().slice(0,10) === result ? result : null; }
    match = s.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T].*)?$/);
    if (match) { const result = match[1]+"-"+match[2]+"-"+match[3]; const d = new Date(result+"T00:00:00Z"); return !Number.isNaN(d.valueOf()) && d.toISOString().slice(0,10) === result ? result : null; }
    return null;
  }
  function classify(headers) {
    if (headers.includes("TAGID") && headers.includes("DataIngresso") && headers.includes("DataUscita")) return "movimenti";
    if (headers.includes("Tag ID") && headers.includes("Struttura")) return "tag";
    if (headers.includes("Cognome") && headers.includes("Nome") && headers.includes("Ingresso")) return "persone";
    throw new Error("Intestazioni non riconosciute come report NewPod.");
  }
  function analyzeDataset(dataset, archive) {
    if (!["ospiti", "divise"].includes(archive)) throw new Error("Seleziona l'archivio di provenienza.");
    const kind = classify(dataset.headers), rows = dataset.rows.map(x => x.data);
    const result = { archive, kind, rows: rows.length, issues: [], uniqueTags: 0, entries: 0, exits: 0, paired: 0, entryOnly: 0, exitOnly: 0, minDate: null, maxDate: null, technicalPeople: 0 };
    const seen = new Set(), tags = new Set(), dates = [], identities = new Map();
    const count = (code, label) => { let issue = result.issues.find(x => x.code === code); if (!issue) { issue = { code, label, count: 0 }; result.issues.push(issue); } issue.count++; };
    for (const r of rows) {
      const signature = JSON.stringify(dataset.headers.map(h => r[h]));
      if (seen.has(signature)) count("duplicate", "Righe identiche da verificare"); seen.add(signature);
      const tag = clean(r.TAGID || r["Tag ID"]).toUpperCase();
      if (tag) tags.add(tag); else if (kind !== "persone") count("tag_missing", "Codice tag assente");
      if (kind === "movimenti") {
        const rawIn = clean(r.DataIngresso), rawOut = clean(r.DataUscita), incoming = isoDate(rawIn), outgoing = isoDate(rawOut);
        if (rawIn && !incoming) count("date_invalid", "Date non valide");
        if (rawOut && !outgoing) count("date_invalid", "Date non valide");
        if (incoming) { result.entries++; dates.push(incoming); }
        if (outgoing) { result.exits++; dates.push(outgoing); }
        if (incoming && outgoing) { result.paired++; if (incoming > outgoing) count("date_order", "Uscita precedente all'ingresso"); }
        else if (incoming) result.entryOnly++;
        else if (outgoing) result.exitOnly++;
        else count("dates_missing", "Righe senza date valide");
        if ((rawIn && clean(r.Sporco) !== "1") || (rawOut && clean(r.Pulito) !== "1") || (!rawIn && clean(r.Sporco) === "1") || (!rawOut && clean(r.Pulito) === "1")) count("flags", "Indicatori sporco/pulito non coerenti con le date");
        if (clean(r.CLIEID)) {
          const id = externalPersonKey(archive, r.CLIEID), p = personKey(r);
          if (!identities.has(id)) identities.set(id, new Set()); identities.get(id).add(p);
        }
      }
      if (kind === "persone" && (!clean(r.Cognome) || !clean(r.Nome))) count("name_missing", "Nominativi incompleti");
    }
    result.uniqueTags = tags.size; result.technicalPeople = identities.size;
    for (const names of identities.values()) if (names.size > 1) count("identity_ambiguous", "Codici tecnici associati a più nominativi");
    dates.sort(); result.minDate = dates[0] || null; result.maxDate = dates[dates.length-1] || null;
    return result;
  }
  function reconcile(files) {
    const result = { absentActiveTags: 0, assignmentDifferences: 0, crossArchivePersonIds: 0 };
    const personIds = new Map();
    for (const archive of ["ospiti","divise"]) {
      const currentFiles = files.filter(f => f.archive === archive && classify(f.dataset.headers) === "tag");
      const movements = files.filter(f => f.archive === archive && classify(f.dataset.headers) === "movimenti");
      const active = new Map(), absent = new Set(), mismatched = new Set();
      currentFiles.forEach(f => f.dataset.rows.forEach(({data:r}) => active.set(clean(r["Tag ID"]).toUpperCase(), personKey(r))));
      movements.forEach(f => f.dataset.rows.forEach(({data:r}) => {
        const tag = clean(r.TAGID).toUpperCase(), id = clean(r.CLIEID);
        if (currentFiles.length && !active.has(tag)) absent.add(tag);
        if (active.has(tag) && active.get(tag) !== personKey(r)) mismatched.add(tag);
        if (id) { if (!personIds.has(id)) personIds.set(id,new Set()); personIds.get(id).add(archive); }
      }));
      result.absentActiveTags += absent.size; result.assignmentDifferences += mismatched.size;
    }
    result.crossArchivePersonIds = [...personIds.values()].filter(s => s.size > 1).length;
    return result;
  }
  const nextStates = { preparazione: "pronto", pronto: "ritirato", ritirato: "consegnato" };
  function advanceDelivery(delivery) {
    const next = nextStates[delivery.status]; if (!next) throw new Error("La consegna non ha altri passaggi disponibili.");
    return Object.assign({}, delivery, { status: next });
  }
  return { parseCSV, isoDate, classify, analyzeDataset, reconcile, personKey, externalPersonKey, advanceDelivery };
});
