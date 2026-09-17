# Ghost Node privilege review

Date: 2026-09-16. Read-only inspection; no privileges or services changed.

## Conclusion

The inspected workload needs specific database and operating-system authorities.
It does not demonstrate a requirement for a continuously superuser PostgreSQL
runtime identity. Earlier success with superuser is consistent with missing
ownership/schema grants being bypassed. Revocation alone is not a complete
migration: maintenance responsibilities must still have an authorized execution
path.

## Live evidence

Connected with the repository's configured `ghostnode` credentials to database
`telemetry`, PostgreSQL 15.19, using read-only transactions and statement timeouts.
No application records or secrets were printed.

- `ghostnode`: SUPERUSER=false, CREATEDB=false, CREATEROLE=false, BYPASSRLS=false.
- No other role memberships were returned for the connected role.
- Schema `public`: USAGE=true, CREATE=false.
- Effective SELECT/INSERT/UPDATE/DELETE permissions were all true on
  `memory_logs`, `integrity_registry`, `invariant_audit_ledger`,
  `sentinel_ledger`, `suspicious_urls`, and `telemetry_log`.
- These tables are owned by `amara_admin`, except `suspicious_urls`, owned by
  `ghostnode`. Row-level security was disabled on the inspected tables.
- USAGE on the eight listed public sequences was true.
- `memory_logs`, `sentinel_ledger`, and `telemetry_log` are ordinary tables
  (`relkind=r`), not partitioned parents (`relkind=p`). No actual matching date
  partitions were returned by the inspected name patterns.
- `amara_admin` is non-superuser but retains BYPASSRLS. This is a separate role
  observation; it does not give Ghost Node inherited powers.

## Workload-to-authority mapping

| Work | Required authority | PostgreSQL superuser required? |
|---|---|---|
| Read integrity baseline and lockout state | SELECT on specific registry columns/table | No |
| Append telemetry and invariant audit | INSERT and required sequence access | No |
| Update URL queue and lockout status | Scoped UPDATE plus necessary reads | No |
| Delete expired memory rows | SELECT for predicates and DELETE on target | No |
| Provision/drop partitions | Correct partitioned schema plus controlled ownership/DDL authority | No, but ordinary DML grants are insufficient |
| Pause/unpause rootless containers | Authority of the owning OS account/runtime | Database privilege is unrelated |
| TPM writes and system-level response | Appropriate device/policy/OS authority for the exact operation | Database privilege is unrelated |

The source comment in `sentinel/neurogenesis.py` equating DELETE with a superuser
requirement is incorrect. Its current implementation actually does more than
DELETE: it creates an audit table, drops partitions, and creates future
partitions. These are legitimate maintenance functions, but they need a distinct
authority boundary.

PostgreSQL documents that ALTER/DROP ownership rights are not ordinary grantable
table privileges. A controlled owner role or carefully restricted maintenance
interface can supply these powers without cluster superuser.
[PostgreSQL GRANT](https://www.postgresql.org/docs/15/sql-grant.html).

## Runtime observations and limits

The active user service definitions point to this repository's
`sentinel/sentinel.py` and `sentinel/neurogenesis.py`. Their timers are scheduled;
their latest recorded exits were status 0. However, the scripts catch important
exceptions and can exit successfully after work fails. Available filtered
journals did not establish successful partition work. No pruning, pause,
unpause, TPM write, or schema mutation was executed during this review.

The current configured database cannot support the partition workflow as written
without schema preparation. Restoring superuser alone would not convert the
ordinary tables into partitioned parents. We cannot attribute every maintenance
issue to privilege revocation without a before/after execution history.

The repository's permissions auditor is insufficient as proof: it targets a
particular container and suppresses SQL failures with `|| true`, allowing empty
output from a failed query to be interpreted as “no application superusers.” This
review used a successful direct catalog query instead.

## Recommended authority arrangement

1. Keep Ghost Node's runtime database role NOSUPERUSER.
2. Preserve the specific permissions needed for its authorized routine work.
3. Place partition creation, migration and retirement behind a dedicated,
   non-superuser maintenance identity that owns only the intended objects. Do not
   give the ingestion process credentials or role membership that recover that
   authority. A restricted owner-executed function is another option only with
   fixed targets, controlled search_path, no arbitrary SQL and restricted EXECUTE.
4. Resolve the ordinary-table/partitioned-table design before testing retention.
5. Separate ordinary retention from immutable evidence: Ghost Node currently can
   UPDATE and DELETE `sentinel_ledger` and `invariant_audit_ledger`. Revoking
   superuser has not made those tables append-only for this role.
6. Verify actions and side effects, not just service exit status: successful
   insertion, authorized expiry, bounded partition lifecycle, failed forbidden
   mutation, and unchanged protected audit records.

Keep emergency cluster administration as a separately controlled operator
capability. If a future operation truly requires superuser, document that exact
operation and give a narrow administrative component responsibility for it.

This conclusion applies to the inspected code and database connection. Other
deployments or a historical Ghost Node packet-sniffer may have different OS
capability requirements and were not certified by this review.
