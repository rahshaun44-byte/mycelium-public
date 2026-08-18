# OPERATION KINETIC YIELD: PHASE 2 TARGET HITLIST & OUTREACH REPERTORY

> **Target Domain:** Mid-Tier Defense Subcontractors & Federal IT Integrators ($50M–$1B Revenue)  
> **Regulatory Trigger:** [OMB Memorandum M-26-15](https://postquantum.com/security-pqc/omb-m-26-15-pqc-migration/) (October 22, 2026 Deadline) & CMMC Level 2/3 CUI Infrastructure Mandates  
> **Core Deliverable:** Architectural Advisory Retainers ($3.5k–$7.5k SOW) under FinallyFungus LLC

---

## I. Target Firm Intelligence Matrix

| Company | Core Domain & Contract Footprint | CMMC / Federal Posture | Why Vulnerable to OMB M-26-15 |
|---|---|---|---|
| **Radiance Technologies** | Defense software, edge computing, directed energy, cyber systems | CMMC Level 2 / NIST SP 800-171 | Builds custom bare-metal & edge software for DoD where hardcoded cryptography cannot be patched via cloud. |
| **Riverside Research** | Open-source intelligence, quantum computing research, cyber-physical systems | CMMC Level 2/3 | High-assurance government research contracts requiring verifiable PQC transition architectures. |
| **LinQuest Corporation** | Space systems engineering, C4ISR, military satellite operations | CMMC Level 2 / DoD Primes | Satellite and telemetry ground stations require zero-downtime cryptographic failover. |
| **Torch Technologies** | Software modeling, missile defense simulation, tactical command networks | CMMC Level 2 | Simulation and live telemetry feeds sensitive to encryption handshake latency and connection resets. |
| **Modern Technology Solutions, Inc. (MTSI)** | Unmanned systems, cybersecurity engineering, avionics software | CMMC Level 2 | Autonomous nodes requiring local policy-driven crypto-swaps without cloud dependency. |
| **Agile Defense** | Federal enterprise IT modernization, zero-trust cloud infrastructure | CMMC Level 2 / FCEB Integrator | Direct prime/subcontractor on civilian agency networks requiring automated CycloneDX CBOM scans. |
| **Systems Planning and Analysis (SPA)** | Advanced analytics, strategic system engineering, nuclear/naval cyber | CMMC Level 3 | High-value assets (HVAs) where single-lattice algorithms carry high structural risk. |
| **V2X (Vectrus / Vertex)** | Global defense logistics, mission infrastructure, base ops networks | CMMC Level 2 | Distributed edge networks and warehouse transit pipelines vulnerable to harvest-now, decrypt-later (HNDL). |

---

## II. OSINT Persona Taxonomy & Boolean Queries

### 1. Primary Target Personas
- **Persona A (The Operational Owner):** Chief Information Security Officer (CISO) / VP of Information Security
- **Persona B (The Systems Architect):** Principal Security Architect / Lead Cryptographic Engineer / Chief Architect
- **Persona C (The Implementation Lead):** Director of Infrastructure Security / DevSecOps Lead / CMMC Program Manager

### 2. Search Queries
- **Query 1 (Security Architecture & Cryptography):**
  ```text
  ("Chief Security Architect" OR "Lead Security Architect" OR "Principal Security Engineer" OR "Director of Cybersecurity Architecture") AND ("DoD" OR "Defense" OR "CMMC" OR "NIST" OR "Zero Trust") AND ("C++" OR "Linux" OR "Kernel" OR "Infrastructure") -recruiter -sales -account
  ```
- **Query 2 (CISO & Technical Directors at Mid-Tier Defense):**
  ```text
  (CISO OR "VP of Cybersecurity" OR "Director of Information Security") AND ("Defense" OR "Federal" OR "Aerospace" OR "Intelligence") AND ("CMMC" OR "800-171" OR "Post-Quantum" OR "Crypto") -intern -assistant
  ```
- **Query 3 (GovTribe / SAM.gov Procurement Filter):**
  - **NAICS Codes:** `541512` (Computer Systems Design Services), `541715` (R&D in Physical, Engineering, and Life Sciences), `541330` (Engineering Services).
  - **PSC Codes:** `DA01` (IT and Telecom - Business Application Software Support), `R425` (Support - Professional: Engineering/Technical).

---

## III. Cold Technical Outreach Sequences

### Variation 1: The Math-First / CISO Architecture Angle
**Target:** CISO / VP of Information Security  
**Subject:** `OMB M-26-15 / dynamic CBOM vs hardcoded ML-KEM migration`

```text
{{First_Name}},

OMB M-26-15 mandates that federal contractors submit PQC migration plans by October 2026, but the majority of migration roadmaps are making a structural error: hardcoding ML-KEM (FIPS 203) directly into application stacks.

If a mathematical flaw or side-channel vulnerability emerges in structured lattices, static implementations force another full codebase refactor. Furthermore, static CBOM scans generated at compile time fail to satisfy continuous compliance once binaries are deployed on live infrastructure.

I engineered a native C++/POSIX crypto-agility supervisor that solves this at runtime:
1. Generates continuous CycloneDX-compliant CBOM snapshots every 500ms.
2. Uses an Open Policy Agent (OPA) sidecar to evaluate algorithm health.
3. Automatically collapses compromised ML-KEM instances down to an unstructured lattice fallback (FrodoKEM) via atomic provider config swaps—with zero worker process restarts and zero dropped connections.

I drafted a 2-page technical whitepaper detailing the supervisor's kernel signal handling and OPA integration. Are you open to reviewing the architecture doc to see how we handle live crypto-swaps without service disruption?

Best,
Rahshaun "Rocky" Chambers
FinallyFungus LLC | Quantum Flex Architecture
```

---

### Variation 2: The Systems Architect / Infrastructure Failure Mode Angle
**Target:** Principal Security Architect / Lead Cryptographic Engineer  
**Subject:** `Atomic KEM rollover: ML-KEM-768 to FrodoKEM-976-AES fallback`

```text
{{First_Name}},

Most PQC discussions overlook process survivability during in-flight cipher suite renegotiation. Under NIST FIPS 203/204, swapping key encapsulation mechanisms on active defense network nodes typically requires tearing down the cryptographic tunnel or bouncing daemon processes.

We built a bare-metal reference supervisor designed for high-availability systems:
- It maintains active workers across SIGHUP/SIGUSR1 signal reloads.
- It parses dynamic threat feeds via a local OPA engine (membrane_health.rego).
- Upon a TOXIC verdict, it executes an atomic rewrite of provider configurations, stepping down from ML-KEM to FrodoKEM in <0.5ms while keeping the network tunnel intact.
- It treats policy engine unreachability as a fail-secure event, triggering immediate autonomous fallback.

If you are architecting your CMMC Level 2/3 boundary for upcoming PQC requirements, I can share our C++ kernel design and the live test harness output. Let me know if you want the whitepaper sent over.

Best,
Rahshaun "Rocky" Chambers
FinallyFungus LLC | Quantum Flex Architecture
```

---

### Variation 3: The CMMC / October 2026 Compliance Deadline Angle
**Target:** Director of Infrastructure / DevSecOps Lead / CMMC Program Manager  
**Subject:** `Automating CycloneDX CBOM generation ahead of Oct 2026 M-26-15`

```text
{{First_Name}},

With CMMC Level 2 assessments accelerating and OMB M-26-15 setting an October 2026 deadline for cryptographic migration plans, manual cryptographic asset spreadsheets are creating significant audit liability. Federal auditors will require proof of continuous cryptographic visibility (CBOM) and verifiable crypto-agility across CUI boundaries.

We packaged a lightweight advisory integration:
1. Automated CycloneDX v1.5 CBOM generation tracking active KEMs and signature schemes across native endpoints.
2. Localized OPA policy enforcement validating active suites against NIST FIPS 203/204 standards.
3. Live-fire validation verifying that algorithmic failovers execute without infrastructure downtime.

We provide this as a rapid, fixed-scope engineering advisory sprint ($3.5k–$7.5k) to get your technical documentation and prototype supervisor operational ahead of Q4 audit cycles.

Would you be open to a 10-minute technical brief this week?

Best,
Rahshaun "Rocky" Chambers
FinallyFungus LLC | Quantum Flex Architecture
```
