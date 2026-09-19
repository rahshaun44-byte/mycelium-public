#!/usr/bin/env bash
# Install the host trust anchor outside the mutable mycelium tree.
# Template lives in-repo; the judge is $HOME/.local/libexec/quantumflex.
set -euo pipefail

if [[ "${EUID}" -eq 0 ]]; then
  echo "[FAIL-CLOSED] Refusing to install the trust anchor as root." >&2
  exit 1
fi

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${QF_TRUST_ANCHOR:-$HOME/.local/libexec/quantumflex}"
SRC_VERIFIER="${REPO_ROOT}/host-trust/verify-provenance"
SRC_KEY="${REPO_ROOT}/release/release_signing_key.pub"
REPLACE="${1:-}"

if [[ ! -f "${SRC_VERIFIER}" ]]; then
  echo "[FAIL-CLOSED] Missing template: ${SRC_VERIFIER}" >&2
  exit 1
fi
if [[ ! -f "${SRC_KEY}" ]]; then
  echo "[FAIL-CLOSED] Missing public key: ${SRC_KEY}" >&2
  exit 1
fi

if [[ "${REPLACE}" != "--replace" ]]; then
  for existing in "${DEST}/verify-provenance" "${DEST}/release_signing_key.pub"; do
    if [[ -e "${existing}" ]]; then
      echo "[FAIL-CLOSED] ${existing} already exists." >&2
      echo "Re-installing would overwrite the judge from a (possibly dirty) checkout." >&2
      echo "Pass --replace only from a tree you already trust." >&2
      exit 1
    fi
  done
fi

mkdir -p "${DEST}"
chmod 0700 "${DEST}"

# Write via a temp file then chmod so a partial copy is never left executable.
install -m 0400 "${SRC_KEY}" "${DEST}/release_signing_key.pub"
install -m 0500 "${SRC_VERIFIER}" "${DEST}/verify-provenance"

echo "[+] Trust anchor directory : ${DEST} (0700)"
echo "[+] Pinned public key      : ${DEST}/release_signing_key.pub (0400)"
echo "[+] Verifier               : ${DEST}/verify-provenance (0500)"
echo "[+] This judge ignores scripts/verify_provenance_manifest.py inside any repo."
