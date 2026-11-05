begin;
create function np_private.clean_text(value text) returns text language sql immutable security invoker set search_path=pg_catalog as $$
 select upper(regexp_replace(btrim(coalesce(value,'')),'\s+',' ','g'))
$$;
create function np_private.clean_floor(value text) returns text language sql immutable security invoker set search_path=pg_catalog,np_private as $$
 select case when np_private.clean_text(value) in ('','X','XX','.X','.','-') then ''
 when np_private.clean_text(value) ~ '^\.*[0-9]+\.*$' then trim(both '.' from np_private.clean_text(value))
 else np_private.clean_text(value) end
$$;
revoke all on function np_private.clean_text(text),np_private.clean_floor(text) from public,anon;
grant execute on function np_private.clean_text(text),np_private.clean_floor(text) to authenticated;
create table public.np_location_versions(
 archive text not null check(archive in ('ospiti','divise')),
 source_department text not null check(length(source_department)<=120),
 source_floor text not null check(length(source_floor)<=120),
 revision integer not null check(revision>0),
 department text not null check(length(department)<=120),
 floor text not null check(length(floor)<=120),
 reason text not null check(length(btrim(reason)) between 3 and 1000),
 recorded_by uuid not null references auth.users(id),
 recorded_at timestamptz not null default now(),
 primary key(archive,source_department,source_floor,revision)
);
create index np_locations_actor on public.np_location_versions(recorded_by);
alter table public.np_location_versions enable row level security;
revoke all on public.np_location_versions from public,anon,authenticated;
grant select,insert on public.np_location_versions to authenticated;
create policy owner_reads_locations on public.np_location_versions for select to authenticated using(exists(select 1 from public.app_members m where m.user_id=(select auth.uid()) and m.active and m.role='owner'));
create policy owner_appends_locations on public.np_location_versions for insert to authenticated with check(recorded_by=(select auth.uid()) and exists(select 1 from public.app_members m where m.user_id=(select auth.uid()) and m.active and m.role='owner'));
create function np_private.validate_location() returns trigger language plpgsql security invoker set search_path=pg_catalog,public,np_private as $$
declare last_revision integer;
begin
 if auth.uid() is null or not exists(select 1 from public.app_members where user_id=auth.uid() and active and role='owner') then raise insufficient_privilege using message='Account non abilitato.';end if;
 new.source_department=np_private.clean_text(new.source_department);new.source_floor=np_private.clean_text(new.source_floor);
 new.department=np_private.clean_text(new.department);new.floor=np_private.clean_floor(new.floor);
 perform pg_advisory_xact_lock(hashtextextended(jsonb_build_array(new.archive,new.source_department,new.source_floor)::text,0));
 select max(revision) into last_revision from public.np_location_versions where archive=new.archive and source_department=new.source_department and source_floor=new.source_floor;
 if new.revision<>coalesce(last_revision,0)+1 then raise exception using errcode='40001',message='La regola è stata modificata. Aggiorna prima di salvare.';end if;
 new.recorded_by=auth.uid();new.recorded_at=clock_timestamp();return new;
end $$;
revoke all on function np_private.validate_location() from public,anon,authenticated;
create trigger validate_location before insert on public.np_location_versions for each row execute function np_private.validate_location();
create view public.np_latest_locations with(security_invoker=true) as
 select distinct on(archive,source_department,source_floor) * from public.np_location_versions order by archive,source_department,source_floor,revision desc;
revoke all on public.np_latest_locations from public,anon,authenticated;
grant select on public.np_latest_locations to authenticated;

-- Read-through normalization, never a mutation of source rows or assignments.
create view public.np_catalogue_records with(security_invoker=true) as
 with source as (
 select r.*,b.archive,b.kind,
 np_private.clean_text(coalesce(r.raw_json->>'Area',r.raw_json->>'Reparto')) as source_department,
 np_private.clean_text(r.raw_json->>'Piano') as source_floor,
 np_private.clean_text(r.raw_json->>'Cognome') as surname,np_private.clean_text(r.raw_json->>'Nome') as given_name
 from public.np_latest_batches b join public.np_source_records r on r.batch_id=b.id
 ), normalized as (
 select s.*,coalesce(l.department,case when s.source_department in ('X','XX','.','-') then '' else s.source_department end) as department,
 coalesce(l.floor,np_private.clean_floor(s.source_floor)) as floor,coalesce(l.revision,0) as correction_revision,
 np_private.clean_text(coalesce(s.raw_json->>'Classe merceologica',s.raw_json->>'Classe Merceologica')) as article,
 np_private.clean_text(s.raw_json->>'Stato di usura') as wear,
 case when coalesce(s.raw_json->>'Nr. lavaggi','') ~ '^[0-9]{1,8}$' then (s.raw_json->>'Nr. lavaggi')::integer end as washes,
 case when s.given_name in ('SCORTA','SCORTE') or s.surname in ('SCORTA','SCORTE') then 'scorta'
 when s.surname ~ '^TAGLIA' or s.given_name ~ '^TAGLIA' or (s.surname='PIANO' and s.given_name ~ '^[0-9]+') then 'generica'
 when s.surname='' or s.given_name='' or s.surname ~ '^[0-9]+$' then 'da_verificare' else 'persona' end as category
 from source s left join public.np_latest_locations l on l.archive=s.archive and l.source_department=s.source_department and l.source_floor=s.source_floor
 ) select *, (department='' or department ~ '^[0-9]+$' or (floor<>'' and floor !~ '^[0-9]+$') or (archive='ospiti' and department not in ('PAPAVERO','GERANIO','MIMOSA','CICLAMINO','ROSA','MARGHERITA','GIRASOLE') and correction_revision=0) or (archive='divise' and length(department)=1)) as needs_review from normalized;
revoke all on public.np_catalogue_records from public,anon,authenticated;
grant select on public.np_catalogue_records to authenticated;

create function public.np_catalogue(p_archive text,p_view text default 'persone',p_search text default '',p_department text default '',p_floor text default '',p_article text default '',p_category text default '',p_wear text default '',p_from date default null,p_to date default null,p_offset integer default 0,p_limit integer default 50,p_person_key text default '')
 returns jsonb language plpgsql stable security invoker set search_path=pg_catalog,public as $$
declare result jsonb; k text;
begin
 if p_archive not in ('ospiti','divise') or p_view not in ('persone','tag','dotazioni','movimenti','report') then raise exception 'Vista non valida.';end if;
 if p_from>p_to then raise exception 'Il periodo non è valido.';end if;
 k=case when p_view='dotazioni' then 'tag' when p_view='report' then 'movimenti' else p_view end;
 with base as materialized(select * from public.np_catalogue_records where archive=p_archive and kind=k),
 filtered as materialized(select * from base where
 (coalesce(p_search,'')='' or strpos(upper(concat_ws(' ',surname,given_name,tag_id,article,department,source_department)),upper(btrim(p_search)))>0)
 and (p_person_key='' or person_name_key=p_person_key) and (p_department='' or department=p_department) and (p_floor='' or floor=p_floor)
 and (p_article='' or article=p_article) and (p_category='' or category=p_category) and (p_wear='' or wear=p_wear)
 and ((p_from is null and p_to is null) or (incoming_date between coalesce(p_from,'0001-01-01') and coalesce(p_to,'9999-12-31')) or (outgoing_date between coalesce(p_from,'0001-01-01') and coalesce(p_to,'9999-12-31')))),
 items as (select person_name_key,surname,given_name,department,floor,category,article,count(*) as quantity,bool_or(needs_review) as needs_review,min(id) as id from filtered where p_view='dotazioni' group by person_name_key,surname,given_name,department,floor,category,article),
 detail as (
 select jsonb_build_object('id',id,'source_row',source_row,'person_key',person_name_key,'surname',surname,'name',given_name,'tag',tag_id,'department',department,'floor',floor,'source_department',source_department,'source_floor',source_floor,'category',category,'article',article,'wear',wear,'washes',washes,'incoming',incoming_date,'outgoing',outgoing_date,'needs_review',needs_review,'raw',raw_json) as row,surname||' '||given_name as sort_key,id::text as tie from filtered where p_view<>'dotazioni'
 union all
 select jsonb_build_object('person_key',person_name_key,'surname',surname,'name',given_name,'department',department,'floor',floor,'category',category,'garments',sum(quantity),'articles',jsonb_agg(jsonb_build_object('article',article,'quantity',quantity) order by article),'needs_review',bool_or(needs_review)),surname||' '||given_name,min(id)::text
 from items group by person_name_key,surname,given_name,department,floor,category),
 page as(select row from detail order by sort_key,tie offset greatest(coalesce(p_offset,0),0) limit least(greatest(coalesce(p_limit,50),1),100)),
 article_totals as(select article,count(*) as records from filtered group by article),
 department_totals as(select department,floor,count(*) as records from filtered group by department,floor),
 daily as (
 select d,count(*) filter(where event='ingresso') as entries,count(*) filter(where event='uscita') as exits from (
 select incoming_date as d,'ingresso' as event from filtered where incoming_date between coalesce(p_from,'0001-01-01') and coalesce(p_to,'9999-12-31')
 union all select outgoing_date,'uscita' from filtered where outgoing_date between coalesce(p_from,'0001-01-01') and coalesce(p_to,'9999-12-31')) e group by d)
 select jsonb_build_object('rows',coalesce((select jsonb_agg(row) from page),'[]'::jsonb),'total',(select count(*) from detail),
 'summary',jsonb_build_object('records',(select count(*) from filtered),'review',(select count(*) from filtered where needs_review),'people',(select count(*) from filtered where category='persona'),'stocks',(select count(*) from filtered where category<>'persona'),
 'entries',(select coalesce(sum(entries),0) from daily),'exits',(select coalesce(sum(exits),0) from daily)),
 'facets',jsonb_build_object('departments',(select coalesce(jsonb_agg(d order by d),'[]') from(select distinct department d from base where department<>'')x),'floors',(select coalesce(jsonb_agg(d order by d),'[]') from(select distinct floor d from base where floor<>'')x),'articles',(select coalesce(jsonb_agg(d order by d),'[]') from(select distinct article d from base where article<>'')x),'wear',(select coalesce(jsonb_agg(d order by d),'[]') from(select distinct wear d from base where wear<>'')x)),
 'reports',jsonb_build_object('articles',(select coalesce(jsonb_agg(to_jsonb(a) order by records desc),'[]') from article_totals a),'departments',(select coalesce(jsonb_agg(to_jsonb(a) order by department,floor),'[]') from department_totals a),'daily',(select coalesce(jsonb_agg(to_jsonb(a) order by d),'[]') from daily a))) into result;
 return result;
end $$;
revoke all on function public.np_catalogue(text,text,text,text,text,text,text,text,date,date,integer,integer,text) from public,anon;
grant execute on function public.np_catalogue(text,text,text,text,text,text,text,text,date,date,integer,integer,text) to authenticated;

create function public.np_quality(p_archive text) returns jsonb language sql stable security invoker set search_path=pg_catalog,public as $$
 with groups as (
 select archive,source_department,source_floor,department,floor,correction_revision,
 count(*) filter(where kind='persone') as people,count(*) filter(where kind='tag') as garments,count(*) filter(where kind='movimenti') as history,bool_or(needs_review) as needs_review,
 bool_or(source_department<>department or source_floor<>floor) as normalized
 from public.np_catalogue_records where archive=p_archive group by archive,source_department,source_floor,department,floor,correction_revision)
 select coalesce(jsonb_agg(to_jsonb(g) order by needs_review desc,source_department,source_floor),'[]'::jsonb) from groups g
$$;
revoke all on function public.np_quality(text) from public,anon;
grant execute on function public.np_quality(text) to authenticated;
comment on view public.np_catalogue_records is 'Normalized overlay. Names are not merged, imported raw_json and historical assignments remain unchanged.';
commit;
