# Post-Quantum Cryptographic Readiness & CBOM Audit Report
**Audited Target:** `/home/quant/pqc-immune-daemon/mycelium`  
**Issuing Authority:** FinallyFungus LLC // QuantumFlex Audit Engine  
**Standard:** NIST FIPS 203/204/205 • OMB Memorandum M-26-15 • CycloneDX v1.5 CBOM  
**Date:** 2026-09-10 04:28:06Z  
**Serial ID:** `urn:uuid:b053ac72-55ea-4878-a979-e26ee4a4dcef`  

---

## 1. Executive Summary
This cryptographic assessment evaluates the software and configuration boundary against the post-quantum cryptographic standards mandated by OMB M-26-15 and NIST FIPS 203/204.

- **Total Files Scanned:** 7121
- **Cryptographic Assets Discovered:** 22
- **Post-Quantum KEM Coverage:** COMPLIANT (ML-KEM-512, ML-KEM-768, ML-KEM-1024, FrodoKEM-640-AES, FrodoKEM-976-AES, FrodoKEM-1344-AES, Classic-McEliece, HQC)
- **Legacy Classical Footprint:** 3 classical algorithm family references identified.

---

## 2. Discovered Cryptographic Asset Inventory
| Algorithm | Primitive Category | Standard Baseline | Compliance Posture | Discovered References |
| :--- | :--- | :--- | :--- | :--- |
| **ML-KEM-512** | PQC_KEM | NIST FIPS 203 | `APPROVED` | 90 file(s) |
| **ML-KEM-768** | PQC_KEM | NIST FIPS 203 | `APPROVED` | 86 file(s) |
| **ML-KEM-1024** | PQC_KEM | NIST FIPS 203 | `APPROVED` | 79 file(s) |
| **FrodoKEM-640-AES** | PQC_KEM | Experimental / Non-ISO (draft-longa-cfrg) | `isolated` | 18 file(s) |
| **FrodoKEM-976-AES** | PQC_KEM | ISO/IEC 18033-2 / Candidate | `FALLBACK_APPROVED` | 40 file(s) |
| **FrodoKEM-1344-AES** | PQC_KEM | ISO/IEC 18033-2 / Candidate | `FALLBACK_APPROVED` | 17 file(s) |
| **Classic-McEliece** | PQC_KEM | Round 4 Candidate | `MONITORED` | 20 file(s) |
| **HQC** | PQC_KEM | Round 4 Candidate | `MONITORED` | 59 file(s) |
| **ML-DSA-44** | PQC_SIG | NIST FIPS 204 | `APPROVED` | 55 file(s) |
| **ML-DSA-65** | PQC_SIG | NIST FIPS 204 | `APPROVED` | 75 file(s) |
| **ML-DSA-87** | PQC_SIG | NIST FIPS 204 | `APPROVED` | 53 file(s) |
| **SLH-DSA-SHA2-128f** | PQC_SIG | NIST FIPS 205 | `APPROVED` | 216 file(s) |
| **RSA-2048** | CLASSICAL_ASYMMETRIC | NIST SP 800-56B | `DEPRECATED_OMB_M26_15` | 1 file(s) |
| **RSA-4096** | CLASSICAL_ASYMMETRIC | NIST SP 800-56B | `DEPRECATED_OMB_M26_15` | 1 file(s) |
| **ECDSA-P256** | CLASSICAL_ASYMMETRIC | FIPS 186-4 | `DEPRECATED_OMB_M26_15` | 1 file(s) |
| **X25519** | CLASSICAL_ASYMMETRIC | RFC 7748 | `TRANSITIONAL_HYBRID_ONLY` | 30 file(s) |
| **Ed25519** | CLASSICAL_ASYMMETRIC | RFC 8032 | `TRANSITIONAL_HYBRID_ONLY` | 26 file(s) |
| **AES-256-GCM** | SYMMETRIC | NIST SP 800-38D | `APPROVED` | 3 file(s) |
| **SHA-256** | HASH | NIST FIPS 180-4 | `APPROVED` | 74 file(s) |
| **SHA-384** | HASH | NIST FIPS 180-4 | `APPROVED` | 13 file(s) |
| **SHA-512** | HASH | NIST FIPS 180-4 | `APPROVED` | 22 file(s) |
| **SHA-1** | HASH | DISALLOWED | `TOXIC` | 4 file(s) |

---

## 3. Buffer Exhaustion Vectors (NIST Level 3/5 Inelasticity)
The following static buffer allocations were detected within the AST/source code. These allocations are strictly bounded below the 15,792 byte requirement for FIPS 203 (FrodoKEM-976-AES) hybrid ciphertexts, guaranteeing memory truncation and process crashes during post-quantum key exchange.

| File | Line | Static Allocation Size | Offending Code |
| :--- | :--- | :--- | :--- |
| `liboqs/src/kem/classic_mceliece/pqclean_mceliece460896_avx2/decrypt.c` | 59 | `1024 bytes` (Critically Undersized) | `unsigned char r[ 1024 ];` |
| `liboqs/src/kem/classic_mceliece/pqclean_mceliece460896f_avx2/decrypt.c` | 59 | `1024 bytes` (Critically Undersized) | `unsigned char r[ 1024 ];` |
| `liboqs/src/kem/classic_mceliece/pqclean_mceliece6688128_avx2/decrypt.c` | 59 | `1024 bytes` (Critically Undersized) | `unsigned char r[ 1024 ];` |
| `liboqs/src/kem/classic_mceliece/pqclean_mceliece6688128f_avx2/decrypt.c` | 59 | `1024 bytes` (Critically Undersized) | `unsigned char r[ 1024 ];` |
| `liboqs/src/kem/classic_mceliece/pqclean_mceliece6960119_avx2/decrypt.c` | 59 | `1024 bytes` (Critically Undersized) | `unsigned char r[ 1024 ];` |
| `liboqs/src/kem/classic_mceliece/pqclean_mceliece6960119f_avx2/decrypt.c` | 59 | `1024 bytes` (Critically Undersized) | `unsigned char r[ 1024 ];` |
| `liboqs/src/kem/ml_kem/mlkem-native_ml-kem-1024_aarch64/mlkem/src/native/aarch64/src/arith_native_aarch64.h` | 35 | `4096 bytes` (Critically Undersized) | `MLK_INTERNAL_DATA_DECLARATION const uint8_t mlk_rej_uniform_table[4096];` |
| `liboqs/src/kem/ml_kem/mlkem-native_ml-kem-1024_aarch64/mlkem/src/native/aarch64/src/arith_native_aarch64.h` | 171 | `4096 bytes` (Critically Undersized) | `unsigned buflen, const uint8_t table[4096])` |
| `liboqs/src/kem/ml_kem/mlkem-native_ml-kem-1024_aarch64/mlkem/src/native/aarch64/src/mlkem_rej_uniform_aarch64_asm.S` | 9 | `4096 bytes` (Critically Undersized) | `Signature: uint64_t mlk_rej_uniform_aarch64_asm(int16_t r[256], const uint8_t *buf, unsigned buflen, const uint8_t table[4096])` |
| `liboqs/src/kem/ml_kem/mlkem-native_ml-kem-1024_aarch64/mlkem/src/native/aarch64/src/mlkem_rej_uniform_aarch64_asm.S` | 35 | `4096 bytes` (Critically Undersized) | `c_parameter: const uint8_t table[4096]` |
| `liboqs/src/kem/ml_kem/mlkem-native_ml-kem-1024_x86_64/mlkem/src/native/x86_64/src/arith_native_x86_64.h` | 18 | `4096 bytes` (Critically Undersized) | `MLK_INTERNAL_DATA_DECLARATION const uint8_t mlk_rej_uniform_table[4096];` |
| `liboqs/src/kem/ml_kem/mlkem-native_ml-kem-512_aarch64/mlkem/src/native/aarch64/src/arith_native_aarch64.h` | 35 | `4096 bytes` (Critically Undersized) | `MLK_INTERNAL_DATA_DECLARATION const uint8_t mlk_rej_uniform_table[4096];` |
| `liboqs/src/kem/ml_kem/mlkem-native_ml-kem-512_aarch64/mlkem/src/native/aarch64/src/arith_native_aarch64.h` | 171 | `4096 bytes` (Critically Undersized) | `unsigned buflen, const uint8_t table[4096])` |
| `liboqs/src/kem/ml_kem/mlkem-native_ml-kem-512_aarch64/mlkem/src/native/aarch64/src/mlkem_rej_uniform_aarch64_asm.S` | 9 | `4096 bytes` (Critically Undersized) | `Signature: uint64_t mlk_rej_uniform_aarch64_asm(int16_t r[256], const uint8_t *buf, unsigned buflen, const uint8_t table[4096])` |
| `liboqs/src/kem/ml_kem/mlkem-native_ml-kem-512_aarch64/mlkem/src/native/aarch64/src/mlkem_rej_uniform_aarch64_asm.S` | 35 | `4096 bytes` (Critically Undersized) | `c_parameter: const uint8_t table[4096]` |
| `liboqs/src/kem/ml_kem/mlkem-native_ml-kem-512_x86_64/mlkem/src/native/x86_64/src/arith_native_x86_64.h` | 18 | `4096 bytes` (Critically Undersized) | `MLK_INTERNAL_DATA_DECLARATION const uint8_t mlk_rej_uniform_table[4096];` |
| `liboqs/src/kem/ml_kem/mlkem-native_ml-kem-768_aarch64/mlkem/src/native/aarch64/src/arith_native_aarch64.h` | 35 | `4096 bytes` (Critically Undersized) | `MLK_INTERNAL_DATA_DECLARATION const uint8_t mlk_rej_uniform_table[4096];` |
| `liboqs/src/kem/ml_kem/mlkem-native_ml-kem-768_aarch64/mlkem/src/native/aarch64/src/arith_native_aarch64.h` | 171 | `4096 bytes` (Critically Undersized) | `unsigned buflen, const uint8_t table[4096])` |
| `liboqs/src/kem/ml_kem/mlkem-native_ml-kem-768_aarch64/mlkem/src/native/aarch64/src/mlkem_rej_uniform_aarch64_asm.S` | 9 | `4096 bytes` (Critically Undersized) | `Signature: uint64_t mlk_rej_uniform_aarch64_asm(int16_t r[256], const uint8_t *buf, unsigned buflen, const uint8_t table[4096])` |
| `liboqs/src/kem/ml_kem/mlkem-native_ml-kem-768_aarch64/mlkem/src/native/aarch64/src/mlkem_rej_uniform_aarch64_asm.S` | 35 | `4096 bytes` (Critically Undersized) | `c_parameter: const uint8_t table[4096]` |
| `liboqs/src/kem/ml_kem/mlkem-native_ml-kem-768_x86_64/mlkem/src/native/x86_64/src/arith_native_x86_64.h` | 18 | `4096 bytes` (Critically Undersized) | `MLK_INTERNAL_DATA_DECLARATION const uint8_t mlk_rej_uniform_table[4096];` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-44_aarch64/mldsa/src/native/aarch64/src/arith_native_aarch64.h` | 33 | `4096 bytes` (Critically Undersized) | `MLD_INTERNAL_DATA_DECLARATION const uint8_t mld_rej_uniform_eta_table[4096];` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-44_aarch64/mldsa/src/native/aarch64/src/arith_native_aarch64.h` | 118 | `4096 bytes` (Critically Undersized) | `const uint8_t table[4096])` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-44_aarch64/mldsa/src/native/aarch64/src/arith_native_aarch64.h` | 138 | `4096 bytes` (Critically Undersized) | `const uint8_t table[4096])` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-44_aarch64/mldsa/src/native/aarch64/src/mldsa_rej_uniform_eta2_aarch64_asm.S` | 10 | `4096 bytes` (Critically Undersized) | `Signature: uint64_t mld_rej_uniform_eta2_aarch64_asm(int32_t r[256], const uint8_t *buf, unsigned buflen, const uint8_t table[4096])` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-44_aarch64/mldsa/src/native/aarch64/src/mldsa_rej_uniform_eta2_aarch64_asm.S` | 36 | `4096 bytes` (Critically Undersized) | `c_parameter: const uint8_t table[4096]` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-44_aarch64/mldsa/src/native/aarch64/src/mldsa_rej_uniform_eta4_aarch64_asm.S` | 10 | `4096 bytes` (Critically Undersized) | `Signature: uint64_t mld_rej_uniform_eta4_aarch64_asm(int32_t r[256], const uint8_t *buf, unsigned buflen, const uint8_t table[4096])` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-44_aarch64/mldsa/src/native/aarch64/src/mldsa_rej_uniform_eta4_aarch64_asm.S` | 36 | `4096 bytes` (Critically Undersized) | `c_parameter: const uint8_t table[4096]` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-65_aarch64/mldsa/src/native/aarch64/src/arith_native_aarch64.h` | 33 | `4096 bytes` (Critically Undersized) | `MLD_INTERNAL_DATA_DECLARATION const uint8_t mld_rej_uniform_eta_table[4096];` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-65_aarch64/mldsa/src/native/aarch64/src/arith_native_aarch64.h` | 118 | `4096 bytes` (Critically Undersized) | `const uint8_t table[4096])` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-65_aarch64/mldsa/src/native/aarch64/src/arith_native_aarch64.h` | 138 | `4096 bytes` (Critically Undersized) | `const uint8_t table[4096])` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-65_aarch64/mldsa/src/native/aarch64/src/mldsa_rej_uniform_eta2_aarch64_asm.S` | 10 | `4096 bytes` (Critically Undersized) | `Signature: uint64_t mld_rej_uniform_eta2_aarch64_asm(int32_t r[256], const uint8_t *buf, unsigned buflen, const uint8_t table[4096])` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-65_aarch64/mldsa/src/native/aarch64/src/mldsa_rej_uniform_eta2_aarch64_asm.S` | 36 | `4096 bytes` (Critically Undersized) | `c_parameter: const uint8_t table[4096]` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-65_aarch64/mldsa/src/native/aarch64/src/mldsa_rej_uniform_eta4_aarch64_asm.S` | 10 | `4096 bytes` (Critically Undersized) | `Signature: uint64_t mld_rej_uniform_eta4_aarch64_asm(int32_t r[256], const uint8_t *buf, unsigned buflen, const uint8_t table[4096])` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-65_aarch64/mldsa/src/native/aarch64/src/mldsa_rej_uniform_eta4_aarch64_asm.S` | 36 | `4096 bytes` (Critically Undersized) | `c_parameter: const uint8_t table[4096]` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-87_aarch64/mldsa/src/native/aarch64/src/arith_native_aarch64.h` | 33 | `4096 bytes` (Critically Undersized) | `MLD_INTERNAL_DATA_DECLARATION const uint8_t mld_rej_uniform_eta_table[4096];` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-87_aarch64/mldsa/src/native/aarch64/src/arith_native_aarch64.h` | 118 | `4096 bytes` (Critically Undersized) | `const uint8_t table[4096])` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-87_aarch64/mldsa/src/native/aarch64/src/arith_native_aarch64.h` | 138 | `4096 bytes` (Critically Undersized) | `const uint8_t table[4096])` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-87_aarch64/mldsa/src/native/aarch64/src/mldsa_rej_uniform_eta2_aarch64_asm.S` | 10 | `4096 bytes` (Critically Undersized) | `Signature: uint64_t mld_rej_uniform_eta2_aarch64_asm(int32_t r[256], const uint8_t *buf, unsigned buflen, const uint8_t table[4096])` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-87_aarch64/mldsa/src/native/aarch64/src/mldsa_rej_uniform_eta2_aarch64_asm.S` | 36 | `4096 bytes` (Critically Undersized) | `c_parameter: const uint8_t table[4096]` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-87_aarch64/mldsa/src/native/aarch64/src/mldsa_rej_uniform_eta4_aarch64_asm.S` | 10 | `4096 bytes` (Critically Undersized) | `Signature: uint64_t mld_rej_uniform_eta4_aarch64_asm(int32_t r[256], const uint8_t *buf, unsigned buflen, const uint8_t table[4096])` |
| `liboqs/src/sig/ml_dsa/mldsa-native_ml-dsa-87_aarch64/mldsa/src/native/aarch64/src/mldsa_rej_uniform_eta4_aarch64_asm.S` | 36 | `4096 bytes` (Critically Undersized) | `c_parameter: const uint8_t table[4096]` |
| `liboqs/src/sig/uov/pqov_ov_III_avx2/gf16_tabs.c` | 64 | `8192 bytes` (Critically Undersized) | `PQOV_ALIGN const unsigned char __gf256_mul[8192] = {` |
| `liboqs/src/sig/uov/pqov_ov_III_neon/gf16_tabs_neon.c` | 73 | `8192 bytes` (Critically Undersized) | `PQOV_ALIGN const unsigned char __gf256_mul[8192] = {` |
| `liboqs/src/sig/uov/pqov_ov_III_pkc_avx2/gf16_tabs.c` | 64 | `8192 bytes` (Critically Undersized) | `PQOV_ALIGN const unsigned char __gf256_mul[8192] = {` |
| `liboqs/src/sig/uov/pqov_ov_III_pkc_neon/gf16_tabs_neon.c` | 73 | `8192 bytes` (Critically Undersized) | `PQOV_ALIGN const unsigned char __gf256_mul[8192] = {` |
| `liboqs/src/sig/uov/pqov_ov_III_pkc_skc_avx2/gf16_tabs.c` | 64 | `8192 bytes` (Critically Undersized) | `PQOV_ALIGN const unsigned char __gf256_mul[8192] = {` |
| `liboqs/src/sig/uov/pqov_ov_III_pkc_skc_neon/gf16_tabs_neon.c` | 73 | `8192 bytes` (Critically Undersized) | `PQOV_ALIGN const unsigned char __gf256_mul[8192] = {` |
| `liboqs/src/sig/uov/pqov_ov_Ip_avx2/gf16_tabs.c` | 64 | `8192 bytes` (Critically Undersized) | `PQOV_ALIGN const unsigned char __gf256_mul[8192] = {` |
| `liboqs/src/sig/uov/pqov_ov_Ip_neon/gf16_tabs_neon.c` | 73 | `8192 bytes` (Critically Undersized) | `PQOV_ALIGN const unsigned char __gf256_mul[8192] = {` |

---

## 4. Required Remediation Roadmap (OMB M-26-15)

1. **Replace Asymmetric Key Encapsulation**: Any classical ECDH / RSA key exchange must implement NIST FIPS 203 ML-KEM-768 or FrodoKEM-976 hybrid wrapper.
2. **Eliminate Hardcoded Ciphers**: Migrate all hardcoded cipher suites to runtime policy evaluation via Open Policy Agent (OPA).
3. **Continuous CBOM Verification**: Ensure automated CycloneDX generation is embedded in pre-commit and CI/CD pipelines.

---
*Report certified by FinallyFungus LLC.*
