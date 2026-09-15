#!/usr/bin/env bash
# Quantum Flex: publish the local HUD on the private Tailscale mesh only.
# The Python server stays on 127.0.0.1. Tailscale Serve adds a trusted
# HTTPS certificate for MagicDNS. This is not Funnel (no public internet).
set -euo pipefail

BOT_PORT="${QF_BOT_PORT:-9000}"

systemctl --user start qf-bot.service

tailscale serve --bg --yes "${BOT_PORT}"

DNS_NAME="$(tailscale status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"

echo
echo "[+] QF-Bot on 127.0.0.1:${BOT_PORT}"
echo "[+] Phone URL (tailnet HTTPS): https://${DNS_NAME}"
echo
tailscale serve status
