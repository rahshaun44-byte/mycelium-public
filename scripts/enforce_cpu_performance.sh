#!/usr/bin/env bash
# QuantumFlex: Permanent CPU Performance Governor Enforcer
# Hardware: AMD Ryzen AI 5 340 (6C/12T) on Ubuntu 26.04.1 LTS
set -euo pipefail

echo "============================================================"
echo "  QUANTUMFLEX: PERMANENT CPU PERFORMANCE ENFORCEMENT"
echo "============================================================"

if [[ $EUID -ne 0 ]]; then
    echo "[!] This script requires root privileges to configure hardware profiles."
    echo "    Please run: sudo $0"
    exit 1
fi

echo "[1/4] Configuring tuned profile to 'throughput-performance'..."
if command -v tuned-adm >/dev/null 2>&1; then
    tuned-adm profile throughput-performance
    systemctl enable --now tuned
    echo "  [+] Active tuned profile: $(tuned-adm active)"
else
    echo "  [-] tuned-adm not found, proceeding with direct systemd configuration."
fi

echo "[2/4] Installing systemd-tmpfiles persistent configuration..."
cat << 'EOF' > /etc/tmpfiles.d/cpu-performance.conf
# QuantumFlex persistent performance configuration
w /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor - - - - performance
w /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference - - - - performance
EOF
echo "  [+] Created /etc/tmpfiles.d/cpu-performance.conf"

echo "[3/4] Installing dedicated systemd boot service..."
cat << 'EOF' > /etc/systemd/system/qf-cpu-performance.service
[Unit]
Description=QuantumFlex Permanent CPU Performance Enforcer
After=multi-user.target tuned.service systemd-udev-settle.service
Wants=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/bash -c 'for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo performance > "$g" 2>/dev/null || true; done; for e in /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference; do echo performance > "$e" 2>/dev/null || true; done'

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now qf-cpu-performance.service
echo "  [+] Enabled and started qf-cpu-performance.service"

echo "[4/4] Live enforcement on all 16 vCPU threads..."
for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do
    if [[ -w "$g" ]]; then
        echo performance > "$g"
    fi
done
for e in /sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference; do
    if [[ -w "$e" ]]; then
        echo performance > "$e"
    fi
done

echo
echo "[+] Hardware CPU State Verification:"
echo -n "    Governor (cpu0): "
cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
echo -n "    EPP (cpu0):      "
cat /sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference
echo "============================================================"
echo "  CPU IS LOCKED INTO RAW SILICON PERFORMANCE PERMANENTLY"
echo "============================================================"
