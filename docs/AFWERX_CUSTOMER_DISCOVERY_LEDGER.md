# 🛰️ QUANTUMFLEX AFWERX SBIR PHASE I CUSTOMER DISCOVERY LEDGER
## Task 1 Discovery Campaign: 30 Planned Engagement Slots (Discovery Registry)

**Entity:** FINALLYFUNGUS LLC (PA Entity ID: 13706513) DBA QuantumFlex  
**Principal Investigator:** Rahshaun Chambers  
**Proposal Title:** QuantumFlex: Autonomous Post-Quantum Cryptographic Agility, Shock-Absorbing Telemetry & TOCTOU-Resistant Runtime Admission for National Security Systems  
**Governing SOW Baseline:** [`docs/AFWERX_PHASE_I_WORK_PLAN.md#L55-L72`](file:///home/quant/mycelium/docs/AFWERX_PHASE_I_WORK_PLAN.md#L55-L72) (Task 1: Days 1–30)  
**Primary Output Deliverable:** Deliverable D1 (*Tactical Interface Baseline & Customer Discovery Synthesis Report*, Day 30)  
**Commit Baseline:** `564dc13`

---

## 1. Discovery Governance & Procurement Ground Rules

> [!IMPORTANT]
> **GOVERNMENT STAKEHOLDER DEMARCATION & DISCOVERY REGISTRY RULES**  
> In accordance with federal procurement governance and the QuantumFlex Claim Ledger ([`docs/AFWERX_CLAIM_LEDGER.md`](file:///home/quant/mycelium/docs/AFWERX_CLAIM_LEDGER.md)):
> 1. **30 Registry Rows $\neq$ 30 Completed Engagements:** This document establishes a **30-target discovery campaign** maintaining **30 planned engagement slots**. An engagement is classified as **`COMPLETED`** strictly after conducting the structured interview and recording verified stakeholder feedback ("What They Actually Said").
> 2. **Candidate Status Only:** All Department of the Air Force (DAF), Space Force, and Department of Defense (DoD) organizations listed herein are designated as **CANDIDATE DISCOVERY STAKEHOLDERS**. No organization is claimed as a customer, partner, or transition sponsor prior to an executed MOU, MOA, or LOI.
> 3. **Hardware Determination Linkage:** Discovery findings directly dictate the selection of representative edge compute and cryptographic evaluation hardware for Phase I Direct Materials ($11,000 under FAR 31.205-26) and Compute ODC ($4,000) under Task 2, establishing the empirical requirements for Phase II operational demonstration.
> 4. **Standard Lifecycle Statuses:** Every slot in this registry is tracked through one of five standard states:  
>    `PLANNED` $\rightarrow$ `CONTACTED` $\rightarrow$ `SCHEDULED` $\rightarrow$ `COMPLETED` $\rightarrow$ `FOLLOW-UP`.

---

## 2. Priority Target Stakeholder Profiles

### Target Profile 1: Hanscom AFB — PEO Cyber & Networks (AFLCMC/HN)
* **Directorate:** Command, Control, Communications, Intelligence and Networks (C3I&N)
* **Mission Scope:** Development and fielding of tactical communications, airborne datalink gateways, and cryptographic modernization systems for combat air and Joint All-Domain Command and Control (JADC2) operations.
* **Core Problem Statement:** Existing airborne cryptosystems require static keying, manual re-key ceremonies, or link resets that sever active RF connections during key rotation. High bit-error-rate and Disconnected, Intermittent, and Limited (DIL) environments cause crypto-synchronization loss.
* **QuantumFlex Technical Match:**
  * Sub-35 ms atomic configuration and cipher migration without tearing down active network sockets.
  * Measured EWMA response under hostile socket injection (`CL-02`), preventing buffer starvation on tactical edge transceivers.
* **Primary Discovery Questions:**
  1. What is the allowable socket re-key latency window across airborne datalinks (e.g., Link 16, MADL, TTNT) before mission telemetry drops?
  2. How do current datalink gateways handle adversarial packet flooding and corrupted frame injection at edge nodes?
  3. What are the size, weight, and power (SWaP-C) limitations for retrofitting software-defined sidecars onto existing Line Replaceable Units (LRUs)?

---

### Target Profile 2: Rome Research Site — AFRL Information Directorate (AFRL/RI)
* **Directorate:** Cyber Assurance & Resilient Edge Computing Division
* **Mission Scope:** Advanced R&D in post-quantum cryptography, formal methods, secure edge execution, and resilient distributed mesh networks for contested environments.
* **Core Problem Statement:** CNSA 2.0 mandates post-quantum transition (FIPS 203 ML-KEM, FIPS 204 ML-DSA), but legacy edge hardware lacks the compute capacity for monolithic crypto upgrades. Unverified code execution on edge devices introduces supply-chain vulnerabilities.
* **QuantumFlex Technical Match:**
  * ACVP-compatible test harness ingesting official NIST CAVP vectors for FIPS 203/204.
  * TOCTOU-resistant runtime admission (`fexecve` FD pinning, `CL-09`), closing on-disk binary swapping before kernel execution.
  * Mathematical memory zeroization (`0 bytes leaked`, `CL-01`) verified post-Shamir threshold recovery.
* **Primary Discovery Questions:**
  1. What formal evaluation metrics does AFRL/RI require for pre-validation post-quantum cryptographic primitives?
  2. How does the Directorate evaluate TOCTOU race condition mitigations on flash-constrained microcontrollers versus Linux-based SBCs?
  3. What are the key architectural criteria for integrating sidecar engines into the Common Open Mission Systems (COMS) standard?

---

### Target Profile 3: Air Combat Command — ACC / A6 (Tactical Edge Communications)
* **Directorate:** Directorate of Communications and Information
* **Mission Scope:** Agile Combat Employment (ACE) communications resilience, austere forward operating node defense, and multi-domain command and control under active electronic warfare.
* **Core Problem Statement:** Forward-deployed ACE units operate from austere airfields with minimal physical security, intermittent satellite backhaul, and high risk of edge node capture. Memory compromise or stolen hardware risks full cryptographic master key exposure.
* **QuantumFlex Technical Match:**
  * Shamir Secret Sharing threshold unlock (`4.651 ms`, `CL-03`), ensuring master keys never reside unencrypted in persistent non-volatile storage.
  * Mobile command role segregation (`CL-12`), allowing dispersed field operators to authenticate telemetry without holding decryption authority.
* **Primary Discovery Questions:**
  1. What are the zeroization and anti-tamper requirements when an ACE edge node is compromised or abandoned in an austere theater?
  2. How do forward teams verify software and cryptographic patch integrity without continuous access to centralized PKI infrastructure?
  3. What role can COTS mobile devices (e.g., Samsung Knox, Google Pixel Titan M2) play as authenticated operator interfaces?

---

### Target Profile 4: Space Systems Command (SSC / Cyber & Datalinks)
* **Directorate:** Resilient Space Telemetry & Laser Cross-Link Nodes
* **Mission Scope:** Resilient communications, telemetry tracking and control (TT&C), and cross-link encryption for proliferated low-Earth orbit (pLEO) constellations.
* **Core Problem Statement:** In-orbit satellite systems face extreme SWaP-C and radiation constraints. Static cryptographic algorithms cannot be updated once launched, exposing long-duration orbital assets to Harvest-Now-Decrypt-Later threats.
* **QuantumFlex Technical Match:**
  * Decoupled C++20 architecture with sub-64MB memory footprint, ideal for radiation-tolerant single-board space processors.
  * Dynamic cryptographic agility enabling seamless cipher updates over restricted telemetry bandwidth.
* **Primary Discovery Questions:**
  1. What are the operating system and container constraints on next-generation pLEO bus processors?
  2. How is key rollover performed on high-latency space-to-ground and cross-satellite links?

---

### Target Profile 5: Tactical Avionics Primes (Defense Industrial Base)
* **Target Firms:** Primes and Tier-1 sub-system integrators (e.g., Collins Aerospace, Northrop Grumman Mission Systems, Lockheed Martin RMS).
* **Mission Scope:** Pod integration, avionics bus adapters, and edge cryptographic hardware accelerators for Collaborative Combat Aircraft (CCA) and legacy platforms.
* **Core Problem Statement:** Flight recertification for entire flight computers is cost-prohibitive. Any cryptographic modernization must function as a bolt-on sidecar without modifying underlying flight-critical code.
* **QuantumFlex Technical Match:**
  * Independent C++20 data plane operating as a transparent sidecar proxy.
  * Direct support for standard tactical bus interfaces (Ethernet, Serial, MIL-STD-1553 bridging).
* **Primary Discovery Questions:**
  1. What software isolation guarantees (e.g., ARINC 653, SELinux, seccomp) are required for sidecar applications on shared mission processors?
  2. What are the hardware interface standards (e.g., OpenVPX, SOSA) planned for CCA sensor pods?

---

## 3. Master Customer Discovery Interview Registry (30 Planned Engagement Slots)

*Note: All 30 slots represent planned target engagements. Rows transition to `COMPLETED` upon interview completion and verification of testimony.*

| Engagement ID | Organization / Unit | Candidate Role / Persona | Problem Hypothesis | Validated Feedback ("What They Actually Said") | SWaP-C / Bus Constraints | Acquisition / Transition Pathway | Evidence / Ref | Follow-Up Required | Status |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- | :---: | :--- | :---: |
| **ENG-01** | AFLCMC/HN (Tactical Datalinks) | Lead Avionics Systems Engineer | Datalink key rollover drops active airborne RF connections | *[Pending Interview]* | MIL-STD-1553 / Ethernet; <35W | FY28 Datalink Mod Block; CSfC dual-layer | TBD | Schedule via AFRL liaison | `PLANNED` |
| **ENG-02** | AFLCMC/HN (Tactical Datalinks) | Program Manager, Link 16 Mod | DIL link conditions desynchronize static crypto state | *[Pending Interview]* | Serial / IP; <64MB RAM | Airborne Terminal Modernization Line | TBD | Request unclassified briefing | `PLANNED` |
| **ENG-03** | AFLCMC/HN (Crypto Modernization) | NSA CSfC Integration Officer | Lack of agile migration pathway to CNSA 2.0 PQC | *[Pending Interview]* | Dual-layer IPsec/TLS CSfC envelope | CSfC Components List qualification | TBD | Review CSfC Addendum Draft .5 | `PLANNED` |
| **ENG-04** | AFLCMC/HN (Advanced Gateways) | Airborne Gateway Architect | Monolithic gateways cannot bridge legacy and post-quantum buses | *[Pending Interview]* | OpenVPX 3U / 1GbE copper | BACN / E-11A Gateway Tech Refresh | TBD | Coordinate via Hanscom TPOC | `PLANNED` |
| **ENG-05** | AFLCMC/HN (Aerial Networks) | Cyber Defense Lead | Malformed packet storms crash edge datalink processors | *[Pending Interview]* | Socket saturation resilience | DAF Defensive Cyber Operations | TBD | Present EWMA socket data | `PLANNED` |
| **ENG-06** | AFRL/RI (Cyber Assurance) | Senior Research Computer Scientist | PQC implementations introduce untested memory leakage | *[Pending Interview]* | C++20 / Valgrind clean / zero leaks | AFRL Core Research Grant / Phase II | TBD | Share zeroization test suite | `PLANNED` |
| **ENG-07** | AFRL/RI (Resilient Edge Compute) | Lead Edge Security Researcher | Flash storage tampering bypasses static signature verification | *[Pending Interview]* | Linux Kernel namespaces / seccomp | Resilient Edge Computing Line | TBD | Demo `fexecve` test harness | `PLANNED` |
| **ENG-08** | AFRL/RI (Secure Communications) | Post-Quantum Cryptography SME | Hybrid classical-PQC frame headers exceed packet MTU | *[Pending Interview]* | Low-overhead frame encapsulation | CSfC PQC Migration Research | TBD | Transmit ML-KEM frame profile | `PLANNED` |
| **ENG-09** | AFRL/RI (Quantum Information) | Applied Physicist / Info Theory | Volatile key remnants survive incomplete power-down cycles | *[Pending Interview]* | Volatile SRAM zeroization timing | NSA Physical Security Standards | TBD | Provide Valgrind leak proof | `PLANNED` |
| **ENG-10** | AFRL/RI (Embedded Security) | Microelectronics Security Engineer | Discrete TPM evaluation lacks side-channel hardening data | *[Pending Interview]* | ARM64 / SPI TPM 2.0 evaluation bus | Trusted Microelectronics Program | TBD | Inquire on candidate eval boards | `PLANNED` |
| **ENG-11** | ACC / A6 (Tactical Operations) | Tactical Communications Officer (A6) | ACE austere bases lack secure remote master-key distribution | *[Pending Interview]* | Austere solar/battery power (<50W) | Agile Combat Employment Comm Kit | TBD | Present Shamir unlock metrics | `PLANNED` |
| **ENG-12** | ACC / A6 (Edge Network Security) | Defensive Cyber Operations Lead | Overrun of forward node exposes platform master keys | *[Pending Interview]* | Instantaneous zeroization on tamper | Air Force Forward Base Defense | TBD | Discuss physical trigger inputs | `PLANNED` |
| **ENG-13** | ACC / A6 (Expeditionary Comm) | Expeditionary Network Chief | Disconnected edge mesh unable to reach centralized CA | *[Pending Interview]* | Private zero-trust mesh / zero WAN | Tactical Comm Squadron Fielding | TBD | Demo Tailscale/loopback mesh | `PLANNED` |
| **ENG-14** | ACC / A6 (ACE Logistics & Cyber) | ACE Cyber Warfare Planner | Mobile field operators have no secure node provisioning tool | *[Pending Interview]* | Android Knox Vault / Titan M2 | Expeditionary Cyber Tool Kit | TBD | Share mobile CLI role demo | `PLANNED` |
| **ENG-15** | ACC / A6 (Air Operations Center) | Combat Communications Architect | High latency WAN telemetry stalls critical AOC situational feeds | *[Pending Interview]* | Variable latency, intermittent satcom | AOC Weapon System Modernization | TBD | Present intake 202 benchmarks | `PLANNED` |
| **ENG-16** | Space Systems Cmd (Resilient Comm) | Satcom Cyber Architect | Orbital crypto cannot be patched post-launch without mission risk | *[Pending Interview]* | Space-grade ARM64 / Rad-tolerant | Next-Gen Resilient Space Bus | TBD | Review pLEO crypto constraints | `PLANNED` |
| **ENG-17** | Space Systems Cmd (Domain Awareness) | Telemetry Ground Systems Lead | Space telemetry bursts overwhelm ground station ingestion sockets | *[Pending Interview]* | Variable burst rate (>10k msg/s) | Space Delta TT&C Modernization | TBD | Review Kafka pipeline invariants | `PLANNED` |
| **ENG-18** | Space Systems Cmd (Defensive Cyber) | Space Vehicle Security Engineer | Ground-to-space firmware uploads vulnerable to payload alteration | *[Pending Interview]* | Ultra-low bandwidth downlink | Space RMF Accreditation Line | TBD | Share hash-admission evidence | `PLANNED` |
| **ENG-19** | AFTC / 412th TW (EW Test Squadron) | Flight Test Instrumentation Lead | External instrumentation pod lacks isolated crypto processing | *[Pending Interview]* | External pod enclosure / ARINC 429 | Edwards AFB Test Pod Program | TBD | Confirm pod physical envelope | `PLANNED` |
| **ENG-20** | AFTC / 96th TW (Cyber Test Squadron) | Red Team Cyber Test Lead | Network test harnesses lack controlled socket attack simulation | *[Pending Interview]* | Malformed frame injection benches | Eglin AFB Cyber Test Facility | TBD | Compare test methodologies | `PLANNED` |
| **ENG-21** | 16th Air Force (Information Warfare) | Cyber Weapon System Strategist | Threat policy updates require full software rebuild and re-test | *[Pending Interview]* | Sub-second Rego policy swapping | 616th Operations Center Cyber Ops | TBD | Demo OPA sidecar SIGHUP reload | `PLANNED` |
| **ENG-22** | AFWERX Ventures | Defense Innovation Liaison | SBIR Phase I feasibility lacks clear PEO transition champion | *[Pending Interview]* | Program Element transition alignment | DAF Open Topic Phase II Matching | TBD | Submit preliminary D1 report | `PLANNED` |
| **ENG-23** | Prime Integrator 1 (Tactical Avionics) | Chief Software Architect | Flight-critical computer recertification blocks crypto upgrades | *[Pending Interview]* | SOSA / OpenVPX 3U slot | Collaborative Combat Aircraft (CCA) | TBD | Present transparent proxy data | `PLANNED` |
| **ENG-24** | Prime Integrator 1 (Mission Systems) | Cryptographic Hardware Lead | Discrete HSMs exceed thermal and weight budgets on uncrewed pods | *[Pending Interview]* | Weight <5 lbs; passive cooling | Dispensable Autonomous Drones | TBD | Contrast SWaP-C metrics | `PLANNED` |
| **ENG-25** | Prime Integrator 2 (Electronic Warfare) | EW Systems Engineering Director | Hostile electronic warfare jamming floods receiver socket buffers | *[Pending Interview]* | EWMA microsecond packet rejection | Airborne EW Pod Upgrade | TBD | Share socket-stress test logs | `PLANNED` |
| **ENG-26** | Prime Integrator 2 (Edge Computing) | Principal Edge Software Engineer | In-memory binary injection bypasses static OS integrity checks | *[Pending Interview]* | IMA / Secure Boot / `fexecve` | Edge Mission Computer Refresh | TBD | Share runtime admission code | `PLANNED` |
| **ENG-27** | Prime Integrator 3 (Autonomous Systems)| Collaborative Combat Aircraft Lead | Uncrewed swarm nodes require lightweight, dispensable crypto | *[Pending Interview]* | Sub-$5k per-node avionics cost | Air Force CCA Incremental RFP | TBD | Discuss modular architecture | `PLANNED` |
| **ENG-28** | DAF PEO Digital (Enterprise IT) | Cloud-to-Edge Security Lead | WAN-dependent zero-trust architectures fail at contested edge | *[Pending Interview]* | Zero public IP exposure / mesh | Contested Logistics Architecture | TBD | Review loopback/mesh topology | `PLANNED` |
| **ENG-29** | NSA CSfC Office | CSfC Client Integration Officer | Commercial-off-the-shelf crypto fails CSfC Annex requirements | *[Pending Interview]* | CSfC Components List criteria | CSfC Modernization Roadmap | TBD | Request pre-validation feedback | `PLANNED` |
| **ENG-30** | DAF SBIR / STTR Transition Office | SBIR Transition Program Manager | Defense software lacks dual-use commercial sustainability | *[Pending Interview]* | Non-defense commercial enterprise tier | Commercialization Readiness Program | TBD | Present commercial SCADA model | `PLANNED` |

---

## 4. Standardized 5-Question Discovery Inquiry Protocol

Each interview is conducted using a standardized, open-ended technical inquiry protocol designed to elicit verifiable operational requirements:

```text
+---------------------------------------------------------------------------------------------------------+
|                                    STANDARDIZED DISCOVERY INQUIRY PROTOCOL                              |
+---------------------------------------------------------------------------------------------------------+
| Q1: CRYPTO MIGRATION & RUNTIME DOWNTIME                                                                 |
|     "When your platform performs cryptographic key rollover or algorithm replacement, does it require  |
|     rebooting the operational software, resetting the communications socket, or severing the datalink?  |
|     What is the maximum allowable downtime during in-flight operations?"                                |
|                                                                                                         |
| Q2: NETWORK ADVERSITY & SOCKET SATURATION                                                               |
|     "How does your edge computing node or telemetry intake service respond when subjected to malformed  |
|     frame injection, unauthenticated packet storms, or hostile connection stalling? Does it degrade     |
|     gracefully or crash the host daemon?"                                                               |
|                                                                                                         |
| Q3: RUNTIME INTEGRITY & FLASH-LEVEL WEAPON EXECUTIVES                                                   |
|     "How does your platform ensure that an executable verified during pre-boot or stage-in has not been |
|     swapped in flash storage immediately prior to execution (TOCTOU race conditions)? Do you currently  |
|     enforce kernel file-descriptor execution binding?"                                                   |
|                                                                                                         |
| Q4: EDGE HARDWARE CONSTRAINTS (SWaP-C & INTERFACES)                                                     |
|     "What specific single-board computers, processor architectures (ARM64, x86_64, RISC-V), and bus     |
|     interfaces (MIL-STD-1553, ARINC 429, Ethernet, Serial) are mandated for the next program upgrade?" |
|                                                                                                         |
| Q5: TRANSITION WINDOWS & ACCREDITATION GATES                                                            |
|     "What is the target program insertion window (e.g., FY28 Block upgrade), what accreditation        |
|     pathway governs the platform (CSfC, RMF, DoDIN APL), and who serves as the operational TPOC?"      |
+---------------------------------------------------------------------------------------------------------+
```

---

## 5. Synthesis Output Trace (Mapping to Task 1 Deliverable D1)

All findings recorded in this ledger synthesize directly into **Deliverable D1 (Day 30)**:
1. **Defense Need Evidence:** Validated mission problem statements and customer friction across AFLCMC/HN, AFRL/RI, ACC/A6, and SSC.
2. **Technical Merit Input:** Tactical interface and SWaP-C specifications dictating the **$11,000 Direct Materials** (hardware modules) and **$4,000 Compute ODC** procurement under Task 2 (Days 31–60).
3. **Accreditation Strategy:** NSA CSfC and Air Force RMF alignment roadmap.
4. **Commercialization & Transition Pathways:** Prospective military evaluators for Phase II Letters of Intent / Memoranda of Agreement.
