#!/usr/bin/env bash
# ==============================================================================
# QuantumFlex: Hardened Mobile Node Bootstrap (Pixel 11 Pro)
# ==============================================================================
# Invariant: Verify before execute. Zero unverified code enters the mobile plane.
# Target Host: 100.64.1.31:9000 (quantumflex)
# ==============================================================================

set -euo pipefail

# 1. HARD STOP: Refuse execution on the host engine
CURRENT_HOST="$(hostname 2>/dev/null || echo "")"
CURRENT_USER="${USER:-$(whoami 2>/dev/null || echo "")}"
if [ "$CURRENT_HOST" = "qfx-yoga" ] || [ "$CURRENT_USER" = "quant" ]; then
    echo "[!] HARD STOP: Refusing to execute on master host ($CURRENT_USER@$CURRENT_HOST)." >&2
    echo "[!] This script is strictly for mobile clients (Pixel 11 Pro)." >&2
    exit 1
fi

HOST_IP="100.64.1.31"
PORT="9000"
TRUST_ANCHOR_DIR="$HOME/.quantumflex"
TRUST_ANCHOR="$TRUST_ANCHOR_DIR/release_signing_key.pub"

echo "================================================="
echo "   QUANTUMFLEX: Hardened Mobile Node Setup (M1)  "
echo "================================================="

# 2. Check Python 3 and OpenSSL availability
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "[!] FATAL: Python is missing. Please install python3 first:" >&2
    echo "    In Termux: pkg update && pkg install -y python openssl curl" >&2
    exit 1
fi

if ! command -v openssl &> /dev/null; then
    echo "[!] FATAL: openssl is required for cryptographic verification." >&2
    echo "    In Termux: pkg install -y openssl" >&2
    exit 1
fi

echo "[+] Python runtime : $PYTHON_CMD ($($PYTHON_CMD --version))"
echo "[+] Cryptography   : $(openssl version)"

# 3. Resolve pinned trust anchor
mkdir -p "$TRUST_ANCHOR_DIR"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo ".")"

if [ -f "$SCRIPT_DIR/release_signing_key.pub" ]; then
    cp -a "$SCRIPT_DIR/release_signing_key.pub" "$TRUST_ANCHOR"
    chmod 0444 "$TRUST_ANCHOR"
    echo "[+] Trust Anchor   : Pinned from co-located media ($TRUST_ANCHOR)"
elif [ -f "$TRUST_ANCHOR" ]; then
    echo "[+] Trust Anchor   : Existing pinned key found ($TRUST_ANCHOR)"
else
    echo "[*] Fetching trust anchor from host over Tailscale..."
    curl -fsS --connect-timeout 5 "http://$HOST_IP:$PORT/mobile/download/trust-anchor" -o "$TRUST_ANCHOR"
    chmod 0444 "$TRUST_ANCHOR"
    echo "[+] Trust Anchor   : Acquired and pinned to $TRUST_ANCHOR"
fi

# 4. Acquire artifacts and detached signatures
STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT

CLI_FILE="$STAGE_DIR/qflex_cli.py"
MANIFEST_FILE="$STAGE_DIR/qflex_cli.py.manifest.json"
SIG_FILE="$STAGE_DIR/qflex_cli.py.sig"

if [ -f "$SCRIPT_DIR/qflex_cli.py" ] && [ -f "$SCRIPT_DIR/qflex_cli.py.manifest.json" ] && [ -f "$SCRIPT_DIR/qflex_cli.py.sig" ]; then
    cp -a "$SCRIPT_DIR/qflex_cli.py" "$CLI_FILE"
    cp -a "$SCRIPT_DIR/qflex_cli.py.manifest.json" "$MANIFEST_FILE"
    cp -a "$SCRIPT_DIR/qflex_cli.py.sig" "$SIG_FILE"
    echo "[+] Artifact Source: Co-located directory ($SCRIPT_DIR)"
else
    echo "[*] Downloading signed mobile CLI over Tailscale mesh..."
    curl -fsS --connect-timeout 5 "http://$HOST_IP:$PORT/mobile/download/cli" -o "$CLI_FILE"
    curl -fsS --connect-timeout 5 "http://$HOST_IP:$PORT/mobile/download/cli/manifest" -o "$MANIFEST_FILE"
    curl -fsS --connect-timeout 5 "http://$HOST_IP:$PORT/mobile/download/cli/sig" -o "$SIG_FILE"
    echo "[+] Downloaded artifact, manifest, and detached Ed25519 signature."
fi

# 5. Cryptographic Admission Verification (Verify before execute)
echo "[*] Verifying Ed25519 signature against pinned trust anchor..."
SIG_VERIFY_OUTPUT="$(openssl pkeyutl -verify -rawin -pubin -inkey "$TRUST_ANCHOR" -in "$MANIFEST_FILE" -sigfile "$SIG_FILE" 2>&1 || true)"

if ! echo "$SIG_VERIFY_OUTPUT" | grep -q "Signature Verified Successfully"; then
    echo "[!] FATAL: Ed25519 signature verification FAILED against trust anchor!" >&2
    echo "    $SIG_VERIFY_OUTPUT" >&2
    echo "[!] HALT: Refusing to install unverified code." >&2
    exit 1
fi
echo "[PASS] Ed25519 Manifest Signature verified successfully."

# 6. Verify SHA-256 match against signed manifest
EXPECTED_SHA="$($PYTHON_CMD -c "import json; print(json.load(open('$MANIFEST_FILE'))['sha256'])")"
ACTUAL_SHA="$(sha256sum "$CLI_FILE" | awk '{print $1}')"

if [ "$EXPECTED_SHA" != "$ACTUAL_SHA" ]; then
    echo "[!] FATAL: Artifact SHA-256 does not match signed manifest!" >&2
    echo "    Expected: $EXPECTED_SHA" >&2
    echo "    Actual:   $ACTUAL_SHA" >&2
    echo "[!] HALT: Refusing to install tampered artifact." >&2
    exit 1
fi
echo "[PASS] SHA-256 byte integrity verified ($ACTUAL_SHA)."

# 7. Install verified CLI
cp -a "$CLI_FILE" "$HOME/qflex_cli.py"
chmod 0755 "$HOME/qflex_cli.py"
echo "[+] Installed verified CLI: $HOME/qflex_cli.py"

# 8. Configure Shell Aliases
for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
    if [ -f "$rc" ] || [ "$rc" = "$HOME/.bashrc" ]; then
        touch "$rc"
        if ! grep -q "alias qf=" "$rc" 2>/dev/null; then
            cat << 'EOF_ALIASES' >> "$rc"

# QuantumFlex Sovereign Mobile Aliases (QF-M1)
alias qf="python3 $HOME/qflex_cli.py"
alias qf-status="python3 $HOME/qflex_cli.py status"
alias qf-verify="python3 $HOME/qflex_cli.py verify"
alias qf-invariant="python3 $HOME/qflex_cli.py invariant"
alias qf-custody="python3 $HOME/qflex_cli.py custody"
alias qf-node="python3 $HOME/qflex_cli.py node"
alias qf-doctor="python3 $HOME/qflex_cli.py doctor"
EOF_ALIASES
            echo "[+] Deployed 'qf' aliases to $rc"
        fi
    fi
done

echo ""
echo "================================================="
echo "  Bootstrap Complete. Device Identity & Health:  "
echo "================================================="
$PYTHON_CMD "$HOME/qflex_cli.py" node
$PYTHON_CMD "$HOME/qflex_cli.py" status
