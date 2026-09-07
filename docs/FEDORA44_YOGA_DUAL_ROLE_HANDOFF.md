# Fedora 44 Yoga Primary Node — Dual-Role Technical Handoff

## Scope
This handoff operationalizes a single Lenovo Yoga Fedora node for two non-conflicting roles:
1. Academic execution (`student` profile)
2. Quantum Flex engineering and security operations (`operator` profile)

Repository source of truth:
- `/home/runner/work/mycelium/mycelium`

Primary provisioning entrypoint:
- `/home/runner/work/mycelium/mycelium/scripts/fedora_yoga7i_setup.sh`

---

## 1. Implemented baseline in repository

### 1.1 Provisioning script capabilities
`/home/runner/work/mycelium/mycelium/scripts/fedora_yoga7i_setup.sh` now performs:
- Fedora package install and DNF optimization (or rpm-ostree layering on OSTree hosts)
- Lenovo Yoga hardware prep
  - `iio-sensor-proxy`
  - power profile service (`power-profiles-daemon` or `tuned-ppd`, host-dependent)
  - `/usr/local/bin/yoga-battery-conservation`
  - `/etc/modprobe.d/yoga-audio.conf`
- Tailscale + forwarding + firewalld `qf-tailscale` zone setup
- Role separation and school workflow controls
  - users: `student`, `operator`
  - optional operator sudo delegation only when `OPERATOR_WHEEL=1`
  - directories: `/home/student/School`, `/home/operator/Projects`
  - focus utility: `/usr/local/bin/qf-school-focus`
  - session launcher: `/usr/local/bin/qf-school-session`
  - shell mode functions: `/etc/profile.d/qf-role-modes.sh`
  - student autostart: `~student/.config/autostart/qf-school-lms.desktop`
  - backups: `/usr/local/bin/school-backup` + `student-school-backup.timer`
- Hardened daemon scaffold
  - unprivileged service user: `pyworker`
  - daemon root: `/opt/daemons`
  - unit: `/etc/systemd/system/mesh-daemon.service`
- Podman network verification harness
  - `/usr/local/share/mesh-test-harness/run_route_test.sh`

### 1.2 Runtime stack map (repo)
- Sentinel logic: `/home/runner/work/mycelium/mycelium/sentinel`
- Dashboard/monitor: `/home/runner/work/mycelium/mycelium/amara`
- RAG/swarm/orchestration: `/home/runner/work/mycelium/mycelium/mcp_layer`
- Gateway API: `/home/runner/work/mycelium/mycelium/api_node`
- C++ engine: `/home/runner/work/mycelium/mycelium/src`, `/home/runner/work/mycelium/mycelium/include/quantum-flex`
- PQC immune daemon: `/home/runner/work/mycelium/mycelium/pqc-immune-daemon/immune_daemon.py`

---

## 2. DoD/OMB context (source clarification)
DoD/OMB content appears in strategy and compliance documentation, including:
- `/home/runner/work/mycelium/mycelium/docs/CISO_DISCOVERY_DIAGNOSTIC_FRAMEWORK.md`
- `/home/runner/work/mycelium/mycelium/docs/AFWERX_SBIR_VOLUME_2_SLIDES_1_TO_5.md`
- `/home/runner/work/mycelium/mycelium/docs/QUANTUM_WEALTH_ELEVATION_STRATEGY.md`
- `/home/runner/work/mycelium/mycelium/sentinel/knowledge_base/OMB_M_26_15_CMMC_GUIDELINES.md`

This is positioning and planning context. Runtime implementation truth remains the code paths listed in section 1.

---

## 3. Target operating model

### 3.1 Network
- Starlink Gen 4 in bypass mode
- Archer as primary router/NAT/firewall
- Tailscale as encrypted overlay control plane

### 3.2 Human-role boundary
- `student`: school-only workspace and session launcher
- `operator`: infrastructure/development workspace

Boundary objective: no profile/tooling drift between academic and ops contexts.

### 3.3 Data model
- School data root: `/home/student/School`
- Operator data root: `/home/operator/Projects`
- Daily school backup timer with local and optional external sync targets

---

## 4. Day-0 to Day-3 deployment runbook

## Day-0: Pre-migration capture
1. Export irreplaceable data from current Yoga installation.
2. Record current network parameters (LAN subnet, gateway, DHCP reservation targets).
3. Save critical credentials in secure vault.
4. Confirm Fedora installer media availability and checksum verification.

## Day-1: Base OS install and bootstrap
1. Install Fedora 44 with full disk encryption.
2. Clone/pull this repository to Yoga.
3. Run baseline provisioning:
   ```bash
   sudo bash /home/runner/work/mycelium/mycelium/scripts/fedora_yoga7i_setup.sh
   ```
4. Authenticate Tailscale node:
   ```bash
   sudo tailscale up --ssh --accept-routes
   ```

## Day-2: Verification and hard acceptance
Run and pass all gates:
```bash
systemctl status iio-sensor-proxy.service
systemctl status power-profiles-daemon.service || systemctl status tuned-ppd.service
sysctl net.ipv4.ip_forward net.ipv6.conf.all.forwarding
firewall-cmd --zone=qf-tailscale --list-interfaces
systemctl status tailscaled.service
sudo systemctl status mesh-daemon.service
/usr/local/share/mesh-test-harness/run_route_test.sh
systemctl status student-school-backup.timer
```

Role-mode checks:
```bash
su - student -c 'school-mode'
su - operator -c 'ops-mode'
```

## Day-3: Stack activation and phased bring-up
1. Start Python control-plane services first.
2. Validate dashboard/API/RAG health on loopback and tailnet.
3. Add C++ engine services only after Python layer is stable.
4. Snapshot final system state and save validation output.

---

## 5. Operational commands

### 5.1 School mode and focus controls
```bash
su - student
school-mode
qf-school-focus on
```

### 5.2 Operator mode
```bash
su - operator
ops-mode
```

### 5.3 Backup run on demand
```bash
sudo -u student /usr/local/bin/school-backup
```

### 5.4 HP Pavilion hardware audit (remote)
```bash
ssh <hp-host> "free -h; lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,MODEL; lscpu | head -n 20"
```

---

## 6. Risk and rollback controls
- Stage activation by subsystem (network, roles, daemon, stack)
- Keep installer media and backup image available during first boot cycle
- Keep Tailscale route advertisement minimal until verified
- Promote components only after each acceptance gate passes

---

## 7. Acceptance criteria (final)
Deployment is accepted when all statements are true:
1. `student` and `operator` exist with isolated working roots.
2. School launcher, focus utility, and backup timer are functioning.
3. Tailscale + forwarding are active and `tailscale0` is bound to `qf-tailscale` with masquerade enabled.
4. `mesh-daemon.service` runs under `pyworker` with hardening controls.
5. Podman harness succeeds on isolated bridge network.
6. Python control-plane services start cleanly before C++ engine promotion.
