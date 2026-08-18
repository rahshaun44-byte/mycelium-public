# NIST FIPS 203, 204, and 205: Post-Quantum Cryptography Standards

## Overview
In August 2024, the National Institute of Standards and Technology (NIST) finalized the first three Post-Quantum Cryptography (PQC) standards designed to withstand attacks by quantum computers. These algorithms replace classical public-key cryptography (such as RSA and Diffie-Hellman) which are vulnerable to Shor's algorithm on a cryptographically relevant quantum computer (CRQC).

## FIPS 203: Module-Lattice-Based Key-Encapsulation Mechanism (ML-KEM)
- **Primary Use:** Key establishment and encryption across public networks.
- **Based on:** The CRYSTALS-Kyber algorithm.
- **Structure:** Relies on the hardness of the Module Learning with Errors (MLWE) problem over structured lattices.
- **Security Levels:**
  - `ML-KEM-512`: Maps to AES-128 equivalent security (NIST Security Level 1).
  - `ML-KEM-768`: Maps to AES-192 equivalent security (NIST Security Level 3). Recommended baseline for enterprise.
  - `ML-KEM-1024`: Maps to AES-256 equivalent security (NIST Security Level 5). Mandated by CNSA 2.0 for Top Secret/National Security Systems.
- **Performance Characteristics:** Highly efficient encapsulation and decapsulation, making it suitable for high-traffic TLS 1.3 handshakes.

## FIPS 204: Module-Lattice-Based Digital Signature Algorithm (ML-DSA)
- **Primary Use:** Digital signatures for identity authentication and document non-repudiation.
- **Based on:** The CRYSTALS-Dilithium algorithm.
- **Structure:** Also relies on structured lattices, specifically the Module Short Integer Solution (MSIS) and MLWE problems.
- **Security Levels:**
  - `ML-DSA-44` (Level 2)
  - `ML-DSA-65` (Level 3)
  - `ML-DSA-87` (Level 5) - Mandated by CNSA 2.0.

## FIPS 205: Stateless Hash-Based Digital Signature Algorithm (SLH-DSA)
- **Primary Use:** Digital signatures, acting as a highly conservative fallback.
- **Based on:** The SPHINCS+ algorithm.
- **Structure:** Relies entirely on the security of hash functions (SHA-2 or SHAKE), avoiding lattice-based mathematics entirely.
- **Trade-offs:** Significantly larger signature sizes and slower generation times compared to ML-DSA, but provides mathematical diversity in case structural weaknesses are found in lattices.

## Migration Directives
NIST strongly advises all organizations to implement cryptographic agility—the ability to hot-swap cryptographic primitives without requiring architectural refactoring or prolonged downtime. Hybrid modes (combining classical X25519 with ML-KEM) are recommended during the transition period.
