-- Run as an authenticated active owner, after catalogue_quality.sql.
-- These floor assignments were explicitly confirmed by the user.
-- No raw source row, person name, tag or historical assignment is changed.
with aliases(source,department,floor) as(values
 ('PAPAVERO','PAPAVERO','1'),('GERANIO','GERANIO','1'),('MIMOSA','MIMOSA','1'),('MIMOSE','MIMOSA','1'),
 ('CICLAMINO','CICLAMINO','2'),('CILCAMINO','CICLAMINO','2'),('CICLAMINI','CICLAMINO','2'),('ROSA','ROSA','2'),
 ('MARGHERITA','MARGHERITA','3'),('MARGHERITE','MARGHERITA','3'),('GIRASOLE','GIRASOLE','3'),('GIRAOLE','GIRASOLE','3'),('GIRASOLI','GIRASOLE','3')),
 pairs as(select distinct archive,source_department,source_floor from public.np_catalogue_records where archive='ospiti'),
 proposed as(
 select p.*,coalesce(a.department,swapped.department) as department,coalesce(a.floor,swapped.floor) as floor
 from pairs p left join aliases a on p.source_department=a.source
 left join aliases swapped on p.source_department ~ '^[0-9]+$' and p.source_floor=swapped.source
 )
insert into public.np_location_versions(archive,source_department,source_floor,revision,department,floor,reason,recorded_by)
select p.archive,p.source_department,p.source_floor,1,p.department,p.floor,
 'Reparti e piani Emmaus confermati dal proprietario; normalizzazione delle varianti di scrittura e dei campi invertiti.',auth.uid()
from proposed p where p.department is not null and not exists(select 1 from public.np_latest_locations l where l.archive=p.archive and l.source_department=p.source_department and l.source_floor=p.source_floor);
