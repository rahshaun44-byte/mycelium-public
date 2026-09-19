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
DRY_MANIFEST="${QF_DRY_RUN_MANIFEST:-${REPO_ROOT}/release/PROVENANCE_MANIFEST.json}"
DRY_ROOT="${QF_DRY_RUN_ROOT:-${REPO_ROOT}}"
DRY_KEY="${QF_DRY_RUN_KEY:-${SRC_KEY}}"
REPLACE=0
FORCE_UNVERIFIED=0
for arg in "$@"; do
  case "${arg}" in
    --replace) REPLACE=1 ;;
    --force-unverified) FORCE_UNVERIFIED=1 ;;
    *)
      echo "[FAIL-CLOSED] Unknown argument: ${arg}" >&2
      echo "Usage: $0 [--replace] [--force-unverified]" >&2
      exit 1
      ;;
  esac
done

if [[ ! -f "${SRC_VERIFIER}" ]]; then
  echo "[FAIL-CLOSED] Missing template: ${SRC_VERIFIER}" >&2
  exit 1
fi
if [[ ! -f "${SRC_KEY}" ]]; then
  echo "[FAIL-CLOSED] Missing public key: ${SRC_KEY}" >&2
  exit 1
fi

# Hard-Stop: lock only after this template has ALLOW'd a known-good tree.
# --force-unverified installs a denier from a dirty tree. That is not QF-R2 complete.
if [[ "${FORCE_UNVERIFIED}" -eq 0 ]]; then
  if ! python3 "${SRC_VERIFIER}" "${DRY_MANIFEST}" --repo-root "${DRY_ROOT}" --key "${DRY_KEY}"; then
    echo "[FAIL-CLOSED] Dry-run did not ALLOW ${DRY_ROOT}." >&2
    echo "Signature-valid + hash mismatch is DENY. Inspect with:" >&2
    echo "  python3 scripts/inspect_qfa5_release.py" >&2
    echo "Restore signed artifacts or mint a new signed release, then retry." >&2
    echo "Do not pass --force-unverified unless you are intentionally installing a denier." >&2
    exit 1
  fi
fi

if [[ "${REPLACE}" -eq 0 ]]; then
  for existing in "${DEST}/verify-provenance" "${DEST}/release_signing_key.pub"; do
    if [[ -e "${existing}" ]]; then
      echo "[FAIL-CLOSED] ${existing} already exists." >&2
      echo "Re-installing would overwrite the judge from a (possibly dirty) checkout." >&2
      echo "Pass --replace only from a tree the dry-run already ALLOW'd." >&2
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
