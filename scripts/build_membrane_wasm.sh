#!/usr/bin/env bash
# Rebuild the deployed Wasm from the daemon's canonical source.
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
BUNDLE_DIR=$(mktemp -d)
trap 'rm -rf -- "$BUNDLE_DIR"' EXIT
cmp "$ROOT_DIR/pqc-immune-daemon/membrane_health.rego" "$ROOT_DIR/sentinel/policies/membrane_health.rego"
opa build -t wasm \
    -e membrane/health/verdict \
    -e membrane/health/fallback_map \
    -e membrane/health/recovery_map \
    -e membrane/health/active_fallback_map \
    -e membrane/health/recommended_fallback \
    -o "$BUNDLE_DIR/policy.tar.gz" "$ROOT_DIR/pqc-immune-daemon/membrane_health.rego"
python3 - "$BUNDLE_DIR/policy.tar.gz" "$ROOT_DIR/sentinel/policies/membrane_health.wasm" <<'PY'
import pathlib, sys, tarfile
with tarfile.open(sys.argv[1]) as bundle:
    member = next(m for m in bundle.getmembers() if m.name.lstrip('/') == 'policy.wasm')
    pathlib.Path(sys.argv[2]).write_bytes(bundle.extractfile(member).read())
PY
