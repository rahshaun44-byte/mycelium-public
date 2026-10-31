#!/usr/bin/env bash
# ==============================================================================
# Build sentinel/policies/operating_constitution.wasm from canonical Rego source
# ==============================================================================
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OPA_BIN="${OPA_BIN:-$(command -v opa 2>/dev/null || echo "/home/quant/.local/bin/opa")}"
BUNDLE_DIR="$(mktemp -d)"
trap 'rm -rf -- "$BUNDLE_DIR"' EXIT

"${OPA_BIN}" test "${ROOT_DIR}/sentinel/policies/operating_constitution.rego" "${ROOT_DIR}/sentinel/policies/operating_constitution_test.rego"

"${OPA_BIN}" build -t wasm \
    -e quantumflex/constitution/evaluation \
    -o "${BUNDLE_DIR}/policy.tar.gz" \
    "${ROOT_DIR}/sentinel/policies/operating_constitution.rego"

python3 - "${BUNDLE_DIR}/policy.tar.gz" "${ROOT_DIR}/sentinel/policies/operating_constitution.wasm" <<'PY'
import pathlib, sys, tarfile
with tarfile.open(sys.argv[1]) as bundle:
    member = next(m for m in bundle.getmembers() if m.name.lstrip('/') == 'policy.wasm')
    pathlib.Path(sys.argv[2]).write_bytes(bundle.extractfile(member).read())
PY

echo "[+] Compiled Wasm bundle: ${ROOT_DIR}/sentinel/policies/operating_constitution.wasm"

