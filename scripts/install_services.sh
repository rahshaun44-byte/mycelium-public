#!/bin/bash
set -e

echo "[*] Auditing Systemd Services for Loopback Compliance..."
SERVICE_FILE="/home/quant/mycelium/systemd-backup/quantum-flex-engine-mycelium.service"

# Fail if 0.0.0.0 is found in the service definition
if grep -q "0.0.0.0" "$SERVICE_FILE"; then
    echo "[!] ERROR: Service file attempts to bind to 0.0.0.0. Autonomy requires loopback only."
    exit 1
fi

# Ensure 127.0.0.1 is strictly enforced
if ! grep -q "QF_BIND_ADDRESS=127.0.0.1" "$SERVICE_FILE"; then
    echo "[!] ERROR: Service file does not strictly bind to 127.0.0.1."
    exit 1
fi

echo "[+] Loopback compliance verified."

echo "[*] Enabling Systemd Linger for user 'quant'..."
loginctl enable-linger quant || echo "[!] Notice: loginctl failed. You may need to run this on the host."

echo "[*] Installing User Services..."
mkdir -p ~/.config/systemd/user/
cp "$SERVICE_FILE" ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now quantum-flex-engine-mycelium.service

echo "[+] QuantumFlex Engine autonomous execution initialized."
