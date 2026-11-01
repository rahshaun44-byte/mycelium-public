# Mycelium — QuantumFlex Engine, Coordination Architecture & pqc-immune-daemon

[![License](https://img.shields.io/badge/License-Apache_2.0_|_MIT-blue.svg)](LICENSE)
[![NLnet Grant](https://img.shields.io/badge/NLnet_Restack_Fund-Application_2026--11--4af-green.svg)](sovereign_missions/02_NLNET_SUBMISSION_RECEIPT_2026-11-4af.md)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Open Policy Agent](https://img.shields.io/badge/OPA-Rego_Policies_Passing-brightgreen.svg)](sentinel/policies/)
[![Tests Passing](https://img.shields.io/badge/tests-551%20passed-success.svg)](tests/)

> **Status:** Open-source research prototype published for study, peer review, and public-good development under the **NLnet Foundation / NGI Zero Restack Fund** (Grant Application `2026-11-4af`). All experimental post-quantum key establishment modules (legacy hand-written FrodoKEM-976) are quarantined. Canonical cryptographic runtime definitions reside in [`quantumflex`](https://github.com/rahshaun44-byte/quantumflex). See [`STATUS.md`](STATUS.md) and [`HANDOFF.md`](HANDOFF.md).

---

## 🇪🇺 NLnet Public-Good Grant Project (`2026-11-4af`)

### `pqc-immune-daemon`: Formally Verified Post-Quantum Edge Security Membrane & Descriptor-Bound Runtime

Edge Linux systems, decentralized nodes, and civic infrastructure face two urgent threats: **Harvest Now, Decrypt Later (HNDL)** quantum cryptanalysis and **Time-of-Check to Time-of-Use (TOCTOU)** binary substitution attacks. 

This repository hosts **Mycelium** and the **`pqc-immune-daemon`** project, an open-source, zero-cloud security architecture delivering:

1. **Formally Verified Decision Core**: Low* / F* 2026.09 formal specification with automated C11 extraction via KaRaMeL and a 10,000+ vector differential test harness proving state-machine non-bypassability.
2. **Descriptor-Bound Loader (`pqc-exec-bound`)**: Linux kernel-sealed execution using `memfd_create()`, write-sealing (`F_SEAL_WRITE | F_SEAL_SEAL`), and `fexecve()` to mathematically eliminate TOCTOU disk substitution races.
3. **In-Process OPA WebAssembly Membrane**: Sub-millisecond ($<0.50\text{ms}$) declarative policy enforcement running entirely in-process without exposed network sockets.
4. **Automated Cryptographic Inventory (CBOM) & SLSA v1.0 Provenance**: Standalone CycloneDX 1.6 Cryptographic Bill of Materials mapping NIST post-quantum algorithm levels (FIPS 203 / 204 / 205).

### Grant Deliverables & Milestone Roadmap (€40,000 / 20 Weeks)

| Milestone | Deliverable | Effort | Description | Acceptance Criteria |
| :--- | :--- | :--- | :--- | :--- |
| **Milestone 1** | Formally Verified Decision Core & C11 Extraction | 6 Weeks (~120h) | Formal state machine in F* 2026.09 (`ACTIVE`, `QUARANTINE`, `RECOVERY`, `COLLAPSED`), KaRaMeL extraction to zero-dependency C11 (`pqc_core.c` / `pqc_core.h`), differential test harness. | CI passes in isolated container; F* verification succeeds with 0 admitted axioms; 10,000+ differential vectors pass without divergence. |
| **Milestone 2** | Descriptor-Bound `fexecve` Runtime Loader | 6 Weeks (~120h) | Standalone binary (`pqc-exec-bound`) implementing anonymous memory sealing (`memfd_create` + `F_SEAL_WRITE`) and `fexecve` execution with hybrid signature validation. | Multi-threaded race test harness achieves 0 successful binary substitution exploits across 1,000 concurrent race test runs. |
| **Milestone 3** | In-Process OPA WebAssembly Policy Membrane | 5 Weeks (~100h) | Embedded WebAssembly runtime executing compiled OPA Rego policies in-process; 3-state self-healing circuit breaker with crypto-agility fallbacks. | Benchmarks demonstrate average policy evaluation latency $< 0.50\text{ms}$; 65+ boundary test cases pass cleanly. |
| **Milestone 4** | CycloneDX 1.6 CBOM, SLSA Provenance & Packaging | 3 Weeks (~60h) | Automated CBOM generator, signed SLSA v1.0 Level 3 build provenance attestation, standalone offline verification tool, and packaging (.deb, apk, OCI). | Bit-for-bit reproducible builds verified; clean pass on 10-vector tamper matrix; independent offline verification verified. |

Full application dossier and submission receipts:
- [NLnet Grant Application Dossier](sovereign_missions/02_NLNET_PUBLIC_GOOD_GRANT_DOSSIER.md)
- [Official Submission Receipt `2026-11-4af`](sovereign_missions/02_NLNET_SUBMISSION_RECEIPT_2026-11-4af.md)

---

## Quickstart & Verification (Reviewers & Contributors)

This repository requires **$0.00 cloud spend** and zero proprietary dependencies to build and verify.

### 1. Run the Regression Suite (551+ Tests)

```bash
# Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run the complete test suite
pytest -q
```

### 2. Verify Open Policy Agent (OPA) Security Policies

```bash
# Verify supervisor and membrane health policies
opa test pqc-immune-daemon/ -v

# Verify kernel gatekeeper, bootgate, and universal reserve policies
opa test sentinel/policies/ -v
```

### 3. Generate Cryptographic Bill of Materials (CBOM)

```bash
# Run the automated compliance and inventory auditor
python3 tools/qf_audit.py .
```
Outputs CycloneDX v1.5/1.6 CBOM and OPA compliance verdict in `qf-audit-output/`.

---

## Architectural Components

```text
                     Client / Consumer
                             │
                    mutual TLS (OpenSSL)
                             │
                   QFXK Frame Reassembly
              (quantumflex/src/wire/wire_framing.cpp)
                             │
                 IpcServer::handle_framed_message
                    (src/core/ipc_server.cpp)
                             │
              ┌──────────────┴──────────────┐
              │                             │
         0x12 / 0x13                   Anything Else
              │                             │
        MLKem768Engine                 0x7F REJECT
      (OpenSSL ML-KEM-768)        (Fail-Closed Drop)
              │
         0x14 CONFIRM
  HMAC-SHA256(ss, label || ct)
```

- **pqc-immune-daemon (`pqc-immune-daemon/`)**: Working Python supervisor prototype implementing the 3-state circuit breaker (`ACTIVE`, `QUARANTINE`, `RECOVERY`), OPA Rego policy membrane, and PID-tracked process supervision.
- **Host Engine & IPC Server (`src/core/ipc_server.cpp`)**: Coordinates node communication over mTLS with single-frame QFXK framing.
- **Declarative Policy Membrane (`sentinel/policies/`)**: Open Policy Agent (OPA) Rego policies enforcing cryptographic algorithm selection, TPM hardware attestation, and fail-closed isolation.
- **Automated CBOM Auditor (`tools/qf_audit.py`)**: Cryptographic inventory tool inspecting source trees for post-quantum primitives (ML-KEM, ML-DSA) and flagging unapproved classical algorithms.

---

## Security Model & Invariants

1. **Fail-Closed Default**: Any condition, malformed frame, provider failure, or missing evidence immediately drops session state and rejects transaction flow (`0x7F` / quarantine).
2. **Zero Cryptographic Theater**: No claims of FIPS 140-3 certification, full-wire PQ encryption, or quantum immunity.
3. **Descriptor Write Sealing**: Binaries staged into memory via `memfd_create()` are sealed against modification before execution (`fexecve()`), closing the TOCTOU window.
4. **Universal Invariant ($R \ge O$)**: System homeostasis and state preservation are strictly verified before mutating transactions.

---

## Community & Governance

- **Contributing**: Please review [`CONTRIBUTING.md`](CONTRIBUTING.md) for environment setup, code style, and test requirements.
- **Code of Conduct**: This project adheres to the Contributor Covenant v2.1. See [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).
- **Security Policy**: Follow instructions in [`SECURITY.md`](SECURITY.md) to report vulnerabilities privately via [GitHub Security Advisories](https://github.com/rahshaun44-byte/mycelium/security/advisories/new).
- **Dual Licensing**: Apache-2.0 and MIT. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
