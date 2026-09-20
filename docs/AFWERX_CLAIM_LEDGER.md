# ⚖️ QUANTUMFLEX AFWERX CLAIM LEDGER
## Empirical Verification, Scope Scrutiny & Proposal Trace Matrix

**Entity:** FINALLYFUNGUS LLC (PA Entity ID: 13706513) DBA QuantumFlex  
**Governing Principle:** *Only empirically verified facts survive into formal federal proposals.*  
**Primary Reference:** [`docs/DUE_DILIGENCE_DOSSIER.pdf`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.pdf) (SHA-256: `71b505c762834cc44f166873a86960389bcbf6312f5f6b27277e5f4777193866`)  
**Audit Date:** September 20, 2026  
**Commit Baseline:** `31ed9c9`

---

## 1. Statutory Regulatory & Certification Demarcation

> [!IMPORTANT]
> **MANDATORY PROCUREMENT DISCLOSURES (CMVP / CAVP & SBIR BOUNDARIES)**  
> 1. **NIST CMVP Module Validation Certificate:** `NULL` (None issued; none claimed).  
> 2. **NIST CAVP Algorithm Validation Certificate:** `NULL` (Self-administered ACVP-compatible test vectors; none claimed).  
> 3. **CMVP Listing Status:** `NOT LISTED` (Internal pre-validation engineering research prototype).  
> 4. **Technology Readiness Level (TRL):** **Self-assessed TRL 4** (Component and integrated laboratory breadboard validation per GAO guidelines).  
> 5. **Data Rights Framework:** In accordance with DFARS 252.227-7018, the Government receives **SBIR Data Rights** (technical data limited rights and software restricted rights) for a period of 20 years from award; Government Purpose Rights (GPR) apply post-protection period.  
> 6. **Foreign Ownership (FOCI):** No known foreign ownership, control, or influence identified in company records as of submission.

---

## 2. Empirical Verification Claim Matrix

| Item # | Technical Claim | Claimed Value / Metric | Primary Source Reference | Verification Mechanism & Test Artifact | Claim Status |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **CL-01** | **Memory Cleansing & Zeroization** | 0 bytes leaked / 0 errors (37 allocs / 37 frees) | [`docs/DUE_DILIGENCE_DOSSIER.md#L318-L320`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.md#L318-L320) | Valgrind Memcheck 3.27.1 full leak check post-Shamir recovery (`tools/test_zeroization.cpp`) | **VERIFIED** |
| **CL-02** | **Shock Absorber Telemetry Cadence** | 15.01s interval under forged signature attack (Nominal: 15.00s; $\Delta < 0.1\%$) | [`docs/DUE_DILIGENCE_DOSSIER.md#L138-L139`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.md#L138-L139) | Leaky Integrate-and-Fire (EWMA LIF) Sentinel socket log under forged Ed25519 barrage | **VERIFIED** |
| **CL-03** | **Shamir Threshold Unlock Latency** | 4.651 ms state transition (`LOCKED -> ACTIVE`) | [`docs/DUE_DILIGENCE_DOSSIER.md#L151-L160`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.md#L151-L160) | IPC Master Key activation benchmark (`tools/genesis_tool.cpp`) | **VERIFIED** |
| **CL-04** | **Decoupled Ingestion Acknowledgment** | 3.9–8.5 ms receipt latency (average 6.29 ms) | [`docs/DUE_DILIGENCE_DOSSIER.md#L305-L341`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.md#L305-L341) | `scripts/benchmark_lead_triage.py` (Suite 1: immediate HTTP 202 before inference) | **VERIFIED** |
| **CL-05** | **Atomic Config Swap Latency ($T_{\text{write}}$)** | $< 35\text{ ms}$ atomic swap on policy shift | [`docs/DUE_DILIGENCE_DOSSIER.md#L70`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.md#L70) | POSIX `SIGHUP` / `os.replace` atomic configuration watcher benchmark | **VERIFIED** |
| **CL-06** | **Automated Regression Suite Pass Rate** | 30 passed, 1 warning in 0.42s (100% pass) | Commit `31ed9c9`, Pytest execution output | 30 tests pass. 1 warning: `DeprecationWarning: anyio.abc.BlockingPortal alias is deprecated` in Starlette TestClient (Classified: **BENIGN / EXTERNAL DEPENDENCY**) | **VERIFIED** |
| **CL-07** | **QF-A4 Pre-Link Hash Verification** | Raw SHA-256 byte digests match `QuantumFlexAdmission.json` | `cmake/AdmitQuantumFlex.cmake` | CMake pre-link inspection gate (Cases 1 & 2 in admission test harness) | **VERIFIED** |
| **CL-08** | **QF-A5 External Provenance Authority** | 7/7 adversarial negative cases fail-closed | `scripts/test_quantumflex_admission.py` | External verifier `~/.local/libexec/quantumflex/verify-provenance` against `0400` trust anchor | **VERIFIED** |
| **CL-09** | **QF-A6 TOCTOU-Resistant Runtime Admission** | 10/10 adversarial cases pass ($EXECUTED\_FD == VERIFIED\_FD$) | `scripts/test_quantumflex_runtime_admission.py` | `fexecve(fd)` launcher and dynamic loader (`LD_PRELOAD`) sanitizer closes on-disk binary substitution | **VERIFIED** |
| **CL-10** | **Zero-Loss Kafka Pipeline Invariant** | `enable_auto_commit=False`; commits advance only post-AMARA write | `api_node/kafka_consumer.py` | Pytest mock suite (`tests/test_kafka_consumer.py` 7/7 pass) | **VERIFIED** |
| **CL-11** | **SQLite WAL Lease Fencing & Idempotency** | Stale workers rejected via `claim_token`; webhook retry protected | `scripts/intake_store.py` | Concurrency and lease fencing test suite (`tests/test_intake_fencing.py` 3/3 pass) | **VERIFIED** |
| **CL-12** | **Mobile Command Role Segregation** | Hardware role segregation; observer mutations fail-closed | `mobile/qflex_cli.py` | Mobile CLI test harness (`tests/test_mobile_cli.py` 5/5 pass) | **VERIFIED** |
| **CL-13** | **Zero-Trust Network Perimeter** | Loopback binding (`127.0.0.1:9000`); Tailscale Serve MagicDNS HTTPS | Tailscale Serve configuration | `tailscale serve status` showing proxying to `127.0.0.1:9000`; zero open LAN Wi-Fi listeners | **VERIFIED** |
| **CL-14** | **NIST CMVP / CAVP Formal Certification** | `Certificate: NULL` (None claimed) | `TRUTH_LOG_MASTER.md`, Dossier Regulatory Notice | Self-administered ACVP-compatible test harness; pre-validation prototype only | **NOT CLAIMED** |

---

## 3. Proposal Document Usage Rules & Grounded Standards

1. **Strict Inclusion:** Any performance number quoted in proposal documents must map directly to an entry with **`VERIFIED`** status above.
2. **Pre-Validation Discipline:** Never state or imply that QuantumFlex is a "validated cryptographic module" or "certified by NIST". It must always be described as an *"empirically verified pre-validation engineering prototype designed for accredited laboratory evaluation during Phase II"*.
3. **CNSA 2.0 Scoping:** Cite NSA's guidance accurately as *CSfC Post Quantum Cryptography Guidance Addendum 1.0, Draft .5* (2027 new product requirement in CSfC, 2030–2031 migration, NSM-10 2035 target). Note that ML-KEM (FIPS 203) and ML-DSA (FIPS 204) are finalized NIST standards.
4. **TOCTOU Scope:** Frame as *TOCTOU-Resistant Runtime Admission* closing the specific on-disk binary-swapping race condition via same-open-FD execution (`fexecve`), rather than a blanket operating-system-wide immunity.
5. **Physical Hardware Grounded Truth:** Distinguish between current engineering assets (x86_64 Linux engineering workstation + COTS mobile devices with Titan M2 / Knox enclaves) and planned Phase I equipment acquisitions (tactical single-board computers and discrete TPM 2.0 evaluation boards procured under Task 2 direct materials).
