# 🛡️ DSIP SUBMISSION COMPLIANCE CHECKLIST & GATEKEEPER
## Department of the Air Force (DAF) / AFWERX SBIR Open Topic Phase I

**Applicant Organization:** FINALLYFUNGUS LLC (PA Entity ID: 13706513) DBA QuantumFlex  
**Principal Investigator (PI):** Rahshaun Chambers  
**Proposal Title:** QuantumFlex: Autonomous Post-Quantum Cryptographic Agility, Shock-Absorbing Telemetry & TOCTOU-Resistant Runtime Admission for National Security Systems  
**Portal:** Defense SBIR/STTR Innovation Portal ([www.dodsbirsttr.mil/submissions](https://www.dodsbirsttr.mil/submissions))  
**Date of Audit:** September 20, 2026  
**Commit Baseline:** `31ed9c9`

---

## ⚠️ OVERALL GATEKEEPER STATUS: CONDITIONAL / NOT LOCKED

> [!CAUTION]
> **SUBMISSION READINESS STATUS: BLOCKED / NOT YET LOCKED**  
> **Final Green Submission Status is REFUSED.**  
> As of September 19, 2026, the AFWERX funding portal indicates active Specific Topic Release 5 (closing Sep 23) and Release 6 (opening Sep 23) activity, with **no active Open Topic Phase I solicitation currently accepting proposals**. In accordance with federal procurement governance, all solicitation-dependent parameters remain **CONDITIONAL PLACEHOLDERS** and cannot be certified as submission-ready until an official DAF Open Topic solicitation card, deadline, and controlling template revision are published and verified in DSIP.

---

## 1. Solicitation-Controlled Parameter Trace

The table below catalogs every parameter that is strictly controlled by the governing solicitation document. No parameter may be marked as "Green" or "Locked" until verified against the active solicitation.

| Parameter | Proposal Assumption | Controlling Authority | Verification Status | Gate Status |
| :--- | :--- | :--- | :--- | :---: |
| **Solicitation Number** | DAF SBIR Open Topic Phase I | DSIP / AFWERX Get Funded Portal | Currently in Specific Topic Releases 5 & 6 | **NOT LOCKED** |
| **Submission Deadline** | [PENDING OPEN TOPIC RELEASE] | Official Solicitation Instructions | Awaiting Open Topic release schedule | **NOT LOCKED** |
| **Volume Architecture** | 4 to 7 Volumes depending on release | Controlling Solicitation Document | Varies by solicitation (e.g., 25.5/E vs 24.7/E) | **SOLICITATION-CONTROLLED** |
| **Technical Volume Format** | 13-Page Designated-Page Template | Official Proposal Template Instructions | Evaluators only evaluate designated pages | **SCAFFOLDED / NOT LOCKED** |
| **Award Ceiling** | Planned $75,000.00 Fixed Price | Solicitation Topic Instructions | Historically up to $75k; unverified in DSIP | **SOLICITATION-CONTROLLED** |
| **Appendix Page Allowance** | 10 Pages ([`DUE_DILIGENCE_DOSSIER.pdf`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.pdf)) | Solicitation Topic Instructions | Subject to controlling upload rules | **SOLICITATION-CONTROLLED** |

---

## 2. Administrative Gateway Prerequisites (Statutory Registrations)

These items are government-wide prerequisites independent of specific solicitations:

- [x] **State Corporate Registration (Pennsylvania):**
  - *Entity Name:* FINALLYFUNGUS LLC
  - *Entity ID:* `13706513`
  - *Status:* Active / Good Standing in the Commonwealth of Pennsylvania.
  - *Imminent Action:* File the 2026 Pennsylvania Annual Report via the PA Department of State portal prior to September 30, 2026.
- [ ] **System for Award Management (SAM.gov):**
  - *Unique Entity Identifier (UEI):* Must be active and displayed on DSIP profile.
  - *Commercial and Government Entity (CAGE) Code:* Must be active and linked to the registered entity.
  - *NAICS Codes:* Primary `541512` (Computer Systems Design) / `541715` (R&D in Physical/Engineering Sciences).
  - *Representations & Certifications:* Current and validated in SAM.gov.
- [ ] **Small Business Administration (SBA.gov):**
  - *Small Business Concern (SBC) Registration:* Completed on `SBIR.gov` firm registry.
  - *SBC ID:* Active and recorded for Volume 1 entry.
- [ ] **DSIP Corporate Account:**
  - Registered firm profile linking Authorized Representative (AR) and Principal Investigator (PI).

---

## 3. Package Deliverables & Governance Architecture

The proposal repository is partitioned into distinct artifacts to prevent premature certification of unverified procurement assumptions:

| Proposal Asset | File Path | Governance Role | Current Status |
| :--- | :--- | :--- | :---: |
| **Claim Ledger** | [`docs/AFWERX_CLAIM_LEDGER.md`](file:///home/quant/mycelium/docs/AFWERX_CLAIM_LEDGER.md) | Substates every empirical metric (0 bytes, 15.01s, 4.651ms, 30/30) to test logs | **VERIFIED** |
| **Technical Appendix** | [`docs/DUE_DILIGENCE_DOSSIER.pdf`](file:///home/quant/mycelium/docs/DUE_DILIGENCE_DOSSIER.pdf) | 10-page signed empirical due-diligence report | **VERIFIED & COMPILED** |
| **Technical Volume** | [`docs/AFWERX_PHASE_I_TECHNICAL_VOLUME.md`](file:///home/quant/mycelium/docs/AFWERX_PHASE_I_TECHNICAL_VOLUME.md) | Scaffold for 13-page designated-page template (Release 25.5/E standard) | **SCAFFOLDED (PENDING RELEASE)** |
| **Customer Discovery Deck** | [`docs/AFWERX_SBIR_CUSTOMER_DISCOVERY_DECK.md`](file:///home/quant/mycelium/docs/AFWERX_SBIR_CUSTOMER_DISCOVERY_DECK.md) | 10-slide internal briefing deck for stakeholder interviews | **ALIGNED (INTERNAL ASSET)** |
| **Work Plan (SOW)** | [`docs/AFWERX_PHASE_I_WORK_PLAN.md`](file:///home/quant/mycelium/docs/AFWERX_PHASE_I_WORK_PLAN.md) | Formatted to AFWERX SOW schema (Scope, Tasks, Kickoff, Day 45, Day 90) | **ALIGNED** |
| **Cost Basis** | [`docs/AFWERX_PHASE_I_COST_BASIS.md`](file:///home/quant/mycelium/docs/AFWERX_PHASE_I_COST_BASIS.md) | Itemized $75k budget breakdown ($45k labor, $15k compute, $5k ODC, $10k G&A) | **PLANNED (SUBJECT TO CEILING)** |

---

## 4. Mandatory Regulatory & Technical Demarcation Rules

All proposal assets must strictly adhere to the following demarcation rules:

1. **CNSA 2.0 Scope Precision:**  
   National Security Systems are entering a staged transition toward post-quantum cryptography under CNSA 2.0 and related federal migration policy, creating an engineering need for crypto-agile systems that can validate, replace, and operationally bind cryptographic components without introducing uncontrolled runtime or supply-chain state. NSA guidance identifies ML-KEM and ML-DSA as the post-quantum public-key algorithms for CNSA 2.0 and establishes a 2027 requirement for new products and services in applicable CSfC contexts, with broader migration milestones extending through 2030–2031 (and NSM-10 targeting 2035 for full NSS migration).  
   *(Never state "mandatory ML-KEM by 2027 across all NSS").*
2. **Customer Relationship Scoping:**  
   Air Force program offices (PEO Cyber and Networks, AFRL Information Directorate, Space Systems Command) must be explicitly designated as **candidate discovery stakeholders**. Never refer to them as confirmed customers, transition sponsors, or partners without executed agreements.
3. **Month 3 Milestone Scoping:**  
   The Month 3 milestone must state: *"Pursue and document Phase II transition interest, including LOI/MOA or equivalent customer evidence where obtainable"*. Securing an external government signature cannot be a required contractual success criterion.
4. **CMVP Demarcation:**  
   NIST CMVP / CAVP certificates are `NULL`. The system is an internal pre-validation engineering prototype; never imply formal NIST certification.
5. **Prototype Laboratory Grounded Truth:**  
   QuantumFlex is validated on a **laptop-centered prototype laboratory** (Lenovo Yoga 7 primary node running Fedora Linux with Pluton/TPM; HP Pavilion worker node; supported mobile enclaves) with software-defined network isolation (loopback, container networks, Tailscale mesh). Never claim single-board computers, discrete TPM modules, or physical injection benches as currently possessed.

---

## 5. Unlock Protocol (Path to Green Status)

To transition this checklist from **`CONDITIONAL / BLOCKED`** to **`SUBMISSION-READY GREEN`**, the following four gates must be passed:

```
[GATE 1: SOLICITATION VERIFICATION]
  -> Identify active Open Topic Phase I solicitation number on DSIP.
  -> Record exact submission deadline and award ceiling in this checklist.

[GATE 2: TEMPLATE RECONCILIATION]
  -> Download controlling Technical Volume template from the active solicitation package.
  -> Populate docs/AFWERX_PHASE_I_TECHNICAL_VOLUME.md into the exact template format.
  -> Verify designated page boundaries.

[GATE 3: REGISTRATION & COMPLIANCE SIGN-OFF]
  -> Confirm active SAM.gov UEI and CAGE code profiles.
  -> Complete 2026 PA Annual Report filing prior to September 30.

[GATE 4: PRE-SUBMISSION UPLOAD AUDIT]
  -> Upload Volume 1 form data.
  -> Upload Volume 2 PDF (Technical Volume + Appendix).
  -> Upload Volume 3 Cost Proposal.
  -> Complete Volume 6 Fraud, Waste & Abuse training.
  -> Perform visual check on generated DSIP preview bundle.
```
