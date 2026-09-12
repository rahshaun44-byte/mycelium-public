#!/usr/bin/env bash
# Unlocks the Quantum Flex C++ engine by recovering the Shamir secret from local shards
# and transmitting the UNLOCK command over mTLS to the engine socket.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

GENESIS_TOOL="$BASE_DIR/build_check/qf_genesis_tool"
if [[ ! -x "$GENESIS_TOOL" ]]; then
    GENESIS_TOOL="$BASE_DIR/build/qf_genesis_tool"
fi

if [[ ! -x "$GENESIS_TOOL" ]]; then
    echo "[!] qf_genesis_tool binary not found in build_check/ or build/" >&2
    exit 1
fi

SHARDS_DIR="${SHARDS_DIR:-$HOME/qfx-shards}"
DATA_DIR="${QF_DATA_DIR:-$HOME/.local/share/quantum-flex-mycelium}"
PORT="${QF_BIND_PORT:-9444}"
HOST="${QF_BIND_ADDRESS:-127.0.0.1}"

# Any 3 of the 5 shards suffice. Use SHARD_FILES="a,b,c" to name them explicitly
# (e.g. two on disk plus one just Taildropped into /tmp); otherwise take the
# first three shard_*.txt found in SHARDS_DIR.
if [[ -z "${SHARD_FILES:-}" ]]; then
    mapfile -t found < <(ls "$SHARDS_DIR"/shard_*.txt 2>/dev/null | head -n 3)
    if [[ ${#found[@]} -lt 3 ]]; then
        echo "[!] Need 3 shard files; found ${#found[@]} in $SHARDS_DIR. Set SHARD_FILES=a,b,c" >&2
        exit 1
    fi
    SHARD_FILES="$(IFS=,; echo "${found[*]}")"
fi

UNLOCK_LINE=$("$GENESIS_TOOL" recover --quiet \
    --shards "$SHARD_FILES" \
    --threshold 3 | grep '^UNLOCK|')

if [[ -z "$UNLOCK_LINE" ]]; then
    echo "[!] Failed to generate UNLOCK line from shards" >&2
    exit 1
fi

python3 "$SCRIPT_DIR/qf_ipc_client.py" \
    --host "$HOST" \
    --port "$PORT" \
    --cert "$DATA_DIR/mtls/client.crt" \
    --key "$DATA_DIR/mtls/client.key" \
    --ca "$DATA_DIR/mtls/ca.crt" \
    --line "$UNLOCK_LINE"
