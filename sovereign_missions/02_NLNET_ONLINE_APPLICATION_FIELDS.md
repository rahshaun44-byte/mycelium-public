# NLnet Foundation / NGI Zero Commons Fund — Online Application Form Helper

**Document ID:** `QF-GRANT-NLNET-2026-ONLINE-001`  
**Purpose:** Pre-validated copy-paste text chunks formatted specifically for the NLnet Foundation NGI Zero Commons Fund web submission portal (<https://nlnet.nl/propose/>).  
**Parent Dossier:** [`02_NLNET_PUBLIC_GOOD_GRANT_DOSSIER.md`](file:///home/quant/mycelium/sovereign_missions/02_NLNET_PUBLIC_GOOD_GRANT_DOSSIER.md) (`QF-GRANT-NLNET-2026-001`)  
**Applicant:** Rahshaun Chambers (Rocky)  
**Contracting Structure:** Option A: Individual Developer / Natural Person (Zero-equity, non-corporate)  
**Requested Budget:** €40,000 across 4 milestone tranches  
**Target Program:** NGI Zero Commons Fund (<https://nlnet.nl/commonsfund/>)  

---

## Field 1: Project Name
```text
pqc-immune-daemon: Formally Verified Post-Quantum Edge Security Membrane & Descriptor-Bound Runtime Loader
```

---

## Field 2: Website / Repository
```text
https://github.com/rahshaun44-byte/mycelium
```

---

## Field 3: Abstract (Limit: 1,200 characters including spaces)
*Character Count: 1,123 / 1,200 characters*

```text
Edge Linux systems, decentralized validator nodes, local AI agents, and civic infrastructure face two converging vulnerabilities: Harvest Now, Decrypt Later (HNDL) attacks archiving traffic for future quantum decryption, and Time-of-Check to Time-of-Use (TOCTOU) disk binary substitution attacks. pqc-immune-daemon is a zero-cloud open-source project delivering a formally verified post-quantum edge security supervisor and descriptor-bound runtime loader. This grant project advances a working Python prototype into: (1) an F*-verified, zero-dependency C11 state engine extracted via KaRaMeL with a 10,000+ vector differential test harness; (2) a descriptor-bound runtime loader (pqc-exec-bound) leveraging memfd_create, kernel write sealing (F_SEAL_WRITE), and fexecve to eliminate binary swapping; (3) an in-process Open Policy Agent (OPA) WebAssembly policy membrane evaluating cryptographic health in <0.5ms without external sockets; and (4) CycloneDX 1.6 Cryptographic Bills of Materials (CBOM) with signed SLSA v1.0 Level 3 provenance. Permissively licensed (Apache-2.0/MIT), operable on commodity hardware at $0.00 cloud spend, it democratizes high-assurance post-quantum defense.
```

---

## Field 4: Have you received funding before from NLnet or other European programs?
```text
No. This is a first-time application to NLnet and the NGI Zero Commons Fund.
```

---

## Field 5: What is the problem you want to solve? (General Problem Statement)
```text
Public civic infrastructure, municipal networks, non-profit organizations, edge Linux gateways, and decentralized validator nodes operate under severe resource constraints and cannot afford proprietary enterprise cloud EDR services ($15-$60/node/month). Simultaneously, these systems face two existential security threats:

1. The "Harvest Now, Decrypt Later" (HNDL) Threat:
State and criminal adversaries are passively recording encrypted communication streams across the internet today. When Cryptanalytically Relevant Quantum Computers (CRQCs) become operational, all recorded traffic protected solely by classical RSA and ECC public-key cryptography will be decrypted retroactively. While NIST has standardized post-quantum algorithms (FIPS 203 ML-KEM and FIPS 204 ML-DSA), edge devices lack lightweight, verified supervisor daemons capable of enforcing post-quantum crypto-agility, health telemetry, and automatic fail-closed fallback without cloud telemetry exfiltration.

2. Time-of-Check to Time-of-Use (TOCTOU) Runtime Binary Races:
Standard Linux application verification suffers from a fundamental architectural race: signatures are verified against files residing on the disk filesystem, but between signature validation and the kernel's subsequent execve() syscall, a local unprivileged process or symlink swap can alter the binary or its dynamic dependencies on disk. Path-based execution verification provides no cryptographic guarantee of the code actually loaded into kernel address space.

Current solutions force operators to choose between expensive, privacy-invasive cloud agents or unverified, manual shell scripts that fail open when cryptographic boundaries degrade.
```

---

## Field 6: What is the proposed solution and technical approach?
```text
pqc-immune-daemon provides a high-assurance, zero-cloud security membrane and runtime loader engineered specifically for edge and decentralized infrastructure. 

The project builds upon an existing, working Python 3.14 prototype with a 3-state circuit breaker and local OPA Rego policy membrane, advancing it into a production-grade, zero-dependency C11 suite across four key technical layers:

1. Formally Verified Decision Core (F* -> KaRaMeL -> C11):
We model the complete security supervisor state machine in F* (2026.09), proving mathematical invariants including progress, fail-closed absorbing collapse, credential-gated recovery, and strict non-bypassability. The verified specification is automatically extracted into pure C11 using KaRaMeL, backed by a differential parity test harness running 10,000+ vectors across F*, C11, and Python to prove bit-for-bit equivalence.

2. Descriptor-Bound Runtime Admission Loader (pqc-exec-bound):
We eliminate TOCTOU binary races entirely by binding signature verification directly to kernel-sealed memory file descriptors. Using Linux memfd_create(), hybrid Ed25519 + NIST ML-DSA-65 signatures are checked directly against the buffer in memory. The descriptor is sealed against further write modification using fcntl(fd, F_ADD_SEALS, F_SEAL_WRITE | F_SEAL_SEAL) and launched via fexecve(). The disk path is never re-read, mathematically closing the execution race window.

3. In-Process OPA WebAssembly Policy Membrane:
We compile Open Policy Agent (OPA) Rego security assertions into a zero-dependency WebAssembly runtime embedded directly within the daemon process. This eliminates external HTTP sockets, daemon dependencies, and port listening, dropping policy evaluation latency below 0.5 milliseconds.

4. CycloneDX 1.6 CBOM and SLSA v1.0 Provenance:
Every release and runtime evaluation generates a standardized CycloneDX 1.6 Cryptographic Bill of Materials (CBOM) documenting algorithm OIDs, NIST quantum levels, and key lifecycles, combined with signed SLSA v1.0 Level 3 build provenance.

All deliverables are 100% free and open source (dual Apache-2.0 / MIT), requiring zero paid cloud dependencies ($0.00 cloud spend), and run reliably on commodity and refurbished hardware.
```

---

## Field 7: Compare your project with existing state of the art
```text
Existing approaches to edge security and cryptographic migration fall into three inadequate categories:

1. Cryptographic Primitive Libraries (OpenSSL 3.5, liboqs):
Libraries provide raw mathematical implementations of ML-KEM or ML-DSA, but provide no runtime supervisor, no formal state machine guarantees, no descriptor-bound execution loaders, and no automated health monitoring. Operators are left to manually script process execution.

2. Linux Kernel LSMs (AppArmor, SELinux):
Kernel security modules enforce mandatory access control based on paths or security labels, but they do not perform post-quantum cryptographic signature validation, cannot inspect in-memory CBOM metadata, and still remain vulnerable to filesystem TOCTOU races during userland package staging.

3. Commercial Cloud EDR Agents (CrowdStrike, Datadog, SentinelOne):
Commercial endpoint solutions require high-cost monthly subscriptions ($15-$60/node/month), exfiltrate continuous telemetry to proprietary cloud servers (violating sovereign edge and privacy requirements), do not provide machine-checked formal verification, and rely on closed-source heuristics rather than deterministic mathematical state machines.

In contrast, pqc-immune-daemon delivers:
- Machine-checked formal F* proofs with KaRaMeL C11 extraction;
- Complete immunity to TOCTOU file substitution via sealed memfd_create + fexecve;
- Sub-millisecond (<0.5ms) in-process WebAssembly policy evaluation with no open ports;
- 100% offline, zero-cloud execution with zero telemetry exfiltration;
- Permissive FOSS licensing (Apache-2.0 / MIT) accessible to all public-good infrastructure.
```

---

## Field 8: Work Plan & Milestone Breakdown (€40,000 / 20 Weeks)

```text
Milestone 1: Formally Verified Decision Core & C11 Differential Suite
- Duration: 6 Weeks | Budget: €12,000
- Deliverables:
  1. Complete machine-checked F* formal specification (pqc_state_machine.fst) modeling states (ACTIVE, QUARANTINE, RECOVERY, COLLAPSED), proving fail-closed termination and non-bypassability with zero admitted axioms.
  2. KaRaMeL extraction pipeline producing standalone, zero-dependency C11 source code (pqc_core.c / pqc_core.h).
  3. Differential parity test harness executing 10,000+ automated test vectors across Python, C11, and Wasm targets with zero divergence.
- Acceptance Criteria: CI verification script verify_formal_core.sh passes cleanly in an isolated container; F* verification succeeds with zero warnings.

Milestone 2: Descriptor-Bound fexecve Runtime Admission Loader
- Duration: 6 Weeks | Budget: €12,000
- Deliverables:
  1. Standalone Linux admission binary (pqc-exec-bound) implementing memfd_create, hybrid Ed25519 + NIST ML-DSA-65 validation, kernel write sealing (F_SEAL_WRITE | F_SEAL_SEAL), and fexecve execution.
  2. Multi-threaded race condition test harness simulating aggressive inotify file swaps during launch (100% block rate against TOCTOU substitution).
  3. Compatibility layer supporting Linux kernels >= 5.15 on glibc and musl.
- Acceptance Criteria: Zero successful binary substitution exploits across 1,000 concurrent race test runs.

Milestone 3: In-Process OPA WebAssembly Policy Membrane
- Duration: 5 Weeks | Budget: €10,000
- Deliverables:
  1. In-process Wasm policy runtime embedding membrane_health.rego without external HTTP daemon or listening ports.
  2. Policy-driven crypto-agility fallback matrix: strict fail-closed enforcement under default fips_strict paired with supervised rollover to FrodoKEM-976-AES under the agility profile.
  3. Three-state self-healing circuit breaker with configurable quarantine windows and recovery telemetry.
- Acceptance Criteria: Benchmark proving average policy evaluation latency < 0.50ms; adversarial test suite passing 65+ boundary test cases.

Milestone 4: CycloneDX 1.6 CBOM, SLSA v1.0 Provenance & Independent Verifier
- Duration: 3 Weeks | Budget: €6,000
- Deliverables:
  1. Standalone CycloneDX 1.6 Cryptographic Bill of Materials (CBOM) generator mapping algorithms, OIDs, and NIST quantum levels.
  2. Signed SLSA v1.0 Level 3 build provenance attestation generator binding commits, toolchain hashes, and release digests.
  3. Standalone offline verification script (verify_dossier_independent.py) for third-party auditing without proprietary dependencies.
  4. Packaging for Debian/Ubuntu (.deb), Alpine Linux (apk), and OCI container images.
- Acceptance Criteria: Bit-for-bit reproducible builds verified across two independent environments; clean pass against 10-vector adversarial tamper matrix.
```

---

## Field 9: Applicant Background & Relevant Experience
```text
Rahshaun Chambers (Rocky) is an independent systems, applied cryptography, and autonomous systems researcher. His work focuses on formal verification, post-quantum cryptographic engineering, reproducible software supply chains, and sovereign edge computing. He has engineered verifiable systems utilizing F*, KaRaMeL, C11, Rust, Python, and Open Policy Agent, designing fail-closed runtime architectures that operate under strict zero-cloud constraints.

As an independent open-source maintainer (Option A: Natural Person), he operates with zero corporate overhead, venture backing, or commercial licensing tiers, dedicating all grant resources directly to the development, verification, and documentation of open-source public commons software.
```

---

## Field 10: Licensing & Commons Commitment
```text
All software, formal specifications, policy modules, documentation, and test suites developed under this grant will be published under the OSI-approved Apache License 2.0 and the MIT License (dual-licensed). All specifications and documentation will be released under Creative Commons Attribution 4.0 International (CC-BY 4.0). The project has no commercial tiers, proprietary forks, or dual-license commercial paywalls.
```
