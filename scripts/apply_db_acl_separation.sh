#!/usr/bin/env bash
# scripts/apply_db_acl_separation.sh
# Generates 0600 role credentials and applies the isolated QuantumFlex database roles.

set -euo pipefail

ENV_DIR="${HOME}/.config/quantumflex"
ENV_FILE="${ENV_DIR}/db_roles.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="${SCRIPT_DIR}/sql/002_enforce_writer_verifier_acl.sql"
AUTH_SQL_FILE="${SCRIPT_DIR}/sql/003_qf_device_authorization_and_audit.sql"
CONTEXT_SQL_FILE="${SCRIPT_DIR}/sql/005_qf_context_engine.sql"

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
DB_ADMIN_USER="${DB_ADMIN_USER:-rocky}"
TARGET_DATABASES=("${DB_NAME:-telemetry}")

mkdir -p "${ENV_DIR}"
chmod 700 "${ENV_DIR}"

if [[ ! -f "${ENV_FILE}" ]]; then
    WRITER_PASS="$(openssl rand -hex 32)"
    VERIFIER_PASS="$(openssl rand -hex 32)"
    CONTEXT_PASS="$(openssl rand -hex 32)"
    CONTEXT_IDENTITY_KEY="$(openssl rand -hex 32)"
    cat > "${ENV_FILE}" <<EOF
# QuantumFlex separated database role credentials (mode 0600)
QF_DB_HOST=${DB_HOST}
QF_DB_PORT=${DB_PORT}
QF_WRITER_DB_USER=qf_writer
QF_WRITER_DB_PASS=${WRITER_PASS}
QF_VERIFIER_DB_USER=qf_verifier
QF_VERIFIER_DB_PASS=${VERIFIER_PASS}
QF_CONTEXT_DB_USER=qf_context
QF_CONTEXT_DB_PASS=${CONTEXT_PASS}
QF_CONTEXT_IDENTITY_HMAC_KEY=${CONTEXT_IDENTITY_KEY}
EOF
    chmod 600 "${ENV_FILE}"
    echo "[+] Generated isolated role credentials at ${ENV_FILE} (0600)"
else
    chmod 600 "${ENV_FILE}"
    echo "[*] Using existing role credentials at ${ENV_FILE}"
    if ! grep -q '^QF_CONTEXT_DB_PASS=' "${ENV_FILE}"; then
        CONTEXT_PASS="$(openssl rand -hex 32)"
        if ! grep -q '^QF_CONTEXT_DB_USER=' "${ENV_FILE}"; then
            printf '\nQF_CONTEXT_DB_USER=qf_context\n' >> "${ENV_FILE}"
        fi
        printf 'QF_CONTEXT_DB_PASS=%s\n' "${CONTEXT_PASS}" >> "${ENV_FILE}"
    fi
    if ! grep -q '^QF_CONTEXT_IDENTITY_HMAC_KEY=' "${ENV_FILE}"; then
        CONTEXT_IDENTITY_KEY="$(openssl rand -hex 32)"
        printf 'QF_CONTEXT_IDENTITY_HMAC_KEY=%s\n' "${CONTEXT_IDENTITY_KEY}" >> "${ENV_FILE}"
    fi
fi

# shellcheck disable=SC1090
source "${ENV_FILE}"

if [[ ! "${QF_WRITER_DB_PASS}" =~ ^[0-9a-fA-F]{64}$ ]] ||
   [[ ! "${QF_VERIFIER_DB_PASS}" =~ ^[0-9a-fA-F]{64}$ ]] ||
   [[ ! "${QF_CONTEXT_DB_PASS}" =~ ^[0-9a-fA-F]{64}$ ]] ||
   [[ ! "${QF_CONTEXT_IDENTITY_HMAC_KEY}" =~ ^[0-9a-fA-F]{64}$ ]]; then
    echo "[!] Role passwords and context identity key must be 32-byte hexadecimal values." >&2
    exit 1
fi

apply_role_acl_sql() {
    local sql_file="$1"
    shift
    {
        printf "\\set qf_writer_password '%s'\n" "${QF_WRITER_DB_PASS}"
        printf "\\set qf_verifier_password '%s'\n" "${QF_VERIFIER_DB_PASS}"
        cat "${sql_file}"
    } | "$@" -v ON_ERROR_STOP=1
}

apply_context_sql() {
    {
        printf "\\set qf_context_password '%s'\n" "${QF_CONTEXT_DB_PASS}"
        printf "\\set qf_context_identity_hmac_key '%s'\n" "${QF_CONTEXT_IDENTITY_HMAC_KEY}"
        cat "${CONTEXT_SQL_FILE}"
    } | "$@" -v ON_ERROR_STOP=1
}

apply_plain_sql() {
    local sql_file="$1"
    shift
    "$@" -v ON_ERROR_STOP=1 < "${sql_file}"
}

for db in "${TARGET_DATABASES[@]}"; do
    echo "[*] Applying 002_enforce_writer_verifier_acl.sql to database '${db}'..."

    # Check if native psql is available, else use podman exec into amara-matrix container
    if command -v psql >/dev/null 2>&1; then
        apply_role_acl_sql "${SQL_FILE}" \
            psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_ADMIN_USER}" -d "${db}"
        apply_plain_sql "${AUTH_SQL_FILE}" \
            psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_ADMIN_USER}" -d "${db}"
        apply_context_sql \
            psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_ADMIN_USER}" -d "${db}"
    elif command -v podman >/dev/null 2>&1 && podman ps -q -f name=amara-matrix | grep -q .; then
        apply_role_acl_sql "${SQL_FILE}" \
            podman exec -i amara-matrix psql -U "${DB_ADMIN_USER}" -d "${db}"
        apply_plain_sql "${AUTH_SQL_FILE}" \
            podman exec -i amara-matrix psql -U "${DB_ADMIN_USER}" -d "${db}"
        apply_context_sql \
            podman exec -i amara-matrix psql -U "${DB_ADMIN_USER}" -d "${db}"
    else
        echo "[!] Error: Neither native psql nor running amara-matrix podman container found." >&2
        exit 1
    fi
    echo "[+] ACL separation successfully enforced on '${db}'."
done
