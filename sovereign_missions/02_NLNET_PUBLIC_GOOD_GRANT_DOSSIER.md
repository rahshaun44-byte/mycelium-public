# Non-Dilutive Open-Source Public-Good Grant Dossier (`pqc-immune-daemon`)

**Target Grant Programs:** NLnet Foundation (NGI Zero Core / Entrust), OpenSSF, Sovereign Tech Fellowships  
**Applicant Structure:** Independent Individual Systems & Cryptography Researcher (Non-Corporate, Zero-Equity, Open-Source Public Good)  
**Public Repository:** `pqc-immune-daemon` (Apache-2.0 / MIT Dual License)  
**Requested Grant Range:** `€15,000 – €50,000` (Milestone-Based Individual Fellowship)  

---

## 1. Abstract & Public-Good Mission
Edge Linux nodes, autonomous software agents, and decentralized infrastructure increasingly face two converging threats:
1. **Harvest-Now, Decrypt-Later Quantum Adversaries** targeting legacy RSA/ECDH transport channels.
2. **Time-of-Check to Time-of-Use (TOCTOU) Runtime Binary Substitution & Policy Bypass** (such as kernel/userspace descriptor races).

`pqc-immune-daemon` provides a lightweight, fail-closed post-quantum edge security membrane combining:
- **Post-Quantum Hybrid Key Encapsulation:** NIST FIPS 203 (`ML-KEM-768`) / `FrodoKEM-976-AES` with `X25519` hybrid failover and FIPS 204 (`ML-DSA-65`) / `Ed25519` detached provenance signatures.
- **Formally Verified Policy & Decision Core (`QF-A3` / `QF-A4`):** Machine-checked F\* specifications extracted to deterministic C11 via KaRaMeL and paired with an in-process WebAssembly Open Policy Agent (`OPA Wasm`) gatekeeper.
- **Descriptor-Bound Runtime Execution (`QF-A6`):** Eliminates binary substitution race conditions between cryptographic verification and execution by enforcing `EXECUTED_FD == VERIFIED_FD` via Linux `fexecve` and `memfd_create`.

---

## 2. Measurable Technical Milestones (Pay-Per-Milestone)

| Milestone | Public-Good Deliverable | Verification & Acceptance Test | Grant Allocation |
| :--- | :--- | :--- | :--- |
| **M1: Formal Core & C11 Differential Suite** | Publish F\* 2026.09 proofs and KaRaMeL-extracted C11 admission core with `10,000+` differential parity vectors. | Automated CI pass (`verify_formal_core.sh`) | `€12,000` |
| **M2: Descriptor-Bound `fexecve` Runtime Loader** | Release Linux `fexecve` runtime admission wrapper preventing TOCTOU binary modification on disk. | Adversarial race-condition test suite (`100%` block rate) | `€12,000` |
| **M3: In-Process OPA Wasm Policy Membrane** | Zero-network-hop Rego-to-Wasm policy evaluator with bit-for-bit Python/C/Wasm decision parity. | `61/61` adversarial & boundary test suite pass | `€10,000` |
| **M4: Reproducible CBOM & Independent Verifier** | Standalone cryptographic bill of materials (CBOM) and Merkle provenance verifier (`verify_dossier_independent.py`). | Reproducible build & independent audit pass | `€6,000` |

---

## 3. Why This Serves the Greater Good Without Corporate Gravity (`QF-M5` Grant Readiness)
- **100% Free & Open Source Deliverable:** Every line of code, F\* proof, and test vector in `pqc-immune-daemon` is released publicly under Apache-2.0 / MIT so hospitals, municipalities, journalists, and independent developers can harden Linux edge systems at `$0.00` licensing cost.
- **Reproducible Technical Demonstrations:** Every milestone is backed by deterministic verification scripts (`verify_formal_core.sh`, `verify_dossier_independent.py`) and a pinned SHA-256 evidence manifest.
- **Realistic Maintenance & Household Boundary:** Milestones are scoped to self-contained, zero-SLA open-source releases (`<= 6 hours/day` under `QF-OPS-01`) that never compromise Operator household stability.
- **Safeguard A & C Compliance:** All individual grant agreements and tax reporting obligations are honored; unreceived grant milestones (`pending_grants_usd`) are strictly excluded from $R_{\text{verified liquid}}$ until settled in liquid cash.
- **Zero Cloud Dependency:** Runs entirely on modest commodity hardware (`<= 14 GiB RAM`) without requiring proprietary cloud security subscriptions.
