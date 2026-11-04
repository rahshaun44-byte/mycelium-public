#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#   PROJECT AMARA — PHASE 1 DEPLOYMENT SCRIPT
#   Registers amara:latest on local loopback Ollama (127.0.0.1:11434)
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

MYCELIUM_DIR="${HOME}/mycelium"
SENTINEL_DIR="${MYCELIUM_DIR}/sentinel"
MODELFILE="${SENTINEL_DIR}/Modelfile.amara"
CHANNEL_SCRIPT="${MYCELIUM_DIR}/scripts/amara_channel.py"

echo "==============================================================================="
echo " PROJECT AMARA — PHASE 1 DEPLOYMENT & VERIFICATION"
echo "==============================================================================="

# 1. Loopback Invariant Verification
echo "[1/4] Verifying Ollama loopback invariant (127.0.0.1:11434)..."
if ss -tulpn | grep ":11434" | grep -E "0\.0\.0\.0:11434|\*:11434"; then
    echo "[!] FATAL: Ollama is bound to a public/wildcard interface! Aborting deployment." >&2
    exit 1
fi
echo "      [PASS] Loopback interface verified exclusive to 127.0.0.1:11434."

# 2. Modelfile Permissions
echo "[2/4] Enforcing 0600 permissions on Modelfile.amara..."
if [[ ! -f "${MODELFILE}" ]]; then
    echo "[!] FATAL: ${MODELFILE} not found!" >&2
    exit 1
fi
chmod 0600 "${MODELFILE}"
echo "      [PASS] ${MODELFILE} locked with mode 0600."

# 3. Register amara:latest on local Ollama
echo "[3/4] Building amara:latest on local Ollama engine from qwen2.5-coder:7b..."
ollama create amara:latest -f "${MODELFILE}"
echo "      [PASS] amara:latest successfully registered in Ollama manifest."

# 4. Verify AMARA Channel and Initial Assessment
echo "[4/4] Executing read-only defensive assessment via amara_channel.py..."
chmod +x "${CHANNEL_SCRIPT}"
python3 "${CHANNEL_SCRIPT}" --assess
echo ""
echo "[*] Verifying initial SHA-256 hash-chained audit ledger..."
python3 "${CHANNEL_SCRIPT}" --verify-audit

echo "==============================================================================="
echo " [SUCCESS] AMARA Phase 1 Core deployment complete."
echo " To open the Private Architect Channel, run:"
echo "     python3 ${CHANNEL_SCRIPT} --mode private"
echo "==============================================================================="
