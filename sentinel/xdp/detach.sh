#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
    echo "This command requires root to detach eBPF programs from tailscale0."
    echo "Run: sudo $0"
    exit 1
fi

echo "[*] Detaching eBPF/XDP filter from tailscale0..."
ip link set dev tailscale0 xdpgeneric off
echo "[+] Successfully detached. Current interface state:"
ip link show dev tailscale0
