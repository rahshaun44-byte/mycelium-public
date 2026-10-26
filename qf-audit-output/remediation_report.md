# Post-Quantum Cryptographic Readiness & CBOM Audit Report
**Audited Target:** `/home/quant/mycelium`  
**Issuing Authority:** Rahshaun Chambers // QuantumFlex Audit Engine  
**Standard:** NIST FIPS 203/204/205 • OMB Memorandum M-26-15 • CycloneDX v1.5 CBOM  
**Date:** 2026-10-26 17:12:39Z  
**Serial ID:** `urn:uuid:10469e52-e272-4098-8a03-0fe27e604483`  

---

## 1. Executive Summary
This cryptographic assessment evaluates the software and configuration boundary against the post-quantum cryptographic standards mandated by OMB M-26-15 and NIST FIPS 203/204.

- **Total Files Scanned:** 483
- **Cryptographic Assets Discovered:** 17
- **Post-Quantum KEM Coverage:** COMPLIANT (ML-KEM-512, ML-KEM-768, ML-KEM-1024, FrodoKEM-640-AES, FrodoKEM-976-AES, FrodoKEM-1344-AES)
- **Legacy Classical Footprint:** 1 classical algorithm family references identified.

---

## 2. Discovered Cryptographic Asset Inventory
| Algorithm | Primitive Category | Standard Baseline | Compliance Posture | Discovered References |
| :--- | :--- | :--- | :--- | :--- |
| **ML-KEM-512** | PQC_KEM | NIST FIPS 203 | `APPROVED` | 8 file(s) |
| **ML-KEM-768** | PQC_KEM | NIST FIPS 203 | `APPROVED` | 49 file(s) |
| **ML-KEM-1024** | PQC_KEM | NIST FIPS 203 | `APPROVED` | 15 file(s) |
| **FrodoKEM-640-AES** | PQC_KEM | Experimental / Non-ISO (draft-longa-cfrg) | `isolated` | 6 file(s) |
| **FrodoKEM-976-AES** | PQC_KEM | ISO/IEC 18033-2 / Candidate | `FALLBACK_APPROVED` | 23 file(s) |
| **FrodoKEM-1344-AES** | PQC_KEM | ISO/IEC 18033-2 / Candidate | `FALLBACK_APPROVED` | 6 file(s) |
| **ML-DSA-44** | PQC_SIG | NIST FIPS 204 | `APPROVED` | 3 file(s) |
| **ML-DSA-65** | PQC_SIG | NIST FIPS 204 | `APPROVED` | 27 file(s) |
| **ML-DSA-87** | PQC_SIG | NIST FIPS 204 | `APPROVED` | 3 file(s) |
| **SLH-DSA-SHA2-128f** | PQC_SIG | NIST FIPS 205 | `APPROVED` | 8 file(s) |
| **ECDSA-P256** | CLASSICAL_ASYMMETRIC | FIPS 186-4 | `DEPRECATED_OMB_M26_15` | 4 file(s) |
| **X25519** | CLASSICAL_ASYMMETRIC | RFC 7748 | `TRANSITIONAL_HYBRID_ONLY` | 24 file(s) |
| **Ed25519** | CLASSICAL_ASYMMETRIC | RFC 8032 | `TRANSITIONAL_HYBRID_ONLY` | 59 file(s) |
| **AES-256-GCM** | SYMMETRIC | NIST SP 800-38D | `APPROVED` | 3 file(s) |
| **SHA-256** | HASH | NIST FIPS 180-4 | `APPROVED` | 91 file(s) |
| **SHA-384** | HASH | NIST FIPS 180-4 | `APPROVED` | 2 file(s) |
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
