# 🛰️ QUANTUMFLEX AFWERX SBIR PHASE I CUSTOMER DISCOVERY LEDGER
## Task 1 Stakeholder Discovery Campaign (Target: ≥30 Structured Engagements)

**Entity:** FINALLYFUNGUS LLC (PA Entity ID: 13706513) DBA QuantumFlex  
**Principal Investigator:** Rahshaun Chambers  
**Proposal Title:** QuantumFlex: Autonomous Post-Quantum Cryptographic Agility, Shock-Absorbing Telemetry & TOCTOU-Resistant Runtime Admission for National Security Systems  
**Governing SOW Baseline:** [`docs/AFWERX_PHASE_I_WORK_PLAN.md#L55-L72`](file:///home/quant/mycelium/docs/AFWERX_PHASE_I_WORK_PLAN.md#L55-L72) (Task 1: Days 1–30)  
**Primary Output Deliverable:** Deliverable D1 (*Tactical Interface Baseline & Customer Discovery Synthesis Report*, Day 30)  
**Commit Baseline:** `45f8383`

---

## 1. Discovery Governance & Procurement Ground Rules

> [!IMPORTANT]
> **GOVERNMENT STAKEHOLDER DEMARCATION RULE**  
> In accordance with federal procurement governance and the QuantumFlex Claim Ledger ([`docs/AFWERX_CLAIM_LEDGER.md`](file:///home/quant/mycelium/docs/AFWERX_CLAIM_LEDGER.md)):
> 1. All Department of the Air Force (DAF) and Department of Defense (DoD) organizations listed herein are designated as **CANDIDATE DISCOVERY STAKEHOLDERS**.
> 2. No stakeholder, program executive office, or military command is claimed as an active customer, commercial partner, or committed transition sponsor prior to an executed Memorandum of Understanding (MOU), Memorandum of Agreement (MOA), or Letter of Intent (LOI).
> 3. Discovery findings will directly dictate the hardware selection for the Phase I Direct Materials procurement ($15,000) under Task 2 and shape the Phase II demonstration architecture.

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

## 3. Master Customer Discovery Interview Registry (Target: ≥30 Engagements)

The table below tracks all 30 planned structured interviews across Task 1 (Days 1–30).

| # | Command / Org | Unit / Branch | Candidate Persona / Title | Operational Focus Area | Primary QF Vector | SWaP-C / Bus Constraints | Status | Target Date |
| :-: | :--- | :--- | :--- | :--- | :---: | :--- | :---: | :---: |
| **01** | AFLCMC/HN | Tactical Datalinks Division | Lead Avionics Systems Engineer | Airborne Datalink Key Rollover | Vector 1 / 4 | MIL-STD-1553 / Ethernet; <35W | Targeted | Day 5 |
| **02** | AFLCMC/HN | Tactical Datalinks Division | Program Manager, Link 16 Mod | Contested DIL RF Retransmission | Vector 2 / 5 | Serial / IP; <64MB RAM | Targeted | Day 6 |
| **03** | AFLCMC/HN | Cryptographic Modernization | NSA CSfC Integration Officer | Staged Post-Quantum Transition | Vector 1 / 7 | CSfC Dual-Layer Envelope | Targeted | Day 7 |
| **04** | AFLCMC/HN | Advanced Gateways Branch | Airborne Gateway Architect | Cross-Domain Datalink Bridging | Vector 2 / 4 | OpenVPX 3U / 1GbE | Targeted | Day 8 |
| **05** | AFLCMC/HN | Aerial Networks Division | Cyber Defense Lead | In-Flight Packet Injection Defense | Vector 2 (EWMA) | Socket saturation resilience | Targeted | Day 9 |
| **06** | AFRL/RI | Cyber Assurance Division | Senior Research Computer Scientist | Formal Verification of PQC Primitives | Vector 1 (FIPS 203/204) | C++20 / Valgrind clean | Targeted | Day 11 |
| **07** | AFRL/RI | Resilient Edge Computing | Lead Edge Security Researcher | TOCTOU-Resistant Runtime Launch | Vector 7 (fexecve) | Linux Kernel namespaces / seccomp | Targeted | Day 12 |
| **08** | AFRL/RI | Secure Communications Branch | Post-Quantum Cryptography SME | Hybrid Classical-PQC Key Exchange | Vector 1 (X25519 + ML-KEM) | Low-overhead frame headers | Targeted | Day 13 |
| **09** | AFRL/RI | Quantum Information Section | Applied Physicist / Info Theory | Memory Zeroization & Anti-Tamper | Vector 3 (Shamir + Cleanse) | Volatile SRAM zeroization | Targeted | Day 14 |
| **10** | AFRL/RI | Embedded Systems Security | Microelectronics Security Engineer | Discrete vs Integrated TPM Bench | Vector 7 / Task 2 | ARM64 / SPI TPM 2.0 | Targeted | Day 15 |
| **11** | ACC / A6 | Tactical Comm Operations | Tactical Communications Officer (A6) | ACE Austere Base Deployment | Vector 5 (Shamir Unlock) | Austere solar/battery power | Targeted | Day 16 |
| **12** | ACC / A6 | Edge Network Security | Defensive Cyber Operations Lead | Forward Operating Node Tamper | Vector 3 / 7 | Zeroization under capture risk | Targeted | Day 17 |
| **13** | ACC / A6 | Expeditionary Comm Squad | Expeditionary Network Chief | Disconnected Edge Authentication | Vector 5 / 6 | Private mesh / zero WAN | Targeted | Day 18 |
| **14** | ACC / A6 | Agile Combat Employment | ACE Logistics & Cyber Planner | Rapid Node Commissioning | Vector 6 (Mobile CLI) | Android Titan M2 / Knox Vault | Targeted | Day 19 |
| **15** | ACC / A6 | Air Operations Center (AOC) | Combat Communications Architect | AOC-to-Tactical Edge Telemetry | Vector 4 (Decoupled Intake) | High latency, variable jitter | Targeted | Day 20 |
| **16** | Space Systems Cmd | Resilient Space Comm | Satcom Cyber Architect | pLEO Datalink Crypto-Agility | Vector 1 / 4 | Space-grade ARM64 / Rad-tolerant | Targeted | Day 21 |
| **17** | Space Systems Cmd | Space Domain Awareness | Telemetry Ground Systems Lead | Shock-Absorbing Space Telemetry | Vector 2 (EWMA) | Burst telemetry streams | Targeted | Day 22 |
| **18** | Space Systems Cmd | Defensive Cyber for Space | Space Vehicle Security Engineer | In-Orbit Firmware/Crypto Update | Vector 7 (TOCTOU) | Limited downlink bandwidth | Targeted | Day 23 |
| **19** | AFTC / 412th TW | Electronic Warfare Test Sq | Flight Test Instrumentation Lead | Pod Instrumentation & Sidecar SWaP | Task 2 / Phase II SOW | External pod enclosure / ARINC 429 | Targeted | Day 24 |
| **20** | AFTC / 96th TW | Cyber Test Squadron | Red Team Cyber Test Lead | Hostile Socket Injection Vector | Vector 2 / 7 | Malformed frame injection | Targeted | Day 24 |
| **21** | 16th Air Force | Information Warfare (616 OC) | Cyber Weapon System Strategist | Defensive Sidecar Orchestration | Vector 6 (OPA Rego) | Dynamic policy reloads | Targeted | Day 25 |
| **22** | AFWERX Ventures | Military Evaluator Roster | Defense Innovation Liaison | Phase II Transition Alignment | Task 3 (LOI/MOA) | Program Element alignment | Targeted | Day 25 |
| **23** | Prime Integrator 1 | Tactical Avionics Division | Chief Software Architect | CCA Sensor Pod Sidecar Adapter | Vector 1 / 2 | SOSA / OpenVPX 3U | Targeted | Day 26 |
| **24** | Prime Integrator 1 | Mission Systems Engineering | Cryptographic Hardware Lead | Discrete HSM vs Software Sidecar | Vector 1 / 3 | Weight / Thermal envelope | Targeted | Day 26 |
| **25** | Prime Integrator 2 | Electronic Warfare Group | EW Systems Engineering Director | Datalink Shock Absorption | Vector 2 (EWMA) | Microsecond packet rejection | Targeted | Day 27 |
| **26** | Prime Integrator 2 | Edge Computing Center | Principal Edge Software Engineer | Kernel fexecve Binary Admission | Vector 7 (TOCTOU) | Secure Boot / IMA integration | Targeted | Day 27 |
| **27** | Prime Integrator 3 | Autonomous Systems Division | Collaborative Combat Aircraft Lead | Uncrewed System Crypto-Agility | Vector 1 / 5 | Low-cost dispensable airframe | Targeted | Day 28 |
| **28** | DAF PEO Digital | Enterprise IT Modernization | Cloud-to-Edge Security Lead | Zero-Trust Private Mesh Transport | Vector 6 (Tailnet/Mesh) | Zero public IP exposure | Targeted | Day 28 |
| **29** | NSA CSfC Office | CSfC Client Integration | Accredited CSfC Evaluator | Commercial Solutions for Classified | Vector 1 / Task 2 | CSfC Components List pathway | Targeted | Day 29 |
| **30** | DAF SBIR / STTR | Technology Transition Office | SBIR Transition Program Manager | Commercialization & Dual-Use Strategy | Task 3 / Commercial | Non-defense commercial spin-in | Targeted | Day 30 |

---

## 4. Standardized 5-Question Discovery Interview Protocol

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
1. **Validated Mission Problem Statements:** Codified operational pain points across AFLCMC/HN and ACC/A6.
2. **Tactical Interface & SWaP-C Envelope Specification:** Specific hardware metrics informing the **$15,000 Direct Materials procurement** under Task 2 (Days 31–60).
3. **Accreditation Strategy:** NSA CSfC and Air Force RMF alignment roadmap.
4. **Transition Candidate Roster:** Prospective military evaluators for Phase II Letters of Intent / Memoranda of Agreement.
