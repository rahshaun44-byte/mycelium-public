# Fedora 44 Yoga Primary Node — Dual-Role Technical Handoff

**Verified:** 2026-09-11 against the live Yoga (`user quant`, kernel `7.2.4-200.fc44.x86_64`).

## Scope

This node already runs Quantum Flex as a **single operator account**: `quant`. Dual-role (`student` vs a dedicated ops login) is an **optional overlay**, not the current runtime.

1. **Live ops (accepted today):** systemd **user** services under `quant`, repo at `/home/quant/mycelium`.
2. **Optional academic overlay:** login `student` plus a **non-system** ops login `qf-operator`. Never reuse the reserved Linux account `operator` (uid 11, `nologin`, home `/root` on this host).

Repository source of truth:

- `/home/quant/mycelium`

Primary provisioning entrypoint (optional overlay / fresh box only):

- `/home/quant/mycelium/scripts/fedora_yoga7i_setup.sh`

Do **not** run that script against this Yoga as a Day-1 bootstrap. It is not a GitHub Actions checkout; `REPO_ROOT` must be the real repo (the script now defaults to the directory that contains `scripts/`).

---

## 1. Live baseline (this host)

### 1.1 What is actually running

| Item | Live truth |
|---|---|
| Interactive user | `quant` (uid 1000), linger enabled |
| Repo | `/home/quant/mycelium` |
| Engine | `quantum-flex-engine-mycelium.service` → `127.0.0.1:9444` mTLS |
| Engine data | `~/.local/share/quantum-flex-mycelium` |
| Postgres | Podman `amara-matrix` → `127.0.0.1:5432` |
| OPA | `opa-immune.service` → `127.0.0.1:8181` |
| Tailscale | `tailscaled` active; `tailscale0` in firewalld zone `qf-tailscale` |
| Application binds | Loopback only (`127.0.0.1`). Remote access is Tailscale Serve, not LAN `0.0.0.0`. |
| Dual-role users | **`student` does not exist.** System `operator` (uid 11) is **not** the QF ops profile. |
| `mesh-daemon.service` / `pyworker` | **Not installed** |
| School launcher / backup timer | **Not installed** |

### 1.2 Provisioning script capabilities (repo, not yet applied as dual-role)

`scripts/fedora_yoga7i_setup.sh` can still:

- Fedora packages / DNF (or rpm-ostree layering)
- Yoga hardware prep (`iio-sensor-proxy`, power-profile daemon, battery conservation, yoga audio modprobe)
- Tailscale + forwarding + firewalld `qf-tailscale` zone
- Role overlay: `student` + `qf-operator` (override with `OPERATOR_USER`; refuses uid &lt; 1000 collisions)
- School dirs, `qf-school-focus`, `qf-school-session`, `qf-role-modes.sh`, school backup timer
- Optional `pyworker` / `/opt/daemons` / `mesh-daemon.service` scaffold
- Podman harness: `/usr/local/share/mesh-test-harness/run_route_test.sh`

### 1.3 Runtime stack map (repo on this host)

- Sentinel: `/home/quant/mycelium/sentinel`
- Dashboard/monitor: `/home/quant/mycelium/amara`
- RAG/swarm/orchestration: `/home/quant/mycelium/mcp_layer`
- Gateway API: `/home/quant/mycelium/api_node`
- C++ engine: `/home/quant/mycelium/src`, `/home/quant/mycelium/include/quantum-flex`
- PQC immune daemon: `/home/quant/mycelium/pqc-immune-daemon/immune_daemon.py` (live unit also uses `/home/quant/pqc-immune-daemon/pqc-immune-daemon`)

---

## 2. DoD/OMB context (source clarification)

Planning/sales only — not runtime:

- `docs/CISO_DISCOVERY_DIAGNOSTIC_FRAMEWORK.md`
- `docs/QUANTUM_WEALTH_ELEVATION_STRATEGY.md`
- `sentinel/knowledge_base/OMB_M_26_15_CMMC_GUIDELINES.md`

---

## 3. Target operating model

### 3.1 Network

- Starlink Gen 4 in bypass mode
- Archer as primary router/NAT/firewall
- Tailscale as encrypted overlay control plane
- Application sockets on **loopback**; publish via Tailscale Serve when needed

### 3.2 Human-role boundary

- **Today:** `quant` is the operator.
- **If overlay is applied:** `student` = school-only; `qf-operator` = infrastructure (optional; do not collide with system `operator`).

### 3.3 Data model

- Live QF state: `~quant/.local/share/quantum-flex-mycelium`, `~quant/.local/state/quantum-flex-mycelium`
- Optional school root: `/home/student/School`
- Optional overlay ops root: `/home/qf-operator/Projects`

---

## 4. Day-0 to Day-3 (fresh install only)

Skip Day-0/Day-1 if this Yoga is already running Fedora 44 + QF under `quant`.

### Day-0: Pre-migration capture

1. Export irreplaceable data.
2. Record LAN subnet, gateway, DHCP reservations.
3. Store credentials in a vault (not git).
4. Confirm Fedora installer media + checksum.

### Day-1: Base OS and bootstrap

1. Install Fedora 44 with full disk encryption.
2. Clone this repository to `/home/<login>/mycelium` (not a CI runner path).
3. Provision **after** setting `REPO_ROOT` if needed:

   ```bash
   sudo REPO_ROOT=/home/quant/mycelium bash /home/quant/mycelium/scripts/fedora_yoga7i_setup.sh
   ```

4. Authenticate Tailscale:

   ```bash
   sudo tailscale up --ssh --accept-routes
   ```

### Day-2: Verification

Always (this host):

```bash
systemctl status iio-sensor-proxy.service
systemctl status tailscaled.service
firewall-cmd --zone=qf-tailscale --list-interfaces
sysctl net.ipv4.ip_forward net.ipv6.conf.all.forwarding
systemctl --user status quantum-flex-engine-mycelium opa-immune amara-dashboard api-node athena-node
ss -lntH | awk '$4 ~ /127\.0\.0\.1:(8000|8001|8080|8181|9000|9050|9444|5432)$/'
```

Optional dual-role overlay only:

```bash
sudo systemctl status mesh-daemon.service
systemctl status student-school-backup.timer
/usr/local/share/mesh-test-harness/run_route_test.sh
su - student -c 'school-mode'
su - qf-operator -c 'ops-mode'
```

`power-profiles-daemon` / `tuned-ppd` may be inactive; do not fail the live host solely on that gate.

### Day-3: Stack activation

1. Start Python control-plane user units (OPA first, then immune daemon, dashboard, Athena, API).
2. Health-check on `127.0.0.1`, then Tailscale Serve if remote access is required.
3. Start `quantum-flex-engine-mycelium`, then unlock over mTLS (`scripts/unlock_engine.sh`).
4. Snapshot unit status and `ss` output.

---

## 5. Operational commands (optional overlay)

```bash
su - student
school-mode
qf-school-focus on

su - qf-operator
ops-mode

sudo -u student /usr/local/bin/school-backup
```

Live QF control plane (this host):

```bash
systemctl --user start opa-immune immune-daemon amara-matrix amara-dashboard athena-node api-node
systemctl --user start quantum-flex-engine-mycelium
/home/quant/mycelium/scripts/unlock_engine.sh
```

---

## 6. Risk and rollback

- Do not apply dual-role provisioning onto the live `quant` stack without a backup.
- Do not name the ops user `operator` on Fedora (reserved system account).
- Keep Tailscale route advertisement minimal until verified.
- Promote C++ engine only after OPA + Python loopback health.

---

## 7. Acceptance criteria

### 7.1 Live host (current) — accepted when

1. `quant` linger is on and `/home/quant/mycelium` is the repo.
2. QF application listeners are `127.0.0.1` only (see `docs/port-inventory.md`).
3. `tailscale0` is in `qf-tailscale`; `tailscaled` is active.
4. Engine is on `127.0.0.1:9444` and can be unsealed over mTLS.
5. Python control plane (OPA, dashboard, Athena, API) answers on loopback.

### 7.2 Dual-role overlay — accepted only when additionally

1. `student` and `qf-operator` exist with isolated homes (and system `operator` is untouched).
2. School launcher, focus utility, and backup timer function.
3. `mesh-daemon.service` runs under `pyworker` if that scaffold is installed.
4. Podman harness succeeds on an isolated bridge.
