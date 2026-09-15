#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ${EUID} -ne 0 ]]; then
    echo "This command requires root to attach eBPF programs to tailscale0."
    echo "Run: sudo $0"
    exit 1
fi

echo "[*] Attaching eBPF/XDP filter to tailscale0 (generic mode)..."
ip link set dev tailscale0 xdpgeneric obj "$DIR/qf_ingress.o" sec xdp
echo "[+] Successfully attached. Current interface state:"
ip link show dev tailscale0
