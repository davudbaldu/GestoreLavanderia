-- Initial pilot only. Explicitly refuse to infer source ownership when more
-- than one client/site exists. Future imports require a scoped import mapping.
do $$declare client uuid;begin
 if (select count(*) from public.rf_clients)<>1 then raise exception 'Associa esplicitamente gli archivi al cliente: sono presenti più clienti.';end if;
 select id into client from public.rf_clients;
 insert into public.rf_bindings(source_record_id,client_id)
 select r.id,client from public.np_source_records r join public.np_latest_batches b on b.id=r.batch_id where b.kind='tag'
 on conflict(source_record_id) do nothing;
end$$;
