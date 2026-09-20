# ⚖️ QUANTUMFLEX AFWERX CLAIM LEDGER
## Empirical Verification & Proposal Substantiation Trace Matrix

**Entity:** FINALLYFUNGUS LLC (PA Entity ID: 13706513) DBA QuantumFlex  
**Governing Rule:** *Only VERIFIED claims survive into formal federal proposal documents.*  
**Primary Reference:** [`docs/DUE_DILIGENCE_DOSSIER.pdf`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.pdf) (Document ID: `QF-DUE-DILIGENCE-2026-V1`)  
**Audit Date:** September 20, 2026  
**Commit Baseline:** `239e8eb`

---

## 1. Regulatory & Certification Demarcation Statement

> [!IMPORTANT]
> **MANDATORY PROCUREMENT DISCLOSURE (CMVP / CAVP BOUNDARY)**  
> - **NIST CMVP Module Validation Certificate:** `NULL` (None issued; none claimed).  
> - **NIST CAVP Algorithm Validation Certificate:** `NULL` (Self-administered Known Answer Test [KAT] vectors; none claimed).  
> - **CMVP Listing Status:** `NOT LISTED` (Pre-validation engineering research prototype).  
> In compliance with the False Claims Act and federal procurement ethics, terms such as *"FIPS 203 aligned"*, *"uses NIST PQC algorithms"*, and *"tested against reference vectors"* describe architectural design and internal laboratory testing only. They must never be represented as formal government certifications.

---

## 2. Empirical Verification Claim Matrix

The table below catalogs every empirical metric, performance figure, and architectural claim cited in the proposal documents, linking directly to its underlying test artifact and repository evidence.

| Item # | Technical Claim | Claimed Value / Metric | Primary Source Reference | Verification Mechanism & Test Artifact | Claim Status |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **CL-01** | **Memory Cleansing & Zeroization** | 0 bytes leaked / 0 errors (37 allocs / 37 frees) | [`docs/DUE_DILIGENCE_DOSSIER.md#L318-L320`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.md#L318-L320) | Valgrind Memcheck 3.27.1 full leak check post-Shamir recovery (`tools/test_zeroization.cpp`) | **VERIFIED** |
| **CL-02** | **Shock Absorber Telemetry Cadence** | 15.01s interval under forged signature attack (Nominal: 15.00s; $\Delta < 0.1\%$) | [`docs/DUE_DILIGENCE_DOSSIER.md#L138-L139`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.md#L138-L139) | Leaky Integrate-and-Fire (EWMA LIF) Sentinel socket log under forged Ed25519 barrage | **VERIFIED** |
| **CL-03** | **Shamir Threshold Unlock Latency** | 4.651 ms state transition (`LOCKED -> ACTIVE`) | [`docs/DUE_DILIGENCE_DOSSIER.md#L151-L160`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.md#L151-L160) | IPC Master Key activation benchmark (`tools/genesis_tool.cpp`) | **VERIFIED** |
| **CL-04** | **Decoupled Ingestion Acknowledgment** | 3.9–8.5 ms receipt latency (average 6.29 ms) | [`docs/DUE_DILIGENCE_DOSSIER.md#L305-L341`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.md#L305-L341) | `scripts/benchmark_lead_triage.py` (Suite 1: immediate HTTP 202 before inference) | **VERIFIED** |
| **CL-05** | **Atomic Config Swap Latency ($T_{\text{write}}$)** | $< 35\text{ ms}$ atomic swap on policy shift | [`docs/DUE_DILIGENCE_DOSSIER.md#L70`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.md#L70) | POSIX `SIGHUP` / `os.replace` atomic configuration watcher benchmark | **VERIFIED** |
| **CL-06** | **Automated Regression Suite Pass Rate** | 30 passed in 0.44s (100% pass) | Commit `239e8eb`, Pytest execution output | `tests/test_external_verifier.py` (6), `test_kafka_consumer.py` (7), `test_intake_fencing.py` (3), `test_mobile_cli.py` (5), `test_mobile_distribution.py` (4), `test_mobile_ota_routes.py` (5) | **VERIFIED** |
| **CL-07** | **QF-A4 Pre-Link Hash Verification** | Raw SHA-256 byte digests match `QuantumFlexAdmission.json` | `cmake/AdmitQuantumFlex.cmake` | CMake pre-link inspection gate (Cases 1 & 2 in admission test harness) | **VERIFIED** |
| **CL-08** | **QF-A5 External Provenance Authority** | 7/7 adversarial negative cases fail-closed | `scripts/test_quantumflex_admission.py` | External verifier `~/.local/libexec/quantumflex/verify-provenance` against `0400` trust anchor | **VERIFIED** |
| **CL-09** | **QF-A6 TOCTOU Runtime Binding** | 10/10 adversarial cases pass ($EXECUTED\_FD == VERIFIED\_FD$) | `scripts/test_quantumflex_runtime_admission.py` | `fexecve(fd)` launcher and dynamic loader (`LD_PRELOAD`) sanitizer (`scripts/qf_runtime_admit.py`) | **VERIFIED** |
| **CL-10** | **Zero-Loss Kafka Pipeline Invariant** | `enable_auto_commit=False`; commits advance only post-AMARA write | `api_node/kafka_consumer.py` | Pytest mock suite (`tests/test_kafka_consumer.py` 7/7 pass) | **VERIFIED** |
| **CL-11** | **SQLite WAL Lease Fencing & Idempotency** | Stale workers rejected via `claim_token`; webhook retry protected | `scripts/intake_store.py` | Concurrency and lease fencing test suite (`tests/test_intake_fencing.py` 3/3 pass) | **VERIFIED** |
| **CL-12** | **Mobile Command Role Segregation** | Hardware role segregation; observer mutations fail-closed | `mobile/qflex_cli.py` | Mobile CLI test harness (`tests/test_mobile_cli.py` 5/5 pass) | **VERIFIED** |
| **CL-13** | **Zero-Trust Network Perimeter** | Loopback binding (`127.0.0.1:9000`); Tailscale Serve MagicDNS HTTPS | Tailscale Serve configuration | `tailscale serve status` showing proxying to `127.0.0.1:9000`; zero open LAN Wi-Fi listeners | **VERIFIED** |
| **CL-14** | **NIST CMVP / CAVP Formal Certification** | `Certificate: NULL` (None claimed) | `TRUTH_LOG_MASTER.md`, Dossier Regulatory Notice | Self-administered KAT tests; formal validation targeted for Phase II | **NOT CLAIMED** |

---

## 3. Proposal Document Usage Rules

1. **Strict Inclusion:** Any performance number quoted in proposal documents (technical volume, work plan, customer-discovery deck) must map directly to an entry with **`VERIFIED`** status above.
2. **Pre-Validation Discipline:** Never state or imply that QuantumFlex is a "validated cryptographic module" or "certified by NIST". It must always be described as an *"empirically verified pre-validation engineering prototype designed for accredited laboratory evaluation during Phase II"*.
3. **Commit Association:** Every formal document generation must reference the exact Git commit hash (`239e8eb` or later) at which the 30/30 regression suite and empirical proofs were validated.
