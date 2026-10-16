#!/usr/bin/env bash
# QuantumFlex Power & Lid Sleep Policy Setup Script
# Configures Ubuntu / GNOME and systemd-logind to never suspend on lid close.

set -euo pipefail

echo "======================================================================"
echo " QuantumFlex Node Power Policy: Lid Close Suspend Prevention"
echo "======================================================================"

# 1. Configure GNOME power settings for current user
echo "[1/3] Configuring GNOME Desktop power settings..."
if command -v gsettings &>/dev/null; then
    export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"
    gsettings set org.gnome.settings-daemon.plugins.power lid-close-ac-action 'nothing'
    gsettings set org.gnome.settings-daemon.plugins.power lid-close-battery-action 'nothing'
    gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'
    gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-battery-type 'nothing'
    echo "      GNOME lid-close-ac-action      : $(gsettings get org.gnome.settings-daemon.plugins.power lid-close-ac-action)"
    echo "      GNOME lid-close-battery-action : $(gsettings get org.gnome.settings-daemon.plugins.power lid-close-battery-action)"
    echo "      [+] GNOME desktop settings successfully applied."
else
    echo "      [!] gsettings command not found, skipping desktop config."
fi

# 2. Check / Start systemd user-level inhibitor guard
echo "[2/3] Checking QuantumFlex Lid Guard User Service..."
if systemctl --user is-active --quiet qf-lid-guard.service; then
    echo "      [+] qf-lid-guard.service is active and blocking lid sleep."
else
    echo "      Starting and enabling qf-lid-guard.service..."
    systemctl --user daemon-reload
    systemctl --user enable --now qf-lid-guard.service
    echo "      [+] qf-lid-guard.service started."
fi

# 3. Apply system-wide logind drop-in (requires root / sudo)
echo "[3/3] Checking system-wide /etc/systemd/logind.conf.d/ configuration..."
DROPIN_DIR="/etc/systemd/logind.conf.d"
DROPIN_FILE="$DROPIN_DIR/99-laptop-lid.conf"

if [[ $EUID -eq 0 ]]; then
    mkdir -p "$DROPIN_DIR"
    cat << 'EOF' > "$DROPIN_FILE"
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
EOF
    chmod 644 "$DROPIN_FILE"
    systemctl restart systemd-logind
    echo "      [+] System-wide logind drop-in installed: $DROPIN_FILE"
    echo "      [+] systemd-logind restarted."
else
    echo "      Note: To lock this in at the OS kernel/login manager level across reboots,"
    echo "      run the following command with sudo:"
    echo "      sudo bash $0"
fi

echo "======================================================================"
echo " Active Inhibitors Verification:"
systemd-inhibit --list --no-legend | grep -i lid || echo "      (Check systemd-inhibit list)"
echo "======================================================================"
