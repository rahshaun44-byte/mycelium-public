#!/bin/bash
# Operator Policy File: Yoga Laptop Power & Sleep Policy
# This defines the operational sleep behavior for the QuantumFlex autonomous daemon.

echo "[*] Setting Laptop Lid and AC Power Policies for Autonomous Operation..."

# Explicitly ignore lid close events using a systemd drop-in configuration
sudo mkdir -p /etc/systemd/logind.conf.d/
sudo tee /etc/systemd/logind.conf.d/99-quantumflex-power.conf << 'EOF'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
EOF

# Apply the changes to the login daemon
sudo systemctl restart systemd-logind

echo "[+] Policy Applied: The machine will remain awake when the lid is closed."
