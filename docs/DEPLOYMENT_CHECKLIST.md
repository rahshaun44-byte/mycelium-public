# QuantumFlex Release-Quality Deployment Checklist

This checklist defines mandatory preflight, provisioning, key management, and incident response procedures before promoting a QuantumFlex Alpha Node to production.

---

## 1. Cryptographic Preflight & Environment Isolation

- [ ] **CPU Frequency Scaling Verification**:
  - Run `scripts/hertzbleed-gate.sh` to confirm CPU governor posture (`performance` or fixed frequency) to mitigate microarchitectural DVFS leakage.
  - Record baseline frequencies: `cur_freq`, `min_freq`, `max_freq`.
- [ ] **OpenSSL Provider Alignment**:
  - Verify OpenSSL 3.5.8+ default and fips providers are active.
  - Execute `openssl list -kem-algorithms` and confirm support for `ML-KEM-768` and `X25519MLKEM768`.
- [ ] **Memory Protection & Swapping**:
  - Ensure swap is disabled or encrypted (`swapoff -a`).
  - Verify `mlock` permissions for the `quantum_flex_engine` process to prevent secret key paging.

---

## 2. Key Lifecycle & Root CA Isolation

- [ ] **Root CA Generation**:
  - Root CA (`CN=QuantumFlex-Root-CA`) must be generated inside an offline workstation or hardware security module using Ed25519 or ML-DSA-65.
  - **Zero Key Shipping Invariant**: Under no circumstances should `ca.key` or node private keys be packaged into distributable bundles (`package_alpha_node.py` enforces this guard).
- [ ] **Shamir Master Secret Distribution**:
  - Fracture master unlock entropy with genesis tool default **k=3, n=5**. Live Yoga unlock presents three files (`~/qfx-shards/shard_{1,2,3}.txt`) at threshold 3. Do not document k=2 unless that split is regenerated.
    - Shard #1: Stored on Pixel GrapheneOS Titan M2 enclave (`/data/secure/shard1.qfx`).
    - Shard #2: Stored on Samsung Galaxy Ultra Knox Vault enclave (`/data/secure/shard2.qfx`).
    - Shard #3: Stored on physical host secure vault (`/etc/quantum-flex/vault/shard3.qfx`).
- [ ] **Per-Node Certificate Enrollment**:
  - Each node must generate its own private key pair locally at installation time.
  - Submit Certificate Signing Request (CSR) to Root CA and obtain leaf certificate with SAN matching the Tailscale node hostname (e.g., `alpha-node.tailscale.net`).

---

## 3. Network Surface & Boundary Confinement

- [ ] **Port Exposure Verification**:
  - `9444/tcp`: mTLS engine IPC bound strictly to `127.0.0.1`.
  - `8181/tcp`: Open Policy Agent sidecar bound strictly to `127.0.0.1`.
  - `8000/tcp`: AMARA console bound to `127.0.0.1` (publish with Tailscale Serve if needed).
  - `8080/tcp`: API node bound to `127.0.0.1` (publish with Tailscale Serve if needed).
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
