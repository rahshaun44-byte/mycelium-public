# Post-Quantum Cryptographic Readiness & CBOM Audit Report
**Audited Target:** `/home/quant/mycelium`  
**Issuing Authority:** Rahshaun Chambers // QuantumFlex Audit Engine  
**Standard:** NIST FIPS 203/204/205 • OMB Memorandum M-26-15 • CycloneDX v1.5 CBOM  
**Date:** 2026-10-23 01:16:52Z  
**Serial ID:** `urn:uuid:e4f7e9ed-4642-430e-9205-420cc53bb36c`  

---

## 1. Executive Summary
This cryptographic assessment evaluates the software and configuration boundary against the post-quantum cryptographic standards mandated by OMB M-26-15 and NIST FIPS 203/204.

- **Total Files Scanned:** 583
- **Cryptographic Assets Discovered:** 19
- **Post-Quantum KEM Coverage:** COMPLIANT (ML-KEM-512, ML-KEM-768, ML-KEM-1024, FrodoKEM-640-AES, FrodoKEM-976-AES, FrodoKEM-1344-AES, HQC)
- **Legacy Classical Footprint:** 2 classical algorithm family references identified.

---

## 2. Discovered Cryptographic Asset Inventory
| Algorithm | Primitive Category | Standard Baseline | Compliance Posture | Discovered References |
| :--- | :--- | :--- | :--- | :--- |
| **ML-KEM-512** | PQC_KEM | NIST FIPS 203 | `APPROVED` | 21 file(s) |
| **ML-KEM-768** | PQC_KEM | NIST FIPS 203 | `APPROVED` | 81 file(s) |
| **ML-KEM-1024** | PQC_KEM | NIST FIPS 203 | `APPROVED` | 26 file(s) |
| **FrodoKEM-640-AES** | PQC_KEM | Experimental / Non-ISO (draft-longa-cfrg) | `isolated` | 11 file(s) |
| **FrodoKEM-976-AES** | PQC_KEM | ISO/IEC 18033-2 / Candidate | `FALLBACK_APPROVED` | 39 file(s) |
| **FrodoKEM-1344-AES** | PQC_KEM | ISO/IEC 18033-2 / Candidate | `FALLBACK_APPROVED` | 10 file(s) |
| **HQC** | PQC_KEM | Round 4 Candidate | `MONITORED` | 1 file(s) |
| **ML-DSA-44** | PQC_SIG | NIST FIPS 204 | `APPROVED` | 4 file(s) |
| **ML-DSA-65** | PQC_SIG | NIST FIPS 204 | `APPROVED` | 38 file(s) |
| **ML-DSA-87** | PQC_SIG | NIST FIPS 204 | `APPROVED` | 7 file(s) |
| **SLH-DSA-SHA2-128f** | PQC_SIG | NIST FIPS 205 | `APPROVED` | 16 file(s) |
| **RSA-2048** | CLASSICAL_ASYMMETRIC | NIST SP 800-56B | `DEPRECATED_OMB_M26_15` | 1 file(s) |
| **ECDSA-P256** | CLASSICAL_ASYMMETRIC | FIPS 186-4 | `DEPRECATED_OMB_M26_15` | 4 file(s) |
| **X25519** | CLASSICAL_ASYMMETRIC | RFC 7748 | `TRANSITIONAL_HYBRID_ONLY` | 42 file(s) |
| **Ed25519** | CLASSICAL_ASYMMETRIC | RFC 8032 | `TRANSITIONAL_HYBRID_ONLY` | 96 file(s) |
| **AES-256-GCM** | SYMMETRIC | NIST SP 800-38D | `APPROVED` | 3 file(s) |
| **SHA-256** | HASH | NIST FIPS 180-4 | `APPROVED` | 121 file(s) |
| **SHA-384** | HASH | NIST FIPS 180-4 | `APPROVED` | 2 file(s) |
| **SHA-512** | HASH | NIST FIPS 180-4 | `APPROVED` | 5 file(s) |

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
