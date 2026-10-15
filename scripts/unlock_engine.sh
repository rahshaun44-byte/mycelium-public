#!/usr/bin/env bash
# Unlocks through checked recovery of the original three share files. The shared
# recovery helper verifies the saved ledger before opening the mTLS transport.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SHARDS_DIR="${SHARDS_DIR:-$HOME/qfx-shards}"

# Any 3 of the 5 shards suffice.
# If only 1 shard is kept on this host (as per sovereign security posture),
# the operator provides the remaining file paths via SHARD_FILES.
if [[ -z "${SHARD_FILES:-}" ]]; then
    shopt -s nullglob
    found=("$SHARDS_DIR"/shard_*.txt)
    shopt -u nullglob

    if [[ ${#found[@]} -lt 3 ]]; then
        echo "[*] Local shard files found: ${#found[@]}"
        echo "[*] 3-of-5 threshold required for unsealing ceremony."
        if [[ -t 0 ]]; then
            echo "[*] Provide file paths only; never paste shard values."
            read -r -p "Enter three comma-separated shard file paths: " INPUT_SHARDS
            SHARD_FILES="$INPUT_SHARDS"
        fi
    else
        SHARD_FILES="$(IFS=,; echo "${found[*]:0:3}")"
    fi

    if [[ -z "${SHARD_FILES:-}" ]]; then
        echo "[!] Need three existing shard file paths. For encrypted custody use tools/qf_recovery.py --check." >&2
        exit 1
    fi
fi

refuse_files() {
    echo "[!] Supply exactly three distinct, readable plaintext shard file paths. For encrypted custody use tools/qf_recovery.py --check." >&2
    exit 2
}

# Reject values before passing anything to another process. Content validation
# stays in the Python helper so share bytes never enter shell variables.
[[ "$SHARD_FILES" != *$'\n'* && "$SHARD_FILES" != *$'\r'* ]] || refuse_files
[[ ",$SHARD_FILES," != *,,* ]] || refuse_files
IFS=, read -r -a shard_paths <<< "$SHARD_FILES"
[[ ${#shard_paths[@]} -eq 3 ]] || refuse_files
checked_paths=()
for shard_path in "${shard_paths[@]}"; do
    [[ "$shard_path" != *'<'* && "$shard_path" != *'>'* ]] || refuse_files
    [[ ! "$shard_path" =~ ^[0-9]+:[[:xdigit:]]+$ ]] || refuse_files
    case "${shard_path,,}" in
        *.gpg|*.pgp|*.asc|*.age|*.enc) refuse_files ;;
    esac
    [[ -f "$shard_path" && -r "$shard_path" ]] || refuse_files
    checked_path=$(realpath -e -- "$shard_path" 2>/dev/null) || refuse_files
    case "${checked_path,,}" in
        *.gpg|*.pgp|*.asc|*.age|*.enc) refuse_files ;;
    esac
    for previous_path in "${checked_paths[@]}"; do
        [[ "$checked_path" != "$previous_path" ]] || refuse_files
    done
    checked_paths+=("$checked_path")
done

RECOVERY_HELPER="$BASE_DIR/tools/qf_recovery.py"
if [[ ! -f "$RECOVERY_HELPER" ]]; then
    echo "[!] Checked recovery helper is unavailable; no unlock was attempted." >&2
    exit 1
fi
SHARD_FILES=$(IFS=,; echo "${checked_paths[*]}")
exec python3 "$RECOVERY_HELPER" --share-files "$SHARD_FILES" --unlock
