# AMARA/ATHENA task continuity

## Current assessment (2026-11-05)

- Native PostgreSQL 15.19 (`127.0.0.1:5432`, database `telemetry`) is accepting connections. The existing `task_queue` and `memory_logs` tables are present; the queue had zero rows during inspection. No dedicated checkpoint table existed.
- AMARA dashboard, ATHENA API, swarm worker, and the evidence engine were running. `witness.service` and `ghost-sink.service` were inactive. No service was restarted or reconfigured.
- Existing PostgreSQL task rows already retain the task payload, state, and result. The worker reclaims expired `RUNNING` tasks after its 120-second lease. AMARA/IaC actions remain deliberately unwired and must not be reported as successful execution.

## Persistence design

PostgreSQL `task_queue` remains the source of truth; this adds no tables, grants, elevated database role, or cross-database credential sharing. `mcp_layer/task_checkpoint.py` snapshots committed task state to `data/task_checkpoints/<id>.json` using atomic replacement, `fsync`, directory mode `0700`, and file mode `0600`. The local snapshot contains status/timestamps and SHA-256 digests of the payload/result only—not the directive, payload, result, or credentials. Recovery always compares against PostgreSQL and can rebuild a missing, invalid, or stale local snapshot. It does not execute or requeue work.

The controller checkpoints a task after enqueue. New worker processes checkpoint claim, completion, and release transitions best-effort; local mirror failures are logged and do not alter PostgreSQL task behavior. The already-running swarm worker was intentionally not restarted, so it will use these hooks only after a normal future process start. PostgreSQL and the recovery CLI remain available without that restart.

## Conversation access status

The source has a PostgreSQL-backed ContextStore, encrypted message storage, and signed-device plus `qf_device_authorization` checks for conversation operations. In addition to owner scoping, every conversation read, append, and delete is filtered by an explicit per-device `qf_context_access` grant. The creating device receives its initial grants; it can grant other device identities through `/api/conversations/{id}/access`. Owner identity is now passed as a short-lived HMAC-signed claim; the migration validates it in PostgreSQL and RLS reads the resulting protected backend/transaction identity. A caller-set `qf.owner_id` setting is not used as authorization. This source change is not active until the migration is applied and verified.

The mobile bootstrap reports client authentication separately from current device authorization. The key filename aliases `pixel-11-pro` and `qfx-pixel` resolve to the same enrolled device identity. A dedicated hard-stop operation still requires its separate policy permission. The plaintext SHA-256 side-channel field was removed; Fernet authenticated encryption protects message integrity. The reader fails closed when it encounters an encryption-key version it does not support, but key rotation and recovery are not implemented.

The running QF-Bot process has not been restarted and still uses the pre-persistence implementation; its in-memory conversations are lost on restart. The new source is not active until the database migration, `qf_context` role credentials, HMAC identity key, and operator-provisioned encryption key are installed through the approved deployment path. Migration 005 does not change device operation grants; those require a separate authorization approval. No service restart or live permission change has occurred.

This phase has not yet established uniform authorization on every QF-Bot API route. The new operation checks cover conversation read/append/delete and the hard-stop path; remaining APIs still require a route-by-route capability pass before shared-context production access.

## Approved retention policy for the future Context API

The selected default is owner-controlled indefinite retention for conversations and task records, with explicit owner deletion. Checkpoints, summaries, and embeddings must be deleted with their parent; temporary files should expire after seven days; security access logs should be restricted and retained for one year; deleted data may remain in backups for at most 90 days. A legal hold blocks deletion. Credentials and secrets must not be retained as ordinary memory.

The approved key source for the future API is an operator-provisioned 0600 local key file; no TPM protection is claimed. `scripts/create_context_key.py` creates that key once and refuses to overwrite an existing one. The encryption module fails closed if the key is missing, malformed, symlinked, or accessible beyond its owner.

The PostgreSQL schema is in `scripts/sql/005_qf_context_engine.sql`. It defines encrypted message storage, owner/resource access metadata, legal-hold fields, forced owner RLS, and a one-year security-audit expiry. It no longer drops the legacy message digest or grants new device operations; those destructive/authorization changes are excluded from provisioning. Per-conversation grants are still required for resource access. `scripts/apply_db_acl_separation.sh` reapplies the device authorization/audit grants after the broad writer/verifier ACL migration, then applies the Context schema. The migration has not been applied and that script has not been run.

The source-level Context API encrypts messages and refuses several common credential patterns and `RESTRICTED` data classification; this is heuristic filtering, not a guarantee that credentials can never be stored. The UI clients do not yet render the stored history or expose conversation selection, the task queue is not yet linked to conversations, and deletion does not yet propagate to task checkpoints or other memory stores. Key rotation, embedding/cache propagation, scheduled security-log expiry, and backup expiry are also not implemented. Operational state, approved project knowledge, and security logs must remain separate stores with separate authorization and deletion paths. No context key has been generated.

## Verification and recovery

Run a clean, synthetic end-to-end verification (it uses a non-runnable `CONTINUITY_TEST` row, starts a fresh recovery process, verifies PostgreSQL plus the local file, then removes only its uniquely tagged row/file):

```bash
/home/quant/mycelium/venv/bin/python3 /home/quant/mycelium/scripts/task_checkpoint.py self-test
```

For an existing task, checkpoint then recover without displaying its content:

```bash
/home/quant/mycelium/venv/bin/python3 /home/quant/mycelium/scripts/task_checkpoint.py checkpoint TASK_ID
/home/quant/mycelium/venv/bin/python3 /home/quant/mycelium/scripts/task_checkpoint.py recover TASK_ID
```

A successful `recover` reports `source=filesystem-verified-against-postgresql`; if the local copy is missing or disagrees, it reports a PostgreSQL restore/reconciliation instead. These commands do not restart services or dispatch a task.
