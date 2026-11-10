do $$declare v jsonb;begin
 if not exists(select 1 from public.np_catalogue_records where surname='BATTAGLIA' and kind='persone' and floor='1' and source_floor='3' and raw_json->>'Piano'='3') then raise exception 'Original floor lost or wrong correction';end if;
 if not exists(select 1 from public.np_catalogue_records where surname='ALTRA' and department='GIRASOLE' and floor='3') then raise exception 'Swapped fields not corrected';end if;
 v=public.np_catalogue('ospiti','dotazioni',p_person_key=>'BATTAGLIA|DEMO');
 if (v->>'total')::integer<>1 or (v->'rows'->0->>'garments')::integer<>2 or (v->'rows'->0->'articles'->0->>'quantity')::integer<>2 then raise exception 'Dotation aggregation wrong';end if;
 v=public.np_catalogue('ospiti','tag',p_department=>'MIMOSA',p_floor=>'1');if (v->>'total')::integer<>2 then raise exception 'Canonical filters do not find aliases';end if;
 if (public.np_catalogue('ospiti','tag',p_search=>'000123')->>'total')::integer<>1 then raise exception 'Leading-zero tag search';end if;
 begin insert into public.np_location_versions select archive,source_department,source_floor,revision,department,floor,'stale edit',recorded_by,recorded_at from public.np_latest_locations limit 1;raise exception 'Stale correction accepted';exception when serialization_failure then null;end;
 begin update public.np_location_versions set floor='8';raise exception 'Correction history overwritten';exception when insufficient_privilege then null;end;
 begin delete from public.np_source_records;raise exception 'Sources deletable';exception when insufficient_privilege then null;end;
end$$;
reset role;
update public.app_members set active=false where user_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa';
set local role authenticated;
do $$begin if (public.np_catalogue('ospiti')->>'total')::integer<>0 then raise exception 'Revoked member still reads catalogue';end if;end$$;
reset role;
rollback;
