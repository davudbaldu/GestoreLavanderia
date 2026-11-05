begin;
create schema rf_private;
revoke all on schema rf_private from public,anon;
grant usage on schema rf_private to authenticated;
create table public.rf_clients(id uuid primary key default gen_random_uuid(),name text not null,site text not null,unique(name,site));
create table public.rf_stations(id uuid primary key default gen_random_uuid(),code text not null unique,name text not null,kind text not null check(kind in ('sporco','pulito')),slot_count integer check(slot_count between 1 and 500),hardware_ready boolean not null default false);
create table public.rf_bindings(source_record_id bigint primary key references public.np_source_records(id),client_id uuid not null references public.rf_clients(id));
create index rf_bindings_client on public.rf_bindings(client_id);
create table public.rf_sessions(
 id uuid primary key,station_id uuid not null references public.rf_stations(id),client_id uuid not null references public.rf_clients(id),archive text not null check(archive in ('ospiti','divise','tutti')),
 mode text not null check(mode in ('collaudo','produzione')),status text not null default 'aperta' check(status in ('aperta','chiusa')),
 slot_count integer,empty_confirmed_at timestamptz,opened_by uuid not null references auth.users(id),opened_at timestamptz not null default now(),closed_by uuid references auth.users(id),closed_at timestamptz,closing_note text not null default ''
);
create unique index rf_one_open_station on public.rf_sessions(station_id) where status='aperta';
create index rf_sessions_client on public.rf_sessions(client_id);
create index rf_sessions_opened_by on public.rf_sessions(opened_by);
create index rf_sessions_closed_by on public.rf_sessions(closed_by);
create table public.rf_reads(
 id uuid primary key,seq bigint generated always as identity unique,session_id uuid not null references public.rf_sessions(id),raw_tag text not null,tag text not null,
 observation jsonb not null default '{}'::jsonb check(jsonb_typeof(observation)='object'),observed_at timestamptz not null,received_at timestamptz not null default clock_timestamp(),outcome text not null,
 source_record_id bigint references public.np_source_records(id),person_source_id bigint references public.np_source_records(id),slot integer,
 snapshot jsonb not null default '{}'::jsonb
);
create index rf_reads_session on public.rf_reads(session_id,seq desc);
create index rf_reads_person on public.rf_reads(person_source_id);
create unique index rf_one_accepted_per_session on public.rf_reads(session_id,source_record_id) where outcome='accettata';
create table public.rf_allocations(session_id uuid not null references public.rf_sessions(id),slot integer not null,person_source_id bigint not null references public.np_source_records(id),snapshot jsonb not null,primary key(session_id,slot),unique(session_id,person_source_id));
create index rf_allocations_person on public.rf_allocations(person_source_id);
create table public.rf_reservations(source_record_id bigint not null references public.np_source_records(id),mode text not null,session_id uuid not null references public.rf_sessions(id),primary key(source_record_id,mode));
create index rf_reservations_session on public.rf_reservations(session_id);
create table public.rf_movements(id uuid primary key default gen_random_uuid(),session_id uuid not null references public.rf_sessions(id),read_id uuid not null unique references public.rf_reads(id),source_record_id bigint not null references public.np_source_records(id),direction text not null check(direction in ('ingresso_sporco','uscita_pulito')),occurred_at timestamptz not null,recorded_at timestamptz not null default now());
create index rf_movements_session on public.rf_movements(session_id);
create index rf_movements_garment on public.rf_movements(source_record_id,occurred_at desc);
create table public.rf_label_jobs(id uuid primary key default gen_random_uuid(),session_id uuid not null references public.rf_sessions(id),slot integer not null,payload jsonb not null,created_at timestamptz not null default now(),unique(session_id,slot));
create table public.rf_print_attempts(id uuid primary key,seq bigint generated always as identity unique,job_id uuid not null references public.rf_label_jobs(id),outcome text not null check(outcome in ('richiesta','confermata','errore')),detail text not null default '',actor uuid not null references auth.users(id),recorded_at timestamptz not null default clock_timestamp());
create index rf_print_attempts_job on public.rf_print_attempts(job_id,recorded_at desc);
create index rf_print_attempts_actor on public.rf_print_attempts(actor);

-- Command handlers are the only writers. Every entry point checks the actual JWT
-- subject against active app membership; the public wrappers remain invokers.
create function rf_private.authorize() returns void language plpgsql security invoker set search_path=pg_catalog,public as $$begin
 if auth.uid() is null or not exists(select 1 from public.app_members where user_id=auth.uid() and active and role='owner') then raise insufficient_privilege using message='Account non abilitato alle postazioni.';end if;
end$$;
revoke all on function rf_private.authorize() from public,anon;
grant execute on function rf_private.authorize() to authenticated;
do $$declare t text;begin
 foreach t in array array['rf_clients','rf_stations','rf_bindings','rf_sessions','rf_reads','rf_allocations','rf_reservations','rf_movements','rf_label_jobs','rf_print_attempts'] loop
 execute format('alter table public.%I enable row level security',t);
 execute format('revoke all on public.%I from public,anon,authenticated',t);
 execute format('grant select on public.%I to authenticated',t);
 execute format('create policy owner_reads on public.%I for select to authenticated using(exists(select 1 from public.app_members m where m.user_id=(select auth.uid()) and m.active and m.role=''owner''))',t);
 end loop;
end$$;

revoke all on sequence public.rf_reads_seq_seq,public.rf_print_attempts_seq_seq from public,anon,authenticated;

create function rf_private.start_session(p_id uuid,p_station uuid,p_client uuid,p_archive text,p_mode text,p_empty boolean) returns jsonb
 language plpgsql security definer set search_path='' as $$
declare s public.rf_stations; existing public.rf_sessions;
begin
 perform rf_private.authorize();
 select * into s from public.rf_stations where id=p_station for update;if not found then raise exception 'Postazione non disponibile.';end if;
 select * into existing from public.rf_sessions where id=p_id;
 if found then
 if existing.station_id<>p_station or existing.client_id<>p_client or existing.archive<>p_archive or existing.mode<>p_mode then raise exception 'Identificativo sessione già usato per altri dati.';end if;
 return to_jsonb(existing);end if;
 if p_mode not in ('collaudo','produzione') or p_archive not in ('ospiti','divise','tutti') then raise exception 'Modalità o archivio non valido.';end if;
 if p_mode='produzione' and not s.hardware_ready then raise exception 'La postazione non è ancora collaudata con l’hardware.';end if;
 if s.kind='pulito' and p_empty is not true then raise exception 'Conferma che l’armadio sia stato svuotato prima di riutilizzarlo.';end if;
 if s.kind='pulito' and s.slot_count is null then raise exception 'Configura il numero di caselle prima di iniziare.';end if;
 if exists(select 1 from public.rf_sessions where station_id=p_station and status='aperta') then raise exception 'La postazione ha già una sessione aperta.';end if;
 insert into public.rf_sessions(id,station_id,client_id,archive,mode,slot_count,empty_confirmed_at,opened_by) values(p_id,p_station,p_client,p_archive,p_mode,s.slot_count,case when p_empty then now() end,auth.uid()) returning * into existing;
 return to_jsonb(existing);
end$$;

create function rf_private.read_batch(p_session uuid,p_events jsonb) returns jsonb
 language plpgsql security definer set search_path='' as $$
declare s public.rf_sessions; station public.rf_stations;e jsonb;eid uuid;raw_value text;tag_value text;observed timestamptz;outcome text;matches integer;garment public.np_catalogue_records;
 person_id bigint;person_count integer;assigned integer;busy uuid;prior public.rf_reads;row_read public.rf_reads;results jsonb='[]'::jsonb;details jsonb;
begin
 perform rf_private.authorize();select * into s from public.rf_sessions where id=p_session for update;if not found then raise exception 'Sessione non disponibile.';end if;
 select * into station from public.rf_stations where id=s.station_id;
 if jsonb_typeof(p_events) is distinct from 'array' or jsonb_array_length(p_events) not between 1 and 500 then raise exception 'Invia da 1 a 500 letture per richiesta.';end if;
 if station.kind='pulito' and jsonb_array_length(p_events)<>1 then raise exception 'All’armadio passa un solo capo alla volta.';end if;
 for e in select value from jsonb_array_elements(p_events) loop
  if jsonb_typeof(e) is distinct from 'object' or jsonb_typeof(e->'tag') is distinct from 'string' or length(e->>'tag')>256 or e->>'id' is null or jsonb_typeof(coalesce(e->'metadata','{}'::jsonb)) is distinct from 'object' or octet_length(coalesce(e->'metadata','{}'::jsonb)::text)>4096 then raise exception 'Formato della lettura non valido.';end if;
  eid=(e->>'id')::uuid;raw_value=e->>'tag';tag_value=upper(btrim(raw_value));observed=coalesce((e->>'observed_at')::timestamptz,clock_timestamp());
  -- Retries of the same transport event return the stored result unchanged.
  perform pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(eid::text,87));
  select * into prior from public.rf_reads where id=eid;
  if found then
   if prior.session_id<>p_session or prior.raw_tag<>raw_value or prior.observation<>coalesce(e->'metadata','{}'::jsonb) or (e ? 'observed_at' and prior.observed_at<>observed) then raise exception 'Identificativo evento riutilizzato con altri dati.';end if;
   results=results||jsonb_build_array(to_jsonb(prior));continue;
  end if;
  outcome='accettata';garment=null;person_id=null;assigned=null;details='{}'::jsonb;
  if s.status='chiusa' then outcome='sessione_chiusa';
  elsif tag_value !~ '^[0-9A-F]{8,64}$' then outcome='tag_non_valido';
  else
   select count(*) into matches from public.np_catalogue_records r join public.rf_bindings b on b.source_record_id=r.id where r.kind='tag' and r.tag_id=tag_value;
   if matches=0 then outcome='tag_sconosciuto';elsif matches>1 then outcome='tag_ambiguo';else
    select r.* into garment from public.np_catalogue_records r join public.rf_bindings b on b.source_record_id=r.id where r.kind='tag' and r.tag_id=tag_value;
    if not exists(select 1 from public.rf_bindings where source_record_id=garment.id and client_id=s.client_id) then outcome='cliente_diverso';
    elsif s.archive<>'tutti' and garment.archive<>s.archive then outcome='archivio_diverso';
    elsif exists(select 1 from public.rf_reads where session_id=p_session and source_record_id=garment.id and rf_reads.outcome='accettata') then outcome='ripetizione';select person_source_id,slot into person_id,assigned from public.rf_reads where session_id=p_session and source_record_id=garment.id and rf_reads.outcome='accettata';
    elsif station.kind='pulito' then
     select count(*),min(id) into person_count,person_id from public.np_catalogue_records where kind='persone' and archive=garment.archive and person_name_key=garment.person_name_key and department=garment.department;
     if person_count<>1 then outcome='identita_da_verificare';else
      perform pg_catalog.pg_advisory_xact_lock(garment.id);
      select session_id into busy from public.rf_reservations where source_record_id=garment.id and mode=s.mode;
      if busy is not null and busy<>p_session then outcome='altro_armadio';else
       select slot into assigned from public.rf_allocations where session_id=p_session and person_source_id=person_id;
       if assigned is null then
        select n into assigned from generate_series(1,s.slot_count) n where not exists(select 1 from public.rf_allocations where session_id=p_session and slot=n) order by n limit 1;
        if assigned is null then outcome='armadio_pieno';else
         insert into public.rf_allocations(session_id,slot,person_source_id,snapshot) values(p_session,assigned,person_id,jsonb_build_object('name',garment.surname||' '||garment.given_name,'department',garment.department,'floor',garment.floor,'category',garment.category,'archive',garment.archive));
        end if;
       end if;
      end if;
     end if;
    end if;
    details=jsonb_build_object('name',garment.surname||' '||garment.given_name,'article',garment.article,'archive',garment.archive,'department',garment.department,'floor',garment.floor);
   end if;
  end if;
  insert into public.rf_reads(id,session_id,raw_tag,tag,observation,observed_at,outcome,source_record_id,person_source_id,slot,snapshot)
   values(eid,p_session,raw_value,tag_value,coalesce(e->'metadata','{}'::jsonb),observed,outcome,garment.id,person_id,assigned,details) returning * into row_read;
  if outcome='accettata' and station.kind='sporco' then
   insert into public.rf_movements(session_id,read_id,source_record_id,direction,occurred_at) values(p_session,eid,garment.id,'ingresso_sporco',observed);
  elsif outcome='accettata' then insert into public.rf_reservations(source_record_id,mode,session_id) values(garment.id,s.mode,p_session) on conflict(source_record_id,mode) do nothing;end if;
  results=results||jsonb_build_array(to_jsonb(row_read));
 end loop;return results;
end$$;

create function rf_private.close_session(p_session uuid,p_expected integer,p_note text default '') returns jsonb
 language plpgsql security definer set search_path='' as $$
declare s public.rf_sessions;station public.rf_stations;n integer;problems integer;closed_time timestamptz;
begin
 perform rf_private.authorize();select * into s from public.rf_sessions where id=p_session for update;if not found then raise exception 'Sessione non disponibile.';end if;
 select * into station from public.rf_stations where id=s.station_id;
 if s.status='aperta' then
  select count(*) into n from public.rf_reads where session_id=p_session and outcome='accettata';
  if n<>p_expected then raise exception 'Sono arrivate altre letture: aggiorna e controlla il conteggio prima di chiudere.';end if;
  if station.kind='pulito' and n=0 then raise exception 'Non ci sono capi da chiudere nell’armadio.';end if;
  select count(*) into problems from public.rf_reads where session_id=p_session and outcome not in ('accettata','ripetizione');
  if problems>0 and length(btrim(coalesce(p_note,'')))<3 then raise exception 'Indica come sono stati gestiti i capi segnalati prima di chiudere.';end if;
  if length(p_note)>1000 then raise exception 'Nota di chiusura troppo lunga.';end if;
  closed_time=clock_timestamp();
  update public.rf_sessions set status='chiusa',closed_by=auth.uid(),closed_at=closed_time,closing_note=coalesce(p_note,'') where id=p_session;
  if station.kind='pulito' then
   insert into public.rf_movements(session_id,read_id,source_record_id,direction,occurred_at)
    select p_session,id,source_record_id,'uscita_pulito',closed_time from public.rf_reads where session_id=p_session and outcome='accettata';
   insert into public.rf_label_jobs(session_id,slot,payload)
    select p_session,a.slot,jsonb_build_object('mode',s.mode,'session',s.id,'station',station.name,'client',c.name,'site',c.site,'archive',coalesce(a.snapshot->>'archive',s.archive),'closed_at',closed_time,'slot',a.slot,'subject',a.snapshot,'count',count(r.id),'garments',jsonb_agg(jsonb_build_object('tag',r.tag,'article',r.snapshot->>'article') order by r.seq))
    from public.rf_allocations a join public.rf_reads r on r.session_id=a.session_id and r.slot=a.slot and r.outcome='accettata'
    join public.rf_clients c on c.id=s.client_id where a.session_id=p_session group by a.slot,a.snapshot,c.name,c.site;
   delete from public.rf_reservations where session_id=p_session;
  end if;
 end if;
 return jsonb_build_object('session',p_session,'status','chiusa','movements',(select count(*) from public.rf_movements where session_id=p_session),'labels',(select count(*) from public.rf_label_jobs where session_id=p_session));
end$$;

create function rf_private.configure_slots(p_station uuid,p_slots integer) returns void language plpgsql security definer set search_path='' as $$begin
 perform rf_private.authorize();perform 1 from public.rf_stations where id=p_station and kind='pulito' for update;if not found then raise exception 'Armadio non disponibile.';end if;
 if p_slots is null or p_slots not between 1 and 500 then raise exception 'Numero di caselle non valido.';end if;
 if exists(select 1 from public.rf_sessions where station_id=p_station and status='aperta') then raise exception 'Chiudi la sessione prima di cambiare le caselle.';end if;
 update public.rf_stations set slot_count=p_slots where id=p_station;
end$$;

create function rf_private.print_attempt(p_id uuid,p_job uuid,p_outcome text,p_detail text) returns void language plpgsql security definer set search_path='' as $$
declare previous public.rf_print_attempts;
begin
 perform rf_private.authorize();
 if p_outcome not in ('richiesta','confermata','errore') or length(coalesce(p_detail,''))>1000 then raise exception 'Esito di stampa non valido.';end if;
 perform 1 from public.rf_label_jobs where id=p_job for update;if not found then raise exception 'Etichetta non disponibile.';end if;
 select * into previous from public.rf_print_attempts where id=p_id;
 if found then if previous.job_id<>p_job or previous.outcome<>p_outcome or previous.detail<>coalesce(p_detail,'') then raise exception 'Identificativo stampa già usato.';end if;return;end if;
 insert into public.rf_print_attempts(id,job_id,outcome,detail,actor) values(p_id,p_job,p_outcome,coalesce(p_detail,''),auth.uid());
end$$;
create function public.rf_print_attempt(p_id uuid,p_job uuid,p_outcome text,p_detail text default '') returns void language sql security invoker set search_path='' as $$select rf_private.print_attempt(p_id,p_job,p_outcome,p_detail)$$;
create view public.rf_label_status with(security_invoker=true) as
 select j.*,coalesce(a.outcome,'in_attesa') as print_status,a.detail,a.recorded_at as last_attempt from public.rf_label_jobs j
 left join lateral(select outcome,detail,recorded_at from public.rf_print_attempts where job_id=j.id order by seq desc limit 1)a on true;
revoke all on public.rf_label_status from public,anon;grant select on public.rf_label_status to authenticated;

create function public.rf_start_session(p_id uuid,p_station uuid,p_client uuid,p_archive text,p_mode text default 'collaudo',p_empty boolean default false) returns jsonb language sql security invoker set search_path='' as $$select rf_private.start_session(p_id,p_station,p_client,p_archive,p_mode,p_empty)$$;
create function public.rf_read_batch(p_session uuid,p_events jsonb) returns jsonb language sql security invoker set search_path='' as $$select rf_private.read_batch(p_session,p_events)$$;
create function public.rf_close_session(p_session uuid,p_expected integer,p_note text default '') returns jsonb language sql security invoker set search_path='' as $$select rf_private.close_session(p_session,p_expected,p_note)$$;
create function public.rf_configure_slots(p_station uuid,p_slots integer) returns void language sql security invoker set search_path='' as $$select rf_private.configure_slots(p_station,p_slots)$$;
create function public.rf_snapshot(p_session uuid,p_before bigint default null) returns jsonb language sql stable security invoker set search_path=pg_catalog,public as $$
 select jsonb_build_object('session',to_jsonb(s),'station',to_jsonb(st),'client',to_jsonb(c),
 'counts',jsonb_build_object('reads',(select count(*) from public.rf_reads where session_id=s.id),'accepted',(select count(*) from public.rf_reads where session_id=s.id and outcome='accettata'),'duplicates',(select count(*) from public.rf_reads where session_id=s.id and outcome='ripetizione'),'blocked',(select count(*) from public.rf_reads where session_id=s.id and outcome not in ('accettata','ripetizione')),'movements',(select count(*) from public.rf_movements where session_id=s.id),'labels',(select count(*) from public.rf_label_jobs where session_id=s.id)),
 'reads',(select coalesce(jsonb_agg(to_jsonb(r) order by seq desc),'[]') from(select * from public.rf_reads where session_id=s.id and (p_before is null or seq<p_before) order by seq desc limit 100)r),
 'slots',(select coalesce(jsonb_agg(jsonb_build_object('slot',a.slot,'subject',a.snapshot,'count',(select count(*) from public.rf_reads where session_id=s.id and slot=a.slot and outcome='accettata')) order by a.slot),'[]') from public.rf_allocations a where a.session_id=s.id))
 from public.rf_sessions s join public.rf_stations st on st.id=s.station_id join public.rf_clients c on c.id=s.client_id where s.id=p_session
$$;
create view public.rf_session_list with(security_invoker=true) as select s.*,st.name as station_name,st.kind,c.name as client_name,c.site from public.rf_sessions s join public.rf_stations st on st.id=s.station_id join public.rf_clients c on c.id=s.client_id;
revoke all on public.rf_session_list from public,anon;grant select on public.rf_session_list to authenticated;
do $$declare f record;begin
 for f in select p.oid::regprocedure as signature from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='rf_private' or (n.nspname='public' and p.proname in ('rf_start_session','rf_read_batch','rf_close_session','rf_configure_slots','rf_snapshot','rf_print_attempt')) loop
 execute format('revoke all on function %s from public,anon',f.signature);execute format('grant execute on function %s to authenticated',f.signature);
 end loop;
end$$;
insert into public.rf_clients(name,site) select distinct client_name,site_name from public.op_routes;
insert into public.rf_stations(code,name,kind) values('sporco-01','Tunnel sporco','sporco'),('pulito-01','Armadio 1','pulito'),('pulito-02','Armadio 2','pulito'),('pulito-03','Armadio 3','pulito'),('pulito-04','Armadio 4','pulito');
-- Provisional capacity stated by the owner; editable before each new session.
update public.rf_stations set slot_count=90 where kind='pulito';
comment on table public.rf_movements is 'Native events. Test sessions are marked collaudo and must never be included in production reports.';
comment on table public.rf_label_jobs is 'Immutable label payloads. Enqueued at clean-cabinet closure; enqueue is not confirmation of physical printing.';
commit;
