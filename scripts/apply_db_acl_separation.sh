#!/usr/bin/env bash
# scripts/apply_db_acl_separation.sh
# Generates 0600 role credentials and enforces P1 #2 PostgreSQL ACL separation on 127.0.0.1:5432.

set -euo pipefail

ENV_DIR="${HOME}/.config/quantumflex"
ENV_FILE="${ENV_DIR}/db_roles.env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="${SCRIPT_DIR}/sql/002_enforce_writer_verifier_acl.sql"

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
DB_ADMIN_USER="${DB_ADMIN_USER:-rocky}"
TARGET_DATABASES=("${DB_NAME:-telemetry}")

mkdir -p "${ENV_DIR}"
chmod 700 "${ENV_DIR}"

if [[ ! -f "${ENV_FILE}" ]]; then
    WRITER_PASS="$(openssl rand -hex 32)"
    VERIFIER_PASS="$(openssl rand -hex 32)"
    cat > "${ENV_FILE}" <<EOF
# QuantumFlex P1 #2 Separated Database Role Credentials (mode 0600)
QF_DB_HOST=${DB_HOST}
QF_DB_PORT=${DB_PORT}
QF_WRITER_DB_USER=qf_writer
QF_WRITER_DB_PASS=${WRITER_PASS}
QF_VERIFIER_DB_USER=qf_verifier
QF_VERIFIER_DB_PASS=${VERIFIER_PASS}
EOF
    chmod 600 "${ENV_FILE}"
    echo "[+] Generated isolated role credentials at ${ENV_FILE} (0600)"
else
    chmod 600 "${ENV_FILE}"
    echo "[*] Using existing role credentials at ${ENV_FILE}"
fi

# shellcheck disable=SC1090
source "${ENV_FILE}"

for db in "${TARGET_DATABASES[@]}"; do
    echo "[*] Applying 002_enforce_writer_verifier_acl.sql to database '${db}'..."

    # Check if native psql is available, else use podman exec into amara-matrix container
    if command -v psql >/dev/null 2>&1; then
        psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_ADMIN_USER}" -d "${db}" \
            -v ON_ERROR_STOP=1 \
            -v qf_writer_password="'${QF_WRITER_DB_PASS}'" \
            -v qf_verifier_password="'${QF_VERIFIER_DB_PASS}'" \
            -f "${SQL_FILE}"
    elif command -v podman >/dev/null 2>&1 && podman ps -q -f name=amara-matrix | grep -q .; then
        podman exec -i amara-matrix psql -U "${DB_ADMIN_USER}" -d "${db}" \
            -v ON_ERROR_STOP=1 \
            -v qf_writer_password="'${QF_WRITER_DB_PASS}'" \
            -v qf_verifier_password="'${QF_VERIFIER_DB_PASS}'" < "${SQL_FILE}"
    else
        echo "[!] Error: Neither native psql nor running amara-matrix podman container found." >&2
        exit 1
    fi
    echo "[+] ACL separation successfully enforced on '${db}'."
done
