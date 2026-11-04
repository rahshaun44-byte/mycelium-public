# Athena Knowledge Domain 07: Hardware Security & Silicon Roots of Trust

## Scope and Principles
Governs hardware-based root of trust, cryptographic coprocessors, Trusted Platform Modules (TPM), Secure Enclaves, and hardware attestation.

## Core Focus Areas
1. **Silicon Roots of Trust**:
   - Microsoft Pluton TPM 2.0 (Integrated on-die CPU security processor)
   - Google Titan M2 / M3 StrongBox hardware security module
   - Intel SGX / AMD SEV-SNP confidential computing
2. **TPM 2.0 Specifications**: Non-Volatile (NV) RAM indices, Platform Configuration Registers (PCRs 0-23), TPM Quote generation, Endorsement Keys (EK), and Attestation Keys (AK).
3. **Android Keystore & StrongBox**: Hardware-backed key generation, TEE isolation, attestation certificates, user authentication gating, and tamper-resistant hardware boundaries.
4. **Physical & Side-Channel Security**: Timing attacks, cache side-channels (Spectre/Meltdown variants), power analysis (DPA/CPA), fault injection, and zeroization routines.
5. **Hardware Invariant Verification**: Cryptographically anchoring software state roots into immutable hardware registers to guarantee fail-closed integrity.

## Scientific Mission
Athena analyzes hardware security architectures, verifies silicon-rooted digital certificates, and prevents unauthorized privileged escalation at the hardware boundary.
