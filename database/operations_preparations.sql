begin;
create schema if not exists op_private;
revoke all on schema op_private from public, anon;
grant usage on schema op_private to authenticated;

create table public.op_routes (
 id uuid primary key default gen_random_uuid(),
 code text not null unique,
 client_name text not null,
 site_name text not null,
 service text not null check(service in ('ospiti_divise','piana')),
 origin_name text not null,
 carrier_name text not null,
 issuer_name text not null,
 active boolean not null default true
);
create table public.op_preparation_versions (
 id uuid not null,
 revision integer not null check(revision>0),
 route_id uuid not null references public.op_routes(id),
 delivery_on date not null,
 status text not null check(status in ('preparazione','pronto','ritirato','consegnato')),
 lines jsonb not null check(jsonb_typeof(lines)='array'),
 containers jsonb not null default '[]'::jsonb check(jsonb_typeof(containers)='array'),
 notes text not null default '' check(length(notes)<=2000),
 recorded_by uuid not null references auth.users(id),
 recorded_at timestamptz not null default now(),
 primary key(id,revision)
);
create index op_versions_route on public.op_preparation_versions(route_id);
create index op_versions_actor on public.op_preparation_versions(recorded_by);
create index op_versions_delivery on public.op_preparation_versions(delivery_on desc);
alter table public.op_routes enable row level security;
alter table public.op_preparation_versions enable row level security;
revoke all on public.op_routes, public.op_preparation_versions from public,anon,authenticated;
grant select on public.op_routes,public.op_preparation_versions to authenticated;
grant insert on public.op_preparation_versions to authenticated;
create policy owner_reads_routes on public.op_routes for select to authenticated
 using(exists(select 1 from public.app_members m where m.user_id=(select auth.uid()) and m.active and m.role='owner'));
create policy owner_reads_preparations on public.op_preparation_versions for select to authenticated
 using(exists(select 1 from public.app_members m where m.user_id=(select auth.uid()) and m.active and m.role='owner'));
create policy owner_appends_preparation on public.op_preparation_versions for insert to authenticated
 with check(recorded_by=(select auth.uid()) and exists(select 1 from public.app_members m where m.user_id=(select auth.uid()) and m.active and m.role='owner'));

-- All browser writes pass through this invoker trigger, including direct REST inserts.
-- Versions are append-only; there are no UPDATE or DELETE grants.
create function op_private.validate_preparation() returns trigger
 language plpgsql security invoker set search_path=pg_catalog,public as $$
declare previous public.op_preparation_versions; item jsonb;
begin
 if auth.uid() is null or not exists(select 1 from public.app_members where user_id=auth.uid() and active and role='owner') then
  raise insufficient_privilege using message='Account non abilitato alle distinte.';
 end if;
 perform pg_advisory_xact_lock(hashtextextended(new.id::text,0));
 select * into previous from public.op_preparation_versions where id=new.id order by revision desc limit 1;
 if new.revision<>coalesce(previous.revision,0)+1 then
  raise exception using errcode='40001',message='Distinta aggiornata da un altro utente. Ricarica prima di salvare.';
 end if;
 if not exists(select 1 from public.op_routes where id=new.route_id and active) then
  raise exception 'Percorso non disponibile.';
 end if;
 if previous.id is null then
  if new.status<>'preparazione' then raise exception 'La distinta deve iniziare in preparazione.'; end if;
 else
  if new.route_id<>previous.route_id or new.delivery_on<>previous.delivery_on then
   raise exception 'Destinazione e data non possono cambiare fra versioni.';
  end if;
  if previous.status='consegnato' then raise exception 'La distinta consegnata è chiusa.'; end if;
  if not ((previous.status='preparazione' and new.status in ('preparazione','pronto'))
    or (previous.status='pronto' and new.status in ('preparazione','ritirato'))
    or (previous.status='ritirato' and new.status='consegnato')) then
   raise exception 'Passaggio di stato non consentito.';
  end if;
  if not (previous.status='preparazione' and new.status='preparazione') and
    (new.lines<>previous.lines or new.containers<>previous.containers or new.notes<>previous.notes) then
   raise exception 'Le quantità si modificano solo in preparazione. Riapri la distinta prima di correggerla.';
  end if;
 end if;
 if jsonb_array_length(new.lines) not between 1 and 100 or jsonb_array_length(new.containers)>100 then
  raise exception 'Inserisci da 1 a 100 articoli e al massimo 100 tipi di contenitore.';
 end if;
 for item in select value from jsonb_array_elements(new.lines) loop
  if jsonb_typeof(item)<>'object' or jsonb_typeof(item->'article') is distinct from 'string'
    or length(btrim(item->>'article')) not between 1 and 120
    or jsonb_typeof(item->'quantity') is distinct from 'number'
    or jsonb_typeof(item->'unit') is distinct from 'string'
    or item->>'unit' not in ('pezzi','kg') then
   raise exception 'Articolo, quantità o unità non validi.';
  end if;
  if (item->>'quantity')::numeric<=0 or (item->>'quantity')::numeric>1000000
    or (item->>'quantity')::numeric<>round((item->>'quantity')::numeric,3)
    or (item->>'unit'='pezzi' and (item->>'quantity')::numeric<>trunc((item->>'quantity')::numeric)) then
   raise exception 'Quantità non valida: pezzi interi o kg con al massimo tre decimali.';
  end if;
 end loop;
 for item in select value from jsonb_array_elements(new.containers) loop
  if jsonb_typeof(item)<>'object' or jsonb_typeof(item->'kind') is distinct from 'string'
    or item->>'kind' not in ('roll','sacco','collo') or jsonb_typeof(item->'quantity') is distinct from 'number' then
   raise exception 'Contenitore non valido.';
  end if;
  if (item->>'quantity')::numeric not between 1 and 1000000 or (item->>'quantity')::numeric<>trunc((item->>'quantity')::numeric) then
   raise exception 'Il numero di contenitori deve essere un intero positivo.';
  end if;
 end loop;
 new.recorded_by=auth.uid();
 new.recorded_at=clock_timestamp();
 return new;
end;
$$;
revoke all on function op_private.validate_preparation() from public,anon,authenticated;
create trigger validate_preparation before insert on public.op_preparation_versions
 for each row execute function op_private.validate_preparation();
create view public.op_latest_preparations with (security_invoker=true) as
 select distinct on(id) * from public.op_preparation_versions order by id,revision desc;
revoke all on public.op_latest_preparations from public,anon,authenticated;
grant select on public.op_latest_preparations to authenticated;
comment on table public.op_preparation_versions is 'Append-only operational preparation snapshots. These are not issued DDTs.';
insert into public.op_routes(code,client_name,site_name,service,origin_name,carrier_name,issuer_name) values
 ('emmaus_gratosoglio_ospiti_divise','Emmaus','Gratosoglio','ospiti_divise','Inzago','Cooperativa Mimosa','Servizi Alla Persona'),
 ('emmaus_gratosoglio_piana','Emmaus','Gratosoglio','piana','Dove il lavare è arte · Valbrembo','Cooperativa Mimosa','Servizi Alla Persona');
commit;
