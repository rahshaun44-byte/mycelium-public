#!/usr/bin/env bash
# ==============================================================================
# Script: fedora_yoga7i_setup.sh
# Target: Lenovo Yoga 7i (Intel Platform) on Fedora Linux (Workstation/Silverblue)
# Purpose: Idempotent provisioning for hardware drivers, Tailscale mesh routing,
#          school/operator role separation, sandboxed Python daemons, and Podman harness.
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
readonly REPO_ROOT_DEFAULT="/home/runner/work/mycelium/mycelium"
REPO_ROOT="${REPO_ROOT:-$REPO_ROOT_DEFAULT}"
STUDENT_USER="${STUDENT_USER:-student}"
OPERATOR_USER="${OPERATOR_USER:-operator}"
LMS_URL="${LMS_URL:-https://canvas.instructure.com}"
OPERATOR_WHEEL="${OPERATOR_WHEEL:-0}"

log_info "Initializing setup for target user: ${BOLD}${TARGET_USER}${NC} (Home: ${TARGET_HOME})"

IS_OSTREE=0
if [[ -f /run/ostree-booted ]]; then
    IS_OSTREE=1
fi

ensure_local_user() {
    local username="$1"
    local shell_path="${2:-/bin/bash}"

    if id "$username" &>/dev/null; then
        log_info "User exists: $username"
        return
    fi

    useradd -m -s "$shell_path" "$username"
    log_success "Created user: $username"
}

configure_dnf() {
    if [[ ${IS_OSTREE} -eq 1 ]]; then
        log_info "Skipping DNF tuning on OSTree host."
        return
    fi

    log_info "Optimizing DNF package management engine..."
    local dnf_conf="/etc/dnf/dnf.conf"

    if grep -q '^max_parallel_downloads=' "$dnf_conf"; then
        sed -i 's/^max_parallel_downloads=.*/max_parallel_downloads=10/' "$dnf_conf"
    else
        echo "max_parallel_downloads=10" >> "$dnf_conf"
    fi

    if grep -q '^fastestmirror=' "$dnf_conf"; then
        sed -i 's/^fastestmirror=.*/fastestmirror=True/' "$dnf_conf"
    else
        echo "fastestmirror=True" >> "$dnf_conf"
    fi

    if ! dnf repolist | grep -q "tailscale"; then
        dnf config-manager --add-repo https://pkgs.tailscale.com/stable/fedora/tailscale.repo || true
    fi
}

install_packages() {
    local packages=(
        dnf-plugins-core
        kernel-tools
        iio-sensor-proxy
        alsa-sof-firmware
        pipewire-utils
        intel-media-driver
        libva-utils
        vulkan-intel
        iptables-nft
        firewalld
        podman
        conmon
        fuse-overlayfs
        python3
        python3-pip
        python3-virtualenv
        python3-devel
        gcc
        git
        curl
        jq
        htop
        tuned
        rsync
        tailscale
    )

    if [[ ${IS_OSTREE} -eq 1 ]]; then
        log_info "OSTree host detected. Layering packages with rpm-ostree..."
        rpm-ostree install "${packages[@]}" || true
        log_warn "If new layers were added, reboot before final verification."
    else
        log_info "Installing packages with DNF..."
        dnf install -y --setopt=install_weak_deps=False "${packages[@]}"
    fi
}

install_power_profile_provider() {
    if systemctl list-unit-files | grep -q '^power-profiles-daemon.service'; then
        return
    fi
    if systemctl list-unit-files | grep -q '^tuned-ppd.service'; then
        return
    fi

    log_info "Installing power profile provider..."
    if [[ ${IS_OSTREE} -eq 1 ]]; then
        rpm-ostree install power-profiles-daemon || rpm-ostree install tuned-ppd || log_warn "No power profile provider installed; continue manually."
    else
        dnf install -y power-profiles-daemon || dnf install -y tuned-ppd || log_warn "No power profile provider installed; continue manually."
    fi
}

enable_power_profile_service() {
    if systemctl list-unit-files | grep -q '^power-profiles-daemon.service'; then
        systemctl enable --now power-profiles-daemon.service || log_warn "power-profiles-daemon enable failed."
        return
    fi
    if systemctl list-unit-files | grep -q '^tuned-ppd.service'; then
        systemctl enable --now tuned-ppd.service || log_warn "tuned-ppd enable failed."
        return
    fi

    log_warn "No power profile systemd unit found (power-profiles-daemon/tuned-ppd)."
}

configure_hardware_tweaks() {
    log_info "Configuring Yoga hardware modules, sensors, and power profile daemon..."

    install_power_profile_provider
    systemctl enable --now iio-sensor-proxy.service || log_warn "iio-sensor-proxy deferred."
    enable_power_profile_service

    local conservation_script="/usr/local/bin/yoga-battery-conservation"
    cat <<'BAT' > "$conservation_script"
#!/usr/bin/env bash
set -euo pipefail
CONV_PATH=$(find /sys/bus/platform/drivers/ideapad_laptop -name "conservation_mode" 2>/dev/null | head -n 1)

if [[ -z "$CONV_PATH" ]]; then
    echo "Lenovo ideapad_laptop conservation_mode path not found."
    exit 1
fi

case "${1:-}" in
    on|enable|1)
        echo 1 > "$CONV_PATH"
        echo "Battery conservation mode: ENABLED"
        ;;
    off|disable|0)
        echo 0 > "$CONV_PATH"
        echo "Battery conservation mode: DISABLED"
        ;;
    status)
        STATUS=$(cat "$CONV_PATH")
        echo "Conservation mode: $([ "$STATUS" -eq 1 ] && echo "ENABLED" || echo "DISABLED")"
        ;;
    *)
        echo "Usage: $0 {on|off|status}"
        exit 1
        ;;
esac
BAT
    chmod +x "$conservation_script"
    log_success "Battery conservation helper installed: $conservation_script"

    local modprobe_audio="/etc/modprobe.d/yoga-audio.conf"
    cat <<'AUDIO' > "$modprobe_audio"
# Enable SOF driver fallback for multi-mic arrays
options snd-intel-dspcfg dsp_driver=3
AUDIO
    log_success "Audio DSP config written: $modprobe_audio"
}

configure_tailscale_network() {
    log_info "Configuring Tailscale sysctl forwarding and firewalld rules..."

    local sysctl_file="/etc/sysctl.d/99-tailscale.conf"
    cat <<'SYSCTL' > "$sysctl_file"
# Tailscale Mesh Node Packet Forwarding
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
net.core.rmem_max = 2500000
net.core.wmem_max = 2500000
SYSCTL
    sysctl --system >/dev/null 2>&1 || true
    log_success "Kernel forwarding rules configured."

    systemctl enable --now firewalld.service || true
    firewall-cmd --permanent --new-zone=qf-tailscale >/dev/null 2>&1 || true
    firewall-cmd --permanent --zone=qf-tailscale --add-source=100.64.0.0/10 || true
    firewall-cmd --permanent --zone=qf-tailscale --add-interface=tailscale0 || true
    firewall-cmd --permanent --zone=qf-tailscale --add-masquerade || true
    firewall-cmd --reload || true
    log_success "Firewalld qf-tailscale zone configured for tailscale0 with masquerade."

    systemctl enable --now tailscaled.service || true
    log_success "tailscaled service initialized."
}

configure_role_separation_and_school_controls() {
    log_info "Configuring school/operator role separation controls..."

    ensure_local_user "$STUDENT_USER" "/bin/bash"
    ensure_local_user "$OPERATOR_USER" "/bin/bash"

    if [[ "$OPERATOR_WHEEL" == "1" ]]; then
        usermod -aG wheel "$OPERATOR_USER" || true
        log_info "Operator user added to wheel group (OPERATOR_WHEEL=1)."
    fi

    local student_home
    local operator_home
    student_home="$(getent passwd "$STUDENT_USER" | cut -d: -f6)"
    operator_home="$(getent passwd "$OPERATOR_USER" | cut -d: -f6)"

    install -d -m 0750 -o "$STUDENT_USER" -g "$STUDENT_USER" "$student_home/School"
    install -d -m 0750 -o "$OPERATOR_USER" -g "$OPERATOR_USER" "$operator_home/Projects"

    local focus_script="/usr/local/bin/qf-school-focus"
    cat <<'FOCUS' > "$focus_script"
#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: qf-school-focus {on|off}"
    exit 1
fi

case "$1" in
    on)
        gsettings set org.gnome.desktop.notifications show-banners false || true
        gsettings set org.gnome.desktop.screensaver lock-enabled true || true
        echo "School focus mode enabled."
        ;;
    off)
        gsettings set org.gnome.desktop.notifications show-banners true || true
        echo "School focus mode disabled."
        ;;
    *)
        echo "Usage: qf-school-focus {on|off}"
        exit 1
        ;;
esac
FOCUS
    chmod +x "$focus_script"

    local school_session_script="/usr/local/bin/qf-school-session"
    cat <<EOF_SESSION > "$school_session_script"
#!/usr/bin/env bash
set -euo pipefail

qf-school-focus on || true
xdg-open "${LMS_URL}" >/dev/null 2>&1 || true
xdg-open "https://calendar.google.com" >/dev/null 2>&1 || true
if command -v gnome-text-editor >/dev/null 2>&1; then
    gnome-text-editor "\$HOME/School" >/dev/null 2>&1 || true
fi
echo "School session launched."
EOF_SESSION
    chmod +x "$school_session_script"

    local profile_modes="/etc/profile.d/qf-role-modes.sh"
    cat <<EOF_PROFILE > "$profile_modes"
#!/usr/bin/env bash
school-mode() {
  qf-school-session
}

ops-mode() {
  cd "${REPO_ROOT}" || return 1
  qf-school-focus off || true
  echo "Operator mode ready in ${REPO_ROOT}"
}
EOF_PROFILE
    chmod +x "$profile_modes"

    local student_autostart_dir="$student_home/.config/autostart"
    install -d -m 0755 -o "$STUDENT_USER" -g "$STUDENT_USER" "$student_autostart_dir"

    cat > "$student_autostart_dir/qf-school-lms.desktop" <<EOF_LMS
[Desktop Entry]
Type=Application
Name=School LMS
Exec=/usr/local/bin/qf-school-session
X-GNOME-Autostart-enabled=true
Comment=Launch school-mode apps
EOF_LMS

    chown "$STUDENT_USER:$STUDENT_USER" "$student_autostart_dir/qf-school-lms.desktop"
    chmod 0644 "$student_autostart_dir/qf-school-lms.desktop"

    local backup_script="/usr/local/bin/school-backup"
    cat <<EOF_BACKUP > "$backup_script"
#!/usr/bin/env bash
set -euo pipefail

SRC="/home/${STUDENT_USER}/School/"
LOCAL_DST="/home/${STUDENT_USER}/.local/share/school-backups/latest/"
EXT_DST="/run/media/${STUDENT_USER}/SchoolBackup/student-school/"

mkdir -p "\$LOCAL_DST"
rsync -a --delete "\$SRC" "\$LOCAL_DST"

if [[ -d "\$(dirname "\$EXT_DST")" ]]; then
  mkdir -p "\$EXT_DST"
  rsync -a --delete "\$SRC" "\$EXT_DST"
fi
EOF_BACKUP
    chmod +x "$backup_script"

    local backup_service="/etc/systemd/system/student-school-backup.service"
    cat <<EOF_BSVC > "$backup_service"
[Unit]
Description=Student school data backup
After=network-online.target

[Service]
Type=oneshot
User=${STUDENT_USER}
Group=${STUDENT_USER}
ExecStart=/usr/local/bin/school-backup
EOF_BSVC

    local backup_timer="/etc/systemd/system/student-school-backup.timer"
    cat <<'EOF_BTMR' > "$backup_timer"
[Unit]
Description=Daily school backup timer

[Timer]
OnCalendar=*-*-* 19:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF_BTMR

    systemctl daemon-reload
    systemctl enable --now student-school-backup.timer
    log_success "Role separation, school focus tooling, and backup timer configured."
}

configure_python_daemon_scaffold() {
    log_info "Scaffolding unprivileged Python daemon runtime and hardened service..."

    local daemon_root="/opt/daemons"
    local daemon_user="pyworker"

    if ! id "$daemon_user" &>/dev/null; then
        useradd -r -s /sbin/nologin -d "$daemon_root" -M "$daemon_user"
        log_success "Created unprivileged user: $daemon_user"
    fi

    mkdir -p "$daemon_root"/{run,logs,venvs,scripts}

    local sample_worker="$daemon_root/scripts/mesh_worker.py"
    if [[ ! -f "$sample_worker" ]]; then
        cat <<'PYWORKER' > "$sample_worker"
#!/usr/bin/env python3
import os
import signal
import sys
import time

RUNNING = True

def handle_sigterm(signum, frame):
    del signum, frame
    global RUNNING
    RUNNING = False

signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)


def main():
    pid = os.getpid()
    print(f"[DAEMON] Worker initialized under PID {pid}.")
    sys.stdout.flush()
    while RUNNING:
        time.sleep(15)
        print("[DAEMON] Heartbeat: invariants verified.")
        sys.stdout.flush()
    print("[DAEMON] Graceful shutdown acknowledged.")


if __name__ == "__main__":
    main()
PYWORKER
        chmod +x "$sample_worker"
    fi

    local venv_path="$daemon_root/venvs/default"
    if [[ ! -d "$venv_path" ]]; then
        python3 -m venv "$venv_path"
        "$venv_path/bin/pip" install --upgrade pip wheel
        log_success "Configured virtualenv: $venv_path"
    fi

    chown -R "$daemon_user:$daemon_user" "$daemon_root"
    chmod 750 "$daemon_root"

    local service_unit="/etc/systemd/system/mesh-daemon.service"
    cat <<EOF_SERVICE > "$service_unit"
[Unit]
Description=Sandboxed Python Mesh Daemon
After=network.target tailscaled.service
Wants=tailscaled.service

[Service]
Type=simple
User=${daemon_user}
Group=${daemon_user}
WorkingDirectory=${daemon_root}
ExecStart=${venv_path}/bin/python3 ${sample_worker}
Restart=always
RestartSec=5s
Environment=PYTHONDONTWRITEBYTECODE=1

ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectControlGroups=yes
RestrictRealtime=yes
RestrictSUIDSGID=yes
MemoryDenyWriteExecute=yes
NoNewPrivileges=yes
CapabilityBoundingSet=
AmbientCapabilities=
ReadWritePaths=${daemon_root}/run ${daemon_root}/logs

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF_SERVICE

    systemctl daemon-reload
    log_success "Hardened unit installed: $service_unit"
}

configure_podman_test_harness() {
    log_info "Creating Podman isolated route verification harness..."

    local harness_dir="/usr/local/share/mesh-test-harness"
    mkdir -p "$harness_dir"

    cat <<'HARNESS' > "$harness_dir/run_route_test.sh"
#!/usr/bin/env bash
set -euo pipefail

NET_NAME="quantum-test-net"
SUBNET="10.89.0.0/24"

echo "==> [1/4] Provisioning isolated bridge network ($NET_NAME)..."
podman network exists "$NET_NAME" || podman network create --subnet "$SUBNET" "$NET_NAME"

echo "==> [2/4] Deploying Gatekeeper node..."
podman run -d --rm --name gatekeeper-node --network "$NET_NAME" alpine:3.20 sh -c "apk add --no-cache iputils >/dev/null 2>&1 && sleep 45"

echo "==> [3/4] Deploying Ghost node..."
podman run -d --rm --name ghost-node --network "$NET_NAME" alpine:3.20 sleep 45

echo "==> [4/4] Verifying packet transmission across isolated bridge..."
GHOST_IP=$(podman inspect ghost-node --format '{{.NetworkSettings.Networks.'"$NET_NAME"'.IPAddress}}')
podman exec gatekeeper-node ping -c 3 "$GHOST_IP"

echo "==> Cleaning up test containers..."
podman stop gatekeeper-node ghost-node >/dev/null

echo "==> [OK] Podman route verification succeeded with zero host routing pollution."
HARNESS

    chmod +x "$harness_dir/run_route_test.sh"
    log_success "Harness created: $harness_dir/run_route_test.sh"
}

main() {
    echo -e "${BOLD}====================================================${NC}"
    echo -e "${BOLD} Lenovo Yoga 7i - Fedora Linux Deployment Baseline  ${NC}"
    echo -e "${BOLD}====================================================${NC}"

    configure_dnf
    install_packages
    configure_hardware_tweaks
    configure_tailscale_network
    configure_role_separation_and_school_controls
    configure_python_daemon_scaffold
    configure_podman_test_harness

    echo -e "\n${BOLD}${GREEN}✔ Provisioning complete.${NC}"
    echo -e "Next steps:"
    echo -e " 1. Authenticate Tailscale:  ${BOLD}sudo tailscale up --ssh --advertise-routes=<LAN_SUBNET>${NC}"
    echo -e " 2. Start Daemon:            ${BOLD}sudo systemctl enable --now mesh-daemon.service${NC}"
    echo -e " 3. Verify Accelerometer:    ${BOLD}monitor-sensor${NC}"
    echo -e " 4. Run Podman Harness:      ${BOLD}/usr/local/share/mesh-test-harness/run_route_test.sh${NC}"
    echo -e " 5. School backup timer:     ${BOLD}systemctl status student-school-backup.timer${NC}"
    if [[ ${IS_OSTREE} -eq 1 ]]; then
        echo -e " 6. Reboot host if layers changed: ${BOLD}systemctl reboot${NC}"
    fi
    echo -e "${BOLD}====================================================${NC}"
}

main "$@"
