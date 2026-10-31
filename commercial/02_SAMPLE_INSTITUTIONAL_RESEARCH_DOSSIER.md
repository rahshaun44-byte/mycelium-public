# Sample Institutional Research Dossier: Municipal Zoning, Post-Quantum Cryptography & Escrow Liability Assessment

**Dossier ID:** `QF-RDOS-SAMPLE-2026-001`  
**Prepared For:** Institutional M&A & Regulatory Diligence Counsel  
**Date of Issue:** `2026-10-30`  
**Corpus Merkle Root (SHA-256):** `9efdda9e6d9745f3bcfcebeecbacf7606236411e0eba659567b9648b8721bf95`  
**Citation Verification Status:** `100.0% Grounded (4/4 Primary Source Chunks Verified)`  
**Data Governance Posture:** `100% Local Isolated Compute (Zero External Cloud Transmission)`  

---

## 1. Executive Findings & Regulatory Posture

- **Treasury Escrow Single-Signer Exposure (`target_ma_crypto_inventory.pdf`):** Target entity's treasury state mutation workflows currently lack hardware-enforced dual-control physical attestation, creating a single-signer drain vulnerability prior to closing `[target_ma_crypto_inventory_c0002_d6ca4c84:p2]`.
- **Legacy Cryptographic & Credential Hygiene Finding (`target_ma_crypto_inventory.pdf`):** Target entity relies on legacy RSA-2048 TLS certificates and an unrotated internal microservice credential (`[REDACTED_CREDENTIAL]`). Remediation requires immediate credential rotation and staged migration to NIST FIPS 203 (`ML-KEM-768`) and FIPS 204 (`ML-DSA-65`) `[target_ma_crypto_inventory_c0001_a7951bbd:p1]`.

---

## 2. Cross-Document Municipal & Facility Compliance Verification

- **Permitted Light-Industrial Compute Load (`pittston_zoning_code_2026.pdf`):** Under Section 402.1 (Light Industrial & Sovereign Compute Overlay), sealed commercial data-processing installations with zero external radio-frequency emission are permitted by right up to a continuous electrical load of `15 kW` `[pittston_zoning_code_2026_c0001_48c715b9:p1]`.

---

## 3. Acoustic & Environmental Operating Covenants

- **Nighttime Exterior Acoustic Ceiling (`pittston_zoning_code_2026.pdf`):** Pursuant to Section 508.4 (Setback & Acoustic Mandate), all cooling assemblies and uninterruptible power supply (UPS) enclosures must maintain exterior parcel-boundary sound pressure levels strictly below `45 dBA` between `22:00` and `07:00` local time `[pittston_zoning_code_2026_c0002_47b263c3:p2]`.

---

## 4. Summary of Recommended Transaction Conditions

| Priority | Diligence Domain | Recommended Closing / Escrow Condition | Source Reference |
| :--- | :--- | :--- | :--- |
| **P0 (Pre-Close)** | Treasury Escrow | Enforce hardware-bound two-person authorization prior to funding escrow accounts. | `target_ma_crypto_inventory.pdf` (p. 2) |
| **P0 (Pre-Close)** | Credential Hygiene | Rotate exposed microservice bearer token and revoke legacy static credentials. | `target_ma_crypto_inventory.pdf` (p. 1) |
| **P1 (Post-Close 90d)** | Post-Quantum TLS | Upgrade key-exchange and signature primitives to NIST FIPS 203 / FIPS 204. | `target_ma_crypto_inventory.pdf` (p. 1) |
| **P1 (Facility Ops)** | Acoustic Compliance | Certify cabinet acoustic baffling `< 45 dBA` at parcel boundary during night hours. | `pittston_zoning_code_2026.pdf` (p. 2) |

---

## 5. Deterministic Citation & Cryptographic Provenance Ledger

Every factual statement in this dossier is verified against the following primary filing digests:

| Chunk Identifier | Primary Source Filing | Page Offset | Verified Chunk SHA-256 Digest |
| :--- | :--- | :--- | :--- |
| `target_ma_crypto_inventory_c0002_d6ca4c84` | `filings/target_ma_crypto_inventory.pdf` | p. 2 | `d6ca4c8408449b037843aaf775077e69fcf18d7227d0a340631fa158c3690d1e` |
| `target_ma_crypto_inventory_c0001_a7951bbd` | `filings/target_ma_crypto_inventory.pdf` | p. 1 | `a7951bbde5bc672ac7a8278d09522ae7e6968d22f30b6e7d9ef0a389bc6ee53c` |
| `pittston_zoning_code_2026_c0001_48c715b9` | `filings/pittston_zoning_code_2026.pdf` | p. 1 | `48c715b9af90d378bd3f501478a4bde1ea96ab73105fd82bf3f04da7b219d9fc` |
| `pittston_zoning_code_2026_c0002_47b263c3` | `filings/pittston_zoning_code_2026.pdf` | p. 2 | `47b263c39d940a00f7fa2b31bbe885008ebd8c1a282dba44036e027f0c4d8838` |
