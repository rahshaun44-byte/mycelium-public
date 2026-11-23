#!/usr/bin/env bash
# Rebuild sentinel/policies/reserve_invariant.wasm from its Rego source.
# The .wasm is pinned in release/PROVENANCE_MANIFEST.json and the .rego is a
# QF-PRODUCTION-01 seal artifact: a rebuild needs a re-sign before it ships.
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR=$(mktemp -d)
trap 'rm -rf -- "$BUNDLE_DIR"' EXIT
opa test "$ROOT_DIR/sentinel/policies/reserve_invariant.rego" \
         "$ROOT_DIR/sentinel/policies/reserve_invariant_test.rego"
opa build -t wasm -e quantumflex/invariant \
    -o "$BUNDLE_DIR/policy.tar.gz" "$ROOT_DIR/sentinel/policies/reserve_invariant.rego"
python3 - "$BUNDLE_DIR/policy.tar.gz" "$ROOT_DIR/sentinel/policies/reserve_invariant.wasm" <<'PY'
import pathlib, sys, tarfile
with tarfile.open(sys.argv[1]) as bundle:
    member = next(m for m in bundle.getmembers() if m.name.lstrip('/') == 'policy.wasm')
    pathlib.Path(sys.argv[2]).write_bytes(bundle.extractfile(member).read())
PY
sha256sum "$ROOT_DIR/sentinel/policies/reserve_invariant.wasm"
