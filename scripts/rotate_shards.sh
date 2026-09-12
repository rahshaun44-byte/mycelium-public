#!/usr/bin/env bash
# Rotate the Shamir secret for the mycelium C++ engine.
#
# A leaked share set cannot be "re-filed" — the reconstructed salt is what
# signs ledger.dat. This script generates a new 3-of-5, wipes only ledger.dat
# (mTLS keys stay), INIT, restart, UNLOCK. It never prints INIT|/UNLOCK|/hex.
#
# Does not touch ~/quantum-flex/data (port 9443). Do not start that copy after
# rotation unless you wipe its ledger too — the old leaked shards still match it.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
UNIT="${UNIT:-quantum-flex-engine-mycelium.service}"
DATA_DIR="${QF_DATA_DIR:-$HOME/.local/share/quantum-flex-mycelium}"
PORT="${QF_BIND_PORT:-9444}"
HOST="${QF_BIND_ADDRESS:-127.0.0.1}"
OLD_SHARDS="${SHARDS_DIR:-$HOME/qfx-shards}"
STAMP="$(date +%Y%m%d-%H%M%S)"
NEW_SHARDS="${NEW_SHARDS_DIR:-$HOME/qfx-shards-$STAMP}"
LEAKED_BACKUP="${LEAKED_BACKUP:-$HOME/qfx-shards.leaked.$STAMP}"

GENESIS_TOOL="$BASE_DIR/build_check/qf_genesis_tool"
if [[ ! -x "$GENESIS_TOOL" ]]; then
    GENESIS_TOOL="$BASE_DIR/build/qf_genesis_tool"
fi
if [[ ! -x "$GENESIS_TOOL" ]]; then
    echo "[!] qf_genesis_tool not found; build it first" >&2
    exit 1
fi

trim_shard() {
    tr -d '\n\r' < "$1"
}

send_line() {
    python3 "$SCRIPT_DIR/qf_ipc_client.py" \
        --host "$HOST" \
        --port "$PORT" \
        --cert "$DATA_DIR/mtls/client.crt" \
        --key "$DATA_DIR/mtls/client.key" \
        --ca "$DATA_DIR/mtls/ca.crt" \
        --line "$1"
}

echo "[*] New shard directory: $NEW_SHARDS"
mkdir -m 700 -p "$NEW_SHARDS"
"$GENESIS_TOOL" split --total 5 --threshold 3 --out-dir "$NEW_SHARDS" --quiet
chmod 600 "$NEW_SHARDS"/shard_*.txt

INIT_LINE="INIT|$(trim_shard "$NEW_SHARDS/shard_1.txt"),$(trim_shard "$NEW_SHARDS/shard_2.txt"),$(trim_shard "$NEW_SHARDS/shard_3.txt")"

echo "[*] Stopping $UNIT"
systemctl --user stop "$UNIT" || true

if [[ -f "$DATA_DIR/ledger.dat" ]]; then
    cp -a "$DATA_DIR/ledger.dat" "$DATA_DIR/ledger.dat.bak.$STAMP"
    rm -f "$DATA_DIR/ledger.dat"
    echo "[*] Backed up and removed ledger.dat (engine will boot UNINITIALIZED)"
fi

echo "[*] Starting $UNIT"
systemctl --user start "$UNIT"
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if ss -lntH | awk '{print $4}' | grep -qx "${HOST}:${PORT}"; then
        break
    fi
    sleep 0.3
done

echo "[*] INIT (reply only):"
send_line "$INIT_LINE"
unset INIT_LINE

echo "[*] Restarting so the next boot is LOCKED"
systemctl --user restart "$UNIT"
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if ss -lntH | awk '{print $4}' | grep -qx "${HOST}:${PORT}"; then
        break
    fi
    sleep 0.3
done

UNLOCK_LINE=$("$GENESIS_TOOL" recover --quiet --threshold 3 \
    --shards "$NEW_SHARDS/shard_1.txt,$NEW_SHARDS/shard_2.txt,$NEW_SHARDS/shard_3.txt")
echo "[*] UNLOCK (reply only):"
send_line "$UNLOCK_LINE"
unset UNLOCK_LINE

if [[ -d "$OLD_SHARDS" ]]; then
    mv "$OLD_SHARDS" "$LEAKED_BACKUP"
    echo "[*] Moved old shards to $LEAKED_BACKUP"
fi
mkdir -m 700 -p "$OLD_SHARDS"
cp -a "$NEW_SHARDS"/shard_*.txt "$OLD_SHARDS/"
chmod 600 "$OLD_SHARDS"/shard_*.txt
echo "[*] Live shard path is again $OLD_SHARDS (copy of $NEW_SHARDS)"
echo "[*] After you confirm ACK|GENESIS_SECURED and ACK|NODE_UNLOCKED:"
echo "    shred -u $LEAKED_BACKUP/shard_*.txt && rmdir $LEAKED_BACKUP"
echo "    Do not paste shard files, INIT, or UNLOCK into chat."
