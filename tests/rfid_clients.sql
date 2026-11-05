-- Synthetic multi-client imports. Every change is rolled back.
begin;
insert into auth.users(id) values('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
insert into public.app_members(user_id) values('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
insert into public.rf_stations(code,name,kind,slot_count) values('multi-dirty','Tunnel test','sporco',null),('multi-clean-a','Armadio A','pulito',90),('multi-clean-b','Armadio B','pulito',90);
insert into public.np_import_batches(id,archive,kind,source_key,file_name,status,imported_at) values
 ('10000000-0000-4000-8000-000000000001','ospiti','persone','multi-a-people','synthetic','ready','2020-01-01'),
 ('10000000-0000-4000-8000-000000000002','ospiti','tag','multi-a-old','synthetic','ready','2020-01-01'),
 ('10000000-0000-4000-8000-000000000003','ospiti','persone','multi-b-people','synthetic','ready','2021-01-01'),
 ('10000000-0000-4000-8000-000000000004','ospiti','tag','multi-b-tags','synthetic','ready','2021-01-01'),
 ('10000000-0000-4000-8000-000000000005','ospiti','tag','multi-a-current','synthetic','ready','2022-01-01'),
 ('10000000-0000-4000-8000-000000000006','ospiti','tag','multi-unbound','synthetic','ready','2029-01-01'),
 ('10000000-0000-4000-8000-000000000007','ospiti','tag','multi-b-collision','synthetic','ready','2023-01-01');
insert into public.np_source_records(batch_id,source_row,external_person_id,person_name_key,tag_id,raw_json) values
 ('10000000-0000-4000-8000-000000000001',1,'same-id','DEMO|OMONIMO',null,'{"Cognome":"DEMO","Nome":"OMONIMO","Area":"NORD","Piano":"1"}'),
 ('10000000-0000-4000-8000-000000000002',1,'same-id','DEMO|OMONIMO','AAAA0001','{"Cognome":"DEMO","Nome":"OMONIMO","Area":"NORD","Piano":"1","Classe merceologica":"VECCHIO"}'),
 ('10000000-0000-4000-8000-000000000003',1,'same-id','DEMO|OMONIMO',null,'{"Cognome":"DEMO","Nome":"OMONIMO","Area":"NORD","Piano":"1"}'),
 ('10000000-0000-4000-8000-000000000004',1,'same-id','DEMO|OMONIMO','BBBB0001','{"Cognome":"DEMO","Nome":"OMONIMO","Area":"NORD","Piano":"1","Classe merceologica":"B"}'),
 ('10000000-0000-4000-8000-000000000005',1,'same-id','DEMO|OMONIMO','AAAA0001','{"Cognome":"DEMO","Nome":"OMONIMO","Area":"NORD","Piano":"1","Classe merceologica":"AGGIORNATO"}'),
 ('10000000-0000-4000-8000-000000000006',1,'same-id','DEMO|OMONIMO','CCCC0001','{"Cognome":"DEMO","Nome":"OMONIMO","Area":"NORD","Piano":"1"}'),
 ('10000000-0000-4000-8000-000000000007',1,'same-id','DEMO|OMONIMO','BBBB0001','{"Cognome":"DEMO","Nome":"OMONIMO","Area":"NORD","Piano":"1"}'),
 ('10000000-0000-4000-8000-000000000007',2,'same-id','DEMO|OMONIMO','AAAA0001','{"Cognome":"DEMO","Nome":"OMONIMO","Area":"NORD","Piano":"1"}');
set local role anon;
do $$begin
 begin perform public.rf_register_client(gen_random_uuid(),'Forbidden','Site');raise exception 'Anonymous registers client';exception when insufficient_privilege then null;end;
 begin perform public.rf_bind_import(gen_random_uuid(),gen_random_uuid());raise exception 'Anonymous maps import';exception when insufficient_privilege then null;end;
end$$;
reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',true);
do $$begin
 begin perform public.rf_register_client(gen_random_uuid(),'Forbidden','Site');raise exception 'Non-member registers client';exception when insufficient_privilege then null;end;
 begin perform public.rf_bind_import(gen_random_uuid(),gen_random_uuid());raise exception 'Non-member maps import';exception when insufficient_privilege then null;end;
end$$;
select set_config('request.jwt.claim.sub','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',true);
do $$declare a uuid='cccccccc-cccc-4ccc-8ccc-cccccccccccc';b uuid='dddddddd-dddd-4ddd-8ddd-dddddddddddd';station uuid;ca uuid;cb uuid;ds uuid=gen_random_uuid();sa uuid=gen_random_uuid();sb uuid=gen_random_uuid();v jsonb;expected_person bigint;begin
 perform public.rf_register_client(a,'Cliente A','Sede A');perform public.rf_register_client(a,'Cliente A','Sede A');
 perform public.rf_register_client(b,'Cliente B','Sede B');
 insert into public.np_location_versions(archive,source_department,source_floor,revision,department,floor,reason,recorded_by) values('ospiti','NORD','1',1,'NORD CORRETTO','2','Correzione solo cliente A',auth.uid());
 begin perform public.rf_register_client(a,'Changed','Sede A');raise exception 'Client UUID reused';exception when raise_exception then if sqlerrm='Client UUID reused' then raise;end if;end;
 begin perform public.rf_register_client(gen_random_uuid(),'cliente a','sede a');raise exception 'Duplicate named client';exception when unique_violation then null;end;
 select id into station from public.rf_stations where code='multi-dirty';
 begin perform public.rf_start_session(ds,station,a,'ospiti');raise exception 'Unconfigured client starts';exception when raise_exception then if sqlerrm='Unconfigured client starts' then raise;end if;end;
 perform public.rf_bind_import('10000000-0000-4000-8000-000000000001',a,true);
 perform public.rf_bind_import('10000000-0000-4000-8000-000000000002',a);
 perform public.rf_bind_import('10000000-0000-4000-8000-000000000003',b);
 perform public.rf_bind_import('10000000-0000-4000-8000-000000000004',b);
 v=public.rf_bind_import('10000000-0000-4000-8000-000000000005',a,true);
 if (v->>'records')::integer<>1 then raise exception 'Import mapping wrong';end if;
 perform public.rf_bind_import('10000000-0000-4000-8000-000000000005',a,true);
 begin perform public.rf_bind_import('10000000-0000-4000-8000-000000000005',b);raise exception 'Import reassigned';exception when raise_exception then if sqlerrm='Import reassigned' then raise;end if;end;
 if (select count(*) from public.rf_catalogue_records where kind='tag' and client_id in(a,b))<>2 then raise exception 'New client hides other client or old versions duplicate';end if;
 if not exists(select 1 from public.rf_catalogue_records where client_id=a and article='AGGIORNATO') then raise exception 'Client latest import not selected';end if;
 if not exists(select 1 from public.rf_catalogue_records where client_id=a and department='NORD CORRETTO') or not exists(select 1 from public.rf_catalogue_records where client_id=b and department='NORD') then raise exception 'Pilot corrections leak across client imports';end if;
 if exists(select 1 from public.rf_catalogue_records where tag_id='CCCC0001') then raise exception 'Unbound import inferred';end if;
 perform public.rf_start_session(ds,station,a,'ospiti');
 -- One client per tunnel session: retries preserve it; switching client must close first.
 perform public.rf_start_session(ds,station,a,'ospiti');
 begin perform public.rf_start_session(ds,station,b,'ospiti');raise exception 'Existing session changed client';exception when raise_exception then if sqlerrm='Existing session changed client' then raise;end if;end;
 begin perform public.rf_start_session(gen_random_uuid(),station,b,'ospiti');raise exception 'Tunnel accepted concurrent clients';exception when raise_exception then if sqlerrm='Tunnel accepted concurrent clients' then raise;end if;end;
 if (select client_id from public.rf_sessions where id=ds)<>a then raise exception 'Rejected switch changed session client';end if;
 -- Idempotent repeats are safe, but changing the catalogue during a session is refused.
 perform public.rf_bind_import('10000000-0000-4000-8000-000000000005',a,true);
 begin perform public.rf_bind_import('10000000-0000-4000-8000-000000000006',a);raise exception 'Active client imports changed';exception when raise_exception then if sqlerrm='Active client imports changed' then raise;end if;end;
 v=public.rf_read_batch(ds,jsonb_build_array(jsonb_build_object('id',gen_random_uuid(),'tag','AAAA0001'),jsonb_build_object('id',gen_random_uuid(),'tag','BBBB0001'),jsonb_build_object('id',gen_random_uuid(),'tag','CCCC0001')));
 if v->0->>'outcome'<>'accettata' or v->1->>'outcome'<>'cliente_diverso' or v->2->>'outcome'<>'tag_sconosciuto' then raise exception 'Client detection wrong: %',v;end if;
 if v->1->'snapshot'->>'client'<>'Cliente B' or v->1->'snapshot'->>'site'<>'Sede B' then raise exception 'Actual wrong client missing';end if;
 if (select count(*) from public.rf_movements where session_id=ds)<>1 then raise exception 'Wrong or unknown client moved';end if;
 perform public.rf_close_session(ds,1,'Capi estranei separati per verifica');
 select id into ca from public.rf_stations where code='multi-clean-a';select id into cb from public.rf_stations where code='multi-clean-b';
 perform public.rf_start_session(sa,ca,a,'ospiti','collaudo',true);perform public.rf_start_session(sb,cb,b,'ospiti','collaudo',true);
 v=public.rf_read_batch(sa,jsonb_build_array(jsonb_build_object('id',gen_random_uuid(),'tag','AAAA0001')));
 select id into expected_person from public.np_source_records where batch_id='10000000-0000-4000-8000-000000000001';
 if v->0->>'outcome'<>'accettata' or (v->0->>'person_source_id')::bigint<>expected_person then raise exception 'Homonym from another client merged or blocked';end if;
 v=public.rf_read_batch(sb,jsonb_build_array(jsonb_build_object('id',gen_random_uuid(),'tag','BBBB0001')));
 select id into expected_person from public.np_source_records where batch_id='10000000-0000-4000-8000-000000000003';
 if v->0->>'outcome'<>'accettata' or (v->0->>'person_source_id')::bigint<>expected_person then raise exception 'Second client person lookup wrong';end if;
 perform public.rf_close_session(sa,1);perform public.rf_close_session(sb,1);
 if not exists(select 1 from public.rf_label_jobs where session_id=sa and payload->>'client'='Cliente A' and payload->>'site'='Sede A') or not exists(select 1 from public.rf_label_jobs where session_id=sb and payload->>'client'='Cliente B' and payload->>'site'='Sede B') then raise exception 'Bag labels mix clients';end if;
 perform public.rf_bind_import('10000000-0000-4000-8000-000000000007',b);
 ds=gen_random_uuid();perform public.rf_start_session(ds,station,a,'ospiti');
 v=public.rf_read_batch(ds,jsonb_build_array(jsonb_build_object('id',gen_random_uuid(),'tag','AAAA0001')));
 if v->0->>'outcome'<>'tag_ambiguo' or (select count(*) from public.rf_movements where session_id=ds)<>0 then raise exception 'Same EPC on two clients guessed from session';end if;
 perform public.rf_close_session(ds,0,'Tag duplicato da correggere');
 begin delete from public.rf_import_clients;raise exception 'Browser deletes import ownership';exception when insufficient_privilege then null;end;
end$$;
select set_config('request.jwt.claim.sub','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',true);
do $$begin if exists(select 1 from public.rf_import_clients) or exists(select 1 from public.rf_catalogue_records) then raise exception 'Non-member sees client catalogue';end if;end$$;
reset role;
rollback;
