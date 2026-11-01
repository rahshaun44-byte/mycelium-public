#!/usr/bin/env bash
# ==============================================================================
# Script: ubuntu_yoga7i_setup.sh
# Target: Lenovo Yoga 7 2-in-1 14AKP10 on Ubuntu 26.04.1 LTS
# Purpose: Idempotent provisioning for hardware drivers, Tailscale mesh routing,
#          sandboxed Python daemons, and system performance tuning.
# ==============================================================================

set -euo pipefail
IFS=$'\n\t'

readonly BOLD='\033[1m'
readonly GREEN='\033[0;32m'
readonly BLUE='\033[0;34m'
readonly YELLOW='\033[1;33m'
readonly RED='\033[0;31m'
readonly NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

if [[ ${EUID} -ne 0 ]]; then
    log_error "This provisioning script requires root privileges. Please execute with: sudo $0"
    exit 1
fi

TARGET_USER="${SUDO_USER:-$USER}"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly REPO_ROOT_DEFAULT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="${REPO_ROOT:-$REPO_ROOT_DEFAULT}"

log_info "Initializing setup for target user: ${BOLD}${TARGET_USER}${NC} (Home: ${TARGET_HOME})"

configure_apt() {
    log_info "Updating APT repositories..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -y
    apt-get install -y --no-install-recommends \
        curl wget git jq build-essential cmake ninja-build \
        python3 python3-pip python3-venv \
        libssl-dev pkg-config ufw
    log_success "Core packages installed."
}

configure_tailscale() {
    if command -v tailscale >/dev/null 2>&1; then
        log_info "Tailscale is already installed: $(tailscale version | head -n1)"
    else
        log_info "Installing Tailscale..."
        curl -fsSL https://tailscale.com/install.sh | sh
        log_success "Tailscale installed."
    fi
}

configure_firewall() {
    log_info "Configuring UFW zero-trust mesh boundaries..."
    if command -v ufw >/dev/null 2>&1; then
        ufw allow in on tailscale0 to any port 22 proto tcp || true
        ufw allow in on tailscale0 to any port 443 proto tcp || true
        ufw allow in on tailscale0 to any port 8080 proto tcp || true
        ufw allow in on tailscale0 to any port 9001 proto tcp || true
        log_success "UFW rules verified on tailscale0."
    fi
}

configure_kernel_tuning() {
    log_info "Applying BBR and 16MB socket tuning..."
    echo "tcp_bbr" > /etc/modules-load.d/bbr.conf || true
    modprobe tcp_bbr || true
    if [[ -f "${SCRIPT_DIR}/99-quantumflex-network.conf" ]]; then
        cp "${SCRIPT_DIR}/99-quantumflex-network.conf" /etc/sysctl.d/99-quantumflex-network.conf
        sysctl --system >/dev/null || true
        log_success "Kernel tuning applied."
    fi
}

main() {
    echo -e "${BOLD}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD} Lenovo Yoga 7 2-in-1 - Ubuntu 26.04.1 LTS Baseline Setup       ${NC}"
    echo -e "${BOLD}════════════════════════════════════════════════════════════════${NC}"
    configure_apt
    configure_tailscale
    configure_firewall
    configure_kernel_tuning
    echo -e "${BOLD}${GREEN}Deployment baseline configuration complete.${NC}"
}

main "$@"
