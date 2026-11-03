begin;
create schema if not exists np_private;
revoke all on schema np_private from public,anon,authenticated;
grant usage on schema np_private to authenticated;
create table np_private.owner_setup_tokens (
 token_hash text primary key,
 expires_at timestamptz not null,
 used_by uuid references auth.users(id),
 used_at timestamptz,
 check ((used_by is null) = (used_at is null))
);
alter table np_private.owner_setup_tokens enable row level security;
revoke all on np_private.owner_setup_tokens from public,anon,authenticated;

create function np_private.claim_owner(p_token text) returns uuid
language plpgsql security definer set search_path='' as $body$
declare v_uid uuid; v_hash text; v_token np_private.owner_setup_tokens%rowtype;
begin
 v_uid := auth.uid();
 if v_uid is null then raise exception 'Authentication required' using errcode='42501'; end if;
 if not exists(select 1 from auth.users u where u.id=v_uid and u.email_confirmed_at is not null) then
  raise exception 'Confirm your email before activation' using errcode='42501';
 end if;
 if exists(select 1 from public.app_members m where m.user_id=v_uid and m.active and m.role='owner') then
  return v_uid;
 end if;
 if p_token is null or p_token !~ '^[0-9a-f]{64}$' then
  raise exception 'Invalid activation code' using errcode='28000';
 end if;
 perform pg_catalog.pg_advisory_xact_lock(76861,1);
 v_hash := pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(p_token,'UTF8')),'hex');
 select * into v_token from np_private.owner_setup_tokens t
  where t.token_hash=v_hash and t.used_at is null and t.expires_at>pg_catalog.now()
  for update;
 if not found then raise exception 'Activation code unavailable or expired' using errcode='28000'; end if;
 if exists(select 1 from public.app_members m where m.active and m.role='owner') then
  raise exception 'Owner already configured' using errcode='42501';
 end if;
 insert into public.app_members(user_id,role,active) values(v_uid,'owner',true);
 update np_private.owner_setup_tokens set used_by=v_uid,used_at=pg_catalog.now()
  where token_hash=v_hash;
 return v_uid;
end;
$body$;
revoke all on function np_private.claim_owner(text) from public,anon,authenticated;
grant execute on function np_private.claim_owner(text) to authenticated;

create function public.np_claim_owner(p_token text) returns uuid
language sql security invoker set search_path='' as $body$
 select np_private.claim_owner(p_token);
$body$;
revoke all on function public.np_claim_owner(text) from public,anon,authenticated;
grant execute on function public.np_claim_owner(text) to authenticated;
commit;