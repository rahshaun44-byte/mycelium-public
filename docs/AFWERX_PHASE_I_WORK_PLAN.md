# 📋 DAF / AFWERX SBIR PHASE I FEASIBILITY WORK PLAN (STATEMENT OF WORK)

> [!NOTE]
> **GOVERNING SPECIFICATION: AFWERX OPEN TOPIC STATEMENT OF WORK (SOW)**  
> This work plan is structured in strict compliance with official Air Force SBIR Open Topic SOW guidance (incorporating Scope, Task Outline, Deliverables, Kickoff, Preliminary Report, Final Report, SF 298, and DD Form 882). All budget items represent planned allocations subject to the controlling solicitation award ceiling.

**Solicitation:** Department of the Air Force (DAF) SBIR Open Topic Phase I  
**Project Title:** QuantumFlex: Autonomous Post-Quantum Cryptographic Agility, Shock-Absorbing Telemetry & TOCTOU-Resistant Runtime Admission for National Security Systems  
**Applicant:** FINALLYFUNGUS LLC (PA Entity ID: 13706513) DBA QuantumFlex  
**Principal Investigator:** Rahshaun Chambers (Founder & Systems Architect)  
**Proposed Award Ceiling:** Planned $75,000.00 (Firm Fixed Price, Subject to Controlling Solicitation)  
**Period of Performance (PoP):** Up to 90 Days (3 Months)  
**Controlling Cost Basis:** [`docs/AFWERX_PHASE_I_COST_BASIS.md`](file:///home/quant/mycelium/docs/AFWERX_PHASE_I_COST_BASIS.md)  
**Technical Evidence Dossier:** [`docs/DUE_DILIGENCE_DOSSIER.pdf`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.pdf) (SHA-256: `71b505c762834cc44f166873a86960389bcbf6312f5f6b27277e5f4777193866`)  
**Empirical Trace Matrix:** [`docs/AFWERX_CLAIM_LEDGER.md`](file:///home/quant/mycelium/docs/AFWERX_CLAIM_LEDGER.md)

---

## 1. Scope of Work

The contractor shall conduct a 90-day technical feasibility study and customer discovery campaign to establish operational requirements, validate tactical bus interfaces, and assess hardware-enclave integration pathways for **QuantumFlex**. 

QuantumFlex is an autonomous cryptographic agility and telemetry shock-absorption architecture operating under the **eQUATION OF TRUTH** ($Y = (x - h) + k$). It separates cryptographic execution from dynamic policy supervision, intercepts hostile network packets without host degradation, zeroizes secret state post-recovery, and binds runtime binaries directly to cryptographically attested source packages via TOCTOU-resistant open file-descriptor execution (`fexecve`).

The contractor shall engage candidate Air Force stakeholders to define mission requirements, construct an automated ACVP-compatible NIST FIPS 203 (ML-KEM) test harness, acquire and benchmark tactical edge hardware enclaves, and develop a comprehensive Phase II transition and flight-demonstration plan.

---

## 2. Task Outline

```
+---------------------------------------------------------------------------------------------------------+
|                                    PHASE I WORK BREAKDOWN STRUCTURE                                     |
+---------------------------------------------------------------------------------------------------------+
|  Task 1: Tactical Customer Discovery & Interface Baselines (Days 1–30)                                  |
|  * Milestone 1: Complete ≥30 structured DAF discovery engagements                                      |
|  * Deliverable D1: Tactical Interface Baseline & Customer Discovery Synthesis Report                   |
+---------------------------------------------------------------------------------------------------------+
                                                     |
                                                     v
+---------------------------------------------------------------------------------------------------------+
|  Task 2: ACVP-Compatible Test Bench & Hardware Security Enclave Integration (Days 31–60)                |
|  * Milestone 2: Automated NIST FIPS 203/204 ACVP-compatible test harness & tactical hardware benchmark  |
|  * Deliverable D2: Cryptographic Benchmark & Hardware Enclave Feasibility Assessment                     |
+---------------------------------------------------------------------------------------------------------+
                                                     |
                                                     v
+---------------------------------------------------------------------------------------------------------+
|  Task 3: Phase II Transition Documentation & Final Deliverable Package (Days 61–90)                      |
|  * Milestone 3: Pursue & document Phase II transition interest (LOI/MOA where obtainable)               |
|  * Deliverable D3: Final Phase I Feasibility Report (incorporating SF 298 & DD Form 882)               |
+---------------------------------------------------------------------------------------------------------+
```

### Task 1: Tactical Customer Discovery & Interface Baselines (Days 1–30)
* **Objective:** Conduct rigorous customer discovery across candidate Department of the Air Force stakeholders to establish concrete operational problem statements, bus protocols, and environmental constraints ($x$).
* **Candidate Discovery Stakeholders:**
  * **PEO Cyber and Networks (formerly AFLCMC/HN C3I&N, Hanscom AFB):** Tactical Cryptographic Modernization & Airborne Datalinks.
  * **Air Force Research Laboratory (AFRL) Information Directorate (Rome, NY):** Cyber Assurance & Resilient Edge Computing.
  * **Space Systems Command (SSC):** Resilient Space Telemetry & Laser Cross-Link Nodes.
  * **Defense Industrial Base Primes:** Tactical avionics and pod integration primes.
* **Discovery Execution & Evidence Outputs:**
  The contractor shall target a minimum of **≥30 structured discovery engagements**, producing the following verified outputs:
  1. *Validated Mission Problem Statements:* Documented operational pain points regarding static cryptographic migration and in-flight rollover downtime.
  2. *Tactical Interface & SWaP-C Baselines:* Concrete size, weight, power, and bus interface constraints (MIL-STD-1553, Ethernet, Serial, Link 16).
  3. *Security & Accreditation Constraints:* Air Force Risk Management Framework (RMF) and NSA CSfC accreditation pathways.
  4. *Procurement & Transition Pathways:* Identified program element lines and technology insertion windows.
  5. *Candidate TPOC / End-User Roster:* Prospective transition sponsors and technical evaluators.
  6. *Documented Objections & Unmet Needs:* Operational hurdles to be addressed in the Phase II demonstration design.
* **Task 1 Output:** Deliverable D1.

---

### Task 2: ACVP-Compatible Test Bench & Hardware Security Enclave Integration (Days 31–60)
* **Objective:** Mature the cryptographic verification pipeline and benchmark hardware-rooted trust anchor integration ($k$).
* **Subtasks:**
  * **Subtask 2.1: ACVP-Compatible Test Bench:** Construct an automated Python/C++ test harness consuming official NIST Automated Cryptographic Validation Protocol (ACVP) JSON vectors for FIPS 203 (ML-KEM-512, ML-KEM-768, ML-KEM-1024) and FIPS 204 (ML-DSA-44, ML-DSA-65, ML-DSA-87).
  * **Subtask 2.2: Representative Hardware Acquisition & Enclave Integration:** Utilizing Phase I direct materials funding ($11,000 under FAR 31.205-26), procure the representative edge computing hardware, single-board modules, and discrete cryptographic evaluation boards identified during Task 1 customer discovery to transition beyond the laptop-centered prototype laboratory, benchmarking physical hardware enclaves alongside commercial secure elements (Google Titan M2 and Samsung Knox Vault).
  * **Subtask 2.3: Performance & Latency Stress Profiling:** Benchmark decapsulation throughput, memory zeroization timing, and EWMA LIF shock-absorber rejection latencies under controlled socket-load and adversarial network-stress testing on the acquired candidate hardware.
* **Task 2 Output:** Deliverable D2.

---

### Task 3: Phase II Transition Documentation & Final Deliverable Package (Days 61–90)
* **Objective:** Finalize the Phase II flight-test / tactical pod demonstration plans, compile all empirical findings, and pursue customer transition agreements ($Y$).
* **Subtasks:**
  * **Subtask 3.1: Phase II Demonstration Architecture Formulation:** Formulate the detailed Phase II Statement of Work (SOW) for integrating QuantumFlex into an airborne pod, tactical communications gateway, or ground terminal.
  * **Subtask 3.2: Transition Interest Documentation:** **Pursue and document Phase II transition interest, including Letters of Intent (LOI), Memoranda of Agreement (MOA), or equivalent customer evidence where obtainable.**
  * **Subtask 3.3: Final Reporting & Closeout:** Compile the final comprehensive Phase I feasibility report, incorporating all discovery findings, empirical benchmarks, and statutory closeout forms.
* **Task 3 Output:** Deliverable D3.

---

## 3. Meetings, Progress Reporting & Deliverables

In accordance with AFWERX reporting guidelines, the contractor shall complete the following formal reporting events:

1. **Kickoff Meeting (Day 15):** The contractor shall participate in a virtual orientation and kickoff meeting with the designated Air Force Technical Point of Contact (TPOC) within 15 calendar days of contract award.
2. **Preliminary Progress Report (Day 45):** The contractor shall submit a mid-term progress report detailing initial customer discovery findings, validated stakeholder contacts, tactical interface constraints, and preliminary test bench progress.
3. **Formal Deliverable Schedule:**
   * **Deliverable D1 (Day 30):** *Tactical Interface Baseline & Customer Discovery Synthesis Report*.
   * **Deliverable D2 (Day 60):** *ACVP-Compatible Test Bench & Hardware Enclave Feasibility Assessment*.
   * **Deliverable D3 (Day 90):** *Final Phase I Feasibility Report & Phase II Transition Plan*, formally incorporating:
     - **Standard Form 298 (SF 298):** Report Documentation Page.
     - **DD Form 882:** Report of Inventions and Subcontracts.

---

## 4. Technical, Programmatic & Transition Risk Matrix

| Risk Identified | Severity | Probability | Mitigation Enforced in Work Plan |
| :--- | :---: | :---: | :--- |
| **R1: Tactical Ingress Latency Degradation** | Med | Low | Pre-inference SQLite WAL durability decoupled from local inference (3.9–8.5 ms receipt); EWMA LIF shock absorber rejects malformed frames in sub-millisecond branchless operations. |
| **R2: Hardware Enclave Protocol Incompatibilities** | Med | Med | Evaluates both standard TPM 2.0 interfaces (TSS2 / PKCS#11) and discrete secure elements on acquired test boards during Task 2. |
| **R3: Stakeholder Discovery Scheduling Bottlenecks** | Med | Med | Target pool includes 40+ prospective defense contacts across multiple commands (PEO Cyber & Networks, AFRL, SSC, and defense primes) to ensure quota of ≥30 completed sessions. |
| **R4: Post-Quantum Standard Evolution (NIST FIPS 203)** | Low | Low | Software architecture enforces dynamic algorithm agility; fallback chain supports modular cipher swaps without data worker restarts. |
| **R5: Transition Agreement Availability** | Med | Med | Work plan scopes milestone as "pursuing and documenting transition interest where obtainable", preventing administrative dependencies on external government signature timing. |
