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

## 3. Alpha Node Runtime & Engine Ground Truth

- **Process Status**: `quantum_flex_engine` running on loopback `127.0.0.1:9443`
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

---

## 5. Residual Uncertainty Register (`NULL` Index)

1. **CMVP FIPS 203/204/205 Certificate Numbers**: `NULL` (Pending formal NIST module validation).
2. **CEDRUS Local Execution Profiles**: `NULL` (Awaiting physical binary release).
3. **Hardware Immunity Against DVFS Side-Channels**: `PARTIAL` (Performance pinning active; microarchitectural isolation depends on physical CPU silicon).
