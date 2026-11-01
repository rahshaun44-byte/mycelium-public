# NLnet Foundation Grant Submission Receipt

**Application Code:** `2026-11-4af`  
**Project Name:** `pqc-immune-daemon: Formally Verified Post-Quantum Edge Security Membrane & Descriptor-Bound Runtime`  
**Fund:** Restack_Fund (NLnet NGI Zero Commons Fund / Restack)  
**Requested Amount:** €40,000  
**Applicant Entity:** Individual (Natural Person / Option A)  
**Applicant Name:** Rahshaun Chambers  
**Applicant Email:** `rahshaun44-byte@users.noreply.github.com`  
**Applicant Phone:** `[Redacted for Public Repository / On File with NLnet]`  
**Country:** US  
**Repository Website:** `https://github.com/rahshaun44-byte/mycelium`  
**Recorded Timestamp:** 2026-10-31  

---

## Recorded Application Content

### Synopsis
Edge Linux systems, decentralized nodes, and civic infrastructure face two urgent threats: Harvest Now, Decrypt Later (HNDL) quantum attacks and Time-of-Check to Time-of-Use (TOCTOU) binary substitution attacks. pqc-immune-daemon is a zero-cloud open-source project delivering a formally verified post-quantum security membrane and descriptor-bound loader. This project advances a working Python prototype into: 1. An F*-verified, zero-dependency C11 state machine extracted via KaRaMeL with a 10,000+ vector differential test harness proving non-bypassability. 2. A descriptor-bound loader (pqc-exec-bound) leveraging memfd_create, kernel write sealing (F_SEAL_WRITE), and fexecve to eliminate binary swapping. 3. An in-process OPA WebAssembly policy engine evaluating cryptographic health in <0.5ms without open network ports. 4. CycloneDX 1.6 CBOM and signed SLSA v1.0 Level 3 provenance. Dual-licensed (Apache-2.0/MIT) with zero cloud spend ($0.00).

### Experience
I am an independent systems, applied cryptography, and autonomous systems researcher. My work focuses on formal verification, post-quantum cryptographic engineering, reproducible software supply chains, and sovereign edge computing.

1. RELEVANT TECHNICAL BACKGROUND
My technical background directly covers the exact stack required for this project:
- Formal Verification: Extensive hands-on modeling in F* (2026.09) with Z3 SMT discharge and automated C11 extraction via KaRaMeL, proving state-machine non-bypassability and bounded fail-closed recovery.
- Linux Systems Programming: Practical implementation of Linux VFS APIs, anonymous memory file descriptors (memfd_create), kernel write sealing (F_SEAL_WRITE), and direct fexecve() execution to eliminate TOCTOU races.
- Applied Post-Quantum Cryptography: Engineering hybrid schemes combining NIST FIPS 203 (ML-KEM) and FIPS 204 (ML-DSA) with classic Ed25519 and SHA-256/384 hash agility.
- Declarative Security & Supply Chains: Designing Rego policy bundles for Open Policy Agent (OPA), generating CycloneDX 1.6 Cryptographic Bills of Materials (CBOM), and enforcing SLSA v1.0 Level 3 build provenance.

2. TRACK RECORD & PROTOTYPE MATURITY
This project is already significantly de-risked: I have developed and verified a working Python prototype (immune_daemon.py) with an operational 3-state circuit breaker, local OPA Rego policy membrane, and 550+ passing automated tests. Operating as an individual open-source maintainer (Option A: Natural Person), I have zero corporate overhead, sales quotas, or venture obligations. 100% of my time and grant funding will be dedicated directly to engineering, verifying, and documenting free and open-source public commons software.

### Usage & Milestones (€40,000)
The requested grant of €40,000 will be used exclusively for applied research, formal verification, systems engineering, testing, and documentation over a 20-week (5-month) timeline across four milestone deliverables:

1. MILESTONE BREAKDOWN & EFFORT ALLOCATION
- Milestone 1: Formally Verified Decision Core & C11 Extraction (6 Weeks | ~120 Hours | €12,000)
  - Specify complete security supervisor state machine in F* 2026.09 (ACTIVE, QUARANTINE, RECOVERY, COLLAPSED), proving non-bypassability, progress, and fail-closed termination.
  - Set up KaRaMeL extraction pipeline generating standalone, zero-dependency C11 source code (pqc_core.c / pqc_core.h) passing strict compiler gates (-Wall -Wextra -Werror -pedantic -std=c11).
  - Build differential parity harness running 10,000+ automated test vectors across Python, C11, and Wasm with zero divergence.
  - Acceptance: CI script passes cleanly in isolated container; F* verification succeeds with zero admitted axioms.
- Milestone 2: Descriptor-Bound fexecve Runtime Admission Loader (6 Weeks | ~120 Hours | €12,000)
  - Engineer standalone Linux admission binary (pqc-exec-bound) implementing memfd_create, hybrid Ed25519 + NIST ML-DSA-65 validation, kernel write sealing (F_SEAL_WRITE | F_SEAL_SEAL), and fexecve execution.
  - Build multi-threaded race harness simulating inotify file swaps during launch (100% block rate against TOCTOU substitution).
  - Validate Linux kernel compatibility (>= 5.15) across standard glibc and musl (Alpine).
  - Acceptance: 0 successful binary substitution exploits in 1,000 concurrent race test runs.
- Milestone 3: In-Process OPA WebAssembly Policy Membrane (5 Weeks | ~100 Hours | €10,000)
  - Compile OPA Rego security assertions into a pure in-process WebAssembly runtime embedded in the supervisor process, eliminating external HTTP daemons and open network ports.
  - Implement crypto-agility fallback matrix: strict fail-closed enforcement under fips_strict paired with supervised rollover to FrodoKEM-976-AES under research agility.
  - Implement 3-state self-healing circuit breaker with configurable quarantine windows and recovery telemetry.
  - Acceptance: Benchmark proving average policy evaluation latency < 0.50ms; 65+ boundary test cases passing.
- Milestone 4: CycloneDX 1.6 CBOM, SLSA v1.0 Provenance & Packaging (3 Weeks | ~60 Hours | €6,000)
  - Develop standalone CycloneDX 1.6 Cryptographic Bill of Materials (CBOM) generator mapping algorithms, OIDs, and NIST quantum levels.
  - Implement signed SLSA v1.0 Level 3 build provenance attestation generator binding commits, toolchain hashes, and release digests.
  - Provide standalone offline verification script (verify_dossier_independent.py) for third-party auditing without proprietary dependencies.
  - Package for Debian/Ubuntu (.deb), Alpine Linux (apk), and OCI container images.
  - Acceptance: Bit-for-bit reproducible builds verified across independent environments; clean pass on 10-vector tamper matrix.

2. RATE RATIONALE & TIME COMMITMENT
- Total Effort: 400 engineering hours across 20 weeks (~20 hours/week sustainable dedication).
- Effective Rate: €100 / hour (or €8,000 / month across 5 months). Reflects specialized expertise spanning formal verification (F* / KaRaMeL), Linux kernel systems programming (memfd_create / fexecve), Wasm runtimes, and post-quantum cryptographic engineering (NIST FIPS 203/204).

3. EXPENSES & INFRASTRUCTURE
- Direct Expenses: €0.00. No hardware, lab equipment, or travel expenses are requested.
- Cloud Spend: $0.00 cloud spend. All builds, SMT theorem proving, and regression testing run locally on existing sovereign developer workstations.
- 100% of funding directly compensates open-source research and engineering effort.

### Comparison
1. COMPARISON WITH EXISTING & HISTORICAL EFFORTS
- A. Cryptographic Libraries (OpenSSL 3.5, OQS / liboqs): Primitives, not runtime supervisors.
- B. Linux Kernel LSMs & Integrity Measurement (IMA, AppArmor, SELinux): Standard userland execution is vulnerable to TOCTOU file replacement; descriptor-bound execution eliminates the race.
- C. Commercial Cloud EDR Agents (CrowdStrike, Datadog, SentinelOne): Expensive ($15-$60/node/month), exfiltrate telemetry, lack formal proofs. pqc-immune-daemon is 100% offline at $0.00 cloud spend.

2. WHAT IS NEW, MORE THOROUGH, OR OTHERWISE DIFFERENT?
- Formally Verified Supervisor Core: Proved in F* 2026.09, extracted via KaRaMeL to C11.
- Kernel-Sealed TOCTOU Immunity: memfd_create + F_SEAL_WRITE + fexecve.
- In-Process Policy Membrane: Sub-millisecond (<0.5ms) Wasm OPA evaluation.
- Native Cryptographic Inventory: CycloneDX 1.6 CBOM.

3. CONTRIBUTING TO UPSTREAM COMMONS
- OpenSSL 3.5 & NIST FIPS 203/204 formats.
- Embedded Wasm OPA reference architecture.
- Standalone CycloneDX CBOM generator.

### Challenges & Mitigations
1. Low* / F* to C11 Extraction Fidelity -> Low* memory model + 10,000+ vector differential harness.
2. Descriptor-Bound fexecve() Dynamic Linker -> Primary static musl support + dynamic dependency CBOM staging.
3. In-Process Wasm Footprint -> Lightweight runtime (Wasm3 / static AOT), linear memory <16 MB, <0.5ms latency.
4. PQC Memory Overhead -> Static pre-allocated buffers, zero dynamic heap allocation during monitoring.

### Ecosystem
- Beneficiaries: Decentralized node operators, civic/public institutions, sovereign AI/edge systems.
- Standards: F*, KaRaMeL, NIST FIPS 203/204, OpenSSL 3.5, OPA, CycloneDX 1.6, Linux VFS.
- Distribution: Apache-2.0 / MIT dual-license, .deb, apk, OCI containers.

### Other Funding
Zero external funding. 100% self-funded through personal research time and sovereign developer infrastructure ($0.00 cloud spend). No VC, no commercial backing, no prior grant allocations. First external grant proposal.

### AI Disclosure
- AI use: false
- Codebase AI usage: false

---

## Economic Governance & Invariants
- **Gate M6-05 (Grant Award Verification):** Active / Pending NLnet notification.
- **Gate M6-06 (Settled Funds Reconciliation):** $0.00 realized settled income recorded.
- **M6-D Invariant:** Unsettled awards do NOT count as liquid income. Household reserve calculation ($R \ge 6O$) remains anchored strictly to independently verified liquid reserves ($40,000 USD / 7.00 months).
