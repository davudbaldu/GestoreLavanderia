const test=require("node:test"),assert=require("node:assert/strict");
const Client=require("../docs/private-client.js");
const config={url:"https://example.supabase.co",publishableKey:"sb_publishable_fixture"};
const response=(data,{ok=true,status=200,range=""}={})=>({ok,status,headers:{get:()=>range},text:async()=>JSON.stringify(data)});
test("Le letture private richiedono una sessione",async()=>{
 let called=false;const c=new Client(config,async()=>{called=true;return response([])});
 await assert.rejects(()=>c.batches(),/Accedi/);assert.equal(called,false);
});
test("Il login invia le credenziali soltanto al servizio configurato",async()=>{
 let sent;const c=new Client(config,async(url,options)=>{sent={url,options};return response({access_token:"fixture-session",user:{id:"owner"}})});
 await c.login("fixture@example.invalid","test-password");
 assert.equal(sent.url,"https://example.supabase.co/auth/v1/token?grant_type=password");
 assert.equal(sent.options.headers.Authorization,undefined);
 assert.equal(JSON.parse(sent.options.body).email,"fixture@example.invalid");
 assert.equal(c.token,"fixture-session");assert.equal(sent.options.cache,"no-store");
});
test("Un errore di accesso non crea una sessione",async()=>{
 const c=new Client(config,async()=>response({msg:"Invalid credentials"},{ok:false,status:400}));
 await assert.rejects(()=>c.login("fixture@example.invalid","wrong"),/Invalid credentials/);assert.equal(c.token,null);
});
test("La chiave pubblicabile da sola non autorizza la lettura",async()=>{
 let sent;const c=new Client(config,async(url,options)=>{sent={url,options};return response([{id:"batch"}])});c.token="user-jwt";
 await c.batches();assert.equal(sent.options.headers.Authorization,"Bearer user-jwt");assert.equal(sent.options.headers.apikey,config.publishableKey);
});
test("La ricerca rimane limitata al report selezionato",async()=>{
 let sent;const c=new Client(config,async(url)=>{sent=url;return response([],{range:"0-49/123"})});c.token="user-jwt";
 const r=await c.records("11111111-1111-4111-8111-111111111111",{search:"Demo",field:"person_name_key",limit:50});
 const u=new URL(sent);assert.equal(u.searchParams.get("batch_id"),"eq.11111111-1111-4111-8111-111111111111");assert.equal(u.searchParams.get("person_name_key"),"ilike.*Demo*");assert.equal(r.total,123);
 await assert.rejects(()=>c.records("bad-id"),/Report non valido/);
});
test("Un codice di attivazione non viene inviato prima del login",async()=>{
 let called=false;const c=new Client(config,async()=>{called=true;return response(null)});
 await assert.rejects(()=>c.claim("fixture"),/Accedi/);assert.equal(called,false);
});
test("Il logout svuota la sessione anche se il servizio non risponde",async()=>{
 const c=new Client(config,async()=>{throw Error("network")});c.token="user-jwt";await assert.rejects(()=>c.logout());assert.equal(c.token,null);
});
test("Un endpoint non HTTPS non può ricevere credenziali",()=>{assert.throws(()=>new Client({...config,url:"http://example.supabase.co"}),/Configurazione/);});
