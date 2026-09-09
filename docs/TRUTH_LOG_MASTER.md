# QUANTUM FLEX — MASTER TRUTH LOG & PROVENANCE REGISTER

**System**: Quantum Flex PQC Gateway / Alpha Node  
**Epistemic Standard**: Strict Equation of Truth: $Y = f(x - h) + k$  
**Hard Stop Rule**: Missing validation vector = HALT (`DATA NOT FOUND`). Zero synthetic mock vectors in telemetry or control paths.

---

## 1. Epistemic Principles & Policy Ground Truth

| Claim / Document | Source | SNR | Residual Uncertainty / Invariant |
| :--- | :--- | :--- | :--- |
| **G7 / CISA PQC Joint Guidance** (Published 3 Sep 2026) | CISA, ANSSI, CyberScoop | High | Establishes 5 qualitative priorities (Inventory, Agility, HVAs, Standards, Hybrid). Imposes **zero** statutory calendar deadlines on private infrastructure. |
| **Principle 6 Compliance** | G7 / CISA Joint Guidance | High | *"Do not watch 'quantum supremacy' headlines as a migrate-now trigger. Watch inventory completeness and algorithm agility."* |
| **Federal EO 14412** (2030 / 2031 Dates) | Executive Office of the President | High | Governs federal High-Value Assets (HVAs) and covered defense contractors. **Strict Boundary**: Private edge nodes do not claim federal EO 14412 compliance. |
| **NIST IR 8610 Algorithm Status** (29 Jul 2026) | NIST Computer Security Division | High | Formally records withdrawal of HAWK lattice signature candidate. QuantumFlex excludes HAWK from all active and fallback rosters. |
| **Astra ExploitBench 100% Score** | OpenAI Model Card / Release | High | Model card self-reported synthetic benchmark. Unverified against live hardened memory-safe runtimes. |
| **CRQC Timeline Claims** | External literature / headlines | Low | Theoretical worst-case estimates (e.g. Gao et al. $2^{0.5596n}$) require $2^{n/2}$ memory floor. Speculative headlines are discarded; recorded as `DATA NOT FOUND`. |

---

## 2. Cryptographic Provenance & External Claims (`truth_log_cedrus.yaml`)

- **Paper ID**: IACR-2025-2236 (*Extending the SPHINCS+ Framework*)
- **Canonical Candidate**: `CEDRUS+C-128s-5684`
- **Status**: `EXTERNAL_CLAIM` (`local_validation: NULL`, `gatekeeper_state: NO_INPUT`)
- **Strict Exclusion**: Paper Table 23 `0x06` (192-bit fast set, 30,268 B) is permanently excluded.
- **Published Parameters**:
  - Signature Size: 5,684 bytes (-9.835% vs baseline SPHINCS+C-128s 6,304 B)
  - Signing Hashes: 4,207,118 (exact published figure; never rounded)
  - Verification Hashes: 5,745 (~55% reduction vs baseline 12,766)
- **Preflight Requirement**: Four real artifacts (`BUNDLE_PATH`, `SIG_PATH`, `PUBKEY_PATH`, `VERIFIER_BIN`) required before local sizing. Missing artifact triggers `DATA NOT FOUND`.

---

## 3. Alpha Node Runtime & Engine Ground Truth (Yoga 7 Host)

- **Process Status**: `quantum_flex_engine` running on loopback `127.0.0.1:9443` / `127.0.0.1:9444`
- **Data Directory**: `/home/quant/quantum-flex/data`
- **Genesis Ledger**: `/home/quant/quantum-flex/data/ledger.dat` (193 bytes, sealed)
- **Engine State**: **`LOCKED`** (Ledger suspended in memory; awaiting operator Shamir Secret Sharing `UNLOCK|` token payload)
- **Keystore**: `/home/quant/quantum-flex/data/mtls/`
  - `ca.crt`: QuantumFlex Root CA (SHA-256 / RSA-4096)
  - `server.crt`: Validated against `ca.crt` (`OK`)
  - `client.crt`: Validated against `ca.crt` (`OK`)
- **CPU Posture**:
  - Governor: `performance`
  - Boost / Turbo: `0` (pinned to eliminate DVFS / Hertzbleed side-channel timing leakage)
- **Policy Control Plane**: OPA sidecar listening on loopback `127.0.0.1:8181`

---

## 4. Historical System & Service Hardening Log

### Historical Entries
- `[2026-07-06 18:01]`: Go runtime deployed; service configured with non-root user and clean parameters.
- `[2026-07-06 18:04]`: SELinux labels set to `bin_t` context; daemon executing cleanly.
- `[2026-07-15 11:12]`: Pre-shutdown hardening:
  - Deployed hardened `amara-matrix` (PostgreSQL 15 Alpine) bound to `127.0.0.1:5432` only.
  - Read-only root filesystem with tmpfs mounts (`/tmp`, `/run`, `/var/run/postgresql`).
  - Security flags enforced: `no-new-privileges: true`, resource limits clamped (2 GB RAM / 1.5 CPU).
  - Cleaned up failed service states (`sentinel-drive.service` reset).
- `[2026-09-07 05:23]`: Clean restart of `quantum_flex_engine` bound to `/home/quant/quantum-flex/data` on `127.0.0.1:9443`. Verified sealed state `LOCKED`.
- `[2026-09-09 01:34]`: Automated headless bootstrap of Worker Node 2 (`qf-pavilion-worker`) over local Wi-Fi. Authorized passwordless Ed25519 root SSH key.
- `[2026-09-09 01:38]`: Worker Node 2 joined to Tailscale zero-trust mesh (`100.64.1.34`).
- `[2026-09-09 01:43]`: Deployed native Docker CE 29.8.0 and Layer 4 KRaft Kafka cluster on Worker Node 2. Ports isolated strictly to Tailscale interface.

---

## 5. Distributed Worker Node Registry (Worker Node 2 — HP Pavilion Desktop Tower)

- **Device Identifier**: `qf-pavilion-worker`
- **Hardware Architecture**: HP Pavilion Desktop Tower (Intel Celeron 450 @ 2.20 GHz, 1.9 GB DDR RAM, 456 GB SATA HDD)
- **Operating System**: Debian GNU/Linux 13 (Trixie) minimal netinst (Kernel 6.12.94+deb13-amd64)
- **Network Boundaries**:
  - Local LAN IP: `192.168.100.17` (ens33)
  - Tailscale Mesh IP: `100.64.1.34` (tailscale0)
- **Authentication**: Ed25519 passwordless SSH key authorized exclusively for Yoga 7 master node.
- **Active Workloads**:
  - `qf-kafka-broker`: Confluent Kafka 7.6.0 running in KRaft mode (Listener: `100.64.1.34:9092`, heap: 512M, limit: 900M).
  - `qf-kafka-ui`: Provectus Kafka UI (Listener: `100.64.1.34:8090`, heap: 256M, limit: 400M).
- **Power & Auto-Recovery Posture**:
  - `HandleLidSwitch=ignore` configured in `systemd-logind`.
  - Systemd service persistence: `tailscaled.service`, `docker.service`, `ssh.service` enabled.
  - Container auto-restart: `restart: unless-stopped` active on both containers.
  - Routing persistence: `iptables-persistent` installed and rules saved.
  - Hardware AC Recovery: Set to `Power On` in HP BIOS Setup for unattended cold-boot recovery.

---

## 6. Track C Universal Reserve Invariant Status ($R \ge O$)

Evaluated live via Open Policy Agent (`sentinel/policies/reserve_invariant.rego`):

| Subsystem | Metric | Reserve Measured ($R$) | Obligations / Claims ($O$) | Invariant State | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Digital Memory** | Yoga 7 Host RAM | **15,127.88 MB** | 7,564.06 MB | $R \ge O$ (50% headroom) | **[ADMIT]** |
| **Pluton TPM 2.0** | NVRAM Index `0x1c00010` | `105e7998...787e` | `105e7998...787e` | Exact Root Match | **[ADMIT]** |
| **Physical Water** | Solvency | **500.0 gal** | 350.0 gal (+50 gal $\Delta$) | $R \ge O + \Delta$ | **[ADMIT]** |

---

## 7. Residual Uncertainty Register (`NULL` Index)

1. **CMVP FIPS 140-3 Module Certificate Number**: `NULL` (Unvalidated; internal engineering assurance only).
2. **CAVP FIPS 203/204/205 Algorithm Certificate Numbers**: `NULL` (Self-tested against NIST reference vectors; pending formal NVLAP lab ACVP testing).
2. **CEDRUS Local Execution Profiles**: `NULL` (Awaiting physical binary release).
3. **Hardware Immunity Against DVFS Side-Channels**: `PARTIAL` (Performance pinning active; microarchitectural isolation depends on physical CPU silicon).

---

## 8. Cryptographic Core Verification & Assurance Audit (FIPS 140-3 Alignment Dossier)

- **Date of Verification**: 2026-09-09
- **Audited Target**: `quantumflex::crypto` (`src/crypto/hybrid_kem.cpp`, `src/core/wire_framing.cpp`, `src/core/ipc_server.cpp`)
- **Compilation Environment**: GCC 16.2.1 (`-std=c++20 -O3`), OpenSSL 3.5.8, Linux `7.1.13-200.fc44.x86_64` (AMD Ryzen AI 5 340).
- **CMVP Validation Status**: `NULL` (Pre-validation evidence / internal engineering verification only; not a formal FIPS 140-3 validation or certification).
- **Core Verification Invariants (22/22 PASSED)**:
  1. **Assembly Branchless Decapsulation**: Bitwise sign-bit propagation `((udiff | -udiff) >> 31) - 1U` generates zero conditional jump instructions (`has_jumps=False`) across `-O0`, `-O1`, `-O2`, `-O3`, and `-Os`.
  2. **`dudect` Empirical Timing Indistinguishability**: 5,000 interleaved decapsulations measured via hardware cycle counter `__rdtscp` yielded Welch $t$-statistic $|t| = 2.1606 < 4.5$, proving the null hypothesis of identical execution distributions is not rejected.
  3. **NIST FIPS 203 ML-KEM Suite**: Native OpenSSL 3.5 provider verified for `ML-KEM-512` ($pk=800$ B, $ct=768$ B), `ML-KEM-768` ($pk=1184$ B, $ct=1088$ B), and `ML-KEM-1024` ($pk=1568$ B, $ct=1568$ B). Single-bit perturbations strictly diverge to deterministic pseudo-secrets fail-closed.
  4. **RFC 7748 & RFC 5869 KATs**: Alice/Bob X25519 shared secret exchange and HKDF-SHA256 test cases match reference vectors bit-for-bit.
  5. **Physical Memory Zeroization**: Stack buffers, 31,296-byte FrodoKEM heap keys, `HybridPrivateKey` destruction, and Shamir shards verified 100% `0x00` under `-O3` optimization with volatile pointer inspection.
  6. **Fail-Closed Network Wire Fuzzing**: Corrupted magic bytes, boundary wrap attacks ($2^{32}-1$), trickle fragmentation, and 500-session DoS saturation verified stable without buffer overflow or state compromise.
- **Reference Dossier**: [`docs/CRYPTOGRAPHIC_ASSURANCE_AUDIT_REPORT.md`](file:///home/quant/mycelium/docs/CRYPTOGRAPHIC_ASSURANCE_AUDIT_REPORT.md).
