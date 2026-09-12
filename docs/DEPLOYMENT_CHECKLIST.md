# QuantumFlex Release-Quality Deployment Checklist

This checklist defines mandatory preflight, provisioning, key management, and incident response procedures before promoting a QuantumFlex Alpha Node to production.

---

## 1. Cryptographic Preflight & Environment Isolation

- [ ] **CPU Frequency Scaling Verification**:
  - NOTE: `scripts/hertzbleed-gate.sh` does not exist yet — check manually until it is written.
  - Confirm governor posture: `cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor` (this host is `powersave` by default; DVFS leakage is only a concern if the engine is ever exposed beyond loopback).
  - Record baseline frequencies: `cur_freq`, `min_freq`, `max_freq`.
- [ ] **OpenSSL Provider Alignment**:
  - This host runs OpenSSL **3.5.8 default provider only**. The FIPS provider is **not** loaded (`openssl list -providers` shows `default`).
  - PQC KEMs (`ML-KEM-768`, `X25519MLKEM768`) live in the **default** provider. X25519 is **not** a FIPS-approved curve, so do not require FIPS mode and `X25519MLKEM768` at the same time — that check fails by design.
  - FIPS-legal hybrids (if you ever enable the FIPS provider) are `SecP256r1MLKEM768` / `SecP384r1MLKEM1024`.
  - Live research posture: `openssl list -kem-algorithms` must show `ML-KEM-768` and `X25519MLKEM768` **@ default**. Do not claim FIPS 140-3 module validation.
- [ ] **Memory Protection & Swapping**:
  - This host uses **zram** (`/dev/zram0`, 8 GB, RAM-backed compressed swap) — secrets never page to a physical disk block, so `swapoff -a` is unnecessary here and would only remove a RAM-only device. Confirm with `swapon --show` (expect `zram0`, not a disk partition).
  - `mlock` is **not yet configured**: the engine unit has no `LimitMEMLOCK`, and the engine is `inactive`/LOCKED by default. To enforce no-paging, add `LimitMEMLOCK=infinity` to `quantum-flex-engine-mycelium.service` and have the process `mlockall()` its secret pages.

---

## 2. Key Lifecycle & Root CA Isolation

- [ ] **Root CA Generation**:
  - Root CA (`CN=QuantumFlex-Root-CA`) must be generated inside an offline workstation or hardware security module using Ed25519 or ML-DSA-65.
  - **Zero Key Shipping Invariant**: Under no circumstances should `ca.key` or node private keys be packaged into distributable bundles. NOTE: `package_alpha_node.py` does **not** exist in this repo — this is an operator rule, not an automated guard.
- [ ] **Shamir Master Secret Distribution**:
  - Fracture master unlock entropy with `qf_genesis_tool split` at **k=3, n=5**. Unlock presents any 3 of the 5 files at threshold 3. Do not document k=2 unless that split is regenerated.
  - **TARGET custody** (in progress as of 2026-09-12): Yoga keeps `~/qfx-shards/shard_1.txt`; S23 vault holds `shard_2` (moved by offline QR, not Taildrop); shards 3–5 written on paper in ≥2 locations; then shred 2–5 from disk so only `shard_1.txt` remains on the Yoga.
  - **NOT CURRENTLY TRUE** — do not treat these as live facts:
    - Pixel / GrapheneOS / Titan M2 (`/data/secure/shard1.qfx`) — this host's Pixel is stock, not GrapheneOS, and no Titan-M2 path exists.
    - Samsung Galaxy Ultra Knox (`/data/secure/shard2.qfx`) — the live phone is an **S23 FE**, not Ultra, and no Knox path exists.
    - `/etc/quantum-flex/vault/shard3.qfx` — that directory does not exist on this host.
  - Live unlock after split: `SHARD_FILES=shard_1.txt,<phone-or-tmp>,<paper>` via `scripts/unlock_engine.sh`.
- [ ] **Per-Node Certificate Enrollment**:
  - Each node must generate its own private key pair locally at installation time.
  - This host's engine mTLS uses loopback-only certs under `$QF_DATA_DIR/mtls/` (`CN=localhost O=QuantumFlexMycelium`), **not** a Tailscale SAN. CSR-to-Root-CA with `alpha-node.tailscale.net` is a *target*, not the live enrollment.

---

## 3. Network Surface & Boundary Confinement

- [ ] **Port Exposure Verification** (live 2026-09-12, `ss -lntH`):
  - `9444/tcp`: mTLS engine IPC — `127.0.0.1` **when the unit is started** (it is `inactive` / LOCKED by default; do not enable on boot).
  - `8181/tcp`: OPA sidecar — `127.0.0.1`.
  - `8000/tcp`: AMARA dashboard — `127.0.0.1`.
  - `8080/tcp`: API node — `127.0.0.1`.
  - `9000/tcp`: MCP (`qflex-mcp`) — `127.0.0.1` (also live; was previously omitted).
  - `9050/tcp`: qf-bot HUD — `127.0.0.1` (also live; was previously omitted).
  - `tailscale serve` / Funnel: **none configured**. Do not treat any of the above as tailnet-reachable.
- [ ] **Firewall & Packet Filters**:
  - Ensure `nftables` or `iptables` drops any packet arriving on external physical NICs (`eth0`, `wlan0`) targeting internal daemon ports.

---

## 4. Telemetry Privacy & Secret Scrubbing

- [ ] **Zero Ephemeral Secret Leakage**:
  - Verify that no shared secret, pre-shared key, or raw KEM private key is ever emitted in log files or serialized into OPA telemetry queries.
  - Ephemeral buffers in C++ must invoke `OPENSSL_cleanse` immediately after HKDF expansion.
- [ ] **IP & Hostname Sanitization**:
  - Audit telemetry sent to Kafka / Sentinel to confirm private client IP addresses are hashed or masked.

---

## 5. Incident Response & Downgrade Circuit Breakers

- [ ] **OPA Circuit Breaker Simulation**:
  - Test simulated attack injection using `scripts/test2_malformed_injection.py`.
  - Confirm that OPA (`membrane_health.rego`) transitions `verdict` to `QUARANTINE` within $\le 500\,\text{ms}$.
- [ ] **Forensic Evidence Preservation**:
  - Verify that perturbed handshake bytes are written into the local forensic ring-buffer (`sentinel/quarantine_chamber.py`) with cryptographic hash chain integrity before socket disconnection.
- [ ] **Halt-on-Exhaustion Verification**:
  - Verify daemon process terminates cleanly or isolates network sockets rather than falling back to unapproved classical cipher suites when PQC legs fail.
