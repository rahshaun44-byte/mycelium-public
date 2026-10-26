#!/usr/bin/env bash
# ==============================================================================
# QuantumFlex: Private Tailscale Mesh Service Publisher
# ==============================================================================
# Binds zero services to 0.0.0.0 or physical LAN.
# Publishes local loopback microservices over the encrypted Tailscale overlay
# with automated MagicDNS TLS certificates for mobile HUD & API endpoints.
# Run this saved file as a whole; do not paste its commands into a shell.
# ==============================================================================

set -euo pipefail

fail() {
    printf '[!] Error: %s\n' "$*" >&2
    exit 1
}

if ! TS_BIN="$(command -v "${TAILSCALE_BIN:-tailscale}")"; then
    fail "Tailscale CLI not found. Install it or set TAILSCALE_BIN to its executable path."
fi
command -v python3 >/dev/null || fail "python3 is required to verify Tailscale's JSON configuration."

configure_serve() {
    local label="$1" output
    shift
    if ! output="$("${TS_BIN}" serve --bg --yes "$@" 2>&1)"; then
        printf '[!] Error: Failed to configure %s.\n%s\n' "${label}" "${output}" >&2
        if [[ "${output,,}" == *"access denied"* || "${output,,}" == *"permission"* ]]; then
            printf '[!] Serve needs administrative permission. Re-run this saved script with sudo:\n' >&2
            printf '    sudo env TAILSCALE_BIN=%q bash %q\n' "${TS_BIN}" "${BASH_SOURCE[0]}" >&2
        fi
        printf '[!] Configuration stopped; some earlier mappings may already have been applied.\n' >&2
        exit 1
    fi
    printf '%s\n' "${output}"
}

# Validate the persisted ServeConfig schema used by Tailscale's status --json.
# https://github.com/tailscale/tailscale/blob/v1.104.1/ipn/serve.go
verify_serve() {
    python3 -c '
import json
import sys

def fail(message):
    sys.exit("[!] Error: " + message)

def object_field(config, key):
    value = config.get(key)
    if value is None:
        return {}
    if not isinstance(value, dict):
        fail("Invalid Serve configuration field: " + key)
    return value

try:
    config = json.load(sys.stdin)
except ValueError:
    fail("Invalid JSON in Tailscale Serve configuration.")
if not isinstance(config, dict):
    fail("Tailscale Serve configuration must be a JSON object.")

ports = {"443", "8000", "8080", "9000"}
def check_private(config):
    if not isinstance(config, dict):
        fail("Invalid foreground Serve configuration.")
    for target, enabled in object_field(config, "AllowFunnel").items():
        if enabled and target.rsplit(":", 1)[-1] in ports:
            fail("Funnel is enabled for " + target + "; disable it explicitly before publishing private ingress.")
    for foreground in object_field(config, "Foreground").values():
        check_private(foreground)

check_private(config)
if sys.argv[1] == "preflight":
    sys.exit(0)

tcp = object_field(config, "TCP")
for port in ("8000", "8080", "9000"):
    handler = tcp.get(port)
    if (not isinstance(handler, dict)
        or handler.get("TCPForward") != "127.0.0.1:" + port
        or any(handler.get(key) for key in ("HTTPS", "HTTP", "TerminateTLS", "ProxyProtocol"))):
        fail("Serve TCP :" + port + " is missing or does not forward raw TCP to 127.0.0.1:" + port + ".")
https = tcp.get("443")
if (not isinstance(https, dict) or https.get("HTTPS") is not True
    or https.get("HTTP") or https.get("TCPForward")):
    fail("Serve HTTPS :443 is missing or incorrectly configured.")
web = object_field(config, "Web").get(sys.argv[2] + ":443")
if not isinstance(web, dict):
    fail("Serve HTTPS :443 has no handler for this nodes MagicDNS name.")
handler = object_field(web, "Handlers").get("/")
if (not isinstance(handler, dict) or handler.get("Proxy") != "http://127.0.0.1:9000"
    or any(handler.get(key) for key in ("Path", "Text", "Redirect"))):
    fail("Serve HTTPS :443 / does not proxy to http://127.0.0.1:9000.")
for foreground in object_field(config, "Foreground").values():
    if ports.intersection(object_field(foreground, "TCP")):
        fail("Foreground Serve configuration overrides a QuantumFlex port; stop that foreground session first.")
' "$1" "${DNS_NAME}" <<< "$2"
}

echo "[*] Initializing QuantumFlex Private Tailscale Mesh Services..."

# 1. Read structured node state rather than treating a reachable daemon as Running.
# Keep stderr separate: client/daemon version warnings are not JSON.
if ! TS_STATUS_JSON="$("${TS_BIN}" status --json)"; then
    fail "Tailscale is not running or accessible."
fi
if ! TS_NODE_INFO="$(python3 -c '
import ipaddress
import json
import re
import sys

def fail(message):
    sys.exit("[!] Error: " + message)

try:
    status = json.load(sys.stdin)
except ValueError:
    fail("Invalid JSON in Tailscale node status.")
if not isinstance(status, dict):
    fail("Tailscale node status must be a JSON object.")
if status.get("BackendState") != "Running":
    fail("Tailscale is not Running (state: " + str(status.get("BackendState")) + ").")
node = status.get("Self")
if not isinstance(node, dict):
    fail("Tailscale node status has no Self information.")
dns = node.get("DNSName")
if not isinstance(dns, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]*", dns):
    fail("Failed to obtain a valid Tailscale MagicDNS name.")
addresses = node.get("TailscaleIPs")
if not isinstance(addresses, list):
    fail("Failed to obtain Tailscale IPv4 address.")
for address in addresses:
    try:
        ip = ipaddress.IPv4Address(address)
    except (ValueError, TypeError):
        continue
    print(ip)
    print(dns.rstrip("."))
    break
else:
    fail("Failed to obtain Tailscale IPv4 address.")
' <<< "${TS_STATUS_JSON}")"; then
    exit 1
fi
TS_IP="${TS_NODE_INFO%%$'\n'*}"
DNS_NAME="${TS_NODE_INFO#*$'\n'}"

echo "[+] Node Tailscale IP: ${TS_IP}"
echo "[+] Node MagicDNS:    ${DNS_NAME}"

# Refuse to silently change existing public exposure on the requested ports.
if ! TS_SERVE_JSON="$("${TS_BIN}" serve status --json)"; then
    fail "Unable to read the existing Tailscale Serve configuration."
fi
verify_serve preflight "${TS_SERVE_JSON}" || exit 1

# 2. Configure Tailscale Serve for QuantumFlex Services
echo "[*] Configuring Tailscale Serve ingress proxies..."

# 2.1 AMARA Matrix Dashboard (Port 8000)
configure_serve "AMARA Dashboard TCP :8000" --tcp 8000 127.0.0.1:8000

# 2.2 QuantumFlex Core API Gateway (Port 8080)
configure_serve "API Gateway TCP :8080" --tcp 8080 127.0.0.1:8080

# 2.3 QF-Bot & MCP SSE Endpoint (Port 9000)
configure_serve "QF-Bot / MCP TCP :9000" --tcp 9000 127.0.0.1:9000

# 2.4 Mobile Cockpit HTTPS Gateway (Port 443 -> 9001)
configure_serve "Mobile HTTPS HUD :443" --https 443 http://127.0.0.1:9001

# 3. Independently read back every mapping and its private-only exposure.
echo "[*] Verifying private Tailscale Serve ingress configuration..."
if ! TS_SERVE_JSON="$("${TS_BIN}" serve status --json)"; then
    fail "Unable to read back the Tailscale Serve configuration."
fi
verify_serve configured "${TS_SERVE_JSON}" || exit 1
"${TS_BIN}" serve status || fail "Unable to display verified Tailscale Serve status."

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
