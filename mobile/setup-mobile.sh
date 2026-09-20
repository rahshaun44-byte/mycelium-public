#!/usr/bin/env bash
# ==============================================================================
# Quantum Flex: Hardened Mobile Node Bootstrap (Pixel 11 Pro / Samsung S23 FE)
# ==============================================================================
# Target Host: 100.64.1.17 (quantumflex)
# ==============================================================================

set -euo pipefail

# 1. HARD STOP: Prevent execution on the host engine
CURRENT_HOST="$(hostname 2>/dev/null || echo "")"
CURRENT_USER="${USER:-$(whoami 2>/dev/null || echo "")}"
if [ "$CURRENT_HOST" = "fedora" ] || [ "$CURRENT_USER" = "quant" ]; then
    echo "[!] HARD STOP: Refusing to execute on host ($CURRENT_USER@$CURRENT_HOST)." >&2
    echo "[!] This script is strictly for mobile clients (Pixel 11 Pro / S23 FE)." >&2
    exit 1
fi

HOST_IP="100.64.1.17"
MCP_PORT="9000"
DASH_PORT="8000"
API_PORT="8080"
EXPECTED_CLI_SHA="d5f40a29177184284c0aa5d922519fa427a90890e59cc5cb51ea5cb12da3cdd1"

echo "================================================="
echo "   QUANTUM FLEX: Hardened Mobile Node Setup      "
echo "================================================="

# 2. Check Python availability (no automatic sudo escalation)
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "[!] FATAL: Python is missing. Please install python3 first:" >&2
    echo "    In Debian/AVF Linux: sudo apt update && sudo apt install -y python3 curl" >&2
    echo "    In Termux:           pkg update && pkg install -y python curl" >&2
    exit 1
fi

echo "[+] Python runtime: $PYTHON_CMD ($($PYTHON_CMD --version))"

# 3. Locate and verify co-located qflex_cli.py (no unsigned second-stage fetch)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo ".")"
LOCAL_CLI="$SCRIPT_DIR/qflex_cli.py"

if [ ! -f "$LOCAL_CLI" ]; then
    echo "[!] FATAL: qflex_cli.py not found in $SCRIPT_DIR" >&2
    echo "[!] Unsigned network fetch is disabled. Transfer qflex_cli.py beside this script." >&2
    exit 1
fi

ACTUAL_SHA="$(sha256sum "$LOCAL_CLI" | awk '{print $1}')"
if [ "$ACTUAL_SHA" != "$EXPECTED_CLI_SHA" ]; then
    echo "[!] FATAL: Checksum mismatch for $LOCAL_CLI" >&2
    echo "    Expected: $EXPECTED_CLI_SHA" >&2
    echo "    Actual:   $ACTUAL_SHA" >&2
    exit 1
fi
echo "[+] Integrity verified: qflex_cli.py SHA-256 matches baked pin ($ACTUAL_SHA)"
echo "[*] Hash is not a signature. Workflow 2 detached sig (mobile-ed25519-v1) is a separate plane."

cp -a "$LOCAL_CLI" "$HOME/qflex_cli.py"
chmod 0755 "$HOME/qflex_cli.py"
echo "[+] Installed: $HOME/qflex_cli.py"

# 4. Non-destructive Claude / MCP configuration
mkdir -p "$HOME/.config/claude"
TIMESTAMP="$(date +%s)"

if [ -f "$HOME/.config/claude/config.json" ]; then
    cp -a "$HOME/.config/claude/config.json" "$HOME/.config/claude/config.json.bak.$TIMESTAMP"
    echo "[*] Existing config backed up: ~/.config/claude/config.json.bak.$TIMESTAMP"
fi

if [ -f "$HOME/.claude.json" ]; then
    cp -a "$HOME/.claude.json" "$HOME/.claude.json.bak.$TIMESTAMP"
    echo "[*] Existing config backed up: ~/.claude.json.bak.$TIMESTAMP"
fi

cat << EOF_JSON > "$HOME/.config/claude/config.json"
{
  "mcpServers": {
    "quantum-flex": {
      "url": "http://$HOST_IP:$MCP_PORT/sse"
    }
  }
}
EOF_JSON
cp -a "$HOME/.config/claude/config.json" "$HOME/.claude.json"
echo "[+] Deployed Quantum Flex MCP config pointing to http://$HOST_IP:$MCP_PORT/sse"

# 5. Shell aliases
for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
    if [ -f "$rc" ] || [ "$rc" = "$HOME/.bashrc" ]; then
        touch "$rc"
        if ! grep -q "alias qf=" "$rc" 2>/dev/null; then
            echo "" >> "$rc"
            echo "# Quantum Flex Aliases" >> "$rc"
            echo "alias qf="$PYTHON_CMD \$HOME/qflex_cli.py"" >> "$rc"
            echo "alias qf-status="$PYTHON_CMD \$HOME/qflex_cli.py status"" >> "$rc"
            echo "alias qf-mcp="$PYTHON_CMD \$HOME/qflex_cli.py mcp"" >> "$rc"
            echo "[+] Added 'qf' aliases to $rc"
        fi
    fi
done

echo ""
echo "-------------------------------------------------"
echo "  Probing Host Connectivity ($HOST_IP)"
echo "-------------------------------------------------"

if curl -fsS --connect-timeout 4 "http://$HOST_IP:$API_PORT/status" > /dev/null 2>&1; then
    echo "[+] API Gateway (Port $API_PORT) : REACHABLE"
else
    echo "[!] API Gateway (Port $API_PORT) : NOT REACHABLE (Check Tailscale)"
fi

if curl -fsS --connect-timeout 4 "http://$HOST_IP:$DASH_PORT/" > /dev/null 2>&1; then
    echo "[+] Dashboard   (Port $DASH_PORT) : REACHABLE"
else
    echo "[!] Dashboard   (Port $DASH_PORT) : NOT REACHABLE"
fi

if curl -fsS --connect-timeout 4 "http://$HOST_IP:$MCP_PORT/sse" > /dev/null 2>&1; then
    echo "[+] MCP Server  (Port $MCP_PORT) : REACHABLE"
else
    echo "[!] MCP Server  (Port $MCP_PORT) : NOT REACHABLE"
fi

echo ""
echo "================================================="
echo "  Bootstrap Complete. Commands available:       "
echo "================================================="
echo "  qf status              - Live node health check"
echo "  qf athena \"<query>\"    - Ask Athena RAG a question"
echo "  qf chat                - Interactive terminal chat"
echo "  qf dash                - Print Dashboard Web URL"
echo "================================================="
