begin;
-- Stored search projections; raw_json and source identifiers remain unchanged.
alter table public.np_source_records add column directory_department text generated always as (np_private.clean_text(coalesce(raw_json->>'Area',raw_json->>'Reparto'))) stored;
alter table public.np_source_records add column directory_floor text generated always as (np_private.clean_text(raw_json->>'Piano')) stored;
alter table public.np_source_records add column directory_surname text generated always as (np_private.clean_text(raw_json->>'Cognome')) stored;
alter table public.np_source_records add column directory_given_name text generated always as (np_private.clean_text(raw_json->>'Nome')) stored;
alter table public.np_source_records add column directory_article text generated always as (np_private.clean_text(coalesce(raw_json->>'Classe merceologica',raw_json->>'Classe Merceologica'))) stored;
alter table public.np_source_records add column directory_wear text generated always as (np_private.clean_text(raw_json->>'Stato di usura')) stored;
create index np_directory_person on public.np_source_records(batch_id,person_name_key);
create index np_directory_department on public.np_source_records(batch_id,directory_department,directory_floor);
create or replace view public.np_catalogue_records with(security_invoker=true) as
 with source as (
 select r.id,r.batch_id,r.source_row,r.external_person_id,r.tag_id,r.person_name_key,r.incoming_date,r.outgoing_date,r.raw_json,b.archive,b.kind,
 r.directory_department as source_department,
 r.directory_floor as source_floor,
 r.directory_surname as surname,r.directory_given_name as given_name,r.directory_article,r.directory_wear
 from public.np_latest_batches b join public.np_source_records r on r.batch_id=b.id
 ), normalized as (
 select s.id,s.batch_id,s.source_row,s.external_person_id,s.tag_id,s.person_name_key,s.incoming_date,s.outgoing_date,s.raw_json,s.archive,s.kind,s.source_department,s.source_floor,s.surname,s.given_name,coalesce(l.department,case when s.source_department in ('X','XX','.','-') then '' else s.source_department end) as department,
 coalesce(l.floor,np_private.clean_floor(s.source_floor)) as floor,coalesce(l.revision,0) as correction_revision,
 s.directory_article as article,
 s.directory_wear as wear,
 case when coalesce(s.raw_json->>'Nr. lavaggi','') ~ '^[0-9]{1,8}$' then (s.raw_json->>'Nr. lavaggi')::integer end as washes,
 case when s.given_name in ('SCORTA','SCORTE') or s.surname in ('SCORTA','SCORTE') then 'scorta'
 when s.surname ~ '^TAGLIA' or s.given_name ~ '^TAGLIA' or (s.surname='PIANO' and s.given_name ~ '^[0-9]+') then 'generica'
 when s.surname='' or s.given_name='' or s.surname ~ '^[0-9]+$' then 'da_verificare' else 'persona' end as category
 from source s left join public.np_latest_locations l on l.archive=s.archive and l.source_department=s.source_department and l.source_floor=s.source_floor
 ) select *, (department='' or department ~ '^[0-9]+$' or (floor<>'' and floor !~ '^[0-9]+$') or (archive='ospiti' and department not in ('PAPAVERO','GERANIO','MIMOSA','CICLAMINO','ROSA','MARGHERITA','GIRASOLE') and correction_revision=0) or (archive='divise' and length(department)=1)) as needs_review from normalized;
create or replace function public.np_catalogue(p_archive text,p_view text default 'persone',p_search text default '',p_department text default '',p_floor text default '',p_article text default '',p_category text default '',p_wear text default '',p_from date default null,p_to date default null,p_offset integer default 0,p_limit integer default 50,p_person_key text default '')
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
 select jsonb_build_object('id',id,'source_row',source_row,'person_key',person_name_key,'surname',surname,'name',given_name,'tag',tag_id,'department',department,'floor',floor,'source_department',source_department,'source_floor',source_floor,'category',category,'article',article,'wear',wear,'washes',washes,'incoming',incoming_date,'outgoing',outgoing_date,'needs_review',needs_review,'has_raw',true) as row,surname||' '||given_name as sort_key,id::text as tie from filtered where p_view<>'dotazioni'
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

commit;
