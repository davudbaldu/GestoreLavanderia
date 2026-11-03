\set ON_ERROR_STOP on
-- Test-only Supabase Auth stand-in. Do not deploy this file to Supabase.
create role anon nologin;
create role authenticated nologin;
create schema auth;
create table auth.users (id uuid primary key, email_confirmed_at timestamptz);
create function auth.uid() returns uuid language sql stable as $$
 select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid
$$;
revoke all on schema auth from public;
grant usage on schema auth to authenticated;
grant execute on function auth.uid() to authenticated;
