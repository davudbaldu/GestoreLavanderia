-- Schema-only acquisition migration. No operational records or automatic membership.
begin;
create table public.app_members (
 user_id uuid primary key references auth.users(id) on delete cascade,
 role text not null default 'owner' check (role='owner'),
 active boolean not null default true,
 created_at timestamptz not null default now()
);
create table public.np_import_batches (
 id uuid primary key default gen_random_uuid(),
 archive text not null check (archive in ('ospiti','divise')),
 kind text not null check (kind in ('persone','tag','movimenti')),
 source_key text not null, file_name text not null, source_sha256 text,
 status text not null default 'staging' check (status in ('staging','ready','rejected')),
 summary jsonb not null default '{}'::jsonb check (jsonb_typeof(summary)='object'),
 imported_at timestamptz not null default now(),
 unique (archive,kind,source_key)
);
create table public.np_source_records (
 id bigint generated always as identity primary key,
 batch_id uuid not null references public.np_import_batches(id) on delete restrict,
 source_row integer not null check (source_row>0),
 external_person_id text, tag_id text, person_name_key text not null default '',
 incoming_date date, outgoing_date date,
 raw_json jsonb not null check (jsonb_typeof(raw_json)='object'),
 unique (batch_id,source_row)
);
create table public.np_import_issues (
 id bigint generated always as identity primary key,
 batch_id uuid not null references public.np_import_batches(id) on delete restrict,
 source_row integer, code text not null,
 details jsonb not null default '{}'::jsonb check (jsonb_typeof(details)='object')
);
create index np_records_tag on public.np_source_records(tag_id);
create index np_records_person on public.np_source_records(batch_id,external_person_id);
create index np_batches_latest on public.np_import_batches(archive,kind,imported_at desc);
create index np_issues_batch on public.np_import_issues(batch_id);
alter table public.app_members enable row level security;
alter table public.np_import_batches enable row level security;
alter table public.np_source_records enable row level security;
alter table public.np_import_issues enable row level security;
revoke all on public.app_members,public.np_import_batches,public.np_source_records,public.np_import_issues from public,anon,authenticated;
revoke all on sequence public.np_source_records_id_seq,public.np_import_issues_id_seq from public,anon,authenticated;
grant usage on schema public to authenticated;
grant select on public.app_members,public.np_import_batches,public.np_source_records,public.np_import_issues to authenticated;
create policy member_reads_self on public.app_members
 for select to authenticated using (user_id=(select auth.uid()) and active);
create policy owner_reads_batches on public.np_import_batches
 for select to authenticated using (exists (
  select 1 from public.app_members m
  where m.user_id=(select auth.uid()) and m.active and m.role='owner'
 ));
create policy owner_reads_ready_records on public.np_source_records
 for select to authenticated using (
  exists (select 1 from public.app_members m
    where m.user_id=(select auth.uid()) and m.active and m.role='owner')
  and exists (select 1 from public.np_import_batches b where b.id=batch_id and b.status='ready')
 );
create policy owner_reads_issues on public.np_import_issues
 for select to authenticated using (exists (
  select 1 from public.app_members m
  where m.user_id=(select auth.uid()) and m.active and m.role='owner'
 ));
create view public.np_latest_batches with (security_invoker=true) as
 select distinct on (archive,kind) id,archive,kind,file_name,imported_at,summary
 from public.np_import_batches where status='ready'
 order by archive,kind,imported_at desc,id desc;
revoke all on public.np_latest_batches from public,anon,authenticated;
grant select on public.np_latest_batches to authenticated;
create function public.np_overview() returns jsonb
 language sql stable security invoker set search_path=pg_catalog,public as $body$
 with totals as (
  select b.archive,b.kind,b.id,b.file_name,b.imported_at,
   count(r.id) as records,
   count(distinct r.tag_id) filter (where r.tag_id is not null) as tags,
   count(r.id) filter (where r.incoming_date is not null) as entries,
   count(r.id) filter (where r.outgoing_date is not null) as exits
  from public.np_latest_batches b
  left join public.np_source_records r on r.batch_id=b.id
  group by b.archive,b.kind,b.id,b.file_name,b.imported_at
 )
 select jsonb_build_object('batches',coalesce(
  jsonb_agg(jsonb_build_object(
   'archive',archive,'kind',kind,'batch_id',id,'file_name',file_name,
   'imported_at',imported_at,'records',records,'tags',tags,'entries',entries,'exits',exits
  ) order by archive,kind),'[]'::jsonb
 )) from totals;
$body$;
revoke all on function public.np_overview() from public,anon,authenticated;
grant execute on function public.np_overview() to authenticated;
comment on column public.np_source_records.external_person_id is 'Original CLIEID as text, scoped by source batch archive.';
comment on column public.np_source_records.raw_json is 'Unchanged original fields, including assignment, dates and flags.';
comment on table public.app_members is 'Enrollment requires privileged administration. No first-user-wins enrollment.';
commit;
