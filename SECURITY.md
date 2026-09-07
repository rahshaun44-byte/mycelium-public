# Security Policy & Cryptographic Threat Model

## 1. Overview & Operational Scope

QuantumFlex is a post-quantum immune daemon and cryptographic control plane designed to secure distributed edge infrastructure, mobile enclaves, and workstation nodes against mathematical cryptanalysis, microarchitectural side-channels, and physical network perturbations.

This document formalizes the QuantumFlex threat model, approved cryptographic primitives, downgrade protection policies, and vulnerability disclosure mechanisms in alignment with G7 IAG / CISA guidance (September 2026) and NIST FIPS 203/204/205.

---

## 2. Threat Model & Adversary Capabilities

QuantumFlex assumes an active, computationally bounded classical adversary with prospective access to a Cryptographically Relevant Quantum Computer (CRQC).

| Threat Vector | Adversary Profile | Mitigating Architecture | Failure Behavior |
| :--- | :--- | :--- | :--- |
| **Harvest Now, Decrypt Later (HNDL)** | Intercepts, records, and stores encrypted network traffic today to decrypt once a CRQC becomes operational. | CFRG Hybrid KEM combining FrodoKEM-976-AES (conservative LWE) and RFC 7748 X25519. Unconditional dual decapsulation with dual-PRF HKDF extraction. | **Fail-Closed**: If either leg is broken or compromised, confidentiality reduces to the remaining unbroken primitive. |
| **Microarchitectural Timing & Hertzbleed** | Exploits dynamic frequency/power scaling (DVFS) under data-dependent CPU workloads to leak private keys. | Constant-time execution paths for all scalar multiplications and matrix operations. Bitwise error accumulation (`err_mask |= x25519_err \| frodo_err`) eliminates early-exit timing oracles. Ephemeral memory scrubbed via `OPENSSL_cleanse`. | **Deterministic Rejection**: Constant-time synthetic secret generation upon perturbation; zero timing divergence. |
| **Active Network Manipulation & Reassembly DoS** | Injects malformed MTU frames, duplicates fragments, or spams uncompleted handshake sessions to exhaust memory. | Bounded `QFXK` reassembly table ($\le 64$ sessions), 1200ms dead reckoning timeout, strict chunk bounds ($\le 64$ chunks, $\le 1450$ bytes/chunk), and IEEE 802.3 CRC32 integrity verification. | **Drop & Evict**: Oldest uncompleted session evicted when table is saturated; malformed frames route entropy to Ghost Node sink. |
| **Algorithmic Downgrade Attacks** | Injects faults or blocks PQC packets to coerce fallback to unauthenticated or weak classical algorithms. | Authoritative Open Policy Agent (`membrane_health.rego`) engine. Fallback ladder is strictly unidirectional (`ML-KEM-768 -> FrodoKEM-976 -> X25519`). Unauthorized fallbacks trigger circuit breaker. | **Node Quarantine**: Node isolates network interfaces and enters forensic lockdown upon circuit breaker trip. |

---

## 3. Cryptographic Primitives & Inventory

### A. Key Encapsulation Mechanisms (KEM)
* **Primary Modern**: ML-KEM-768 (NIST FIPS 203 / Module-LWE). Wire size: $pk=1184$ B, $ct=1088$ B, $ss=32$ B.
* **Conservative Fallback**: FrodoKEM-976-AES (CFRG / Matrix LWE without algebraic rings). Wire size: $pk=15632$ B, $ct=15744$ B, $ss=32$ B.
* **Classical Baseline**: X25519 (RFC 7748 / Montgomery Curve25519). Wire size: $pk=32$ B, $ct=32$ B, $ss=32$ B.
* **Combiner Specification**: CFRG `draft-irtf-cfrg-hybrid-kems` Dual-PRF HKDF-SHA256 with explicit transcript binding:
  $$\text{SharedSecret} = \text{HKDF-Expand}(\text{HKDF-Extract}(\text{Salt}, K_{\text{X25519}} \parallel K_{\text{Frodo}}), \text{Context}, 32)$$

### B. Digital Signatures & Node Identity
* **Primary Modern**: ML-DSA-65 (NIST FIPS 204 / Module-Lattice Signatures).
* **Hash-Based Fallback**: SLH-DSA-128s (NIST FIPS 205 / Stateless Hash-Based Signatures).
* **Classical Baseline**: Ed25519 (RFC 8032 / Edwards-curve Digital Signature Algorithm).

### C. Master Entropy Partitioning
* **Shamir's Secret Sharing**: $GF(256)$ polynomials with 2-of-3 threshold ($k=2, n=3$).
* **Shard Distribution**: Shard #1 on Pixel GrapheneOS Titan M2 enclave; Shard #2 on Samsung Galaxy Ultra Knox Vault; Shard #3 on Yoga 7 physical host vault.

---

## 4. KEM Authentication Model & Boundary Enforcement

> [!IMPORTANT]
> **KEM Confers Confidentiality, Not Identity Authenticity**:
> A hybrid KEM handshake provides forward-secret confidentiality against passive eavesdropping and active ciphertext tampering (IND-CCA2). It does **not** identify or authenticate the communicating peer.

To achieve mutual authentication and channel binding:
1. **Transport Carrier Boundary**: All inter-node QFXK binary traffic must be wrapped in mutual TLS 1.3 (`mTLS`) over port `9443` on the Tailscale WireGuard mesh interface.
2. **Identity Verification**: Peers authenticate using Ed25519 or ML-DSA-65 client certificates signed by the QuantumFlex Root CA.
3. **Transcript Binding**: The dual-PRF HKDF context parameter binds the client and server ephemeral public keys and ciphertexts into the derived key, preventing cross-session relay and cross-protocol splicing attacks.

---

## 5. Downgrade Prevention & Circuit Breaker Policy

1. **Unidirectional Agility Ladder**:
   The engine only transitions downward along the approved policy path:
   `ML-KEM-768` $\longrightarrow$ `FrodoKEM-976-AES` $\longrightarrow$ `X25519 (Classical Fallback)`.
2. **OPA Verdict Mandate**:
   No cryptographic transition occurs without an authoritative JSON verdict from the local OPA sidecar (`127.0.0.1:8181/v1/data/membrane/health/verdict`).
3. **Halt-on-Exhaustion**:
   If the classical fallback leg fails or is degraded by network anomalies, the engine immediately halts and drops all unauthenticated sessions rather than negotiating unknown or unapproved algorithms.

---

## 6. Vulnerability Disclosure & Reporting

If you discover a potential cryptographic weakness, timing leak, or protocol vulnerability in QuantumFlex:

1. **Do Not File Public Issues**: Do not open public GitHub issues or forum discussions.
2. **Reporting Channel**: Encrypt your advisory using the QuantumFlex Control Plane Ed25519/ML-DSA public key and transmit to:
   - Security Contact: `security@quantumflex.local`
3. **Response Timeline**:
   - Initial Acknowledgment: Within 24 hours.
   - Triage & Reproduction: Within 72 hours.
   - Patch & Coordinated Disclosure: Within 30 days.
