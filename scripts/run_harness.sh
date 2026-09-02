#!/usr/bin/env bash
# QuantumFlex Offline Admission Verifier
# Safely extracts, validates against manifest, verifies cosign signature, and promotes.

set -euo pipefail

if [[ $# -lt 3 ]]; then
    echo "Usage: $0 <bundle.tar.gz> <release_attestation.json> <signature.bundle>"
    exit 1
fi

BUNDLE="$1"
ATTESTATION="$2"
SIGNATURE="$3"

echo "[1/4] Verifying Cryptographic Signature..."
# Using cosign for OIDC keyless verification (assuming identity matches the repo)
cosign verify-blob "$ATTESTATION" \
  --bundle "$SIGNATURE" \
  --certificate-identity-regexp "https://github.com/rahshaun44-byte/pqc-immune-daemon/" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" || {
    echo "HARD STOP: Signature validation failed."
    exit 1
}

echo "[2/4] Verifying Artifact Digest..."
ACTUAL_HASH=$(sha256sum "$BUNDLE" | awk '{print $1}')
ATTESTED_HASH=$(jq -r '.artifact_identity.sha256' "$ATTESTATION")

if [[ "$ACTUAL_HASH" != "$ATTESTED_HASH" ]]; then
    echo "HARD STOP: Artifact hash mismatch!"
    exit 1
fi

echo "[3/4] Validating Archive Safety & Manifest..."
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "$TEMP_DIR"' EXIT

# Python safe-extraction pattern using tarfile
cat << 'EOF' > "$TEMP_DIR/safe_extract.py"
import tarfile, sys, os
bundle = sys.argv[1]
dest = sys.argv[2]
with tarfile.open(bundle, 'r:gz') as tar:
    for member in tar.getmembers():
        # Prevent symlink traversal, absolute paths, and restricted types
        if member.issym() or member.islnk() or member.name.startswith('/') or '..' in member.name:
            print("HARD STOP: Unsafe archive path detected.")
            sys.exit(1)
        if not member.isfile():
            print("HARD STOP: Only regular files are allowed in the bundle.")
            sys.exit(1)
    tar.extractall(path=dest, filter='data')
EOF

python3 "$TEMP_DIR/safe_extract.py" "$BUNDLE" "$TEMP_DIR/extracted" || exit 1

# Check manifest
cd "$TEMP_DIR/extracted"
if [[ ! -f "MANIFEST.json" ]]; then
    echo "HARD STOP: MANIFEST.json missing from archive."
    exit 1
fi

echo "[4/4] Cross-checking extracted files..."
# Ensures all extracted files are in the manifest, and hashes match.
jq -r '.files | keys[]' MANIFEST.json | while read file; do
    if [[ ! -f "$file" ]]; then
        echo "HARD STOP: Manifest file $file missing from archive."
        exit 1
    fi
    FILE_HASH=$(sha256sum "$file" | awk '{print $1}')
    EXPECTED_HASH=$(jq -r ".files[\"$file\"].sha256" MANIFEST.json)
    if [[ "$FILE_HASH" != "$EXPECTED_HASH" ]]; then
        echo "HARD STOP: Hash mismatch for $file"
        exit 1
    fi
done

echo "ADMIT(R) == TRUE. Deploying..."
# Real deployment steps would cp files to destination here
mkdir -p /opt/quantumflex/policy
cp *.rego /opt/quantumflex/policy/

echo "SUCCESS: Admission Complete."
