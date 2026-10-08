#!/usr/bin/env bash
# ==============================================================================
# QuantumFlex: Private Tailscale Mesh Service Publisher
# ==============================================================================
# Binds zero services to 0.0.0.0 or physical LAN.
# Publishes local loopback microservices over the encrypted Tailscale overlay
# with automated MagicDNS TLS certificates for mobile HUD & API endpoints.
# ==============================================================================

set -euo pipefail

echo "[*] Initializing QuantumFlex Private Tailscale Mesh Services..."

# 1. Ensure Tailscale is running and accessible
if ! TS_STATUS_OUTPUT="$(tailscale status 2>&1)"; then
    echo "[!] Error: Tailscale is not running or accessible: ${TS_STATUS_OUTPUT}" >&2
    exit 1
fi

TS_IP="$(tailscale ip -4 || true)"
if [[ -z "${TS_IP}" ]]; then
    echo "[!] Error: Failed to obtain Tailscale IPv4 address." >&2
    exit 1
fi
DNS_NAME="$(tailscale status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"

echo "[+] Node Tailscale IP: ${TS_IP}"
echo "[+] Node MagicDNS:    ${DNS_NAME}"

# 2. Configure Tailscale Serve for QuantumFlex Services
echo "[*] Configuring Tailscale Serve ingress proxies..."

# 2.1 AMARA Matrix Dashboard (Port 8000)
tailscale serve --bg --yes --tcp 8000 127.0.0.1:8000

# 2.2 QuantumFlex Core API Gateway (Port 8080)
tailscale serve --bg --yes --tcp 8080 127.0.0.1:8080

# 2.3 QF-Bot & MCP SSE Endpoint (Port 9000)
tailscale serve --bg --yes --tcp 9000 127.0.0.1:9000

# 2.4 Mobile Cockpit HTTPS Gateway (Port 443 -> 9000)
tailscale serve --bg --yes 9000

echo
echo "════════════════════════════════════════════════════════════════"
echo "  QUANTUMFLEX MESH INGRESS ACTIVE"
echo "════════════════════════════════════════════════════════════════"
echo "  • AMARA Dashboard  : http://${TS_IP}:8000"
echo "  • API Gateway      : http://${TS_IP}:8080"
echo "  • QF-Bot / MCP SSE : http://${TS_IP}:9000"
echo "  • Mobile HTTPS HUD : https://${DNS_NAME}/"
echo "════════════════════════════════════════════════════════════════"
echo

tailscale serve status
