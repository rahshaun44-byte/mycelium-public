#!/usr/bin/env bash
# ==============================================================================
# QuantumFlex Deployed Permissions and Process Isolation Auditor
# ==============================================================================

set -euo pipefail

FAILURES=0
WARNINGS=0

echo "═══════════════════════════════════════════════════════════════════"
echo "        QUANTUMFLEX DEPLOYED PERMISSIONS & PROCESS AUDITOR         "
echo "═══════════════════════════════════════════════════════════════════"

log_pass() {
    echo -e "  [PASS] $1"
}

log_fail() {
    echo -e "  [FAIL] $1" >&2
    FAILURES=$((FAILURES + 1))
}

log_warn() {
    echo -e "  [WARN] $1"
    WARNINGS=$((WARNINGS + 1))
}

# 1. Network Socket Bindings (Loopback Isolation)
echo -e "
[1] Verifying Network Socket Bindings (Local Loopback Only)..."

APP_PORTS=(5432 8000 8001 8080 8181 9000 9444 11434)
for port in "${APP_PORTS[@]}"; do
    NON_LOOPBACK=$(ss -tlnH "sport = :$port" 2>/dev/null | awk '{print $4}' | grep -vE '^(127\.|\[::1\])' || true)
    if [[ -n "$NON_LOOPBACK" ]]; then
        log_fail "Port :$port is bound to non-loopback address: $NON_LOOPBACK"
    else
        IS_LISTENING=$(ss -tlnH "sport = :$port" 2>/dev/null | awk '{print $4}' || true)
        if [[ -n "$IS_LISTENING" ]]; then
            log_pass "Port :$port strictly bound to loopback ($IS_LISTENING)"
        else
            log_warn "Port :$port is currently not active"
        fi
    fi
done

# 2. Filesystem Permissions (Least Privilege & Secrets Custody)
echo -e "
[2] Auditing Sensitive Filesystem Permissions..."

SHARDS_DIR="$HOME/qfx-shards"
if [[ -d "$SHARDS_DIR" ]]; then
    DIR_PERM=$(stat -c "%a" "$SHARDS_DIR")
    if [[ "$DIR_PERM" =~ ^[75][0][0]$ ]]; then
        log_pass "Shards directory $SHARDS_DIR permission mode is $DIR_PERM"
    else
        log_fail "Shards directory $SHARDS_DIR has permissive mode: $DIR_PERM (expected 0700)"
    fi

    for shard in "$SHARDS_DIR"/shard_*.txt; do
        if [[ -f "$shard" ]]; then
            SHARD_PERM=$(stat -c "%a" "$shard")
            if [[ "$SHARD_PERM" =~ ^[46][0][0]$ ]]; then
                log_pass "$(basename "$shard") permission mode is $SHARD_PERM"
            else
                log_fail "$(basename "$shard") has permissive mode: $SHARD_PERM (expected 0600/0400)"
            fi
        fi
    done
else
    log_warn "Shards directory $SHARDS_DIR does not exist on host"
fi

MTLS_DIR="$HOME/.local/share/quantum-flex-mycelium/mtls"
if [[ -d "$MTLS_DIR" ]]; then
    for keyfile in "$MTLS_DIR"/*.key; do
        if [[ -f "$keyfile" ]]; then
            KEY_PERM=$(stat -L -c "%a" "$keyfile")
            if [[ "$KEY_PERM" =~ ^[46][0][0]$ ]]; then
                log_pass "$(basename "$keyfile") private key mode is $KEY_PERM"
            else
                log_fail "$(basename "$keyfile") private key has permissive mode: $KEY_PERM (expected 0600/0400)"
            fi
        fi
    done
fi

# 3. Process Execution Identity & Rootless Isolation
echo -e "
[3] Auditing Process Execution Identity..."

CURRENT_UID=$(id -u)
if [[ "$CURRENT_UID" -eq 0 ]]; then
    log_fail "Auditor is executing as root! Services must run unprivileged."
else
    log_pass "Auditor executing as unprivileged user: $(id -un) (UID: $CURRENT_UID)"
fi

SERVICES=(amara-dashboard api-node athena-node immune-daemon opa-immune qflex-mcp quantum-flex-engine-mycelium)
for s in "${SERVICES[@]}"; do
    if systemctl --user is-active --quiet "$s.service" 2>/dev/null; then
        PID=$(systemctl --user show -p MainPID --value "$s.service")
        PROC_UID=$(ps -o uid= -p "$PID" 2>/dev/null | tr -d ' ' || echo "UNKNOWN")
        if [[ "$PROC_UID" == "$CURRENT_UID" ]]; then
            log_pass "$s.service is running under user UID $PROC_UID (PID: $PID)"
        else
            log_fail "$s.service is running under unexpected UID $PROC_UID"
        fi
    else
        log_warn "$s.service is inactive"
    fi
done

# 4. Database Privilege & Superuser Separation
echo -e "
[4] Verifying PostgreSQL Role Privileges & Ledger Immutability..."

if command -v podman >/dev/null 2>&1 && podman ps --format '{{.Names}}' | grep -q 'amara-matrix'; then
    # 4a. Verify no unauthorized superuser roles exist
    if SUPERUSERS=$(podman exec -i amara-matrix psql -U amara_admin -d postgres -v ON_ERROR_STOP=1 -tAc         "SELECT rolname FROM pg_roles WHERE rolsuper = true AND rolname NOT IN ('rahshaunchambers', 'postgres');"); then
        if [[ -n "$SUPERUSERS" ]]; then
            log_fail "Found unauthorized application superusers: $SUPERUSERS"
        else
            log_pass "Application roles (ghostnode, amara_admin, quantum_sentinel, sentinel_service) are NOSUPERUSER"
        fi
    else
        log_fail "Failed to execute superuser check against PostgreSQL catalog"
    fi

    # 4b. Verify ghostnode specifically has no elevated catalog attributes
    if GHOST_ATTRS=$(podman exec -i amara-matrix psql -U amara_admin -d postgres -v ON_ERROR_STOP=1 -tAc         "SELECT rolsuper || '|' || rolcreaterole || '|' || rolcreatedb || '|' || rolbypassrls FROM pg_roles WHERE rolname = 'ghostnode';"); then
        if [[ "$GHOST_ATTRS" == "false|false|false|false" || "$GHOST_ATTRS" == "f|f|f|f" ]]; then
            log_pass "ghostnode attributes verified: NOSUPERUSER, NOCREATEROLE, NOCREATEDB, NOBYPASSRLS"
        else
            log_fail "ghostnode has unexpected privileges: $GHOST_ATTRS (expected f|f|f|f)"
        fi
    else
        log_fail "Failed to query ghostnode role attributes from catalog"
    fi

    # 4c. Verify append-only immutability on audit ledgers in telemetry DB
    if PRIVS=$(podman exec -i amara-matrix psql -U amara_admin -d telemetry -v ON_ERROR_STOP=1 -tAc "
        SELECT
            has_table_privilege('ghostnode', 'public.sentinel_ledger', 'UPDATE') || '|' ||
            has_table_privilege('ghostnode', 'public.sentinel_ledger', 'DELETE') || '|' ||
            has_table_privilege('ghostnode', 'public.sentinel_ledger', 'INSERT') || '|' ||
            has_table_privilege('ghostnode', 'public.invariant_audit_ledger', 'UPDATE') || '|' ||
            has_table_privilege('ghostnode', 'public.invariant_audit_ledger', 'DELETE') || '|' ||
            has_table_privilege('ghostnode', 'public.invariant_audit_ledger', 'INSERT');"); then
        if [[ "$PRIVS" == "false|false|true|false|false|true" || "$PRIVS" == "f|f|t|f|f|t" ]]; then
            log_pass "Audit ledgers immutability verified: ghostnode has INSERT/SELECT only (UPDATE=f, DELETE=f)"
        else
            log_fail "Audit ledgers violate immutability for ghostnode: $PRIVS (expected f|f|t|f|f|t)"
        fi
    else
        log_fail "Failed to query audit ledger table privileges in telemetry DB"
    fi
else
    log_fail "amara-matrix podman container is not running; cannot verify live SQL security bounds"
fi

echo "═══════════════════════════════════════════════════════════════════"
echo "AUDIT SUMMARY: $FAILURES failures, $WARNINGS warnings"
echo "═══════════════════════════════════════════════════════════════════"

if [[ $FAILURES -gt 0 ]]; then
    exit 1
fi
exit 0
