# OMB M-26-15 & CNSA 2.0: Defense Subcontractor Compliance

## OMB M-26-15
**Title:** Transition to Post-Quantum Cryptography
**Target Audience:** Heads of Executive Departments and Agencies.
**Key Deadline:** October 2026. Agencies must submit comprehensive cryptographic migration plans to the Office of Management and Budget (OMB) and the Office of the National Cyber Director (ONCD).
**Impact on Subcontractors:** While M-26-15 directly binds federal agencies, it acts as the primary "forcing function" driving RFP (Request for Proposal) requirements down the supply chain. Agencies cannot meet M-26-15 mandates if their software vendors and subcontractors are running legacy cryptography.

## CNSA 2.0 (Commercial National Security Algorithm Suite 2.0)
**Issuer:** National Security Agency (NSA).
**Target:** National Security Systems (NSS) and vendors supplying them.
**Mandate:** 
- Identifies ML-KEM-1024 and ML-DSA-87 as the sole algorithms permitted for securing NSS.
- **January 1, 2027 Gate:** By this date, all new software procured for NSS must natively support CNSA 2.0 post-quantum algorithms. Software lacking PQC capabilities will be legally barred from NSS procurement.

## CMMC Level 2 & Level 3 (Cybersecurity Maturity Model Certification)
**Target:** Defense Industrial Base (DIB) Subcontractors handling Controlled Unclassified Information (CUI).
**Phase 2 Activation:** November 10, 2026.
**Requirements:**
- CMMC requires strict cryptographic protections for CUI at rest and in transit (originally FIPS 140-2/-3).
- As the DoD aligns CMMC with CNSA 2.0 and M-26-15, assessors will increasingly require Cryptographic Bill of Materials (CBOMs) and proof of cryptographic agility.
- Subcontractors unable to demonstrate a clear path to ML-KEM/ML-DSA adoption risk failing CMMC assessments, effectively locking them out of DoD contracts.

## Quantum Flex Alignment
QuantumFlex provides the exact structural bridge required by these mandates. By establishing a "fail-secure" PQC Immune Daemon and an automated CBOM generation process, QuantumFlex allows defense subcontractors to instantly prove cryptographic agility to external assessors without requiring heavy C++ rewrites.
