#!/bin/bash
set -e

TARGET_REPO=${1:-"https://github.com/eclipse/paho.mqtt.c.git"}
TARGET_DIR="/tmp/qf-target"

echo "[*] QuantumFlex Phase 1 Commercial Execution Harness"
echo "[*] Target: $TARGET_REPO"

# 1. Clean previous runs
rm -rf "$TARGET_DIR"
mkdir -p "$TARGET_DIR"

# 2. Clone target repository
echo "[*] Cloning target repository..."
git clone --depth 1 "$TARGET_REPO" "$TARGET_DIR"

# 3. Build Sandbox Image
echo "[*] Building Podman Sandbox Environment..."
podman build -t qf-audit-sandbox -f /home/quant/pqc-immune-daemon/mycelium/scripts/Containerfile.audit /home/quant/pqc-immune-daemon/mycelium/scripts/

# 4. Execute Audit in Container
echo "[*] Launching Sandbox Execution..."
podman run --rm \
    --network none \
    -v "$TARGET_DIR:/mnt/target:z" \
    -v "/home/quant/pqc-immune-daemon/mycelium/tools/qf_audit.py:/opt/quantum-flex/qf_audit.py:ro,z" \
    -v "/home/quant/pqc-immune-daemon/mycelium/pqc-immune-daemon/membrane_health.rego:/opt/quantum-flex/membrane_health.rego:ro,z" \
    qf-audit-sandbox

echo "[+] Audit completed. Artifacts are located at $TARGET_DIR/qf-audit-output"
