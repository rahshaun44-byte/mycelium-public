# 📄 DEPARTMENT OF THE AIR FORCE (DAF) / AFWERX SBIR PHASE I
## VOLUME 2: TECHNICAL PROPOSAL
### Official 13-Page Designated-Page Proposal Structure (Release 25.5/E Standard)

> [!IMPORTANT]
> **GOVERNING COMPLIANCE DIRECTIVE: DESIGNATED-PAGE EVALUATION RULES**  
> In accordance with Department of the Air Force (DAF) Open Topic Commercial Solutions Opening (CSO) instructions (e.g., Release 25.5/E), evaluators review content **strictly on its designated pages**. Content placed on non-designated pages will not be evaluated. This document provides the complete, audit-ready technical narrative mapped precisely to designated pages 1 through 13 (with an optional acronyms/glossary page on page 14).
> 
> * **Target Pathway:** DAF SBIR Open Topic Commercial Solutions Opening (CSO) Phase I
> * **Solicitation Number:** [SOLICITATION-CONTROLLED — PENDING CURRENT DAF OPEN TOPIC RELEASE ON DSIP]
> * **Award Ceiling:** Planned $75,000.00 Firm Fixed Price (Subject to controlling solicitation ceiling)
> * **Period of Performance:** Up to 90 Days (3 Months)
> * **Official Technical Appendix:** [`docs/DUE_DILIGENCE_DOSSIER.pdf`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.pdf) (10 Pages, SHA-256: `71b505c762834cc44f166873a86960389bcbf6312f5f6b27277e5f4777193866`)
> * **Authoritative Empirical Claim Ledger:** [`docs/AFWERX_CLAIM_LEDGER.md`](file:///home/quant/mycelium/docs/AFWERX_CLAIM_LEDGER.md)

---

### [PAGE 1] Proposal Cover & Technical Abstract

#### 1. Identification & Corporate Profile
* **Project Title:** QuantumFlex: Autonomous Post-Quantum Cryptographic Agility, Shock-Absorbing Telemetry & TOCTOU-Resistant Runtime Admission for National Security Systems
* **Topic Number:** [SOLICITATION-CONTROLLED — PENDING CURRENT DAF OPEN TOPIC RELEASE]
* **Applicant Entity:** FINALLYFUNGUS LLC (Pennsylvania Entity ID: 13706513) DBA QuantumFlex
* **Business Address:** 1120 South Main Street, Pittston, PA 18640 / Laboratory: Philadelphia, PA
* **Principal Investigator (PI):** Rahshaun Chambers (Founder & Systems Architect) | quant@quantumflex.network
* **Federal Identifiers:** SAM.gov Unique Entity Identifier (UEI): [VALIDATED] | CAGE Code: [VALIDATED] | SBA SBC ID: [VALIDATED]
* **Business Type:** Small Business Concern (SBC) under 500 employees | 100% US Owned & Controlled | No known foreign ownership, control, or influence identified in company records as of submission
* **Proposed Period of Performance:** 3 Months (90 Calendar Days)
* **Proposed Budget:** Planned $75,000.00 Firm Fixed Price (Subject to controlling solicitation ceiling)
* **Technical Appendix Reference:** 10-Page Empirical Proof Dossier ([`docs/DUE_DILIGENCE_DOSSIER.pdf`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.pdf))

#### 2. Technical Abstract
Tactical military datalinks, airborne edge nodes, and satellite communications face an acute, compounding operational crisis: **cryptographic brittleness under staged post-quantum migration, unmitigated computational exhaustion from hostile socket injection, and supply-chain binary tampering**. Conventional network gateways parse and log malformed ingress, triggering CPU saturation, heap memory accumulation, and service restarts during key rollover that degrade contested tactical operations.

**QuantumFlex** resolves this crisis through the **eQUATION OF TRUTH** ($\mathbf{Y = (x - h) + k}$). QuantumFlex is an autonomous, software-defined cryptographic agility sidecar and shock-absorbing telemetry architecture that:
1. **Decouples High-Throughput Cryptography from Policy Supervision:** Separates a standalone C++20 cryptographic engine (`quantumflex`) from dynamic Open Policy Agent (OPA) Rego evaluation sidecars, executing sub-35ms in-memory cipher swaps without tearing down active data sockets.
2. **Eliminates Computational Exhaustion via EWMA Shock Absorption:** Intercepts unauthenticated or forged binary packets at the socket ingress boundary, utilizing a Leaky Integrate-and-Fire (EWMA LIF) sentinel that shunts toxic perturbations into an isolated Ghost Node entropy sink (applying a Landauer-inspired information-cost analogy) without degrading host CPU or memory cadence.
3. **Guarantees Provable Memory Cleansing:** Overwrites all ephemeral lattice secrets, Shamir polynomial shards, and recovery keys using compiler-barrier `OPENSSL_cleanse` routines, empirically verified under Valgrind with zero memory leaks.
4. **Enforces TOCTOU-Resistant Runtime Admission:** Binds runtime execution directly to cryptographically attested source packages via the QF-A6 admission gate, opening binaries with `O_RDONLY | O_CLOEXEC`, verifying digital signatures over the open descriptor, sanitizing dynamic loader environments (`LD_PRELOAD`), and executing via `fexecve(fd)`—closing on-disk executable path-substitution races.

During this 90-day Phase I feasibility study, the contractor will execute ≥30 structured customer discovery interviews across candidate Air Force stakeholders (PEO Cyber and Networks, AFRL Information Directorate, and Space Systems Command), construct an automated ACVP-compatible NIST FIPS 203 (ML-KEM) pre-validation test harness, validate hardware security enclave integration (TPM 2.0, Titan M2, Knox Vault), and formulate a Phase II demonstration architecture for tactical pod and datalink integration.

---

### [PAGES 2–4] Technical Merit & Feasibility

#### [PAGE 2] Theoretical Formulation — The eQUATION OF TRUTH ($Y = (x - h) + k$)
Distributed tactical computing enclaves operating in contested electromagnetic and cyber environments are governed by high-velocity environmental entropy ($x$), hostile adversarial anomalies ($h$), and deterministic system invariants ($k$). Standard software architectures conflate these layers, allowing hostile inputs ($h$) to contaminate operational state ($Y$) and consume scarce edge resources.

QuantumFlex mathematically restructures this relationship through the **eQUATION OF TRUTH**:
$$\mathbf{Y = (x - h) + k}$$

* **$\mathbf{x}$ (Environmental Tactical Variables):** The high-velocity operational entropy of tactical edge communications—dynamic physical telemetry (e.g., host RAM consumption at 62.8%, thermal fluctuations at 48.0°C), bursty incoming socket frames over tactical radios, and asynchronous multi-tenant message ingress.
* **$\mathbf{h}$ (Adversarial Friction & Anomalies):** Malicious perturbations and hostile vectors—forged Ed25519 signatures, malformed binary wire protocol frames (QFXK), memory scraping, on-disk executable substitution races, and asynchronous webhook retry race conditions.
* **$\mathbf{k}$ (Baseline Invariant Stability):** Deterministic mathematical and cryptographic guarantees enforced at the machine-code and kernel boundaries:
  1. *Sub-Millisecond EWMA LIF Sentinel:* Implements an exponential leaky integrate-and-fire membrane potential:
     $$V_{\text{membrane}}[t] = \lambda \cdot V_{\text{membrane}}[t-1] + (1 - \lambda) \cdot \text{AnomalyCost}(p_t)$$
     Hostile packets that violate protocol framing or fail cryptographic checks immediately elevate the membrane potential. Upon reaching the threshold $V_{\text{th}}$, the socket fails-closed, shunting packets into an isolated Ghost Node entropy sink (drawing upon a Landauer-inspired information-cost analogy to prevent computational heat and host exhaustion) without CPU spikes or thread blocking.
  2. *Branchless Constant-Time Cryptography:* Zero data-dependent branching during post-quantum decapsulation (ML-KEM-768/1024), eliminating timing side-channel leakage.
  3. *Compiler-Barrier Memory Destruction:* Enforcing explicit zeroization of ephemeral state via `OPENSSL_cleanse` across heap and stack boundaries before process exit.
  4. *Declarative OPA Rego Admission Gate:* Evaluating active cipher health against declarative policies, executing atomic configuration rewrites (`os.replace` / POSIX `SIGHUP`) with sub-35ms latency.
* **$\mathbf{Y}$ (Purified Operational State):** The purified operational reality—simultaneously recorded into structured relational audit ledgers (**AMARA PostgreSQL 15**) for microsecond compliance traceability, semantically indexed into local neural vector memory (**Athena ChromaDB RAG**) for natural-language situational awareness, and executed exclusively through cryptographically admitted binaries.

```
+---------------------------------------------------------------------------------------------------------+
|                                         THE eQUATION OF TRUTH                                           |
|                                             Y = (x - h) + k                                             |
+---------------------------------------------------------------------------------------------------------+
                                                     |
                     +-------------------------------+-------------------------------+
                     |                                                               |
            [ x : Environmental Variables ]                                 [ h : Adversarial Anomalies ]
            * Dynamic RAM (62.8%)                                           * Forged Ed25519 Signatures
            * Host Temperature (48.0 C)                                     * Poisoned QFXK Binary Frames
            * High-Velocity Socket Ingress                                  * Heap Scraping / Memory Leaks
            * Tactical Datalink Jitter                                      * On-Disk Executable Swapping
                     |                                                               |
                     +-------------------------------+-------------------------------+
                                                     |
                                                     v
                                 [ k : Baseline Invariant Stability ]
                                 * EWMA LIF Sentinel (Shock Absorber)
                                 * Constant-Time Branchless Decapsulation
                                 * Compiler-Barrier Memory Zeroization
                                 * QF-A4/A5 Pre-Link & Provenance Admission
                                 * QF-A6 Atomic fexecve File-Descriptor Binding
                                 * Atomic Lease Fencing Tokens (claim_token)
                                                     |
                                                     v
                              +---------------------------------------------+
                              |         [ Y : Purified System State ]       |
                              +---------------------------------------------+
                                                     |
                     +-------------------------------+-------------------------------+
                     |                               |                               |
                     v                               v                               v
          [ AMARA Ledger (SQL) ]          [ Athena RAG (Vector) ]         [ Admitted Execution ]
          * PostgreSQL 15 Engine          * ChromaDB / SQLite Engine      * TOCTOU-Resistant Runtime
          * Immutable Log Rows            * 768-dim Embeddings            * Verified File Descriptor
          * Microsecond Invariant Audit   * Natural Language Query        * Hardware-Isolated Mobile
```

---

#### [PAGE 3] Decoupled Engine Architecture & TOCTOU-Resistant Runtime Admission
Conventional cryptographic architectures tightly couple wire protocol handling, algorithm execution, and policy decision-making into single monolithic executables. Under this legacy model, updating an algorithm requires recompiling the core application, halting active datalinks, and risking supply-chain binary substitution on edge non-volatile storage.

QuantumFlex enforces strict architectural decoupling between the **Cryptographic Data Plane** and the **Supervisory Policy Control Plane**, secured by an unbroken cryptographic chain of custody:

```
[ BUILD TIME ]                 [ LINK / PACKAGING ]               [ HOST RUNTIME ]
Standalone Source              Pre-Link Byte Check                Host Trust Anchor (0400)
(qflex_crypto + wire)          SHA-256 Static Archives            verify-provenance Binary
       |                               |                                  |
       v                               v                                  v
+---------------+             +------------------+             +----------------------+
| CMake XOR     | ----------> | QF-A4 Pre-Link   | ----------> | QF-A5 Detached       |
| Admission     |             | Receipt Verifier |             | Provenance Gate      |
+---------------+             +------------------+             +----------------------+
                                                                          |
                                                                          v
[ EXECUTION TIME ]                                             +----------------------+
Open Binary O_RDONLY | O_CLOEXEC ----------------------------> | QF-A6 Runtime Admit  |
Verify Digest on File Descriptor (EXECUTED_FD == VERIFIED_FD)  | (fexecve Binding)    |
Scrub Dynamic Loader (LD_PRELOAD / LD_LIBRARY_PATH) ---------> +----------------------+
                                                                          |
                                                                          v
                                                               [ Admitted Kernel Exec ]
```

1. **Standalone Data Plane Isolation (`quantumflex`):**
   The cryptographic primitives (`qflex_crypto`) and wire protocol (`wire`) are carved into an independent, standalone C++20 repository (`quantumflex`). In-tree source compilation and installed packages are mutually exclusive (CMake XOR admission rule: `ATTESTED` mode requires signed installed packages; `DEV` mode restricts to in-tree testing), eliminating duplicate target collisions and ensuring deterministic receipt generation (`QuantumFlexAdmission.json`).
2. **QF-A4 Pre-Link Hash Verification:**
   Before any linking occurs, the CMake admission gate (`cmake/AdmitQuantumFlex.cmake`) calculates raw SHA-256 byte digests of all installed static archives (`libquantumflex_crypto.a`, `libquantumflex_wire.a`) and public headers against the admission receipt. Any byte modification causes CMake configuration to fail-closed immediately.
3. **QF-A5 External Provenance Authority:**
   Package authenticity is governed by a canonical detached Ed25519 provenance manifest (`QuantumFlexAdmission.provenance.json` / `.sig`). This manifest is verified by an independent host-anchored verifier (`~/.local/libexec/quantumflex/verify-provenance`) referencing an isolated public trust anchor (`release_signing_key.pub`) held with strict `0400` permissions. The trust anchor resides strictly outside the repository tree, preventing circular supply-chain self-attestation.
4. **QF-A6 TOCTOU-Resistant Runtime Admission ($\text{EXECUTED\_FD} == \text{VERIFIED\_FD}$):**
   Standard Linux process execution via `execve(path)` is inherently vulnerable to Time-of-Check to Time-of-Use (TOCTOU) race conditions: an attacker or rogue process with local storage access can swap an admitted binary on disk between the moment a security daemon checks its hash and the moment the kernel invokes it.
   The `qf-runtime-admit` engine closes this specific executable path-substitution race through kernel-level file-descriptor pinning:
   * The launcher opens the target binary with `O_RDONLY | O_CLOEXEC`.
   * It calculates the SHA-256 digest and verifies the Ed25519 digital signature directly over the open file descriptor (`fd`).
   * It completely purges the dynamic loader environment, stripping `LD_PRELOAD`, `LD_LIBRARY_PATH`, and unauthorized environment overrides.
   * It executes the binary directly from the open descriptor using the `fexecve(fd, argv, envp)` system call.
   Because the file descriptor pins the exact inode and data blocks verified in memory, on-disk file swapping is mathematically defeated ($EXECUTED\_FD == VERIFIED\_FD$).
5. **Zero-Trust Network Perimeter:**
   Internal daemons bind strictly to loopback `127.0.0.1:9000`. Remote mesh connectivity is mediated exclusively via Tailscale Serve MagicDNS HTTPS (`https://fedora.example-tailnet.ts.net/`) and tailnet TCP forwarders (`100.64.1.17:9000`), terminating TLS internally with zero open ports exposed to physical local Wi-Fi or LAN interfaces (`192.168.0.x`).

---

#### [PAGE 4] Empirical Laboratory Proofs (Self-Assessed TRL-4 Baseline)
All technical claims, latency figures, and resilience assertions in this proposal are backed by empirical test logs cataloged in [`docs/AFWERX_CLAIM_LEDGER.md`](file:///home/quant/mycelium/docs/AFWERX_CLAIM_LEDGER.md) and fully documented in the 10-page Technical Appendix ([`docs/DUE_DILIGENCE_DOSSIER.pdf`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.pdf)). In accordance with Government Accountability Office (GAO) guidelines, the current prototype represents a **self-assessed TRL 4** (integrated components and breadboards validated in a laboratory environment).

```
=========================================================================================================
                           TRL-4 EMPIRICAL VERIFICATION SUMMARY MATRIX
=========================================================================================================
Claim ID | Operational Invariant Tested            | Measured Empirical Result              | Status
---------------------------------------------------------------------------------------------------------
CL-01    | Valgrind Zero-Leak Memory Invariance    | 0 errors / 0 bytes leaked (37/37 frees)| VERIFIED
CL-02    | EWMA LIF Telemetry Cadence Under Attack | 15.01s interval (Nominal: 15.00s)      | VERIFIED
CL-03    | Shamir Threshold State Transition       | 4.651 ms transition latency            | VERIFIED
CL-04    | Decoupled Ingestion Acknowledgment      | 3.9–8.5 ms receipt (average 6.29 ms)   | VERIFIED
CL-05    | Atomic Configuration Hot-Swap           | < 35 ms atomic rewrite latency (Twrite)| VERIFIED
CL-06    | Automated Regression Suite Pass Rate    | 30 passed, 1 warning (0.42s, c.31ed9c9)| VERIFIED
CL-07    | QF-A4 Pre-Link Raw Byte Hash Check      | 100% fail-closed on flipped byte       | VERIFIED
CL-08    | QF-A5 Detached Ed25519 Provenance       | 7/7 negative adversarial cases caught  | VERIFIED
CL-09    | QF-A6 TOCTOU-Resistant Runtime Admit    | 11/11 adversarial cases pass (fexecve) | VERIFIED
CL-10    | Zero-Loss Kafka Pipeline Invariant      | 0 dropped pulses on DB disconnect      | VERIFIED
CL-11    | SQLite WAL Lease Fencing (claim_token)  | 0 race-condition overwrites            | VERIFIED
CL-12    | Mobile Hardware Role Segregation       | Observer mutations fail-closed (DENY)  | VERIFIED
CL-13    | Zero-Trust Mesh Network Boundary        | 0 open listeners on local LAN (Wi-Fi)  | VERIFIED
CL-14    | NIST CMVP / CAVP Formal Certification   | Certificate: NULL (Pre-validation)     | NOT CLAIMED
=========================================================================================================
```

#### Detailed Empirical Narrative:
1. **Memory Cleansing & Zeroization (`CL-01`):**
   Full leak verification conducted under Valgrind Memcheck 3.27.1 on the Shamir secret recovery engine (`tools/genesis_tool.cpp`) and zeroization suite (`tools/test_zeroization.cpp`). Post-recovery inspection confirmed that `OPENSSL_cleanse` overwrote 100% of secret shard buffers on both heap and stack, leaving `0 bytes in use at exit in 0 blocks` across 37 total allocations and 37 frees.
2. **Measured EWMA Response Under Controlled Hostile Socket Injection (`CL-02`):**
   Under continuous injection of forged Ed25519 signatures and malformed QFXK wire frames, the Leaky Integrate-and-Fire sentinel rejected 100% of adversarial packets at socket ingress. Nominal telemetry streaming maintained an unbroken cadence of **15.01 seconds** (nominal target: 15.00s; cadence jitter $\Delta < 0.1\%$) with zero CPU spikes or thread exhaustion.
3. **Shamir Threshold Unlock Latency (`CL-03`):**
   Benchmarking the transition of the cryptographic core from `LOCKED` to `ACTIVE` across a 2-of-3 Shamir threshold ceremony yielded a completed state transition in **4.651 ms**, enabling near-instantaneous key recovery under tactical edge constraints.
4. **Decoupled Intake Acknowledgment (`CL-04`):**
   Durable telemetry intake benchmarks across 9 test suites demonstrated that HTTP 202 client receipts return in **3.9–8.5 ms** (average 6.29 ms) locally, completely decoupled from local neural inference latency. SQLite WAL persistence with `synchronous=FULL` guarantees durability prior to socket release.
5. **Comprehensive Automated Test Battery (`CL-06`):**
   The unified test battery at commit `31ed9c9` achieved 100% determinism: 30 of 30 tests passed in 0.42s covering external verifier security (6), zero-loss Kafka consumer offset commits (7), intake lease fencing (3), mobile CLI role segregation (5), mobile distribution signatures (4), and mobile OTA routes (5). The single warning recorded (`DeprecationWarning: anyio.abc.BlockingPortal alias is deprecated`) is classified as a **benign external dependency notice** in Starlette TestClient with zero operational impact.
6. **Regulatory Demarcation (`CL-14`):**
   In strict compliance with federal procurement governance, NIST CMVP and CAVP certificates are recorded as `NULL`. QuantumFlex is an internal pre-validation engineering research prototype designed to prime formal accredited laboratory evaluation during SBIR Phase II.

---

### [PAGE 5] Operational Defense Problem & Opportunity

#### 1. The Strategic Post-Quantum Mandate
National Security Systems are entering a staged transition toward post-quantum cryptography under CNSA 2.0 and related federal migration policy, creating an engineering need for crypto-agile systems that can validate, replace, and operationally bind cryptographic components without introducing uncontrolled runtime or supply-chain state. NSA's published draft CSfC PQC guidance (**CSfC Post Quantum Cryptography Guidance Addendum 1.0, Draft .5**) lays out a staged transition requirement for new products and services in applicable Commercial Solutions for Classified (CSfC) contexts beginning in **2027**, with broader migration milestones extending through **2030–2031** (and NSM-10 targeting **2035** for full NSS migration). ML-KEM and ML-DSA themselves are finalized NIST standards under **FIPS 203** and **FIPS 204**.

#### 2. The Operational Threat Matrix
Current Department of the Air Force and Joint Force edge communications architectures suffer from three critical architectural vulnerabilities:

```
+---------------------------------------------------------------------------------------------------------+
|                                    TACTICAL THREAT & VULNERABILITY MATRIX                               |
+---------------------------------------------------------------------------------------------------------+
| Threat Vector                  | Operational Mechanism               | Impact on DAF Enclaves            |
+--------------------------------+-------------------------------------+-----------------------------------+
| 1. Single-Lattice Fragility    | Hardcoding a single PQC primitive   | Total datalink blackout if        |
|    & "Harvest Now, Decrypt     | without automated algorithm agility | mathematical/side-channel flaw    |
|    Later" (HNDL) Exploitation  | or fallback diversity.              | is discovered in ML-KEM.          |
+--------------------------------+-------------------------------------+-----------------------------------+
| 2. Socket Poisoning &          | API gateways parse, buffer, and log | Airborne edge nodes suffer CPU    |
|    Computational Exhaustion    | every unauthenticated/malformed     | spikes, thread deadlocks, and     |
|    Denial-of-Service           | packet, causing heap bloat.         | dropped tactical telemetry.       |
+--------------------------------+-------------------------------------+-----------------------------------+
| 3. On-Disk Binary Swapping     | Malicious local processes swap      | Hostile binaries execute with     |
|    at the Contested Edge       | update binaries on disk between     | full edge system privileges       |
|                                | hash check and kernel execution.    | during in-flight OTA updates.     |
+--------------------------------+-------------------------------------+-----------------------------------+
```

1. **Single-Lattice Fragility & Harvest-Now-Decrypt-Later (HNDL):**
   Adversarial nation-states are actively recording encrypted military radio, datalink, and satellite communications today with the intent to decrypt them once cryptanalytic capabilities or large-scale quantum computers mature. Furthermore, virtually all defense PQC implementations rely exclusively on Module-Lattice cryptography (NIST FIPS 203/204). If an unexpected algebraic breakthrough impairs structured lattices, deployed tactical aircraft will face immediate communications blackout requiring physical depot hardware refits.
2. **Computational Exhaustion & Host Resource Starvation:**
   Standard military data gateways attempt to parse, deserialize, buffer, and audit every incoming network packet. Under intentional adversarial jamming or forged signature flooding, tactical edge computers (constrained by strict size, weight, power, and thermal limits) suffer severe CPU saturation and memory leaks, starving core avionics flight software of compute cycles.
3. **On-Disk Binary Swapping on Contested Edge Hardware:**
   Tactical edge nodes receiving Over-The-Air (OTA) software and algorithm updates risk Time-of-Check to Time-of-Use race conditions. Malicious processes resident on the device can overwrite verified executables on non-volatile flash storage immediately before kernel execution, bypassing static hash checks.

#### 3. The Defense Innovation Opportunity
There is an immediate requirement for an autonomous, software-defined **Crypto-Agility and Shock-Absorption Sidecar** that can be retrofitted onto existing tactical datalinks. QuantumFlex solves this operational gap by decoupling cryptography from control logic, filtering hostile packets under controlled socket-load and adversarial network-stress testing, and mathematically binding executable file descriptors in kernel memory without requiring airframe redesign.

---

### [PAGE 6] Defense Need & Operational Alignment

#### 1. Target Military Operational Enclaves
QuantumFlex directly addresses urgent security requirements across three primary Department of the Air Force and Space Force operational enclaves:

```
+---------------------------------------------------------------------------------------------------------+
|                                    TARGET OPERATIONAL DEFENSE ENCLAVES                                  |
+---------------------------------------------------------------------------------------------------------+
| Enclave Name               | Target Platforms                    | Operational Benefit Delivered         |
+----------------------------+-------------------------------------+---------------------------------------+
| 1. Tactical Airborne       | Link 16 Gateways, Advanced Datalink | Sub-35ms algorithm agility without    |
|    Communications Mesh     | Pods, Common Open Mission Systems   | dropping active airborne RF sockets   |
|                            | (COMS) architecture.                | or requiring flight-line hardware.    |
+----------------------------+-------------------------------------+---------------------------------------+
| 2. Contested Edge UAS      | Group 3–5 Unmanned Aerial Systems   | EWMA shock absorption prevents CPU    |
|    Autonomous Nodes        | (MQ-9, Collaborative Combat         | exhaustion under electronic warfare   |
|                            | Aircraft [CCA]).                    | and forged packet injection.          |
+----------------------------+-------------------------------------+---------------------------------------+
| 3. Resilient Space         | Proliferated Warfighter Space       | Zero-leak memory destruction post-key |
|    Cross-Link Mesh         | Architecture (PWSA) cross-links and | recovery; deterministic telemetry     |
|                            | protected tactical satellite nodes. | streaming over low-bandwidth links.   |
+----------------------------+-------------------------------------+---------------------------------------+
```

#### 2. Candidate Air Force Discovery Stakeholders
During Phase I customer discovery, FINALLYFUNGUS LLC will engage candidate technical evaluators and transition program offices across the DAF ecosystem:

1. **Candidate Transition Stakeholder: PEO Cyber and Networks (formerly AFLCMC/HN C3I&N, Hanscom AFB, MA)**
   * *Organizational Alignment:* Cryptographic Modernization Branch & Airborne Tactical Datalinks Division.
   * *Mission Synergy:* PEO Cyber and Networks oversees cryptologic hardware and datalink security across the Air Force fleet. QuantumFlex provides a software-defined path to meet CNSA 2.0 staged migration timelines without replacing flight-line cryptographic chassis.
2. **Candidate R&D Stakeholder: Air Force Research Laboratory (AFRL) Information Directorate (Rome, NY)**
   * *Organizational Alignment:* Cyber Assurance Branch & Quantum Information Systems Branch.
   * *Mission Synergy:* AFRL/RI develops resilient edge computing and secure cyber architectures. QuantumFlex’s formal invariant modeling ($Y = (x - h) + k$), Ghost Node entropy shunting, and Valgrind-verified memory zeroization directly align with AFRL’s mission to harden edge enclaves against advanced cyber threats.
3. **Candidate Space Stakeholder: Space Systems Command (SSC, El Segundo, CA / Colorado Springs, CO)**
   * *Organizational Alignment:* Space Sensing Directorate & Protected Tactical SATCOM Program Office.
   * *Mission Synergy:* SSC requires ultra-reliable, zero-leak telemetry ingestion and post-quantum security for space vehicle cross-links operating in high-radiation, unattended orbital regimes.

---

### [PAGE 7] Transition Potential & Customer Discovery Plan

#### 1. Phase I Customer Discovery Methodology
In strict alignment with the AFWERX Open Topic mandate, Phase I will be executed primarily as an intensive **Customer Discovery and Technical Feasibility Campaign**. The contractor will conduct a minimum of **≥30 structured discovery engagements** across candidate stakeholders, user commands, and defense primes.

```
+---------------------------------------------------------------------------------------------------------+
|                                    CUSTOMER DISCOVERY ENGAGEMENT PIPELINE                               |
+---------------------------------------------------------------------------------------------------------+
|  Discovery Pool: 40+ Qualified Stakeholders across DAF, Joint Force, and Defense Primes                 |
|  [ Hanscom AFB (PEO Cyber) ]    [ Rome Research Site (AFRL/RI) ]    [ Space Systems Command (SSC) ]     |
|                                                |                                                        |
|                                                v                                                        |
|                        Target: ≥30 Completed Structured Discovery Sessions                              |
|                                                |                                                        |
|                                                v                                                        |
|  Documented Deliverable Outputs:                                                                        |
|  1. Validated Mission Problem Statements   4. Security Accreditation & CSfC Roadmap                     |
|  2. Tactical SWaP-C & Interface Baselines  5. Candidate TPOC / End-User Evaluation Roster               |
|  3. Bus Protocol Constraints (MIL-STD-1553)6. Documented Objections & Technical Gaps                    |
+---------------------------------------------------------------------------------------------------------+
```

#### 2. Concrete Customer Discovery Outputs
Every engagement will feed into a rigorous discovery database generating six concrete operational outputs:
1. *Validated Mission Problem Statements:* Documented operational pain points in cryptographic re-keying, key distribution under Disconnected, Intermittent, Limited (DIL) bandwidth, and socket degradation.
2. *Tactical SWaP-C & Interface Envelopes:* Concrete physical constraints across target platforms (e.g., maximum allowable RAM footprint $< 128\text{ MB}$, CPU budget $< 5\%$, bus latency $< 10\text{ ms}$).
3. *Security Accreditation Pathways:* Identification of required Air Force Risk Management Framework (RMF) security controls, CNSSI 1253 overlays, and NSA Commercial Solutions for Classified (CSfC) capability package requirements.
4. *Procurement & Funding Element Mapping:* Identification of specific Program Element (PE) funding lines and modernization roadmaps across Air Force Major Commands (ACC, AFGSC, AFSOC).
5. *Candidate TPOC / End-User Roster:* Prospective technical evaluators to sponsor operational testing.
6. *Documented Objections & Technical Hurdles:* Operational feedback that will directly define the engineering specifications for the Phase II prototype.

#### 3. Phase II Transition Objective
The primary transition milestone for Phase I is to:
> **Pursue and document Phase II transition interest, including Letters of Intent (LOI), Memoranda of Agreement (MOA), or equivalent customer evidence where obtainable.**

Securing formal customer interest will establish the foundation for a competitive **AFWERX SBIR Phase II proposal (up to $1,250,000)** to integrate QuantumFlex into an operational avionics testbed or tactical communications pod.

---

### [PAGES 8–9] Commercialization & Dual-Use Market Strategy

#### [PAGE 8] Dual-Use Commercial Market Opportunities & Operational Case Study
The systemic vulnerabilities addressed by QuantumFlex—cryptographic fragility, socket exhaustion, and supply-chain tampering—are identical across both contested tactical edges and commercial critical infrastructure. Rather than relying on speculative TAM/SAM projections, FINALLYFUNGUS LLC has validated its dual-use data plane against high-consequence physical facility operations.

```
+---------------------------------------------------------------------------------------------------------+
|                                    DUAL-USE OPERATIONAL PARALLEL                                        |
+---------------------------------------------------------------------------------------------------------+
|  DEFENSE EDGE (Air Force Agile Combat Employment - ACE)  |  COMMERCIAL EDGE (Critical Physical Facilities)|
+----------------------------------------------------------+------------------------------------------------+
|  * Disconnected, Intermittent, Limited (DIL) links       |  * Saturated / failed cellular & cloud links   |
|  * Forward operating sites without reachback to cloud    |  * Medical cold chain & cold storage facilities|
|  * Zero third-party telemetry / no SaaS credentials      |  * Zero third-party cloud data leakage (ACID)  |
|  * Strict human-in-the-loop mission command approval     |  * Strict human dispatch approval (draft-only) |
|  * Sub-10ms localized event ingress & shock absorption   |  * Sub-10ms decoupled HTTP 202 ingress         |
+----------------------------------------------------------+------------------------------------------------+
                                                           |
                                                           v
                                    [ Common Core Sovereign Software Asset ]
                                    * C++20 Zero-Trust Engine & mTLS 1.3 Floor (:9444)
                                    * Rust Ghost Anomaly Sink & Hash-Chain Ledger (:19443)
                                    * Decoupled Loopback Intake & SQLite WAL Durability (:5680)
                                    * Local Model Triage Engine (Ollama / Qwen2.5 @ :11434)
```

1. **Market 1: Critical Cold Chain, Industrial Facilities & Emergency Dispatch:**
   * *Target Customers:* Industrial refrigeration plants, food distribution centers, pharmaceutical cold chain facilities, and critical HVAC/mechanical contractors.
   * *Operational Threat:* High-consequence facility operations suffer catastrophic inventory loss when equipment failures are delayed or dropped due to cloud latency, vendor outages, or public SaaS API rate limits.
   * *Empirical Validation (Scranton Cold Storage Case Study):* FINALLYFUNGUS LLC deployed and verified the QuantumFlex intake architecture under active load:
     - **Decoupled Ingress:** Measured **8.25 ms** loopback receipt response (`HTTP 202 Accepted`), persisting customer tickets to disk (SQLite WAL + `synchronous=FULL`) before model inference begins (CL-04).
     - **Atomic Worker Leases:** Worker claims enforced via unique cryptographic fencing tokens (`claim_token`), eliminating duplicate processing and race conditions (CL-11).
     - **Localhost Model Triage:** Evaluated via local `qwen2.5-coder:7b` in **5.35s–9.33s** (warm avg 6.85s), correctly categorizing critical refrigeration emergencies (`CRITICAL` / `COMMERCIAL_REFRIGERATION`) with zero outbound data leakage (`customer_receipt_delivered = 0`, `operator_alert_delivered = 0`).
     - **Fault Recovery:** 100% recovery of orphaned in-flight tickets following simulated worker termination.
2. **Market 2: Critical Infrastructure SCADA & Industrial Control Systems (ICS):**
   * *Target Customers:* Regional transmission operators, water treatment authorities, and energy pipeline operators requiring local cryptographic shock absorption without risking process crashes.
   * *Operational Value:* Legacy Remote Terminal Units (RTUs) and Programmable Logic Controllers (PLCs) possess minimal compute power and crash when subjected to malformed packet storms. QuantumFlex acts as an edge shock absorber, intercepting corrupted or unauthenticated MODBUS/DNP3 frames under controlled socket-stress conditions without degrading supervisory control.
3. **Market 3: Enterprise Post-Quantum Zero-Trust Migration:**
   * *Target Customers:* Tier-1 financial institutions, healthcare data backbones, and telecommunications providers subject to OMB M-26-15, SEC cyber disclosure rules, and European NIS2 compliance directives.
   * *Operational Value:* Enterprise networks require automated cryptographic discovery, dynamic CycloneDX 1.5 Cryptographic Bill of Materials (CBOM) generation, and mathematically verifiable memory zeroization to protect long-duration financial and medical records against Harvest-Now-Decrypt-Later threats.

---

#### [PAGE 9] Commercialization Business Model & Intellectual Property Strategy
FINALLYFUNGUS LLC will commercialize QuantumFlex through a structured commercial licensing model and statutory SBIR data rights framework:

```
+---------------------------------------------------------------------------------------------------------+
|                                  COMMERCIALIZATION & DATA RIGHTS FRAMEWORK                              |
+---------------------------------------------------------------------------------------------------------+
| Commercial Enterprise Tier                             | Defense Sector: SBIR Data Rights Framework     |
+--------------------------------------------------------+------------------------------------------------+
| * Per-Node Annual Subscription: $1,200–$4,800/yr       | * DFARS 252.227-7018 SBIR Data Rights apply    |
| * Dynamic CBOM Generation & Continuous Asset Discovery | * Technical Data: Limited Rights for 20 years  |
| * Automated OPA Rego Policy Updates & Compliance Logs  | * Computer Software: Restricted Rights (20 yrs)|
| * Tier-1 24/7 Enterprise Mission-Critical Support      | * Government Purpose Rights apply post-20 yrs  |
| * Special License Rights negotiated as required        | * Dedicated Airframe Integration Services      |
+--------------------------------------------------------+------------------------------------------------+
```

1. **Commercial Pricing Model:**
   * *Edge Node Subscription:* Billed annually per deployed gateway node ($1,200 to $4,800/node/year based on bandwidth throughput and high-availability clustering).
   * *Enterprise Controller License:* Centralized management dashboard providing continuous organizational CBOM aggregation, policy orchestration, and automated anomaly auditing ($25,000 to $75,000/year).
2. **Defense Data Rights & Contract Framework:**
   * In accordance with **DFARS 252.227-7018** (Rights in Technical Data and Computer Software: Small Business Innovation Research Program), the Government receives **SBIR Data Rights** across all technical data and computer software developed under the contract for a protection period of **twenty (20) years** from award.
   * During this 20-year period, technical data is protected under limited rights and computer software under restricted rights; the Government receives Government Purpose Rights (GPR) only after the expiration of the 20-year protection period unless special license rights are mutually negotiated.
3. **Intellectual Property (IP) Strategy:**
   * *Trade Secrets & Proprietary Assertions:* FINALLYFUNGUS LLC asserts trade secret protection over proprietary implementation details, mathematical parameterizations, undisclosed internal source code, and deployment heuristics governing the EWMA LIF shock absorber and the QF-A6 runtime admission engine. (Standard public mathematical concepts and Linux system calls such as `fexecve` are not claimed as trade secrets).
   * *Open-Source Boundary:* Permissively licensed public wrappers (`Apache-2.0`) provide zero-dependency client integration without disclosing proprietary kernel binding or defense policy logic.
4. **Three-Year Commercialization Milestones:**
   * *Year 1 (2026–2027):* Complete AFWERX Phase I customer discovery; secure Phase II award; conduct laboratory hardware-in-the-loop testing with defense prime partner.
   * *Year 2 (2027–2028):* Deploy operational prototype in Air Force tactical pod demonstration; onboard 3 commercial beta customers in electrical SCADA grids.
   * *Year 3 (2028–2029):* Achieve formal FIPS 140-3 / CAVP laboratory certification; scale commercial enterprise ARR to $2.5M+ across critical infrastructure operators.

---

### [PAGE 10] Prior, Related & Competitor Work

#### 1. Prior Work Developed by Offeror (Self-Assessed TRL-4 Baseline)
FINALLYFUNGUS LLC has self-funded and engineered an operational, laboratory-validated prototype system (`QuantumFlex` / `mycelium`), establishing a proven self-assessed TRL 4 baseline:
* **Standalone Cryptographic Data Plane:** Fully modular C++20 engine containing NIST FIPS 203 (ML-KEM-768/1024), FrodoKEM-976, and X25519 primitives, decoupled from host control logic.
* **Host-Anchored External Verifier:** Created `verify-provenance` binary and CMake admission gate (`AdmitQuantumFlex.cmake`) enforcing strict XOR developer vs attested package exclusivity.
* **Kernel-Bound Runtime Admission Launcher:** Created `qf-runtime-admit` utility closing on-disk executable path-substitution races via `fexecve(fd)`.
* **Automated 30-Test Regression Suite:** Validated 100% deterministic test execution across unit, integration, and security test harnesses in 0.42s at commit `31ed9c9`.

#### 2. Competitor Analysis & State-of-the-Art Differentiation
Conventional market solutions fail to provide the combined attributes of post-quantum algorithm agility, socket-level shock absorption, and binary execution binding required by tactical defense enclaves:

```
+---------------------------------------------------------------------------------------------------------+
|                                    COMPETITIVE DIFFERENTIATION MATRIX                                  |
+---------------------------------------------------------------------------------------------------------+
| Capability / Feature           | QuantumFlex       | Traditional VPNs  | Hardware Security | Cloud Secret   |
|                                | (Proposed System) | (IPsec/WireGuard) | Modules (HSMs)    | Vaults (KMS)   |
+--------------------------------+-------------------+-------------------+-------------------+----------------+
| Sub-35ms In-Flight Hot Rollover| YES (In-Memory)   | NO (Tears Down RF)| NO (Reboot Req)   | NO (High Lat.) |
| Post-Quantum Multi-Lattice     | YES (ML-KEM +     | NO (Hardcoded     | PARTIAL (Rigid    | PARTIAL (Cloud |
| Fallback Agility               | FrodoKEM + X25519)| Single Cipher)    | Microcode)        | Dependent)     |
| Socket Shock Absorber (LIF)    | YES (Zero CPU     | NO (CPU Spikes    | NO (Buffer        | NO (Rate-Limit |
| Under Hostile Packet Injection | Saturation)       | Under Jamming)    | Exhaustion)       | 429 Errors)    |
| Zero-Leak Memory Destruction   | YES (Valgrind     | NO (Heap Buffer   | YES (Hardware     | NO (Managed    |
| (Compiler-Barrier Cleanse)     | 0-Byte Leak Audit)| Residuals)        | Enclave Zeroize)  | Runtime GC)    |
| TOCTOU File-Descriptor Binding | YES (Kernel       | NO (Path-Based    | N/A (Firmware     | N/A (API Key   |
| (EXECUTED_FD == VERIFIED_FD)   | fexecve Pinning)  | execve Injection) | Only)             | Token Only)    |
| Tactical SWaP-C Compatibility  | YES (<64MB RAM;   | YES (Software)    | NO (Heavy, Power- | NO (Requires   |
| (Constrained Edge Hardware)    | Single-Threaded)  |                   | Hungry Chassis)   | Global WAN)    |
+--------------------------------+-------------------+-------------------+-------------------+----------------+
```

* **Versus Traditional VPN Gateways:** Standard protocols (IPsec, OpenVPN, WireGuard) require full cryptographic renegotiation and socket teardown during key rotation, severing active airborne RF datalinks. Under packet flooding attacks, they parse headers into memory, causing CPU saturation. QuantumFlex switches ciphers in $< 35\text{ ms}$ in memory without socket drops and drops malicious packets via branchless LIF filtering.
* **Versus Hardware Security Modules (HSMs):** While HSMs offer physical tamper protection, they are heavy, power-hungry, expensive, and require physical replacement or firmware re-flashing to support new post-quantum standards. QuantumFlex provides software-defined agility on edge compute platforms and tactical single-board architectures.

---

### [PAGES 11–12] Phase I Feasibility Work Plan (Statement of Work)

#### [PAGE 11] Technical Scope & Task Breakdown
The contractor shall conduct a 90-day technical feasibility study and customer discovery campaign to establish operational requirements, validate tactical bus interfaces, and assess hardware-enclave integration pathways for QuantumFlex.

```
+---------------------------------------------------------------------------------------------------------+
|                                    PHASE I WORK BREAKDOWN SCHEDULE                                      |
+---------------------------------------------------------------------------------------------------------+
|  TASK 1: Tactical Customer Discovery & Interface Baselines (Days 1–30)                                  |
|  * Subtask 1.1: Conduct ≥30 structured DAF discovery interviews (PEO Cyber/Networks, AFRL, SSC).        |
|  * Subtask 1.2: Map airborne/edge interface constraints (MIL-STD-1553, Ethernet, Link 16, SWaP-C).      |
|  * Subtask 1.3: Publish Customer Discovery Synthesis & Interface Baseline Report (D1).                  |
+---------------------------------------------------------------------------------------------------------+
                                                     |
                                                     v
+---------------------------------------------------------------------------------------------------------+
|  TASK 2: ACVP-Compatible Test Bench & Hardware Security Enclave Integration (Days 31–60)                |
|  * Subtask 2.1: Construct ACVP-compatible NIST FIPS 203/204 pre-validation test harness.                |
|  * Subtask 2.2: Benchmark hardware trust enclaves & mobile security architectures (Titan M2 / Knox).     |
|  * Subtask 2.3: Stress-profile decapsulation throughput and memory zeroization under controlled socket  |
|                 injection and adversarial network stress.                                               |
|  * Subtask 2.4: Publish Cryptographic Benchmark & Hardware Enclave Feasibility Report (D2).             |
+---------------------------------------------------------------------------------------------------------+
                                                     |
                                                     v
+---------------------------------------------------------------------------------------------------------+
|  TASK 3: Phase II Transition Documentation & Demonstration Architecture (Days 61–90)                     |
|  * Subtask 3.1: Formulate Phase II tactical pod demonstration Statement of Work (SOW).                  |
|  * Subtask 3.2: Pursue and document Phase II transition interest (LOI/MOA where obtainable).            |
|  * Subtask 3.3: Submit Final Phase I Feasibility Report incorporating SF 298 & DD Form 882 (D3).        |
+---------------------------------------------------------------------------------------------------------+
```

```text
CURRENT STATE
───────────────────────────────────────────────────────────────────────────
Lenovo Yoga 7 (Fedora Linux, C++20 runtime, container isolation,
TPM-backed testing, controlled socket injection, A4/A5/A6 security testing)
+ HP Pavilion (distributed worker / network-path testing)
+ Pixel / Samsung (mobile operator / hardware enclave test vectors)
                             ↓
LABORATORY FEASIBILITY (measured + reproducible empirical evidence)
                             ↓
PHASE I CUSTOMER DISCOVERY (Task 1: Days 1–30)
discover actual operational constraints:
- target compute architecture (ARM64, x86_64, RISC-V)
- bus interfaces (MIL-STD-1553, Ethernet, Serial, Link 16)
- SWaP-C limitations (<35W, constrained physical volume)
- cryptographic module requirements & trust anchors
- tactical network conditions (DIL, high packet jitter)
- accreditation constraints (NSA CSfC, Air Force RMF)
                             ↓
REPRESENTATIVE HARDWARE PROCUREMENT (Task 2: Days 31–60)
Direct Materials ($11,000 FAR 31.205-26) & Cloud/CI Compute ODC ($4,000)
                             ↓
PHASE II TRANSITION & OPERATIONAL DEMONSTRATION (Task 3: Days 61–90)
representative tactical hardware / network emulation
                             ↓
operationally relevant airborne / edge demonstration
```

* **Task 1: Tactical Customer Discovery & Interface Baselines (Days 1–30):**
  The contractor shall engage candidate Air Force stakeholders (PEO Cyber and Networks, AFRL Information Directorate, Space Systems Command, and avionics primes), conducting at least **≥30 structured interviews** to define operational problem statements, bus protocols, and SWaP-C limitations.
* **Task 2: ACVP-Compatible Test Bench & Hardware Enclave Integration (Days 31–60):**
  The contractor shall build an automated ACVP-compatible test harness ingesting official NIST Cryptographic Algorithm Validation Program test vectors for FIPS 203 (ML-KEM) and FIPS 204 (ML-DSA). Utilizing Phase I direct technical resources ($15,000 total: $11,000 physical materials under FAR 31.205-26, $4,000 cloud/CI compute ODC), the contractor shall procure representative edge development hardware, single-board modules, and cryptographic evaluation boards as identified through Task 1 customer discovery to benchmark physical trust anchor integration, throughput, and memory zeroization timing.
* **Task 3: Phase II Transition Documentation & Demonstration Architecture (Days 61–90):**
  The contractor shall develop the complete technical architecture and flight-demonstration plan for Phase II tactical pod integration, pursue and document customer transition interest (including Letters of Intent or Memoranda of Agreement where obtainable), and author the final comprehensive feasibility report.

---

#### [PAGE 12] Meetings, Deliverables & Contract Reporting Schedule
In accordance with official AFWERX Open Topic SOW guidelines, all contract reporting events and deliverables are scheduled as follows:

```
+---------------------------------------------------------------------------------------------------------+
|                                    FORMAL DELIVERABLES & REPORTING SCHEDULE                             |
+---------------------------------------------------------------------------------------------------------+
| Event / Deliverable | Due Date   | Description & Statutory Inclusions                                  |
+---------------------+------------+----------------------------------------------------------------------+
| Kickoff Meeting     | Day 15     | Virtual contract orientation with Air Force TPOC / program office.   |
| Deliverable D1      | Day 30     | Tactical Interface Baseline & Customer Discovery Synthesis Report.   |
| Preliminary Report  | Day 45     | Mid-term progress report detailing stakeholder discovery findings.   |
| Deliverable D2      | Day 60     | ACVP-Compatible Test Bench & Hardware Enclave Feasibility Assessment.|
| Final Meeting       | Day 85     | Final technical briefing and Phase II demonstration review.          |
| Deliverable D3      | Day 90     | Final Comprehensive Feasibility Report & Phase II Transition Plan,   |
| (Final Report)      |            | formally incorporating Standard Form 298 (SF 298) and DD Form 882.   |
+---------------------------------------------------------------------------------------------------------+
```

1. **Kickoff Meeting (Day 15):** Virtual meeting with the designated Air Force Technical Point of Contact (TPOC) to review milestones, confirm communication channels, and approve interview outreach protocols.
2. **Deliverable D1 (Day 30):** *Tactical Interface Baseline & Customer Discovery Synthesis Report.* Synthesizes findings from initial stakeholder discovery, defining platform physical interfaces, SWaP-C envelopes, and datalink constraints.
3. **Preliminary Progress Report (Day 45):** Formal mid-term progress report submitted via DSIP summarizing interview metrics, technical challenges encountered, and initial test bench progress.
4. **Deliverable D2 (Day 60):** *ACVP-Compatible Test Bench & Hardware Enclave Feasibility Assessment.* Documents the automated KAT validation harness, algorithm cycle counts, memory zeroization benchmarks, and TPM 2.0 integration feasibility.
5. **Deliverable D3 (Day 90 — Final Comprehensive Report):** Comprehensive final feasibility report incorporating all customer discovery transcripts, architectural designs, commercialization milestones, and Phase II demonstration SOW. Formally incorporates:
   * **Standard Form 298 (SF 298):** Report Documentation Page.
   * **DD Form 882:** Report of Inventions and Subcontracts.

---

### [PAGE 13] Key Personnel, Facilities & Corporate Transparency

#### 1. Principal Investigator & Key Personnel
* **Rahshaun Chambers (Lead Systems Architect & Principal Investigator):**
  * *Role & Commitment:* **320 Phase I direct project hours; PI primarily employed by the SBC during performance** (fully satisfying SBA requirements that the PI's primary employment be with the small business concern at the time of award and throughout the period of performance). Dedicated to technical execution across all 3 Phase I tasks (~26.7 direct hours/week).
  * *Technical Background:* Founder of QuantumFlex and lead architect of the `mycelium` code repository. Academic background in Computer Science at Southern New Hampshire University (SNHU), with foundational coursework in operating systems, software engineering, algorithms, and discrete mathematics.
  * *Core Competencies:* Direct experience architecting decoupled C++20 and Rust cryptographic engines, POSIX signal inter-process communication, Open Policy Agent (OPA) Rego sidecar integration, Ed25519 provenance validation gates, and kernel-level `fexecve` file-descriptor execution binding.
* **Subcontractors & Independent Consultants ($5,000 ODC):**
  * The contractor will engage an independent cryptographic consultant with formal NVLAP accredited laboratory evaluation experience to perform pre-assessment reviews of the automated ACVP test bench, entropy interfaces, and memory zeroization routines.

#### 2. Corporate Demarcation & Entity Disclosure
In strict adherence to federal procurement integrity standards:
* **Applicant Firm:** FINALLYFUNGUS LLC (PA Entity ID: 13706513, Pittston, PA) DBA QuantumFlex.
* **Commercial Baseline:** Established commercial line operating in agricultural and cultivation supply products.
* **Research Line:** QuantumFlex operates as an early-stage cybersecurity and post-quantum software R&D initiative chartered to resolve algorithmic brittleness and data hoarding in national security systems.
* **Foreign Ownership & Control:** FINALLYFUNGUS LLC is 100% American-owned and operated. **No known foreign ownership, control, or influence identified in company records as of submission.**

#### 3. Facilities & Prototype Laboratory Baseline
QuantumFlex is currently developed and validated on a **laptop-centered physical prototype laboratory** rather than specialized military or rack-mounted test equipment. The primary engineering node is a Lenovo Yoga 7 running Fedora Linux, providing the C++20 runtime, cryptographic test environment, container isolation, local policy enforcement, and hardware-backed TPM functionality. A secondary HP Pavilion node is used for distributed-worker and network-path testing, while supported mobile devices provide additional hardware-rooted trust and remote-operator test vectors.

Network and adversarial testing is performed through controlled loopback, isolated container networks, and private mesh paths, allowing repeatable injection of malformed frames, stalled connections, tampered artifacts, provenance failures, and runtime-admission attacks without exposing the prototype to an uncontrolled external network.

This environment has been sufficient to establish laboratory-scale feasibility for memory zeroization, cryptographic admission, fail-closed runtime binding, telemetry behavior, and controlled socket-stress testing. It is not represented as flight-qualified, radiation-hardened, tactical line-rate, or operationally representative Department of the Air Force hardware.

Phase I will use the existing prototype environment as the validated baseline while determining, through customer discovery, the representative compute, interface, SWaP-C, cryptographic-module, and network-emulation hardware required for a Phase II operational demonstration. In summary, QuantumFlex is running on a real multi-node physical prototype environment today, but the present environment is laboratory-grade rather than representative tactical hardware. Phase I explicitly uses customer discovery to determine and procure the representative compute, cryptographic, and network interfaces required for the next-stage demonstration.

---

### [OPTIONAL PAGE 14] Acronyms & Glossary

* **ACVP:** Automated Cryptographic Validation Protocol (NIST)
* **CAVP:** Cryptographic Algorithm Validation Program (NIST)
* **CBOM:** Cryptographic Bill of Materials (CycloneDX 1.5 JSON standard)
* **CCA:** Collaborative Combat Aircraft
* **CISO:** Chief Information Security Officer
* **CMVP:** Cryptographic Module Validation Program (NIST)
* **CNSA:** Commercial National Security Algorithm Suite (NSA)
* **COMS:** Common Open Mission Systems
* **CSfC:** Commercial Solutions for Classified (NSA)
* **DIL:** Disconnected, Intermittent, and Limited communications
* **DSIP:** Defense SBIR/STTR Innovation Portal
* **EWMA LIF:** Exponentially Weighted Moving Average Leaky Integrate-and-Fire
* **FOCI:** Foreign Ownership, Control, or Influence
* **GPR:** Government-Purpose Rights
* **HIL:** Hardware-in-the-Loop
* **HNDL:** Harvest Now, Decrypt Later
* **HSM:** Hardware Security Module
* **ICS:** Industrial Control Systems
* **KAT:** Known Answer Test
* **ML-KEM:** Module-Lattice Key Encapsulation Mechanism (NIST FIPS 203)
* **ML-DSA:** Module-Lattice Digital Signature Algorithm (NIST FIPS 204)
* **MOA:** Memorandum of Agreement
* **MOU:** Memorandum of Understanding
* **NSS:** National Security Systems
* **NVLAP:** National Voluntary Laboratory Accreditation Program
* **OPA:** Open Policy Agent
* **PEO:** Program Executive Office
* **PQC:** Post-Quantum Cryptography
* **RMF:** Risk Management Framework
* **SBC:** Small Business Concern / Single-Board Computer
* **SCADA:** Supervisory Control and Data Acquisition
* **SOW:** Statement of Work
* **SWaP-C:** Size, Weight, Power, and Cost
* **TOCTOU:** Time-of-Check to Time-of-Use
* **TPOC:** Technical Point of Contact
* **UAS:** Unmanned Aerial System
