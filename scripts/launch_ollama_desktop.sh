#!/usr/bin/env bash
# ==============================================================================
# QuantumFlex Sovereign Neural Studio & Ollama Desktop Launcher
# ==============================================================================
# Invariant: Strictly enforces loopback boundary (127.0.0.1) across all AI daemons.
# ==============================================================================

set -euo pipefail

BOLD="\033[1m"
CYAN="\033[0;36m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
RED="\033[0;31m"
RESET="\033[0m"

echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════${RESET}"
echo -e "${BOLD}  QUANTUMFLEX NEURAL STUDIO & OLLAMA DESKTOP LAUNCHER${RESET}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════${RESET}"

# 1. Check Ollama System Service
echo -ne "  [1/4] Checking Ollama Daemon (:11434)... "
if ! curl -s -m 2 http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo -e "${YELLOW}Starting system service...${RESET}"
    sudo systemctl start ollama 2>/dev/null || systemctl start ollama 2>/dev/null || true
    sleep 1
fi

if curl -s -m 2 http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}ONLINE${RESET}"
else
    echo -e "${RED}FAILED${RESET}"
    echo -e "  ${RED}[!] Ollama service could not be reached on 127.0.0.1:11434.${RESET}"
    exit 1
fi

# 2. Enforce Loopback Security Invariant
echo -ne "  [2/4] Verifying Zero-Trust Loopback Boundary... "
BAD_BINDINGS=$(ss -tulpn | grep 11434 | grep -E "0\.0\.0\.0|\*:" || true)
if [ -n "$BAD_BINDINGS" ]; then
    echo -e "${RED}VIOLATION DETECTED!${RESET}"
    echo -e "  ${RED}[!] CRITICAL: Ollama is listening on a non-loopback interface!${RESET}"
    echo -e "  ${RED}    $BAD_BINDINGS${RESET}"
    echo -e "  ${RED}    Immediate hardstop. Re-bind OLLAMA_HOST to 127.0.0.1:11434.${RESET}"
    exit 1
else
    echo -e "${GREEN}VERIFIED (127.0.0.1 ONLY)${RESET}"
fi

# 3. Check QF-Bot Cockpit Server (:9000)
echo -ne "  [3/4] Checking QuantumFlex Cockpit Service (:9000)... "
if ! curl -s -m 2 http://127.0.0.1:9000/api/status > /dev/null 2>&1; then
    echo -ne "${YELLOW}Starting user service... ${RESET}"
    systemctl --user start qf-bot.service 2>/dev/null || true
    sleep 1
fi

if curl -s -m 2 http://127.0.0.1:9000/api/status > /dev/null 2>&1; then
    echo -e "${GREEN}ONLINE${RESET}"
else
    echo -e "${YELLOW}STARTING IN-PROCESS...${RESET}"
fi

# 4. Launch Desktop Studio
echo -e "  [4/4] Launching QuantumFlex Neural Studio Desktop Window..."
CHROME_BIN=$(which google-chrome 2>/dev/null || which chrome 2>/dev/null || which chromium 2>/dev/null || true)
PROFILE_DIR="${HOME}/.config/quantumflex/chrome-cockpit"
mkdir -p "${PROFILE_DIR}"

if [ -n "${CHROME_BIN}" ]; then
    # Launch in standalone application mode (no address bar, feels like native app)
    "${CHROME_BIN}" \
        --app="http://127.0.0.1:9000" \
        --user-data-dir="${PROFILE_DIR}" \
        --class="QuantumFlexNeuralStudio" \
        --name="QuantumFlex Neural Studio" \
        > /dev/null 2>&1 &
    disown
    echo -e "  ${GREEN}[+] Desktop Studio launched via Chrome App Mode.${RESET}"
else
    # Fallback to default browser
    xdg-open "http://127.0.0.1:9000" > /dev/null 2>&1 &
    disown
    echo -e "  ${GREEN}[+] Desktop Studio opened in default browser.${RESET}"
fi

echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════${RESET}"
echo -e "  ${BOLD}Active Ollama Models:${RESET}"
ollama list | sed 's/^/    /'
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════════${RESET}"
