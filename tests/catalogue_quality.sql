begin;
insert into auth.users(id) values('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'),('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb');
insert into public.app_members(user_id) values('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
insert into public.np_import_batches(id,archive,kind,source_key,file_name,status) values
 ('11111111-1111-4111-8111-111111111111','ospiti','persone','fixture','fixture','ready'),
 ('22222222-2222-4222-8222-222222222222','ospiti','tag','fixture','fixture','ready'),
 ('33333333-3333-4333-8333-333333333333','ospiti','movimenti','fixture','fixture','ready'),
 ('44444444-4444-4444-8444-444444444444','divise','persone','fixture','fixture','ready');
insert into public.np_source_records(batch_id,source_row,person_name_key,raw_json) values
 ('11111111-1111-4111-8111-111111111111',2,'BATTAGLIA|DEMO','{"Cognome":"BATTAGLIA","Nome":"DEMO","Area":"MIMOSA","Piano":"3"}'),
 ('11111111-1111-4111-8111-111111111111',3,'PIANO|1°','{"Cognome":"PIANO","Nome":"1°","Area":"X","Piano":"X"}'),
 ('11111111-1111-4111-8111-111111111111',4,'ALTRA|PERSONA','{"Cognome":"ALTRA","Nome":"PERSONA","Area":"3","Piano":"GIRASOLE"}'),
 ('44444444-4444-4444-8444-444444444444',2,'M|SCORTA','{"Cognome":"M","Nome":"SCORTA","Area":"x","Piano":".X"}');
insert into public.np_source_records(batch_id,source_row,person_name_key,tag_id,raw_json) values
 ('22222222-2222-4222-8222-222222222222',2,'BATTAGLIA|DEMO','000123','{"Cognome":"BATTAGLIA","Nome":"DEMO","Area":"MIMOSE","Classe merceologica":"Pantalone"}'),
 ('22222222-2222-4222-8222-222222222222',3,'BATTAGLIA|DEMO','000124','{"Cognome":"BATTAGLIA","Nome":"DEMO","Area":"MIMOSA","Classe merceologica":"Pantalone"}');
insert into public.np_source_records(batch_id,source_row,person_name_key,tag_id,incoming_date,outgoing_date,raw_json) values
 ('33333333-3333-4333-8333-333333333333',2,'BATTAGLIA|DEMO','000123','2026-06-02','2026-06-03','{"Cognome":"BATTAGLIA","Nome":"DEMO","Reparto":"MIMOSA","Piano":"3","Classe Merceologica":"Pantalone"}');
set local role anon;
do $$begin begin perform public.np_catalogue('ospiti');raise exception 'Anonymous catalogue access';exception when insufficient_privilege then null;end;end$$;
reset role;
set local role authenticated;
select set_config('request.jwt.claim.sub','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',true);
do $$begin
 if (public.np_catalogue('ospiti')->>'total')::integer<>0 then raise exception 'Non-member data leak';end if;
 if jsonb_array_length(public.np_quality('ospiti'))<>0 then raise exception 'Non-member quality leak';end if;
end$$;
select set_config('request.jwt.claim.sub','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',true);
do $$declare v jsonb;begin
 v=public.np_catalogue('ospiti','persone',p_category=>'persona');
 if (v->>'total')::integer<>2 then raise exception 'Real surname BATTAGLIA classified as generic';end if;
 v=public.np_catalogue('divise','persone',p_category=>'scorta');if (v->>'total')::integer<>1 then raise exception 'Staff stocks mixed with people';end if;
 if np_private.clean_floor('.2')<>'2' or np_private.clean_floor('2.')<>'2' then raise exception 'Floor punctuation';end if;
 v=public.np_catalogue('ospiti','report',p_from=>'2026-06-02',p_to=>'2026-06-02');
 if (v->'summary'->>'entries')::integer<>1 or (v->'summary'->>'exits')::integer<>0 then raise exception 'Date range counts paired exit outside range';end if;
end$$;
