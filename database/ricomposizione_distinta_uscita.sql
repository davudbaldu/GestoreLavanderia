-- Introduce distinct cabinet recomposition vs physical dispatch. No history rewrite.
begin;
alter table public.rf_movements drop constraint rf_movements_direction_check;
alter table public.rf_movements add constraint rf_movements_direction_check
  check (direction in ('ingresso_sporco','ricomposizione','uscita_pulito'));
create or replace function rf_private.close_session(p_session uuid,p_expected integer,p_note text default '') returns jsonb
 language plpgsql security definer set search_path='' as $rfclose$
declare s public.rf_sessions;station public.rf_stations;n integer;problems integer;closed_time timestamptz;
begin
 perform rf_private.authorize();select * into s from public.rf_sessions where id=p_session for update;if not found then raise exception 'Sessione non disponibile.';end if;
 select * into station from public.rf_stations where id=s.station_id;
 if s.status='aperta' then
  select count(*) into n from public.rf_reads where session_id=p_session and outcome='accettata';
  if n<>p_expected then raise exception 'Sono arrivate altre letture: aggiorna e controlla il conteggio prima di chiudere.';end if;
  if station.kind='pulito' and n=0 then raise exception 'Non ci sono capi da chiudere nell’armadio.';end if;
  select count(*) into problems from public.rf_reads where session_id=p_session and outcome not in ('accettata','ripetizione');
  if problems>0 and length(btrim(coalesce(p_note,'')))<3 then raise exception 'Indica come sono stati gestiti i capi segnalati prima di chiudere.';end if;
  if length(p_note)>1000 then raise exception 'Nota di chiusura troppo lunga.';end if;
  closed_time=clock_timestamp();
  update public.rf_sessions set status='chiusa',closed_by=auth.uid(),closed_at=closed_time,closing_note=coalesce(p_note,'') where id=p_session;
  if station.kind='pulito' then
   insert into public.rf_movements(session_id,read_id,source_record_id,direction,occurred_at)
    select p_session,id,source_record_id,'ricomposizione',closed_time from public.rf_reads where session_id=p_session and outcome='accettata';
   insert into public.rf_label_jobs(session_id,slot,payload)
    select p_session,a.slot,jsonb_build_object('mode',s.mode,'session',s.id,'station',station.name,'client_id',s.client_id,'client',c.name,'site',c.site,'archive',coalesce(a.snapshot->>'archive',s.archive),'closed_at',closed_time,'slot',a.slot,'subject',a.snapshot,'count',count(r.id),'garments',jsonb_agg(jsonb_build_object('tag',r.tag,'article',r.snapshot->>'article') order by r.seq))
    from public.rf_allocations a join public.rf_reads r on r.session_id=a.session_id and r.slot=a.slot and r.outcome='accettata'
    join public.rf_clients c on c.id=s.client_id where a.session_id=p_session group by a.slot,a.snapshot,c.name,c.site;
   delete from public.rf_reservations where session_id=p_session;
  end if;
 end if;
 return jsonb_build_object('session',p_session,'status','chiusa','movements',(select count(*) from public.rf_movements where session_id=p_session),'labels',(select count(*) from public.rf_label_jobs where session_id=p_session));
end$rfclose$;


comment on column public.rf_movements.direction is
 'ingresso_sporco = dirty input; ricomposizione = cabinet close; uscita_pulito = actual shipment (not yet wired to a DDT).';
commit;
