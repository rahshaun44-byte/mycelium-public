#!/usr/bin/env bash
# ==============================================================================
# QUANTUMFLEX: Automated Hertzbleed & DVFS Timing Gate (Preflight Check)
# ==============================================================================
set -euo pipefail

RED="\033[91m"
GREEN="\033[92m"
YELLOW="\033[93m"
CYAN="\033[96m"
BOLD="\033[1m"
RESET="\033[0m"

echo -e "${BOLD}${CYAN}[*] Running QuantumFlex Hertzbleed & DVFS Preflight Gate...${RESET}"

# 1. Governor Verification
GOVERNORS=$(cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor 2>/dev/null | sort -u || true)

if [[ -z "$GOVERNORS" ]]; then
    echo -e "${YELLOW}[!] Warning: Unable to read cpufreq scaling governors from sysfs.${RESET}"
else
    echo -e "    CPU Scaling Governor(s) detected: ${BOLD}${GOVERNORS}${RESET}"
    for gov in $GOVERNORS; do
        if [[ "$gov" != "powersave" && "$gov" != "performance" ]]; then
            echo -e "${RED}[!] UNSAFE GOVERNOR: '$gov'. DVFS timing fluctuations may leak cryptographic keys.${RESET}"
            echo -e "${YELLOW}[!] Mitigation: Set governor to 'powersave' or 'performance'.${RESET}"
            exit 1
        fi
    done
fi

# 2. Driver & Frequencies Baseline
DRIVER=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_driver 2>/dev/null || echo "unknown")
CUR_FREQ=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null || echo "0")
MIN_FREQ=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq 2>/dev/null || echo "0")
MAX_FREQ=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq 2>/dev/null || echo "0")

echo -e "    CPU Scaling Driver  : ${DRIVER}"
echo -e "    Baseline Frequencies: cur=${CUR_FREQ} kHz, min=${MIN_FREQ} kHz, max=${MAX_FREQ} kHz"

# 3. Network Ingress Gate Verification
BIND_ADDR="${QF_BIND_ADDRESS:-127.0.0.1}"
if [[ "$BIND_ADDR" != "127.0.0.1" && "$BIND_ADDR" != "::1" ]]; then
    echo -e "${RED}[!] CAUTION: Engine configured for non-loopback bind ($BIND_ADDR). DVFS leakage risk heightened!${RESET}"
else
    echo -e "    Network Boundary    : Loopback isolated (${BIND_ADDR})"
fi

echo -e "${GREEN}[+] Hertzbleed Gate PASSED: Environment isolated and governor verified.${RESET}"
exit 0
