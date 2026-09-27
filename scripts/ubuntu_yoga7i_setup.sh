#!/usr/bin/env bash
# ==============================================================================
# Script: ubuntu_yoga7i_setup.sh
# Target: Ubuntu 24.04 LTS on Lenovo Yoga 7i
# Purpose: Complete, idempotent bootstrap for QuantumFlex sovereign OS stack
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
    log_error "This setup script requires root privileges. Run with: sudo $0"
    exit 1
fi

TARGET_USER="${SUDO_USER:-$USER}"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

log_info "Initializing QuantumFlex Ubuntu setup for user: ${BOLD}${TARGET_USER}${NC} (${TARGET_HOME})"

# 1. System Package Updates & Repositories
log_info "Updating APT repositories..."
apt-get update -y

# Install essential dependencies
log_info "Installing core toolchains, libraries, and runtimes..."
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential \
    clang \
    llvm \
    cmake \
    ninja-build \
    pkg-config \
    libssl-dev \
    libpq-dev \
    libpqxx-dev \
    libsqlite3-dev \
    libsystemd-dev \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    git \
    curl \
    jq \
    htop \
    rsync \
    podman \
    uidmap \
    slirp4netns \
    pasta \
    fuse-overlayfs \
    firewalld \
    power-profiles-daemon \
    iio-sensor-proxy \
    ca-certificates

# Install Tailscale if not present
if ! command -v tailscale &>/dev/null; then
    log_info "Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
    systemctl enable --now tailscaled
fi

# Install Rust toolchain for TARGET_USER if missing
if ! sudo -u "$TARGET_USER" command -v cargo &>/dev/null; then
    log_info "Installing Rust toolchain for $TARGET_USER..."
    sudo -u "$TARGET_USER" curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sudo -u "$TARGET_USER" sh -s -- -y
fi

# 2. Kernel & BBR High-Speed Sysctl Tuning
log_info "Applying TCP BBR and high-speed network sysctl parameters..."
modprobe tcp_bbr || log_warn "tcp_bbr module probe completed"
echo "tcp_bbr" > /etc/modules-load.d/bbr.conf

local_sysctl="/etc/sysctl.d/99-quantumflex-network.conf"
if [[ -f "${SCRIPT_DIR}/99-quantumflex-network.conf" ]]; then
    cp "${SCRIPT_DIR}/99-quantumflex-network.conf" "$local_sysctl"
else
    cat <<'EOF' > "$local_sysctl"
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
EOF
fi
sysctl --system >/dev/null

# 3. Firewalld Zero-Trust Configuration (Preserving QF zone architecture)
log_info "Configuring firewalld mesh zone..."
systemctl enable --now firewalld
firewall-cmd --permanent --new-zone=qf-tailscale >/dev/null 2>&1 || true
firewall-cmd --permanent --zone=qf-tailscale --add-source=100.64.0.0/10 || true
firewall-cmd --permanent --zone=qf-tailscale --add-interface=tailscale0 || true
firewall-cmd --permanent --zone=qf-tailscale --add-port=443/tcp --add-port=8443/tcp --add-port=8000/tcp --add-port=8080/tcp --add-port=9000/tcp || true
firewall-cmd --reload >/dev/null || true

# 4. User lingering for 24/7 background systemd services
log_info "Enabling user lingering for ${TARGET_USER}..."
loginctl enable-linger "$TARGET_USER"

# 5. Rootless Podman Configuration for TARGET_USER
log_info "Ensuring rootless Podman subuid/subgid mapping..."
touch /etc/subuid /etc/subgid
if ! grep -q "^${TARGET_USER}:" /etc/subuid; then
    usermod --add-subuids 100000-165535 "$TARGET_USER"
fi
if ! grep -q "^${TARGET_USER}:" /etc/subgid; then
    usermod --add-subgids 100000-165535 "$TARGET_USER"
fi

# 6. Python Virtual Environment Setup
log_info "Building Python virtual environment..."
VENV_DIR="${REPO_ROOT}/venv"
if [[ ! -d "$VENV_DIR" ]]; then
    sudo -u "$TARGET_USER" python3 -m venv "$VENV_DIR"
fi

if [[ -f "${REPO_ROOT}/requirements.txt" ]]; then
    sudo -u "$TARGET_USER" "$VENV_DIR/bin/pip" install --upgrade pip
    sudo -u "$TARGET_USER" "$VENV_DIR/bin/pip" install -r "${REPO_ROOT}/requirements.txt"
fi

# 7. Compile Native C++ Evidence Engine
log_info "Compiling native C++ Evidence Engine & Genesis Tool..."
sudo -u "$TARGET_USER" bash -c "
  cd '$REPO_ROOT'
  cmake -S . -B build_check -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
  cmake --build build_check -j\$(nproc)
"

# 8. Compile Ghost Sink Anomaly Absorber
if [[ -d "${REPO_ROOT}/quantumflex-ghost-sink" ]]; then
    log_info "Compiling Rust Ghost Sink..."
    sudo -u "$TARGET_USER" bash -c "
      source \$HOME/.cargo/env 2>/dev/null || true
      cd '${REPO_ROOT}/quantumflex-ghost-sink'
      cargo build --release
    "
fi

log_success "════════════════════════════════════════════════════════════════"
log_success "  QUANTUMFLEX UBUNTU BOOTSTRAP COMPLETE"
log_success "  Run ./scripts/restore_quantumflex_node.sh to restore keys & DB."
log_success "════════════════════════════════════════════════════════════════"
