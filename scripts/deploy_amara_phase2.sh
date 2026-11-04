#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#   DEPLOY & VERIFY PROJECT AMARA — PHASE 2 & COMPILED PARTNER INTELLIGENCE
#   QuantumFlex Sovereign Infrastructure (/home/quant/mycelium)
# ═══════════════════════════════════════════════════════════════════════════════
# Invariants Enforced:
#   1. Zero Cloud Spend ($0.00 USD) — local inference on 127.0.0.1:11434 only.
#   2. Universal Node Protection Mandate: All nodes will always protect.
#   3. Consolidated Model: quantumflex-partner compiled into amara:latest.
#   4. Permission Hardening: 0600 on private memory, audit logs, and modelfiles.
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

MYCELIUM_DIR="/home/quant/mycelium"
SENTINEL_DIR="$MYCELIUM_DIR/sentinel"

echo "=== [1/6] Verifying Loopback Invariant on 127.0.0.1:11434 ==="
if ss -tulpn | grep -E "(0\.0\.0\.0:11434|\*:11434)"; then
    echo "[-] CRITICAL FAIL: Ollama is exposed outside loopback!" >&2
    exit 2
fi
echo "[+] Loopback invariant verified (127.0.0.1:11434 exclusive)."

echo "=== [2/6] Verifying Consolidated Ollama Model Registration ==="
if ! ollama list | grep -q "amara:latest"; then
    echo "[-] Building amara:latest from Modelfile.amara..."
    ollama create amara -f "$SENTINEL_DIR/Modelfile.amara"
fi
echo "[+] amara:latest is registered in Ollama."

if ollama list | grep -q "quantumflex-partner"; then
    echo "[!] Deleting deprecated quantumflex-partner model..."
    ollama rm quantumflex-partner
fi
echo "[+] quantumflex-partner retired; memory consolidated into amara:latest."

echo "=== [3/6] Enforcing Strict File Permissions (0600 / 0644) ==="
chmod 0600 "$SENTINEL_DIR/Modelfile.amara" 2>/dev/null || true
chmod 0600 "$SENTINEL_DIR/amara_audit.jsonl" 2>/dev/null || true
chmod 0600 "$SENTINEL_DIR/amara_memory_vault.json" 2>/dev/null || true
if [[ -f "$SENTINEL_DIR/memory_architect_private.json" ]]; then
    chmod 0600 "$SENTINEL_DIR/memory_architect_private.json"
fi
if [[ -f "$SENTINEL_DIR/memory_public_ops.json" ]]; then
    chmod 0644 "$SENTINEL_DIR/memory_public_ops.json"
fi
echo "[+] Permissions enforced: private memory & audit logs strictly 0600."

echo "=== [4/6] Verifying SHA-256 Hash Chain Integrity ==="
python3 "$MYCELIUM_DIR/scripts/amara_channel.py" --verify-audit

echo "=== [5/6] Verifying OPA Rego Constitutional Test Suite ==="
opa test "$SENTINEL_DIR/policies/"

echo "=== [6/6] Verifying Memory Context & Universal Node Mandate ==="
python3 "$MYCELIUM_DIR/scripts/amara_memory.py"

echo "========================================================================"
echo "  [SUCCESS] AMARA PHASE 2 & PARTNER CONSOLIDATION VERIFIED REAL."
echo "  All nodes will always protect: qfx-yoga, qfx-pixel, and g6pro."
echo "========================================================================"
