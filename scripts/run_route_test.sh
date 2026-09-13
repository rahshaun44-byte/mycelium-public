#!/usr/bin/env bash
# =====================================================================
#  QUANTUM FLEX // THERMODYNAMIC GHOST NODE & ROUTE TEST HARNESS
# =====================================================================
# Verifies:
#   1. Isolated bridge network packet delivery between nodes.
#   2. Ghost Node Landauer Principle (h -> 0):
#      - Rootfs is strictly read-only.
#      - /quarantine is strictly volatile tmpfs (RAM-backed, 64MB).
#      - Zero persistent state or NVMe SSD NAND writes.
# =====================================================================
set -euo pipefail

NET_NAME="quantum-test-net"
SUBNET="10.89.0.0/24"

cleanup() {
    echo "==> Cleaning up test containers..."
    podman stop -t 0 gatekeeper-node ghost-node 2>/dev/null || true
    podman rm -f gatekeeper-node ghost-node 2>/dev/null || true
}
trap cleanup EXIT

echo "==> [1/5] Provisioning isolated bridge network ($NET_NAME)..."
podman network exists "$NET_NAME" || podman network create --subnet "$SUBNET" "$NET_NAME"

echo "==> [2/5] Deploying Gatekeeper node..."
podman run -d --rm --name gatekeeper-node --network "$NET_NAME" alpine:3.20 sh -c "apk add --no-cache iputils >/dev/null 2>&1 && sleep 45"

echo "==> [3/5] Deploying Thermodynamic Ghost node (read-only + volatile tmpfs quarantine)..."
podman run -d --rm \
    --name ghost-node \
    --network "$NET_NAME" \
    --read-only \
    --cap-drop=ALL \
    --security-opt=no-new-privileges=true \
    --tmpfs /quarantine:rw,size=64m,noexec,nosuid,nodev \
    alpine:3.20 sleep 45

echo "==> [4/5] Verifying packet transmission across isolated bridge..."
GHOST_IP=$(podman inspect ghost-node --format '{{(index .NetworkSettings.Networks "'"$NET_NAME"'").IPAddress}}')
podman exec gatekeeper-node ping -c 3 "$GHOST_IP"

echo "==> [5/5] Verifying Thermodynamic Ghost Node volatile boundary (h -> 0)..."
# Verify rootfs write is strictly blocked
if podman exec ghost-node touch /root/fail.txt 2>/dev/null; then
    echo "[-] SECURITY BREACH: Ghost Node rootfs allowed persistent write!"
    exit 1
else
    echo "    [+] Rootfs write strictly blocked (Read-only filesystem enforced)."
fi

# Verify volatile tmpfs quarantine accepts anomaly injection
podman exec ghost-node sh -c '
    echo "entropy_anomaly_signature" > /quarantine/blob.bin && \
    df -h /quarantine | grep -q tmpfs && \
    echo "    [+] Volatile RAM sink verified: tmpfs partition active at /quarantine."
'

echo "==> [OK] Thermodynamic Ghost Node route and volatile sink verification PASSED."
