# QF-M6-D — Independent Assurance, Key Recovery Drills & Sovereign Economic Return

**Control IDs:** `QF-KEY-01`, `QF-RELEASE-01`, `QF-CAPITAL-01`, `QF-OPS-01`  
**Phase:** `M6-D` (Final Consolidation Phase unblocked by `M6-A`, `M6-B`, and `M6-C`)  
**Historical Infrastructure Baseline Preserved:** `8131899`  
**Authoritative Implementations:**  
- Key Recovery & Re-Delegation: [`src/admission_receipt.py`](file:///home/quant/mycelium/src/admission_receipt.py)  
- Sovereign Economic Return Gates: [`src/bounty_assurance.py`](file:///home/quant/mycelium/src/bounty_assurance.py)  
**Adversarial Test Suite:** [`tests/test_qf_m6_d_independent_assurance.py`](file:///home/quant/mycelium/tests/test_qf_m6_d_independent_assurance.py)

---

## 1. Governing Architecture & Purpose

`QF-M6-D` completes the **QuantumFlex Sovereign Security Consolidation** by uniting:
1. **Adversarial Assurance & Key-Compromise Recovery:** Proving mathematically and operationally that if a Tier 1 release signing key is compromised or retired, the Tier 0 Offline Root of Trust can revoke it, issue a monotonic Key Revocation List (KRL), and authorize a fresh release key without re-architecting the system or risking replay of compromised releases.
2. **Sovereign Economic Return Gates (`M6-01` .. `M6-07`):** Proving that all revenue from Bug Bounties (Pillar 1), Public Good Grants (Pillar 2), or Family Office Research (Pillar 3) adheres strictly to the fail-closed constitutional invariants:
   - **Zero-Client, Zero-Corporate Overhead:** Zero sales calls, zero SLAs, zero cloud LLM spend ($0.00).
   - **Unsettled Awards Rule:** Unsettled awards, bounties, and speculative grants *never* count as liquid income or reserve capital.
   - **Reserve Invariant:** $R_{\text{verified liquid}} \ge 6 \times (O_{\text{household}} + O_{\text{operating}})$ must hold at all times.

---

## 2. Key-Compromise Recovery Drill Procedure (`QF-KEY-01`)

```
┌────────────────────────────────────────────────────────────────────────┐
│ Incident Trigger: Compromise of Tier 1 Prod Key (e.g. key leakage)     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Step 1: Offline Root Ceremony (Air-gapped)                             │
│   • Offline Root invokes issue_key_revocation_list                     │
│   • Increments monotonic KRL sequence: s_krl = s_current + 1           │
│   • Appends compromised key fingerprint & cert_id to KRL               │
│   • Conjunctively signs KRL (Root Ed25519 ∧ Root ML-DSA-65)            │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Step 2: Emergency Keypair Generation                                   │
│   • Generate new isolated Tier 1 keypair (0600 permissions)            │
│   • Ed25519 + NIST FIPS 204 ML-DSA-65                                  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Step 3: Root Re-Delegation Certificate Issuance                        │
│   • Offline Root issues qf.key_delegation_cert.v1 for new keypair      │
│   • Binds to key_environment="prod" and new validity window            │
│   • Conjunctively signs Certificate (Root Ed25519 ∧ Root ML-DSA-65)     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Step 4: Verification and Admission Recovery                            │
│   • Verifier evaluates release with new KRL and new Certificate        │
│   • Any release signed by compromised key fails closed (PermissionError)│
│   • Release signed by new re-delegated key passes conjunctive checks    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Seven Sovereign Economic Acceptance Gates (`M6-01` .. `M6-07`)

Function: [`evaluate_qf_m6_economic_return_gates`](file:///home/quant/mycelium/src/bounty_assurance.py)

| Gate | Description | Fail-Closed Check |
| :--- | :--- | :--- |
| **`M6-01`** | **Explicitly Authorized Target** | Target repository, smart contract, or grant topic is explicitly listed in approved scope (`Immunefi`, `Code4rena`, `NLnet`, etc.). |
| **`M6-02`** | **Local Reproducible Finding** | Vulnerability / deliverable is reproduced entirely in an authorized offline sandbox or local Foundry fork (zero live network exploitation). |
| **`M6-03`** | **Independent Evidence Verification** | Artifact digests, citation graph, and Merkle roots reproduce independently without tampering. |
| **`M6-04`** | **Compliant Submission** | PrivacyFilter scrubs all internal data/hostnames; `$0.00` cloud LLM spend; explicit human approval by `rahshaun_chambers`. |
| **`M6-05`** | **Verified Award Notice** | Official award confirmation received from the bounty platform or grant foundation. |
| **`M6-06`** | **Settled Funds Independently Reconciled** | Canonical 6-decimal USDC settlement or FDIC bank transfer settled; **unsettled awards strictly forbidden from counting as income**. |
| **`M6-07`** | **Reserve Protection ($R \ge 6O$)** | Post-tax net revenue is routed to Reserve Reinvestment (Bucket 1 or 3); liquid reserve coverage remains $\ge 6.00$ months. |
