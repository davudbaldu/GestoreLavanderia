\set ON_ERROR_STOP on
begin;
insert into auth.users(id) values
 ('11111111-1111-4111-8111-111111111111'),
 ('22222222-2222-4222-8222-222222222222');
insert into public.app_members(user_id) values ('11111111-1111-4111-8111-111111111111');
insert into public.np_import_batches(id,archive,kind,source_key,file_name,status)
 values ('33333333-3333-4333-8333-333333333333','ospiti','movimenti','fixture-v1','synthetic.csv','ready');
insert into public.np_source_records(batch_id,source_row,external_person_id,tag_id,incoming_date,raw_json)
 values ('33333333-3333-4333-8333-333333333333',2,'10.001','DEMO001','2026-06-02',
 '{"Cognome":"Demo","Nome":"Uno","TAGID":"DEMO001"}'::jsonb);
set local role anon;
do $check$
begin
 begin
  perform count(*) from public.np_source_records;
  raise exception 'Anonymous record access unexpectedly allowed';
 exception when insufficient_privilege then null; end;
 begin
  perform public.np_overview();
  raise exception 'Anonymous summary unexpectedly allowed';
 exception when insufficient_privilege then null; end;
end;
$check$;
reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub','22222222-2222-4222-8222-222222222222',true);
do $check$
begin
 if (select count(*) from public.np_source_records)<>0 then raise exception 'Non-member reads records'; end if;
 if (select count(*) from public.np_import_batches)<>0 then raise exception 'Non-member reads metadata'; end if;
 if (select count(*) from public.np_latest_batches)<>0 then raise exception 'View bypasses RLS'; end if;
 if jsonb_array_length(public.np_overview()->'batches')<>0 then raise exception 'Summary leaks data'; end if;
 begin
  insert into public.app_members(user_id) values ('22222222-2222-4222-8222-222222222222');
  raise exception 'Self-enrollment allowed';
 exception when insufficient_privilege then null; end;
end;
$check$;
reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub','11111111-1111-4111-8111-111111111111',true);
do $check$
begin
 if (select count(*) from public.np_source_records)<>1 then raise exception 'Owner cannot read ready rows'; end if;
 if (public.np_overview()->'batches'->0->>'entries')::integer<>1 then raise exception 'Owner summary incorrect'; end if;
 begin
  update public.app_members set active=false;
  raise exception 'Browser changes membership';
 exception when insufficient_privilege then null; end;
 begin
  delete from public.np_source_records;
  raise exception 'Browser deletes source history';
 exception when insufficient_privilege then null; end;
end;
$check$;
reset role;
update public.np_import_batches set status='staging';
set local role authenticated;
select set_config('request.jwt.claim.sub','11111111-1111-4111-8111-111111111111',true);
do $check$
begin
 if (select count(*) from public.np_source_records)<>0 then raise exception 'Staging rows visible'; end if;
 if (select count(*) from public.np_latest_batches)<>0 then raise exception 'Staging batch appears current'; end if;
end;
$check$;
reset role;
update public.app_members set active=false;
update public.np_import_batches set status='ready';
set local role authenticated;
select set_config('request.jwt.claim.sub','11111111-1111-4111-8111-111111111111',true);
do $check$
begin
 if (select count(*) from public.np_source_records)<>0 then raise exception 'Revoked account reads records'; end if;
 if jsonb_array_length(public.np_overview()->'batches')<>0 then raise exception 'Revoked account reads summary'; end if;
end;
$check$;
reset role;
rollback;
