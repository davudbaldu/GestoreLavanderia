begin;
insert into auth.users(id) values
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),
 ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
insert into public.app_members(user_id) values('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
set local role anon;
do $$ begin
 begin perform count(*) from public.op_latest_preparations; raise exception 'Anonymous reads preparations';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',true);
do $$ begin
 if exists(select 1 from public.op_routes) then raise exception 'Non-member sees routes'; end if;
 begin
  insert into public.op_preparation_versions(id,revision,route_id,delivery_on,status,lines,recorded_by)
  values('cccccccc-cccc-4ccc-8ccc-cccccccccccc',1,'dddddddd-dddd-4ddd-8ddd-dddddddddddd',current_date,'preparazione','[]','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
  raise exception 'Non-member writes preparation';
 exception when insufficient_privilege then null; end;
end $$;
reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',true);
do $$ declare rid uuid; begin
 select id into rid from public.op_routes where service='ospiti_divise';
 insert into public.op_preparation_versions(id,revision,route_id,delivery_on,status,lines,containers,notes,recorded_by,recorded_at)
 values('cccccccc-cccc-4ccc-8ccc-cccccccccccc',1,rid,current_date,'preparazione','[{"article":"Divise","quantity":50,"unit":"pezzi"}]','[{"kind":"roll","quantity":2}]','Nota originale','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','2000-01-01');
 if not exists(select 1 from public.op_preparation_versions where recorded_by=auth.uid() and recorded_at>now()-interval '1 minute') then raise exception 'Forged audit metadata'; end if;
 begin
  insert into public.op_preparation_versions select id,revision,route_id,delivery_on,status,lines,containers,notes,recorded_by,recorded_at from public.op_preparation_versions;
  raise exception 'Stale write accepted';
 exception when serialization_failure then null; end;
 begin
  insert into public.op_preparation_versions select id,2,route_id,delivery_on,'consegnato',lines,containers,notes,recorded_by,recorded_at from public.op_preparation_versions;
  raise exception 'Skipped transition accepted';
 exception when raise_exception then if sqlerrm='Skipped transition accepted' then raise; end if; end;
 begin
  insert into public.op_preparation_versions select id,2,route_id,delivery_on,status,'[{"article":"Divise","quantity":1.5,"unit":"pezzi"}]',containers,notes,recorded_by,recorded_at from public.op_preparation_versions;
  raise exception 'Fractional pieces accepted';
 exception when raise_exception then if sqlerrm='Fractional pieces accepted' then raise; end if; end;
 begin
  insert into public.op_preparation_versions select id,2,route_id,delivery_on,status,'[{"article":"Divise","unit":"pezzi"}]',containers,notes,recorded_by,recorded_at from public.op_preparation_versions;
  raise exception 'Missing quantity accepted';
 exception when raise_exception then if sqlerrm='Missing quantity accepted' then raise; end if; end;
 insert into public.op_preparation_versions select id,2,route_id,delivery_on,'pronto',lines,containers,notes,recorded_by,recorded_at from public.op_latest_preparations;
 begin
  insert into public.op_preparation_versions select id,3,route_id,delivery_on,'ritirato','[{"article":"Divise","quantity":99,"unit":"pezzi"}]',containers,notes,recorded_by,recorded_at from public.op_latest_preparations;
  raise exception 'Changed ready quantities accepted';
 exception when raise_exception then if sqlerrm='Changed ready quantities accepted' then raise; end if; end;
 -- Explicit reopening preserves the previous ready version, then editing is allowed.
 insert into public.op_preparation_versions select id,3,route_id,delivery_on,'preparazione',lines,containers,notes,recorded_by,recorded_at from public.op_latest_preparations;
 insert into public.op_preparation_versions select id,4,route_id,delivery_on,'preparazione','[{"article":"Divise","quantity":51,"unit":"pezzi"}]',containers,notes,recorded_by,recorded_at from public.op_latest_preparations;
 insert into public.op_preparation_versions select id,5,route_id,delivery_on,'pronto',lines,containers,notes,recorded_by,recorded_at from public.op_latest_preparations;
 insert into public.op_preparation_versions select id,6,route_id,delivery_on,'ritirato',lines,containers,notes,recorded_by,recorded_at from public.op_latest_preparations;
 insert into public.op_preparation_versions select id,7,route_id,delivery_on,'consegnato',lines,containers,notes,recorded_by,recorded_at from public.op_latest_preparations;
 if (select count(*) from public.op_preparation_versions)<>7 then raise exception 'History lost'; end if;
 if (select count(*) from public.op_latest_preparations)<>1 then raise exception 'Latest version incorrect'; end if;
 begin
  insert into public.op_preparation_versions select id,8,route_id,delivery_on,'consegnato',lines,containers,notes,recorded_by,recorded_at from public.op_latest_preparations;
  raise exception 'Delivered preparation modified';
 exception when raise_exception then if sqlerrm='Delivered preparation modified' then raise; end if; end;
 begin update public.op_preparation_versions set notes='Forged';raise exception 'History updated';exception when insufficient_privilege then null;end;
 begin delete from public.op_preparation_versions;raise exception 'History deleted';exception when insufficient_privilege then null;end;
end $$;
reset role;
update public.app_members set active=false where user_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
set local role authenticated;
do $$ begin
 if exists(select 1 from public.op_latest_preparations) then raise exception 'Revoked member reads preparations';end if;
 if exists(select 1 from public.op_preparation_versions) then raise exception 'Revoked member reads history';end if;
end $$;
reset role;
rollback;
