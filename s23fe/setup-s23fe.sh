#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# Quantum Flex: Samsung Galaxy S23 FE Automated Termux Setup Script
# ==============================================================================
# Target Host: 100.64.1.17 (quantumflex)
# Mobile Node: 100.64.1.32 (rahshauns-s23-fe)
# ==============================================================================

set -e

HOST_IP="100.64.1.17"
MCP_PORT="9000"
DASH_PORT="8000"
API_PORT="8080"

echo "================================================="
echo "  QUANTUM FLEX: S23 FE Termux Environment Setup  "
echo "================================================="

# 1. Check Python installation in Termux
if ! command -v python &> /dev/null; then
    echo "[*] Installing Python in Termux..."
    pkg update -y && pkg install python -y
else
    echo "[+] Python is installed ($(python --version))"
fi

# 2. Deploy qflex_cli.py to user home directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/qflex_cli.py" ]; then
    cp "$SCRIPT_DIR/qflex_cli.py" "$HOME/qflex_cli.py"
    echo "[+] Copied local qflex_cli.py to $HOME/qflex_cli.py"
else
    echo "[*] Downloading qflex_cli.py from http://$HOST_IP:$API_PORT/s23fe/qflex_cli.py..."
    curl -s -o "$HOME/qflex_cli.py" "http://$HOST_IP:$API_PORT/s23fe/qflex_cli.py"
    echo "[+] Downloaded qflex_cli.py to $HOME/qflex_cli.py"
fi
chmod +x "$HOME/qflex_cli.py" 

# 3. Configure Claude / MCP Client Config
mkdir -p "$HOME/.config/claude"
cat << 'EOF' > "$HOME/.config/claude/config.json"
{
  "mcpServers": {
    "quantum-flex": {
      "url": "http://100.64.1.17:9000/sse"
    }
  }
}
EOF

# Also create ~/.claude.json for compatibility
cp "$HOME/.config/claude/config.json" "$HOME/.claude.json"
echo "[+] Deployed Quantum Flex MCP config to ~/.config/claude/config.json and ~/.claude.json"

# 4. Set up shell aliases
BASHRC="$HOME/.bashrc"
if ! grep -q "alias qf=" "$BASHRC" 2>/dev/null; then
    echo "" >> "$BASHRC"
    echo "# Quantum Flex Aliases" >> "$BASHRC"
    echo "alias qf='python \$HOME/qflex_cli.py'" >> "$BASHRC"
    echo "alias qf-status='python \$HOME/qflex_cli.py status'" >> "$BASHRC"
    echo "alias qf-mcp='python \$HOME/qflex_cli.py mcp'" >> "$BASHRC"
    echo "[+] Added 'qf' aliases to $BASHRC"
fi

echo ""
echo "-------------------------------------------------"
echo "  Testing Network Connectivity to Host ($HOST_IP)"
echo "-------------------------------------------------"

# Test API Node
if curl -s --connect-timeout 3 "http://$HOST_IP:$API_PORT/status" > /dev/null; then
    echo "[+] API Gateway (Port $API_PORT) : REACHABLE"
else
    echo "[!] API Gateway (Port $API_PORT) : NOT REACHABLE (Check Tailscale connection)"
fi

# Test Dashboard
if curl -s --connect-timeout 3 "http://$HOST_IP:$DASH_PORT/" > /dev/null; then
    echo "[+] Dashboard   (Port $DASH_PORT) : REACHABLE"
else
    echo "[!] Dashboard   (Port $DASH_PORT) : NOT REACHABLE"
fi

# Test MCP Server
if curl -s --connect-timeout 3 "http://$HOST_IP:$MCP_PORT/sse" > /dev/null; then
    echo "[+] MCP Server  (Port $MCP_PORT) : REACHABLE"
else
    echo "[!] MCP Server  (Port $MCP_PORT) : NOT REACHABLE"
fi

echo ""
echo "================================================="
echo "  Setup Complete! Available Commands:           "
echo "================================================="
echo "  qf status              - Live stack health check"
echo "  qf athena \"<query>\"    - Ask Athena RAG a question"
echo "  qf mcp                 - View MCP Server endpoints"
echo "  qf dash                - Get Dashboard Web URL"
echo "================================================="
