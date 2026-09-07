#!/bin/bash
# Operator Policy File: Yoga Laptop Power & Sleep Policy
# This defines the operational sleep behavior for the QuantumFlex autonomous daemon.

echo "[*] Setting Laptop Lid and AC Power Policies for Autonomous Operation..."

# Explicitly ignore lid close events so the daemon survives a closed laptop
echo "HandleLidSwitch=ignore" | sudo tee -a /etc/systemd/logind.conf > /dev/null
echo "HandleLidSwitchExternalPower=ignore" | sudo tee -a /etc/systemd/logind.conf > /dev/null
echo "HandleLidSwitchDocked=ignore" | sudo tee -a /etc/systemd/logind.conf > /dev/null

# Apply the changes to the login daemon
sudo systemctl restart systemd-logind

echo "[+] Policy Applied: The machine will remain awake when the lid is closed."
