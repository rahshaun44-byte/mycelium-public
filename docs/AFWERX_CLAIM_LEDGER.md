# ⚖️ QUANTUMFLEX AFWERX CLAIM LEDGER
## Empirical Verification, Scope Scrutiny & Proposal Trace Matrix

**Entity:** FINALLYFUNGUS LLC (PA Entity ID: 13706513) DBA QuantumFlex  
**Governing Principle:** *Only empirically verified facts survive into formal federal proposals.*  
**Primary Reference:** [`docs/DUE_DILIGENCE_DOSSIER.pdf`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.pdf) (SHA-256: `71b505c762834cc44f166873a86960389bcbf6312f5f6b27277e5f4777193866`)  
**Audit Date:** September 20, 2026  
**Commit Baseline:** `507e046`

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
| **CL-01** | **Memory Cleansing & Zeroization** | 0 bytes leaked / 0 errors (37 allocs / 37 frees) | [`docs/DUE_DILIGENCE_DOSSIER.md#L318-L320`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.md#L318-L320) | Valgrind Memcheck 3.27.1 full leak check post-Shamir recovery (`tools/test_zeroization.cpp`); application-level `OPENSSL_cleanse` on recovery & IPC buffers | **VERIFIED** |
| **CL-02** | **Controlled Socket Anomaly & Local Ghost Sink Absorption** | 15.01s interval under forged signature attack ($\Delta < 0.1\%$); deterministic absorption of friction term ($h$) into append-only JSONL ledger | [`docs/DUE_DILIGENCE_DOSSIER.md#L138-L139`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.md#L138-L139), `quantumflex-ghost-sink` (`127.0.0.1:19443`) | EWMA LIF Sentinel socket drop + local `quantumflex-ghost-sink` SHA-256 hash-chained absorption ledger (`sequence=1`, `previous_hash=0000...`, $H_{\text{attack}}=0$) | **VERIFIED** |
| **CL-03** | **Shamir Threshold Unlock Latency** | 4.651 ms state transition (`LOCKED -> ACTIVE`) | [`docs/DUE_DILIGENCE_DOSSIER.md#L151-L160`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.md#L151-L160) | IPC Master Key activation benchmark (`tools/genesis_tool.cpp`); 3-of-5 offline unseal ceremony verified live | **VERIFIED** |
| **CL-04** | **Decoupled Ingestion Acknowledgment** | 3.9–8.5 ms receipt latency (average 6.29 ms) | [`docs/DUE_DILIGENCE_DOSSIER.md#L305-L341`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.md#L305-L341) | `scripts/benchmark_lead_triage.py` (Suite 1: immediate HTTP 202 before inference) | **VERIFIED** |
| **CL-05** | **Atomic Config Swap Latency ($T_{\text{write}}$)** | $< 35\text{ ms}$ atomic swap on policy shift | [`docs/DUE_DILIGENCE_DOSSIER.md#L70`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.md#L70) | POSIX `SIGHUP` / `os.replace` atomic configuration watcher benchmark | **VERIFIED** |
| **CL-06** | **Automated Regression Suite Pass Rate** | 30 passed, 1 warning in 0.42s (100% pass) | Commit `507e046`, Pytest execution output | 30 tests pass. 1 warning: `DeprecationWarning: anyio.abc.BlockingPortal alias is deprecated` in Starlette TestClient (Classified: **BENIGN / EXTERNAL DEPENDENCY**) | **VERIFIED** |
| **CL-07** | **QF-A4 Pre-Link Hash Verification** | Raw SHA-256 byte digests match `QuantumFlexAdmission.json` | `cmake/AdmitQuantumFlex.cmake` | CMake pre-link inspection gate (Cases 1 & 2 in admission test harness) | **VERIFIED** |
| **CL-08** | **QF-A5 External Provenance Authority** | 7/7 adversarial negative cases fail-closed | `scripts/test_quantumflex_admission.py` | External verifier `~/.local/libexec/quantumflex/verify-provenance` against `0400` trust anchor; 13/13 artifacts byte-accurate | **VERIFIED** |
| **CL-09** | **QF-A6 TOCTOU-Resistant Runtime Admission** | 11/11 adversarial cases pass ($EXECUTED\_FD == VERIFIED\_FD$) | `scripts/test_quantumflex_runtime_admission.py` | `fexecve(fd)` launcher and dynamic loader (`LD_PRELOAD`) sanitizer closes on-disk binary substitution; verified signed A5 release manifest requirement | **VERIFIED** |
| **CL-10** | **Zero-Loss Kafka Pipeline Invariant** | `enable_auto_commit=False`; commits advance only post-AMARA write | `api_node/kafka_consumer.py` | Pytest mock suite (`tests/test_kafka_consumer.py` 7/7 pass) | **VERIFIED** |
| **CL-11** | **SQLite WAL Lease Fencing & Idempotency** | Stale workers rejected via `claim_token`; webhook retry protected | `scripts/intake_store.py` | Concurrency and lease fencing test suite (`tests/test_intake_fencing.py` 3/3 pass) | **VERIFIED** |
| **CL-12** | **Mobile Command Role Segregation** | Hardware role segregation; observer mutations fail-closed | `mobile/qflex_cli.py` | Mobile CLI test harness (`tests/test_mobile_cli.py` 5/5 pass) | **VERIFIED** |
| **CL-13** | **Zero-Trust Network Perimeter** | Loopback binding (`127.0.0.1:9000`); Tailscale Serve MagicDNS HTTPS | Tailscale Serve configuration | `tailscale serve status` showing proxying to `127.0.0.1:9000`; zero open LAN Wi-Fi listeners | **VERIFIED** |
| **CL-14** | **NIST CMVP / CAVP Formal Certification** | `Certificate: NULL` (None claimed) | `TRUTH_LOG_MASTER.md`, Dossier Regulatory Notice | Self-administered ACVP-compatible test harness; pre-validation prototype only | **NOT CLAIMED** |
| **CL-15** | **TLS 1.3 Protocol Floor & Downgrade Rejection** | Fatal startup denial if min version != TLS 1.3; TLS 1.2 clients rejected with `TLSV1_ALERT_PROTOCOL_VERSION` | `src/core/ipc_server.cpp` (lines 278-282), live production test against `:9444` | 4/4 live transport controls pass (TLS 1.3 valid client ALLOW; no cert DENY; rogue CA DENY; TLS 1.2 client DENY) | **VERIFIED** |
| **CL-16** | **Selective State Attestation & Transaction Authority** | Below-the-network admission matrix (12/12 pass), native/Wasm parity (12/12 pass), crash-injection atomicity (4/4 pass), external anti-rollback witness, IEEE-754 sequence bounds ($0 \le \text{seq} \le 2^{53}-1$) | `sentinel/policies/bootgate.rego`, `sentinel/policies/bootgate.wasm`, `tests/test_single_transaction_authority.py`, `tests/test_wasm_parity.py`, `tests/test_critical_state_gate.py` | Strict RFC 8785 canonicalization, Ed25519 provenance, OPA policy binding, atomic SQLite WAL single transaction authority, external monotonic witness | **VERIFIED** |


---

## 3. Proposal Document Usage Rules & Grounded Standards

1. **Strict Inclusion:** Any performance number quoted in proposal documents must map directly to an entry with **`VERIFIED`** status above.
2. **Pre-Validation Discipline:** Never state or imply that QuantumFlex is a "validated cryptographic module" or "certified by NIST". It must always be described as an *"empirically verified pre-validation engineering prototype designed for accredited laboratory evaluation during Phase II"*.
3. **CNSA 2.0 Scoping:** Cite NSA's guidance accurately as *CSfC Post Quantum Cryptography Guidance Addendum 1.0, Draft .5* (2027 new product requirement in CSfC, 2030–2031 migration, NSM-10 2035 target). Note that ML-KEM (FIPS 203) and ML-DSA (FIPS 204) are finalized NIST standards.
4. **TOCTOU Scope:** Frame as *TOCTOU-Resistant Runtime Admission* closing the specific on-disk binary-swapping race condition via same-open-FD execution (`fexecve`), rather than a blanket operating-system-wide immunity.
5. **Physical Hardware Grounded Truth:** Distinguish between the current **laptop-centered prototype laboratory** (Lenovo Yoga 7 primary engineering node running Fedora Linux with Pluton/TPM; HP Pavilion worker node; supported mobile enclaves) with software-defined network isolation (loopback, container networks, Tailscale mesh) and planned Phase I equipment acquisitions (representative edge compute modules and cryptographic evaluation hardware procured under Task 2 direct materials). Never claim single-board computers, discrete TPM modules, or physical injection benches as currently possessed.
