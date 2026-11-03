(function(root,factory){if(typeof module==="object"&&module.exports)module.exports=factory();else root.LaundryPrivateClient=factory();})(typeof globalThis!=="undefined"?globalThis:this,function(){
"use strict";
class Client{
 constructor(config,fetcher){const u=new URL(config.url);if(u.protocol!=="https:"||u.pathname!=="/"||!u.hostname.endsWith(".supabase.co"))throw Error("Configurazione del database non valida.");if(!String(config.publishableKey).startsWith("sb_publishable_"))throw Error("Chiave pubblicabile non configurata.");this.url=u.origin;this.key=config.publishableKey;this.fetcher=fetcher||globalThis.fetch.bind(globalThis);this.token=null;}
 async request(path,{method="GET",body,auth=true,count=false}={}){
  if(auth&&!this.token)throw Error("Accedi per consultare l’archivio.");
  const headers={apikey:this.key,"Content-Type":"application/json"};
  if(auth)headers.Authorization="Bearer "+this.token;
  if(count)headers.Prefer="count=exact";
  const response=await this.fetcher(this.url+path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),cache:"no-store",referrerPolicy:"no-referrer"});
  const text=await response.text();let data;try{data=text?JSON.parse(text):null;}catch(_){throw Error("Risposta del servizio non valida.");}
  if(!response.ok){const message=data&&(data.msg||data.message||data.error_description||data.error);throw Error(typeof message==="string"?message:"Richiesta non completata ("+response.status+").");}
  return {data,total:Number((response.headers.get("content-range")||"").split("/")[1])||0};
 }
 async login(email,password){const r=await this.request("/auth/v1/token?grant_type=password",{method:"POST",auth:false,body:{email,password}});if(!r.data.access_token)throw Error("Accesso non completato.");this.token=r.data.access_token;return r.data.user;}
 async signup(email,password,redirectTo){const r=await this.request("/auth/v1/signup?redirect_to="+encodeURIComponent(redirectTo),{method:"POST",auth:false,body:{email,password}});if(r.data.access_token)this.token=r.data.access_token;return r.data;}
 async user(){return(await this.request("/auth/v1/user")).data;}
 async membership(){return(await this.request("/rest/v1/app_members?select=user_id,role,active&active=eq.true")).data;}
 async claim(token){return(await this.request("/rest/v1/rpc/np_claim_owner",{method:"POST",body:{p_token:token}})).data;}
 async overview(){return(await this.request("/rest/v1/rpc/np_overview",{method:"POST",body:{}})).data;}
 async batches(){return(await this.request("/rest/v1/np_latest_batches?select=id,archive,kind,file_name,imported_at,summary&order=archive.asc,kind.asc")).data;}
 async records(batchId,{offset=0,limit=50,search="",field="person_name_key"}={}){
  if(!/^[a-f0-9-]{36}$/i.test(batchId))throw Error("Report non valido.");
  if(!["person_name_key","tag_id"].includes(field))throw Error("Filtro non valido.");
  const q=new URLSearchParams({select:"id,source_row,tag_id,external_person_id,incoming_date,outgoing_date,raw_json",batch_id:"eq."+batchId,order:"source_row.asc",offset:String(Math.max(0,Math.floor(offset))),limit:String(Math.min(100,Math.max(1,Math.floor(limit))))});
  if(search.trim())q.set(field,"ilike.*"+search.trim().replace(/[\\%_*]/g,"")+"*");
  return this.request("/rest/v1/np_source_records?"+q.toString(),{count:true});
 }
 async issues(){return(await this.request("/rest/v1/np_import_issues?select=code,batch_id&limit=5000")).data;}
 async logout(){try{if(this.token)await this.request("/auth/v1/logout?scope=local",{method:"POST"});}finally{this.token=null;}}
}
return Client;
});
