\set ON_ERROR_STOP on
begin;
insert into auth.users(id,email_confirmed_at) values
 ('44444444-4444-4444-8444-444444444444',now()),
 ('55555555-5555-4555-8555-555555555555',now()),
 ('66666666-6666-4666-8666-666666666666',null);
insert into np_private.owner_setup_tokens(token_hash,expires_at) values
 (encode(sha256(convert_to(repeat('a',64),'UTF8')),'hex'),now()+interval '1 hour'),
 (encode(sha256(convert_to(repeat('b',64),'UTF8')),'hex'),now()-interval '1 hour');
set local role anon;
do $check$
begin
 begin perform public.np_claim_owner(repeat('a',64)); raise exception 'Anonymous activation allowed';
 exception when insufficient_privilege then null; end;
end; $check$;
reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub','66666666-6666-4666-8666-666666666666',true);
do $check$
begin
 begin perform public.np_claim_owner(repeat('a',64)); raise exception 'Unverified email activation allowed';
 exception when insufficient_privilege then null; end;
end; $check$;
reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub','44444444-4444-4444-8444-444444444444',true);
do $check$
begin
 begin perform public.np_claim_owner(repeat('b',64)); raise exception 'Expired code accepted';
 exception when invalid_authorization_specification then null; end;
 begin perform public.np_claim_owner(repeat('c',64)); raise exception 'Unknown code accepted';
 exception when invalid_authorization_specification then null; end;
 if public.np_claim_owner(repeat('a',64))<>'44444444-4444-4444-8444-444444444444'::uuid then
  raise exception 'Owner activation failed'; end if;
 if (select count(*) from public.app_members where active)<>1 then raise exception 'Owner membership missing'; end if;
end; $check$;
reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub','55555555-5555-4555-8555-555555555555',true);
do $check$
begin
 begin perform public.np_claim_owner(repeat('a',64)); raise exception 'Activation code reused';
 exception when insufficient_privilege or invalid_authorization_specification then null; end;
 begin perform count(*) from np_private.owner_setup_tokens; raise exception 'Private setup tokens readable';
 exception when insufficient_privilege then null; end;
end; $check$;
reset role;
rollback;
