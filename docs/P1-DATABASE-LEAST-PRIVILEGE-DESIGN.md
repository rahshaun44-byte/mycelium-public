# P1 database least-privilege and context-engine design

## Scope and evidence boundary

This is a design-only deliverable. No database connection, role provisioning, migration, key generation, permission change, or service restart was performed. Actual PostgreSQL catalog state, ownership, grants, RLS flags, and table contents remain **UNVERIFIED**.

The design is based on source in `src/db_credentials.py`, `mcp_layer/qf_bot/context_store.py`, `scripts/sql/002_enforce_writer_verifier_acl.sql`, `scripts/sql/003_qf_device_authorization_and_audit.sql`, `scripts/sql/005_qf_context_engine.sql`, and `scripts/apply_db_acl_separation.sh`, plus their focused tests.

## Current observed readiness

- The configured API service has a `DASHBOARD_API_KEY`; its value was not read. No outside-repository API callers were confirmed, so activation of P0 route authentication remains gated.
- The protected DB role file exists with mode `0600` and defines writer/verifier credentials, but does not define `QF_CONTEXT_DB_USER` or `QF_CONTEXT_DB_PASS`.
- `context_store.py` uses `DatabaseRole.CONTEXT`, signs short-lived owner claims with `QF_CONTEXT_IDENTITY_HMAC_KEY`, and encrypts message contents before persistence. The migration validates those claims inside PostgreSQL and RLS obtains owner identity from a protected backend/transaction table, not a caller-set GUC. The configured encryption-key path is `~/.config/quantumflex/context.key`; key existence, permissions, backup, and recovery are unverified.
- A read-only catalog query against the configured `telemetry` database found no `qf_context` role and no `qf_context_*` tables. This is measured for that database only.
- The context-engine migration has not been applied. Passing unit tests proves source contracts only, not database readiness.

## Latest read-only grant observations

The following are directly observed on the inspected PostgreSQL database, not proposed permissions:

| Principal | Observed privileges on `quantum_telemetry_channel` | Observed privileges on `telemetry_log` |
|---|---|---|
| `qf_writer` | INSERT | INSERT |
| `qf_verifier` | SELECT | SELECT |
| `api_node_service` | SELECT, INSERT | No direct grant reported |
| `ghostnode` | SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER | SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER |

No memberships among the inspected application roles were returned. The inspected roles had no superuser, createdb, createrole, or bypass-RLS attributes. These results do not cover every relation, schema, function, database, or inherited/default privilege. Do not infer the full role boundary from this targeted query.

`api_node_service`'s SELECT grant and `ghostnode`'s broad mutation privileges should be mapped to actual SQL call sites and service ownership before any change. Avoid changing grants based only on role names or this partial catalog query. Build a full read-only ACL/default-privilege/ownership snapshot and test the exact service queries in staging first.

## Intended privilege matrix

| Principal | Telemetry ledger | Device authorization / governance audit | Context conversations, messages, access | Context security audit |
|---|---|---|---|---|
| `qf_writer` | INSERT only on explicitly listed telemetry tables; sequence access only as required | Existing migration grants must be reviewed per caller; do not infer append-only behavior from role name | No privileges | No privileges |
| `qf_verifier` | SELECT only on explicitly listed telemetry tables | SELECT only where required by verified consumers | No privileges | No privileges |
| `qf_context` | No privileges | No privileges unless a separately reviewed, narrow use case requires them | SELECT/INSERT/UPDATE/DELETE only on the three context tables, constrained by verified owner and principal authorization | INSERT only; no UPDATE/DELETE |
| application / migration owner | No shared runtime use | No shared runtime use | DDL only through separately approved migration identity; runtime must not connect as owner or superuser | DDL only as approved |

These are intended grants, not a statement of current live grants. The `qf_context` runtime also needs a verified non-owner role with `NOBYPASSRLS`; table ownership and `FORCE ROW LEVEL SECURITY` behavior must be checked in staging.

## Migration risks that must be resolved first

1. The legacy `content_sha256` removal is isolated in `006_drop_context_content_digest.sql` and is not part of automatic provisioning. It is destructive: review/back up any target database and authorize that migration separately.
2. Device authorization grants are intentionally not changed by the context-schema migration. Any new device operation requires its own separate authorization review and approval.
3. `apply_db_acl_separation.sh` is not a narrow context-only installer. It may create or change credentials, changes the role credential file, then applies migrations 002, 003, and 005. Migration 002 revokes existing privileges across tables and sequences in `public`; migration 003 grants writer UPDATE access to device authorization. Do not run this bundled script as a context-only deployment.
4. The source now uses a database-verified HMAC claim with a 60-second expiry and a one-time nonce; `qf_context` cannot read or change the signing key or protected transaction identity rows. The migration has not been applied, so this boundary is not active in the database. Verify the migration owner and test the direct-GUC and cross-owner integration cases before treating it as deployed.
5. The migration now enables and forces RLS, and transfers table/function ownership to the migration role. Verify those catalog properties and the runtime role's `NOBYPASSRLS` attribute after applying it. Runtime connections must never use a table owner or superuser.
6. `qf_context` receives DELETE rights on conversation, message, and access rows. The application currently performs physical deletes after checking a legal hold. Review retention, audit, and recovery requirements before enabling this behavior.
7. The context audit table has no RLS policy in the migration. INSERT-only runtime grants are helpful, but owner/administrator access, retention, and audit tamper evidence need separate treatment.

## Staged implementation and acceptance gates

1. **Catalog baseline, read-only:** In a staging clone, record database/schema owners, role attributes, memberships, table/sequence/function ACLs, RLS and FORCE RLS flags, existing column data, row counts, and default privileges. Do not print credential values.
2. **Migration split:** The context provisioning migration excludes the `content_sha256` drop, device authorization updates, and unrelated writer/verifier ACL changes. The digest cleanup is a separate manual migration; apply it only after data-impact review and backup.
3. **Credential handling:** Generate or provision the context password and encryption key only after explicit approval. Store them in protected files with owner-only permissions; verify backup/recovery and rotation procedures. Do not place values in source, shell history, reports, or chat.
4. **Grant review:** Apply only the matrix above in staging. Confirm role separation, no role memberships that inherit broader access, no schema CREATE, least-privilege sequence access, and no telemetry access for `qf_context`.
5. **RLS and identity tests:** Run `tests/test_context_rls_postgres.py` against an isolated database provisioned with the migration and a `qf_context` login. Prove that owner A cannot read owner B's records and that direct `qf.owner_id` changes grant no access. Also test forged/expired/replayed claims, wrong device, revoked grant, legal hold, and unauthorized writes before production use.
6. **Crypto and recovery tests:** Verify encryption-at-rest, authenticated decryption, key-version handling, key-file mode/ownership, backup restore, and failure-closed behavior when the key is absent or invalid.
7. **Caller and durability tests:** Run the existing unit suite and isolated integration tests for transaction rollback, concurrent append sequence allocation, grant revocation, and deletion/audit behavior. Do not run probes against production data.
8. **Separate approvals:** Review the migration diff, exact grants, backup/restore evidence, and staging results. Database migration, permission changes, credential/key provisioning, and service rollout each require their own explicit approval.

## Rollback and recovery

- Before a future approved migration, take and validate a restorable database backup and capture the catalog baseline.
- If staging acceptance fails, stop context-engine callers and revoke or disable only the newly provisioned `qf_context` login/grants. Do not drop context tables or delete data as a rollback shortcut.
- Roll back application code independently from the schema. Preserve encrypted rows and the encryption key until an approved retention/deletion decision is made.
- Do not reverse pre-existing writer/verifier grants or device authorization without a before-state catalog snapshot. The bundled ACL script is not a safe generic rollback.
- Record migration ID, approval reference, before/after catalog evidence, tests, and rollback outcome in the commissioning ledger.

## Stripe test-mode preparation (not configured)

The live Command Center process did not have these variables. No test configuration has been written:

- `STRIPE_WEBHOOK_SECRET`: test endpoint signing secret from the operator-controlled Stripe test configuration.
- `STRIPE_PAYMENT_LINK_ID`: exact test-mode payment link.
- `STRIPE_EXPECTED_AMOUNT_CENTS` and `STRIPE_EXPECTED_CURRENCY`: exact expected test checkout total and currency.
- `STRIPE_EXPECTED_LIVE_MODE=false`.

Provision values only through a separately approved protected service configuration; do not paste them into source, shell commands, or chat. Confirm endpoint URL and event subscription in the Stripe dashboard, then perform an explicitly approved non-value test flow. No provider request or transaction was made as part of this design.
