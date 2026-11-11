begin;
insert into auth.users(id) values('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
insert into public.app_members(user_id) values('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
insert into public.np_import_batches(id,archive,kind,source_key,file_name,status) values
 ('11111111-1111-4111-8111-111111111111','ospiti','persone','rf-fixture','synthetic','ready'),
 ('22222222-2222-4222-8222-222222222222','ospiti','tag','rf-fixture','synthetic','ready'),
 ('33333333-3333-4333-8333-333333333333','divise','tag','rf-fixture','synthetic','ready'),
 ('44444444-4444-4444-8444-444444444444','ospiti','tag','rf-other-fixture','synthetic','ready');
insert into public.np_source_records(batch_id,source_row,person_name_key,raw_json) values
 ('11111111-1111-4111-8111-111111111111',2,'DEMO|UNO','{"Cognome":"DEMO","Nome":"UNO","Area":"PAPAVERO","Piano":"1"}'),
 ('11111111-1111-4111-8111-111111111111',3,'DEMO|DUE','{"Cognome":"DEMO","Nome":"DUE","Area":"PAPAVERO","Piano":"1"}'),
 ('11111111-1111-4111-8111-111111111111',4,'DEMO|TRE','{"Cognome":"DEMO","Nome":"TRE","Area":"PAPAVERO","Piano":"1"}'),
 ('11111111-1111-4111-8111-111111111111',5,'OMONIMO|DEMO','{"Cognome":"OMONIMO","Nome":"DEMO","Area":"PAPAVERO","Piano":"1"}'),
 ('11111111-1111-4111-8111-111111111111',6,'OMONIMO|DEMO','{"Cognome":"OMONIMO","Nome":"DEMO","Area":"PAPAVERO","Piano":"1"}');
insert into public.np_source_records(batch_id,source_row,person_name_key,tag_id,raw_json) values
 ('22222222-2222-4222-8222-222222222222',2,'DEMO|UNO','0000000000000001','{"Cognome":"DEMO","Nome":"UNO","Area":"PAPAVERO","Classe merceologica":"Maglia"}'),
 ('22222222-2222-4222-8222-222222222222',3,'DEMO|UNO','0000000000000002','{"Cognome":"DEMO","Nome":"UNO","Area":"PAPAVERO","Classe merceologica":"Pantalone"}'),
 ('22222222-2222-4222-8222-222222222222',4,'DEMO|DUE','0000000000000003','{"Cognome":"DEMO","Nome":"DUE","Area":"PAPAVERO","Classe merceologica":"Maglia"}'),
 ('22222222-2222-4222-8222-222222222222',5,'DEMO|TRE','0000000000000004','{"Cognome":"DEMO","Nome":"TRE","Area":"PAPAVERO","Classe merceologica":"Maglia"}'),
 ('33333333-3333-4333-8333-333333333333',2,'OPERATORE|DEMO','0000000000000005','{"Cognome":"OPERATORE","Nome":"DEMO","Area":"OSS"}'),
 ('44444444-4444-4444-8444-444444444444',6,'ALTRO|CLIENTE','0000000000000006','{"Cognome":"ALTRO","Nome":"CLIENTE","Area":"PAPAVERO"}'),
 ('22222222-2222-4222-8222-222222222222',7,'OMONIMO|DEMO','0000000000000007','{"Cognome":"OMONIMO","Nome":"DEMO","Area":"PAPAVERO"}');
insert into public.rf_clients(id,name,site) values('cccccccc-cccc-4ccc-8ccc-cccccccccccc','Cliente test','Sede test'),('dddddddd-dddd-4ddd-8ddd-dddddddddddd','Altro cliente test','Altra sede');
insert into public.rf_stations(code,name,kind,slot_count) values('test-sporco','Tunnel test','sporco',null),('test-pulito-01','Armadio test 1','pulito',90),('test-pulito-02','Armadio test 2','pulito',90);
insert into public.rf_import_clients(batch_id,client_id,recorded_by)
 select id,case when id='44444444-4444-4444-8444-444444444444' then 'dddddddd-dddd-4ddd-8ddd-dddddddddddd'::uuid else 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'::uuid end,'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa' from public.np_import_batches where source_key in ('rf-fixture','rf-other-fixture');
insert into public.rf_bindings(source_record_id,client_id) select r.id,m.client_id from public.np_source_records r join public.rf_import_clients m on m.batch_id=r.batch_id;
set local role anon;
do $$begin begin perform public.rf_start_session(gen_random_uuid(),gen_random_uuid(),gen_random_uuid(),'ospiti');raise exception 'Anonymous opens station';exception when insufficient_privilege then null;end;end$$;
reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',true);
do $$begin
 begin perform public.rf_start_session(gen_random_uuid(),gen_random_uuid(),gen_random_uuid(),'ospiti');raise exception 'Non-member starts station';exception when insufficient_privilege then null;end;
 if exists(select 1 from public.rf_bindings) then raise exception 'Non-member sees tag bindings';end if;
end$$;
select set_config('request.jwt.claim.sub','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',true);
do $$declare dirty uuid;clean uuid;second uuid;client uuid='cccccccc-cccc-4ccc-8ccc-cccccccccccc';ds uuid=gen_random_uuid();cs uuid=gen_random_uuid();other_session uuid=gen_random_uuid();events jsonb;v jsonb;event_id uuid=gen_random_uuid();job uuid;print_id uuid=gen_random_uuid();n integer;
begin
 select id into dirty from public.rf_stations where code='test-sporco';select id into clean from public.rf_stations where code='test-pulito-01';select id into second from public.rf_stations where code='test-pulito-02';
 begin perform public.rf_start_session(gen_random_uuid(),dirty,client,'ospiti','produzione');raise exception 'Unverified hardware enabled';exception when raise_exception then if sqlerrm='Unverified hardware enabled' then raise;end if;end;
 perform public.rf_start_session(ds,dirty,client,'ospiti');
 events=jsonb_build_array(jsonb_build_object('id',event_id,'tag','0000000000000001'),jsonb_build_object('id',gen_random_uuid(),'tag','0000000000000001'),jsonb_build_object('id',gen_random_uuid(),'tag','FFFFFFFFFFFFFFFF'),jsonb_build_object('id',gen_random_uuid(),'tag','0000000000000006'),jsonb_build_object('id',gen_random_uuid(),'tag','0000000000000005'),jsonb_build_object('id',gen_random_uuid(),'tag','bad-tag'));
 v=public.rf_read_batch(ds,events);
 if v->0->>'outcome'<>'accettata' or v->1->>'outcome'<>'ripetizione' or v->2->>'outcome'<>'tag_sconosciuto' or v->3->>'outcome'<>'cliente_diverso' or v->4->>'outcome'<>'archivio_diverso' or v->5->>'outcome'<>'tag_non_valido' then raise exception 'Wrong dirty classifications: %',v;end if;
 perform public.rf_read_batch(ds,events);
 if (select count(*) from public.rf_reads where session_id=ds)<>6 or (select count(*) from public.rf_movements where session_id=ds)<>1 then raise exception 'Retransmission duplicated observations/movements';end if;
 begin perform public.rf_close_session(ds,2,'Separate');raise exception 'Stale closure count';exception when raise_exception then if sqlerrm='Stale closure count' then raise;end if;end;
 begin perform public.rf_close_session(ds,1);raise exception 'Ignored unresolved garments';exception when raise_exception then if sqlerrm='Ignored unresolved garments' then raise;end if;end;
 perform public.rf_close_session(ds,1,'Capi segnalati separati per verifica');
 v=public.rf_read_batch(ds,jsonb_build_array(jsonb_build_object('id',gen_random_uuid(),'tag','0000000000000002')));if v->0->>'outcome'<>'sessione_chiusa' then raise exception 'Late observation accepted';end if;
 perform public.rf_configure_slots(clean,2);
 begin perform public.rf_start_session(cs,clean,client,'ospiti');raise exception 'Missing empty confirmation';exception when raise_exception then if sqlerrm='Missing empty confirmation' then raise;end if;end;
 perform public.rf_start_session(cs,clean,client,'ospiti','collaudo',true);
 v=public.rf_read_batch(cs,jsonb_build_array(jsonb_build_object('id',gen_random_uuid(),'tag','0000000000000001')));if (v->0->>'slot')::integer<>1 then raise exception 'No first slot';end if;
 v=public.rf_read_batch(cs,jsonb_build_array(jsonb_build_object('id',gen_random_uuid(),'tag','0000000000000001')));if v->0->>'outcome'<>'ripetizione' or (v->0->>'slot')::integer<>1 then raise exception 'Duplicate loses same slot';end if;
 v=public.rf_read_batch(cs,jsonb_build_array(jsonb_build_object('id',gen_random_uuid(),'tag','0000000000000002')));if (v->0->>'slot')::integer<>1 then raise exception 'Same person allocated two slots';end if;
 perform public.rf_configure_slots(second,2);perform public.rf_start_session(other_session,second,client,'ospiti','collaudo',true);
 v=public.rf_read_batch(other_session,jsonb_build_array(jsonb_build_object('id',gen_random_uuid(),'tag','0000000000000001')));if v->0->>'outcome'<>'altro_armadio' then raise exception 'Same garment reserved by two cabinets';end if;
 v=public.rf_read_batch(cs,jsonb_build_array(jsonb_build_object('id',gen_random_uuid(),'tag','0000000000000003')));if (v->0->>'slot')::integer<>2 then raise exception 'Second person slot';end if;
 v=public.rf_read_batch(cs,jsonb_build_array(jsonb_build_object('id',gen_random_uuid(),'tag','0000000000000004')));if v->0->>'outcome'<>'armadio_pieno' then raise exception 'Full cabinet did not stop allocation';end if;
 v=public.rf_read_batch(cs,jsonb_build_array(jsonb_build_object('id',gen_random_uuid(),'tag','0000000000000007')));if v->0->>'outcome'<>'identita_da_verificare' then raise exception 'Homonyms silently merged';end if;
 if exists(select 1 from public.rf_movements where session_id=cs) then raise exception 'Clean departure created before closure';end if;
 v=public.rf_close_session(cs,3,'Capi segnalati tenuti fuori dalle buste');
 if (v->>'movements')::integer<>3 or (v->>'labels')::integer<>2 then raise exception 'Closure output wrong';end if;
 perform public.rf_close_session(cs,0);
 if (select count(*) from public.rf_movements where session_id=cs)<>3 or (select count(*) from public.rf_label_jobs where session_id=cs)<>2 then raise exception 'Closure retry duplicated movements/labels';end if;
 if (select count(*) from public.rf_movements where session_id=cs and direction='ricomposizione')<>3 then raise exception 'Clean closure must record ricomposizione, never uscita';end if;
 if exists (select 1 from public.rf_movements where session_id=cs and direction='uscita_pulito') then raise exception 'Shipment falsely recorded at cabinet closure';end if;
 if exists(select 1 from public.rf_reservations where session_id=cs) then raise exception 'Reservations leaked after closure';end if;
 if not exists(select 1 from public.rf_label_jobs where session_id=cs and slot=1 and (payload->>'count')::integer=2 and payload->'subject'->>'name'='DEMO UNO' and payload->>'mode'='collaudo') then raise exception 'Label payload not tied to closed bag';end if;
 select id into job from public.rf_label_jobs where session_id=cs limit 1;
 perform public.rf_print_attempt(print_id,job,'richiesta');perform public.rf_print_attempt(print_id,job,'richiesta');
 perform public.rf_print_attempt(gen_random_uuid(),job,'errore','Stampante offline');
 perform public.rf_print_attempt(gen_random_uuid(),job,'richiesta','Ristampa');
 perform public.rf_print_attempt(gen_random_uuid(),job,'confermata','Conferma manuale dopo verifica visiva');
 if (select count(*) from public.rf_movements where session_id=cs)<>3 then raise exception 'Reprint created duplicate departure';end if;
 if not exists(select 1 from public.rf_label_status where id=job and print_status='confermata') then raise exception 'Print status not auditable';end if;
 begin update public.rf_reads set outcome='accettata';raise exception 'Browser rewrites observation';exception when insufficient_privilege then null;end;
 begin delete from public.rf_movements;raise exception 'Browser deletes movements';exception when insufficient_privilege then null;end;
end$$;
do $$declare station uuid;session uuid='eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee';v jsonb;page jsonb;begin
 select id into station from public.rf_stations where code='test-sporco';
 perform public.rf_start_session(session,station,'cccccccc-cccc-4ccc-8ccc-cccccccccccc','tutti');
 v=public.rf_read_batch(session,jsonb_build_array(jsonb_build_object('id',gen_random_uuid(),'tag','0000000000000001'),jsonb_build_object('id',gen_random_uuid(),'tag','0000000000000005')));
 if v->0->>'outcome'<>'accettata' or v->1->>'outcome'<>'accettata' then raise exception 'Mixed client session rejects one archive';end if;
 select jsonb_agg(jsonb_build_object('id',gen_random_uuid(),'tag','FFFFFFFFFFFFFFFF')) into v from generate_series(1,130);
 perform public.rf_read_batch(session,v);
 page=public.rf_snapshot(session);
 if jsonb_array_length(page->'reads')<>100 or (page->'counts'->>'reads')::integer<>132 then raise exception 'Read audit truncated';end if;
 page=public.rf_snapshot(session,(page->'reads'->99->>'seq')::bigint);
 if jsonb_array_length(page->'reads')<>32 then raise exception 'Older reads inaccessible';end if;
 perform public.rf_close_session(session,2,'Letture di collaudo separate');
end$$;
reset role;
update public.app_members set active=false where user_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
set local role authenticated;
do $$begin if exists(select 1 from public.rf_reads) then raise exception 'Revoked member sees reads';end if;
 begin perform public.rf_read_batch(gen_random_uuid(),'[]');raise exception 'Revoked member sends observations';exception when insufficient_privilege then null;end;
end$$;
reset role;
rollback;
