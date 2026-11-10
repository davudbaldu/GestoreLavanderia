# Private database acquisition

The migration in 001_private_imports.sql prepares PostgreSQL/Supabase for versioned NewPod acquisition. It contains no operational data.

## Access boundaries

- Anonymous callers have no access to tables, views, or summaries.
- A signed-in account must also be explicitly enrolled as an active owner in app_members.
- Accounts cannot enroll themselves, change membership, or write acquisition records from the browser.
- Only privileged administration performs imports.
- Source rows remain hidden until their batch is marked ready.
- Latest-batch views and the summary function obey the caller's row-level permissions.

The initial role is owner only. Client, driver, production and subcontractor access requires additional scoped policies before those roles are enabled.

## Data contract

For each of the six reports:
1. Create a staging batch with archive, report type, stable source version key and original filename.
2. Insert every source row once, preserving source row number and original fields in raw_json.
3. Preserve CLIEID and tag identifiers as text. Scope external person identities by archive.
4. Store date-only movements in date columns; do not invent timestamps.
5. Record anomalies in np_import_issues.
6. Reconcile counts and representative records with the source.
7. Mark the batch ready only after successful verification.

The archive, kind and source_key uniqueness constraint rejects a duplicate batch. A new source version is a new batch; older data remains available.

## Activation

A connected Supabase account and selected project are required before deployment or data loading. This repository has no project URL, API key, owner identity or operational records.

After deployment, configure Supabase Auth and allowed site/redirect URLs. Enroll the owner's authenticated user ID through privileged administration. Do not expose an automatic first-user enrollment endpoint.

Only the publishable project key may be used by a browser client. Secret and service-role keys must never enter the public repository, frontend bundles or browser storage.

## Verification

GitHub Actions applies the schema to PostgreSQL 16 with synthetic records. It verifies anonymous denial, non-member denial, owner access, hidden staging rows, immediate revocation and absence of browser-side privilege escalation.

The auth schema and UUIDs in tests/database_bootstrap.sql and tests/database_permissions.sql are test fixtures, not real accounts or credentials.

## Operational preparation module

`operations_preparations.sql` adds two configured Emmaus routes and an append-only
preparation ledger. Hosted migration name: `operational_preparations`. Source
imports are untouched. Each accepted revision records server time and the
current authenticated owner. There is no browser UPDATE or DELETE privilege.

An invoker trigger validates every insert, including direct REST requests. It
serializes revisions by preparation ID, rejects stale writes and skipped states,
and keeps quantities frozen outside preparation. Reopening a ready preparation
creates a new version. Issued DDTs, document numbering and role-specific customer,
subcontractor, driver and production access are not enabled by this migration.

`tests/operations_permissions.sql` checks anonymous/non-member denial, owner
writes, audit metadata, invalid quantities, stale versions, state transitions,
reopening, immutable history and revocation. It runs in a transaction and rolls
back all fixtures. The workflow runs it against PostgreSQL 16.

## Catalogue and location quality

Apply `catalogue_quality.sql`, then `catalogue_search_projection.sql`. The former
adds an invoker/RLS-protected normalized view, paginated catalogue/report RPCs and
an append-only location mapping ledger. The latter stores generated search
projections without changing raw fields and fetches originals on demand.

`seed_emmaus_locations.sql` is an owner-only, idempotent configuration operation
for the floor mapping explicitly confirmed by the user. It applies only to
recognizable guest departments or clearly swapped department/floor fields.
Unknown placeholders and generic numeric departments are not guessed. The
hosted seed created 51 rules; all 70,244 source rows and their raw-data checksum
were preserved. No original source update is part of this workflow.

The catalogue/quality SQL tests run in one session with the seed between the
before/after assertions, then roll back. They cover non-member denial, stock and
generic separation, surname substring collisions, aliases, swapped fields,
leading-zero tags, exact-name drill-down, aggregate dotations, event-period
semantics, stale corrections and revocation.

## Native read sessions

`rfid_sessions.sql` adds owner-gated station commands and read-only audit tables.
All mutations are private, explicitly authorized SECURITY DEFINER handlers behind
public invoker wrappers. They validate the actual authenticated subject against
active application membership. Browser roles receive no direct write grants.

Observations preserve raw tag text, normalized tag text, reader metadata,
observation time, receipt time, outcome and transport event UUID. Replaying an
identical event UUID returns its previous result. Reusing it for changed input
fails. Distinct repeated observations remain visible without duplicating the
accepted garment or movement in the same session.

Dirty sessions record entries at accepted reads. Clean sessions reserve one slot
per unambiguous source subject and keep departures pending until an atomic close.
Closing creates cabinet recomposition movements and immutable bag-label payloads once; printer errors
and reprints have a separate audit and never create a second departure. Physical
printing is not asserted by generating a print job or opening its preview.

Stations start with hardware_ready=false, so production sessions cannot be opened.
Test sessions are marked collaudo and must remain separate from production
reporting. The initial binding seed refuses to infer client ownership if more
than one client/site exists. It never changes source rows or imported history.
