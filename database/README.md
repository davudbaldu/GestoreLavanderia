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
