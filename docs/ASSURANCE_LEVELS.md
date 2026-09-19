# QuantumFlex Assurance Levels & Digital-DNA Identity Specification

**Status**: Active Architecture Standard  
**Date**: 2026-09-16  
**Audience**: Security Architects, Enclave Operators, Independent Assessors  

---

## 1. Assurance Level Hierarchy (QF-A1 to QF-A5)

To eliminate claim inflation and strictly distinguish between tested code, formal models, and authenticated releases, QuantumFlex adopts a 5-tier assurance classification:

| Level | Identifier | Definition | Status in Current Repository |
| :--- | :--- | :--- | :--- |
| **QF-A1** | **Tested** | Automated tests passed (unit, integration, sanitizer, fuzz, memory zeroization). | **VERIFIED (22/22 C++, 41/41 Pytest, 22/22 Rego)** |
| **QF-A2** | **Policy-Enforced** | OPA/Wasm runtime invariants and system boundary gates actively enforce fail-closed decisions. | **VERIFIED (`membrane_health.wasm`, `reserve_invariant.wasm`)** |
| **QF-A3** | **Formally Specified** | Properties expressed and proved mathematically in F* (`formal/QuantumFlex_Core.fst`). | **VERIFIED (5 Theorems Proved)** |
| **QF-A4** | **Verified Implementation** | Running C code mechanically extracted from proven F* models via a verified compiler/toolchain (KaRaMeL). | **NULL / GAP ADMITTED** (`verified_core.c` is manual C reference) |
| **QF-A5** | **Provenance-Authenticated** | Running artifact identity cryptographically bound to an SLSA provenance manifest verified with a pinned asymmetric public key. | **ACTIVE (Ed25519 digital signature verified against pinned key)** |

### Formal Demarcation of QF-A3 vs QF-A4
- **QF-A3 (Formal Model)**: Theorems 1–5 in `formal/QuantumFlex_Core.fst` prove state machine legality, the absorbing quarantine sink, authentication fail-closed, and strict PQC anti-downgrade in F*.
- **QF-A4 (Extraction Gap)**: The running C implementation (`src/core/verified_core.c`) was manually implemented to match the formal specification and verified via test harness `tools/test_verified_core.cpp`. Because `fstar` and `krml` are not run in the local build pipeline, QF-A4 remains a documented engineering target, not an accomplished claim.

---

## 2. Release Provenance Architecture

```text
               Source Code & Build Flags
                         │
                         ▼
             Compiled Release Artifacts
                         │
                         ▼
        SHA-256 Digest per Target Artifact
                         │
                         ▼
            PROVENANCE_MANIFEST.json
                         │
                         ▼ (Ed25519 Sign with Private Key)
             PROVENANCE_MANIFEST.sig
                         │
                         ▼ (host ExecStartPre — outside the repo)
     ~/.local/libexec/quantumflex/verify-provenance
     + pinned release_signing_key.pub (0400)
                         │
            ┌────────────┴────────────┐
         MATCH                     MISMATCH
            │                         │
     TRUSTED (ALLOW)           QUARANTINE (FAIL-CLOSED)
```

### Manifest Standard:
1. **Single Hash Policy**: Standardizes on SHA-256 for artifact digests.
2. **Asymmetric Digital Signature**: Manifest sealed via Ed25519 signature:
   $$\sigma = \text{Sign}_{K_{\text{private}}}(M)$$
3. **Public Key Pinning**: The judge and pinned key live in the host trust
   domain (`~/.local/libexec/quantumflex/`), not beside the artifacts they
   evaluate. `release/release_signing_key.pub` is the bootstrap copy the
   installer reads once. `scripts/verify_provenance_manifest.py` only execs
   the installed judge.
   $$\text{Verify}_{K_{\text{public}}}(M, \sigma) == \text{true}$$
   An attacker who tampers with `PROVENANCE_MANIFEST.json` or any in-repo
   script cannot forge \(\sigma\) without the offline release signing key,
   and cannot replace the host judge by editing the repository.

---

## 3. Digital-DNA Framework: Static Identity ($F_0$) vs Dynamic Identity ($F_t$)

The QuantumFlex Trust Vector evaluates both pre-runtime lineage and runtime behavioral telemetry:

### Static Baseline Identity ($F_0$)
Evaluated before execution:
$$F_0 = \Phi(\text{source\_commit}, \text{compiler}, \text{flags}, \text{artifacts}, \text{sha256}, \text{ed25519\_sig}, \text{policy})$$

### Dynamic Telemetry Identity ($F_t$)
Observed at runtime:
$$F_t = \Phi(\text{state}_t, \Delta\text{state}_t, \text{lif\_anomaly}_t, \text{wire\_seq}_t, \text{reserves}_t)$$

### Invariant Divergence ($\Delta F$)
$$\Delta F = \text{Evaluate}(F_t, F_0)$$

```text
                 QUANTUMFLEX IDENTITY
                         │
             ┌───────────┴───────────┐
             │                       │
      STATIC IDENTITY ($F_0$)  DYNAMIC IDENTITY ($F_t$)
             │                       │
       source / commit            behavior
       provenance                 LIF telemetry
       Ed25519 signature          state transitions
       proof specs                wire sequence
       compiler flags             reserves vs claims
             │                       │
             └───────────┬───────────┘
                         ↓
                    CORRELATION
                         ↓
                 EXPECTED STATE?
                    /          \
                  YES           NO
                   │             │
                ACTIVE       INVESTIGATE
                                 │
                           threshold/policy
                              /       \
                           benign     threat
                             │          │
                          LEARN     QUARANTINE
```

If $F_0$ fails signature or hash verification, the engine never activates:
$$\text{Trust}(A) = 0 \implies \text{QUARANTINE}$$
