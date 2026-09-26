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

Verified 2026-09-11. Historical 9443 / `~/quantum-flex/data` entries below remain in the log as prior boots.

- **Process Status**: mycelium engine on loopback **`127.0.0.1:9444`** only (`quantum-flex-engine-mycelium.service`). Nothing listens on `9443` on this host.
- **Data Directory**: `/home/quant/.local/share/quantum-flex-mycelium`
- **Genesis Ledger**: `/home/quant/.local/share/quantum-flex-mycelium/ledger.dat`
- **Engine State**: boots **`LOCKED`**; unseal with `scripts/unlock_engine.sh` (mTLS + Shamir, live threshold **3** using `~/qfx-shards/shard_{1,2,3}.txt`). Five shard files exist; this is not `k=2,n=3`.
- **Keystore**: `/home/quant/.local/share/quantum-flex-mycelium/mtls/`
  - `ca.crt`: QuantumFlex Root CA
  - `server.crt`: Validated against `ca.crt`
  - `client.crt`: Validated against `ca.crt`
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

---

## 9. Multi-Device Mesh Deployment, Telemetry Pipeline & Compliance Verification

- **Date of Verification**: 2026-09-09
- **Network Topology & Verified Devices**:
  1. **Master Node (`fedora` / Lenovo Yoga 7)**: `192.168.100.11` / `100.64.1.17` — AMD Ryzen AI 5 340, 15 GB RAM, Fedora Linux 44. Runs control plane, PQC engine, OPA policy engine, and `qf-kafka-telemetry.service`.
  2. **Worker Node 2 (`qf-pavilion-worker` / HP Pavilion Desktop)**: `192.168.100.17` / `100.64.1.34` — Intel Celeron 450, 1.9 GB RAM, 456 GB HDD, Debian 13 (Trixie). Runs native Docker CE KRaft Kafka broker (`:9092`), Kafka UI (`:8090`), `qf-kafka-compose.service`, and `qf-worker-sentinel.service`.
  3. **Mobile Node 1 (Pixel 11 Pro)**: `100.64.1.18` — Titan M2 hardware root of trust, Shamir shard custodian, OOB signer.
  4. **Mobile Node 2 (Galaxy S23 FE)**: `100.64.1.32` — Samsung Knox Vault, field ops terminal, mobile PWA client.

- **Verified Invariants & Streaming Telemetry**:
  - **Live Kafka Ingestion**: Topic `qf-telemetry` on Pavilion broker verified actively ingesting pulses every 15s (`offset 64+`, partition 0).
  - **Worker Sentinel Health**: `qf-worker-sentinel.service` on Pavilion verified active (RAM: 51.4%, Disk: 0.7% used, Kafka broker UP, Kafka UI UP).
  - **Cryptographic Test Suites**: 4/4 suites (Known Answer Tests, Memory Zeroization, Wire Fuzzing, Wycheproof Negative) 100% passed.
  - **OPA Policy Compliance**: 16/16 policy unit tests passed; CBOM scanner verdict `[COMPLIANT // QUANTUM-AGILE]`.
  - **Universal Reserve Invariant ($R \ge O$):** `[ADMIT]` for Digital Memory, Pluton TPM 2.0 anchor, and Physical Water.
  - **Regulatory Standing Notice**: Formally recorded as internal pre-validation evidence. `CMVP Module Certificate: NULL`, `CAVP Algorithm Certificate: NULL`.

---

## 10. Stress & Containment Assessment Truth Log (2026-09-16, Tree `2f559ec…`)

**Assessment Date**: 2026-09-16  
**Evaluated Tree**: `2f559ec69064df5806e0288fef239e1076173227` (Modified Working Tree)  
**Host Architecture**: Fedora 44 (Lenovo Yoga 7), unprivileged user `quant` (UID 1000)  

### 10.1 Equation of Truth

- **$x$ (Observed Ground Truth)**: Stress report on tree `2f559ec…`. Loopback control plane strictly on `127.0.0.1`. Engine genesis sealed (`ACK|GENESIS_SECURED`), default runtime state is strictly **`LOCKED`**. Shamir 3-of-5 threshold with $\le 2$ shards on host disk (`~/qfx-shards/shard_1.txt`, `shard_2.txt` at `0600`).
- **$h$ (Hypothesis Demarcation)**: "Alert-only" is not broken SSH. It is a deliberate, decoupled architecture between network anomaly detection and the file quarantine chamber.
- **$k$ (Bounded Evidence Only)**: Rejection and quarantine are distinct machines. Host OpenSSL listing Frodo is NOT the engine security boundary. FIPS 203 algorithmic execution is NOT FIPS 140-3 module validation.

### 10.2 "SSH Weirdness" Defined

- **Network Defense vs File Ingest**:
  - **File Ingestion** (`/ingest` $\rightarrow$ Podman chamber): Copies payload into isolated volatile tmpfs airlock, executes inspection in dropped-capability container, removes staging copy.
  - **Network Engine** (mTLS listener $\rightarrow$ framing/KEM validation): Rejects invalid frames, closes TCP socket, logs LIF anomaly alert.
- **Session vs File**: SSH is a socket session protocol, not an uploaded blob. SSH detection is **alert-only** by design. A malformed network input or brute-force probe being rejected and logged need not produce a quarantined file artifact to count as successful defense.
- **Truth Log Entry**: `SSH auto-quarantine path = NULL (alert-only by design)`. Network rejects and closed sockets are first-class evidence.

### 10.3 Cryptographic Plane Demarcation

| Plane | Description | Host Ground Truth |
| :--- | :--- | :--- |
| **Plane A: Engine KEM** | In-process C++ hybrid/native ML-KEM-768 (`0x12`/`0x13`/`0x14`), frame reassembly, wire decapsulation. | Exercised: 1,000 ML-KEM roundtrips, mutated ciphertext checks, fuzzing negative suite passed. |
| **Plane B: Host OpenSSL / Frodo** | Fedora host OpenSSL provider (`openssl list -kem-algorithms`). | **NOT** the security boundary of the engine; host NULL is normal, expected, and preferred for the Yoga. |
| **Plane C: Fail-Closed Policy** | Strict profile denial, missing API keys, unreachable OPA $\rightarrow$ halt or 401. | Enforced: OPA downtime returns `DENY`; missing/unconfigured API keys strictly return `HTTP 401`. |

### 10.4 Risk Register & Remediations (Post-Stress)

| ID | Finding | Status | Remediated Implementation |
| :--- | :--- | :--- | :--- |
| **R1/R2** | Chamber mount mismatch (`/quarantine` vs `/opt/sentinel/quarantine`) | **RESOLVED** | `sentinel/quarantine_chamber.py` dynamically resolves `CONTAINER_QUARANTINE`, supporting both paths seamlessly. |
| **R3** | Wasm multi-threaded evaluation abort (exit 134) | **RESOLVED** | Added `threading.Lock()` to `OPAWasmEngine::evaluate()` in `sentinel/policies/wasm_gatekeeper.py`; verified under 100 concurrent worker threads. |
| **R4** | Policy reports COMPLIANT on empty CBOM inventory | **RESOLVED** | Added empty/missing component checks to `pqc-immune-daemon/membrane_health.rego`; empty inventories strictly trigger `node_status: TOXIC`. |
| **R5** | API keys unconfigured $\rightarrow$ admitted in isolated test | **RESOLVED** | `api_node/main.py`, `mcp_layer/athena_api.py`, and `mcp_layer/qf_bot/bot_server.py` fail closed with `HTTP 401` if keys are missing or unconfigured. |
| **R6** | SSH/LIF alert-only | **DOCUMENTED** | Clarified as intentional session-layer defense (reject/close socket + alert; no file quarantine). |
| **R7** | Slowloris / socket stalls | **VERIFIED** | 5000ms `SO_RCVTIMEO` socket deadline terminates stalled connections in $\approx 5.0\text{s}$, unblocking subsequent clients. |
| **R8** | Split `QF` magic bytes across TLS writes | **RESOLVED** | Bounded read added to `src/core/ipc_server.cpp` when `buffer[0] == 'Q'`, correctly reassembling fragmented binary headers. |
| **R9** | Host Frodo installation pressure | **REJECTED** | Preserved host default; engine operates in-process ML-KEM-768 via OpenSSL 3.5 native EVP. |
| **R10** | Ghost Node audit ledger mutation vulnerability | **RESOLVED** | Revoked `UPDATE` and `DELETE` on `sentinel_ledger` and `invariant_audit_ledger` from `ghostnode`; verified append-only (`ar`). |

---

## 11. Worker Node 2 (`qf-pavilion-worker`) Recovery & Live Ingestion Verification (2026-09-25)

- **Audit Date**: 2026-09-25
- **Node Identifier**: `qf-pavilion-worker` (HP Pavilion Desktop Tower)
- **Mesh Topology Status**:
  - Direct connection active over LAN (`192.168.100.17:41641`) via encrypted Tailscale WireGuard mesh (`100.64.1.34`).
  - Uptime: 1 day, 18+ hours.
  - OS & Kernel: Debian 13 (Trixie) Linux 6.12, unprivileged user `rocky` (UID 1000). Root login denied by Tailscale ACL tag `tag:worker`.
- **Container Infrastructure (Docker CE)**:
  - `qf-kafka-broker` (confluentinc/cp-kafka:7.6.0): Up 42+ hours. Bound to `127.0.0.1:9092` with Tailscale Serve exposing `100.64.1.34:9092` to Tailnet.
  - `qf-kafka-ui` (provectuslabs/kafka-ui:latest): Up 42+ hours. Bound to `127.0.0.1:8090` with Tailscale Serve exposing HTTPS and HTTP :8090 to Tailnet.
- **Worker Sentinel Health**:
  - `qf-worker-sentinel.service` running active.
  - Vitals: RAM used ~63% (1.2 GB / 1.9 GB, 0 B swap), Disk used 0.8% (428 GB free).
- **Master Node Pipeline Alignment (Lenovo Yoga 7)**:
  - `qf-kafka-telemetry.service`: Actively forward-streaming telemetry pulses (PQC KEM ML-KEM-768, host temps, memory vitals) at 15s cadence to `100.64.1.34:9092` (topic `qf-telemetry`, partition 0, offset > 2000).
  - `qf-kafka-consumer.service`: Actively pulling stream from Pavilion broker, persisting structured vitals to AMARA PostgreSQL (`telemetry` DB), and streaming embeddings to Athena neural cognitive node (`athena-node.service` port 8001).
- **Operational Verdict**: Worker Node 2 fully admitted from degraded/offline posture to **ACTIVE Layer 4 Stream Compute**.

