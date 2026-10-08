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

# Any 3 of the 5 shards suffice.
# If only 1 shard is kept on this host (as per sovereign security posture),
# the operator provides the remaining shards interactively or via SHARD_FILES.
if [[ -z "${SHARD_FILES:-}" ]]; then
    shopt -s nullglob
    found=("$SHARDS_DIR"/shard_*.txt)
    shopt -u nullglob

    if [[ ${#found[@]} -lt 3 ]]; then
        echo "[*] Local shards found in $SHARDS_DIR: ${#found[@]}"
        echo "[*] 3-of-5 threshold required for unsealing ceremony."
        if [[ -t 0 ]]; then
            echo "[*] Please provide paths or strings for the required external shards:"
            read -r -p "Enter comma-separated shard paths (or paste SHARD_FILES=f1,f2,f3): " INPUT_SHARDS
            SHARD_FILES="$INPUT_SHARDS"
        fi
    else
        SHARD_FILES="$(IFS=,; echo "${found[*]:0:3}")"
    fi

    if [[ -z "${SHARD_FILES:-}" ]]; then
        echo "[!] Need 3 shard files; found ${#found[@]} in $SHARDS_DIR. Set SHARD_FILES=shard1,shard2,shard3" >&2
        exit 1
    fi
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
