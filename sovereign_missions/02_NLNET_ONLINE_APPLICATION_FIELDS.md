# NLnet Foundation / NGI Zero Commons Fund — Online Application Form Helper

**Document ID:** `QF-GRANT-NLNET-2026-ONLINE-001`  
**Portal URL:** <https://nlnet.nl/propose/>  
**Parent Dossier:** [`02_NLNET_PUBLIC_GOOD_GRANT_DOSSIER.md`](file:///home/quant/mycelium/sovereign_missions/02_NLNET_PUBLIC_GOOD_GRANT_DOSSIER.md) (`QF-GRANT-NLNET-2026-001`)  
**Applicant:** Rahshaun Chambers (Rocky)  
**Contracting Structure:** Option A: Individual Developer / Natural Person (Zero-equity, non-corporate)  
**Requested Budget:** €40,000 across 4 milestone tranches  

---

## 1. Select a fund
**Field:** *Which of [our funds](https://nlnet.nl/funding.html) are you applying for?*  
**Selection:**
```text
Restack Fund
```
*(Alternative: Select `Other / open call` if you prefer the general NGI Zero Commons call; however, `Restack Fund` is the active European Open Internet Stack initiative specifically dedicated to core infrastructure, full-stack security, post-quantum resilience, and software supply chain integrity).*

---

## 2. Project overview

### Proposal title
```text
pqc-immune-daemon: Formally Verified Post-Quantum Edge Security Membrane & Descriptor-Bound Runtime Loader
```

### Project website(s) / repositories
```text
https://github.com/rahshaun44-byte/mycelium
```

### Please summarise the proposed project and its expected results in a few lines. (max. 1000 characters)
*Character count: 955 / 1,000 characters (Verified)*

```text
Edge Linux systems, decentralized nodes, and civic infrastructure face two urgent threats: Harvest Now, Decrypt Later (HNDL) quantum attacks and Time-of-Check to Time-of-Use (TOCTOU) binary substitution attacks. pqc-immune-daemon is a zero-cloud open-source project delivering a formally verified post-quantum security membrane and descriptor-bound loader.

This project advances a working Python prototype into:
1. An F*-verified, zero-dependency C11 state machine extracted via KaRaMeL with a 10,000+ vector differential test harness proving non-bypassability.
2. A descriptor-bound loader (pqc-exec-bound) leveraging memfd_create, kernel write sealing (F_SEAL_WRITE), and fexecve to eliminate binary swapping.
3. An in-process OPA WebAssembly policy engine evaluating cryptographic health in <0.5ms without open network ports.
4. CycloneDX 1.6 CBOM and signed SLSA v1.0 Level 3 provenance.

Dual-licensed (Apache-2.0/MIT) with zero cloud spend ($0.00).
```

---

## 3. Proposed effort

### How much money do you request for your project?
```text
40000
```
*(In Euros: €40,000 for a first grant, well within the €5,000 – €50,000 range).*

### Please provide a breakdown clarifying how the requested budget would be used. Which tasks will you undertake, and (roughly) how much time/effort will each take? What hourly/daily/monthly rate did you use? Will there be any expenses? (max. 4000 characters)
*Character count: 3,774 / 4,000 characters (Verified)*

```text
The requested grant of €40,000 will be used exclusively for applied research, formal verification, systems engineering, testing, and documentation over a 20-week (5-month) timeline across four milestone deliverables:

1. MILESTONE BREAKDOWN & EFFORT ALLOCATION

Milestone 1: Formally Verified Decision Core & C11 Extraction (6 Weeks | ~120 Hours | €12,000)
- Specify complete security supervisor state machine in F* 2026.09 (ACTIVE, QUARANTINE, RECOVERY, COLLAPSED), proving non-bypassability, progress, and fail-closed termination.
- Set up KaRaMeL extraction pipeline generating standalone, zero-dependency C11 source code (pqc_core.c / pqc_core.h) passing strict compiler gates (-Wall -Wextra -Werror -pedantic -std=c11).
- Build differential parity harness running 10,000+ automated test vectors across Python, C11, and Wasm with zero divergence.
- Acceptance: CI script passes cleanly in isolated container; F* verification succeeds with zero admitted axioms.

Milestone 2: Descriptor-Bound fexecve Runtime Admission Loader (6 Weeks | ~120 Hours | €12,000)
- Engineer standalone Linux admission binary (pqc-exec-bound) implementing memfd_create, hybrid Ed25519 + NIST ML-DSA-65 validation, kernel write sealing (F_SEAL_WRITE | F_SEAL_SEAL), and fexecve execution.
- Build multi-threaded race harness simulating inotify file swaps during launch (100% block rate against TOCTOU substitution).
- Validate Linux kernel compatibility (>= 5.15) across standard glibc and musl (Alpine).
- Acceptance: 0 successful binary substitution exploits in 1,000 concurrent race test runs.

Milestone 3: In-Process OPA WebAssembly Policy Membrane (5 Weeks | ~100 Hours | €10,000)
- Compile OPA Rego security assertions into a pure in-process WebAssembly runtime embedded in the supervisor process, eliminating external HTTP daemons and open network ports.
- Implement crypto-agility fallback matrix: strict fail-closed enforcement under fips_strict paired with supervised rollover to FrodoKEM-976-AES under research agility.
- Implement 3-state self-healing circuit breaker with configurable quarantine windows and recovery telemetry.
- Acceptance: Benchmark proving average policy evaluation latency < 0.50ms; 65+ boundary test cases passing.

Milestone 4: CycloneDX 1.6 CBOM, SLSA v1.0 Provenance & Packaging (3 Weeks | ~60 Hours | €6,000)
- Develop standalone CycloneDX 1.6 Cryptographic Bill of Materials (CBOM) generator mapping algorithms, OIDs, and NIST quantum levels.
- Implement signed SLSA v1.0 Level 3 build provenance attestation generator binding commits, toolchain hashes, and release digests.
- Provide standalone offline verification script (verify_dossier_independent.py) for third-party auditing without proprietary dependencies.
- Package for Debian/Ubuntu (.deb), Alpine Linux (apk), and OCI container images.
- Acceptance: Bit-for-bit reproducible builds verified across independent environments; clean pass on 10-vector tamper matrix.

2. RATE RATIONALE & TIME COMMITMENT
- Total Effort: 400 engineering hours across 20 weeks (~20 hours/week sustainable dedication).
- Effective Rate: €100 / hour (or €8,000 / month across 5 months). This reflects specialized expertise spanning formal verification (F* / KaRaMeL), Linux kernel systems programming (memfd_create / fexecve), Wasm runtimes, and post-quantum cryptographic engineering (NIST FIPS 203/204), consistent with standard European open-source research rates.

3. EXPENSES & INFRASTRUCTURE
- Direct Expenses: €0.00. No hardware, lab equipment, or travel expenses are requested.
- Cloud Spend: $0.00 cloud spend. All builds, SMT theorem proving, and regression testing run locally on existing sovereign developer workstations.
- 100% of funding directly compensates open-source research and engineering effort.
```

---

## 4. Supplementary Form Fields (If Prompted by Portal)

### Applicant Background & Track Record
```text
Rahshaun Chambers (Rocky) is an independent systems, applied cryptography, and autonomous systems researcher. His work focuses on formal verification, post-quantum cryptographic engineering, reproducible software supply chains, and sovereign edge computing. He has engineered verifiable systems utilizing F*, KaRaMeL, C11, Rust, Python, and Open Policy Agent, designing fail-closed runtime architectures that operate under strict zero-cloud constraints.

As an independent open-source maintainer (Option A: Natural Person), he operates with zero corporate overhead, venture backing, or commercial licensing tiers, dedicating all grant resources directly to the development, verification, and documentation of open-source public commons software.
```

### Licensing Commitment
```text
All software, formal specifications, policy modules, documentation, and test suites developed under this grant will be published under the OSI-approved Apache License 2.0 and the MIT License (dual-licensed). All specifications and documentation will be released under Creative Commons Attribution 4.0 International (CC-BY 4.0). The project has no commercial tiers, proprietary forks, or dual-license commercial paywalls.
```
