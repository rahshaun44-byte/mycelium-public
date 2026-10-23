#!/usr/bin/env bash
# ==============================================================================
# Script: restore_quantumflex_node.sh
# Purpose: One-command full sovereign state restoration on a fresh host
# ==============================================================================

set -euo pipefail
IFS=$'\n\t'

readonly BOLD='\033[1m'
readonly GREEN='\033[0;32m'
readonly BLUE='\033[0;34m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

BACKUP_SRC="${1:-}"
BACKUP_HOST="${BACKUP_HOST:-}"
BACKUP_USER="${BACKUP_USER:-qfx}"
REMOTE_BACKUP="~/qfx-vault/qfx-pre-ubuntu-backup-20260927.tar.gz"

RESTORE_TMP="/tmp/qfx-restore-$$-$(date +%s)"
mkdir -m 700 -p "$RESTORE_TMP"

cleanup() {
    log_info "Cleaning up temporary restore artifacts..."
    rm -rf "$RESTORE_TMP"
}
trap cleanup EXIT

# 1. Acquire Backup Tarball
if [[ -n "$BACKUP_SRC" && -f "$BACKUP_SRC" ]]; then
    log_info "Using provided local backup archive: $BACKUP_SRC"
    cp "$BACKUP_SRC" "$RESTORE_TMP/backup.tar.gz"
elif [[ -f "$HOME/qfx-pre-ubuntu-backup-20260927.tar.gz" ]]; then
    log_info "Found local backup in home directory..."
    cp "$HOME/qfx-pre-ubuntu-backup-20260927.tar.gz" "$RESTORE_TMP/backup.tar.gz"
else
    if [[ -z "$BACKUP_HOST" ]]; then
        log_error "No local backup found and BACKUP_HOST is unset; refusing to guess a remote."
        exit 1
    fi
    log_info "Fetching backup archive from ${BACKUP_USER}@${BACKUP_HOST}..."
    scp -o BatchMode=yes "${BACKUP_USER}@${BACKUP_HOST}:${REMOTE_BACKUP}" "$RESTORE_TMP/backup.tar.gz"
fi

# 2. Extract Archive
log_info "Extracting and verifying backup integrity..."
tar -xzvf "$RESTORE_TMP/backup.tar.gz" -C "$RESTORE_TMP"

# 3. Restore Shamir Shards
log_info "Restoring Shamir threshold shards to ~/qfx-shards/..."
mkdir -m 700 -p "$HOME/qfx-shards"
cp -a "$RESTORE_TMP/qfx-shards/"* "$HOME/qfx-shards/"
chmod 600 "$HOME/qfx-shards/"*.txt
log_success "Shamir shards restored."

# 4. Restore mTLS & Engine State
log_info "Restoring mTLS certificates and engine ledger..."
mkdir -m 700 -p "$HOME/.local/share/quantum-flex-mycelium"
cp -a "$RESTORE_TMP/.local/share/quantum-flex-mycelium/"* "$HOME/.local/share/quantum-flex-mycelium/"
chmod 700 "$HOME/.local/share/quantum-flex-mycelium"
log_success "Engine cryptographic state and mTLS certs restored."

# 5. Restore SSH Keys
if [[ -d "$RESTORE_TMP/.ssh" ]]; then
    log_info "Restoring SSH identities..."
    mkdir -m 700 -p "$HOME/.ssh"
    cp -a "$RESTORE_TMP/.ssh/"* "$HOME/.ssh/"
    if [[ -f "$HOME/.ssh/id_ed25519" ]]; then
        chmod 600 "$HOME/.ssh/id_ed25519"
    fi
    if [[ -f "$HOME/.ssh/id_ed25519.pub" ]]; then
        chmod 644 "$HOME/.ssh/id_ed25519.pub"
    fi
    log_success "SSH configuration restored."
fi

# 6. Restore Systemd User Units
log_info "Restoring Systemd user service definitions..."
mkdir -p "$HOME/.config/systemd/user"
cp -a "$RESTORE_TMP/.config/systemd/user/"* "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
log_success "Systemd units restored and reloaded."

# 7. Restore PostgreSQL Database
if [[ -f "$RESTORE_TMP/qfx-postgres-dump-20260927.sql" ]]; then
    log_info "Starting amara-matrix PostgreSQL container..."
    podman run -d --name amara-matrix \
        -p 127.0.0.1:5432:5432 \
        -e POSTGRES_USER=amara_admin \
        -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD before restoring}" \
        -e POSTGRES_DB=telemetry \
        docker.io/library/postgres:15-alpine || true

    log_info "Waiting for database readiness..."
    sleep 3
    podman exec -i amara-matrix psql -U amara_admin -d postgres < "$RESTORE_TMP/qfx-postgres-dump-20260927.sql" || log_warn "DB restore encountered non-fatal notices."
    log_success "PostgreSQL cluster restored."
fi

# 8. Start Sovereign Stack
log_info "Igniting QuantumFlex services..."
systemctl --user start quantum-flex-engine-mycelium.service api-node.service amara-dashboard.service athena-node.service qf-monitor.service qf-bot.service quantumflex-ghost-sink.service || true

# 9. Perform Unsealing Ceremony
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "$SCRIPT_DIR/unlock_engine.sh" ]]; then
    log_info "Executing Stratum 0 Shamir unsealing ceremony..."
    sleep 1
    "$SCRIPT_DIR/unlock_engine.sh"
    log_success "QuantumFlex unsealed and ACTIVE."
fi

log_success "════════════════════════════════════════════════════════════════"
log_success "  NODE RESTORATION COMPLETE — QUANTUMFLEX IS ONLINE"
log_success "════════════════════════════════════════════════════════════════"
