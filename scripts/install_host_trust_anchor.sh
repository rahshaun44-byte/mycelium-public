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
SRC_POINTER="${REPO_ROOT}/scripts/verify_provenance_manifest.py"
SRC_KEY="${REPO_ROOT}/release/release_signing_key.pub"
ASSERT="${REPO_ROOT}/scripts/assert_host_trust_source.py"
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
if [[ ! -f "${ASSERT}" ]]; then
  echo "[FAIL-CLOSED] Missing source-shape assert: ${ASSERT}" >&2
  exit 1
fi

# Never treat the in-repo pointer as a transform source. It has no QF-A5 judge.
if [[ "$(realpath "${SRC_VERIFIER}")" == "$(realpath "${SRC_POINTER}")" ]]; then
  echo "[FAIL-CLOSED] Refusing to install scripts/verify_provenance_manifest.py as the judge." >&2
  exit 1
fi

# Evidence-first: exact trust-boundary text + syntax compile, or write nothing.
python3 "${ASSERT}" "${SRC_VERIFIER}" --role judge
python3 "${ASSERT}" "${SRC_POINTER}" --role pointer

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

# Byte-copy through a staging dir. No re.sub. No "success" unless dest == source.
STAGING="$(mktemp -d "${DEST}/.staging.XXXXXX")"
cleanup_staging() { rm -rf "${STAGING}"; }
trap cleanup_staging EXIT

install -m 0400 "${SRC_KEY}" "${STAGING}/release_signing_key.pub"
install -m 0500 "${SRC_VERIFIER}" "${STAGING}/verify-provenance"
python3 "${ASSERT}" "${STAGING}/verify-provenance" --role judge
python3 -m py_compile "${STAGING}/verify-provenance"

src_hash="$(sha256sum "${SRC_VERIFIER}" | awk '{print $1}')"
stg_hash="$(sha256sum "${STAGING}/verify-provenance" | awk '{print $1}')"
if [[ "${src_hash}" != "${stg_hash}" ]]; then
  echo "[FAIL-CLOSED] Staging copy hash mismatch. Wrote nothing to the live judge." >&2
  exit 1
fi

# Same-filesystem rename: dest inode flips only after staging asserted.
mv -f "${STAGING}/release_signing_key.pub" "${DEST}/release_signing_key.pub"
mv -f "${STAGING}/verify-provenance" "${DEST}/verify-provenance"
python3 "${ASSERT}" "${DEST}/verify-provenance" --role judge
dst_hash="$(sha256sum "${DEST}/verify-provenance" | awk '{print $1}')"
if [[ "${src_hash}" != "${dst_hash}" ]]; then
  echo "[FAIL-CLOSED] Installed judge hash mismatch versus template." >&2
  exit 1
fi

echo "[+] Trust anchor directory : ${DEST} (0700)"
echo "[+] Pinned public key      : ${DEST}/release_signing_key.pub (0400)"
echo "[+] Verifier               : ${DEST}/verify-provenance (0500)"
echo "[+] Installed judge sha256 : ${dst_hash}"
echo "[+] This judge ignores scripts/verify_provenance_manifest.py inside any repo."
echo "[+] Isolation is not a same-user trust boundary. The repo does not supply the key."
