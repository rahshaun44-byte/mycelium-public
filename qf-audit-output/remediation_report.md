# Post-Quantum Cryptographic Readiness & CBOM Audit Report
**Audited Target:** `/home/quant/mycelium`  
**Issuing Authority:** Rahshaun Chambers // QuantumFlex Audit Engine  
**Standard:** NIST FIPS 203/204/205 • OMB Memorandum M-26-15 • CycloneDX v1.5 CBOM  
**Date:** 2026-11-01 19:23:40Z  
**Serial ID:** `urn:uuid:15108f7d-3e6d-4add-9b7b-ec206db145ea`  

---

## 1. Executive Summary
This cryptographic assessment evaluates the software and configuration boundary against the post-quantum cryptographic standards mandated by OMB M-26-15 and NIST FIPS 203/204.

- **Total Files Scanned:** 548
- **Cryptographic Assets Discovered:** 18
- **Post-Quantum KEM Coverage:** COMPLIANT (ML-KEM-512, ML-KEM-768, ML-KEM-1024, FrodoKEM-640-AES, FrodoKEM-976-AES, FrodoKEM-1344-AES)
- **Legacy Classical Footprint:** 2 classical algorithm family references identified.

---

## 2. Discovered Cryptographic Asset Inventory
| Algorithm | Primitive Category | Standard Baseline | Compliance Posture | Discovered References |
| :--- | :--- | :--- | :--- | :--- |
| **ML-KEM-512** | PQC_KEM | NIST FIPS 203 | `APPROVED` | 8 file(s) |
| **ML-KEM-768** | PQC_KEM | NIST FIPS 203 | `APPROVED` | 54 file(s) |
| **ML-KEM-1024** | PQC_KEM | NIST FIPS 203 | `APPROVED` | 13 file(s) |
| **FrodoKEM-640-AES** | PQC_KEM | Experimental / Non-ISO (draft-longa-cfrg) | `isolated` | 6 file(s) |
| **FrodoKEM-976-AES** | PQC_KEM | ISO/IEC 18033-2:2006/Amd 2:2026 | `FALLBACK_APPROVED` | 23 file(s) |
| **FrodoKEM-1344-AES** | PQC_KEM | ISO/IEC 18033-2:2006/Amd 2:2026 | `FALLBACK_APPROVED` | 6 file(s) |
| **ML-DSA-44** | PQC_SIG | NIST FIPS 204 | `APPROVED` | 3 file(s) |
| **ML-DSA-65** | PQC_SIG | NIST FIPS 204 | `APPROVED` | 33 file(s) |
| **ML-DSA-87** | PQC_SIG | NIST FIPS 204 | `APPROVED` | 3 file(s) |
| **SLH-DSA-SHA2-128f** | PQC_SIG | NIST FIPS 205 | `APPROVED` | 8 file(s) |
| **RSA-2048** | CLASSICAL_ASYMMETRIC | NIST SP 800-56B | `DEPRECATED_OMB_M26_15` | 1 file(s) |
| **ECDSA-P256** | CLASSICAL_ASYMMETRIC | FIPS 186-4 | `DEPRECATED_OMB_M26_15` | 4 file(s) |
| **X25519** | CLASSICAL_ASYMMETRIC | RFC 7748 | `TRANSITIONAL_HYBRID_ONLY` | 24 file(s) |
| **Ed25519** | CLASSICAL_ASYMMETRIC | RFC 8032 | `TRANSITIONAL_HYBRID_ONLY` | 70 file(s) |
| **AES-256-GCM** | SYMMETRIC | NIST SP 800-38D | `APPROVED` | 3 file(s) |
| **SHA-256** | HASH | NIST FIPS 180-4 | `APPROVED` | 113 file(s) |
| **SHA-384** | HASH | NIST FIPS 180-4 | `APPROVED` | 5 file(s) |
| **SHA-512** | HASH | NIST FIPS 180-4 | `APPROVED` | 4 file(s) |

---

## 3. Buffer Exhaustion Vectors (NIST Level 3/5 Inelasticity)
The following static buffer allocations were detected within the AST/source code. These allocations are strictly bounded below the 15,792 byte FrodoKEM-976-AES ciphertext size (ISO/IEC 18033-2 candidate; not part of NIST FIPS 203, which specifies ML-KEM only), guaranteeing memory truncation and process crashes during post-quantum key exchange.

| File | Line | Static Allocation Size | Offending Code |
| :--- | :--- | :--- | :--- |
| No vulnerable static buffers detected | N/A | N/A | N/A |

---

## 4. Required Remediation Roadmap (OMB M-26-15)

1. **Replace Asymmetric Key Encapsulation**: Any classical ECDH / RSA key exchange must implement a NIST FIPS 203 ML-KEM-768 or ISO/IEC 18033-2 FrodoKEM-976 hybrid wrapper.
2. **Eliminate Hardcoded Ciphers**: Migrate all hardcoded cipher suites to runtime policy evaluation via Open Policy Agent (OPA).
3. **Continuous CBOM Verification**: Ensure automated CycloneDX generation is embedded in pre-commit and CI/CD pipelines.

---
*Report certified by Rahshaun Chambers.*
