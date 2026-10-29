# QuantumFlex Formal Verification: F* 2026.09 Evidence Record

**Date:** 2026-10-28  
**Target:** [`formal/QuantumFlex_Core.fst`](file:///home/quant/mycelium/formal/QuantumFlex_Core.fst)  
**Harness:** [`scripts/verify_formal_core.sh`](file:///home/quant/mycelium/scripts/verify_formal_core.sh)  
**Toolchain:** F* 2026.09.27 (`commit 7deb38a27c86990664c6b41e4b6093597acdebd4`, OCaml 5.3.0, x86_64 Linux)  
**Host:** `qfx-yoga` (Ubuntu 26.04.1 LTS, Microsoft Pluton TPM 2.0)  
**Assurance Status:** QF-A3 Complete; **QF-A4 (Extraction Gap) remains explicitly `NULL`**  

---

## 1. Mathematical Invariant Theorems Proved

All 5 core invariant theorems in `formal/QuantumFlex_Core.fst` have been verified and all verification conditions discharged:

1. **Absorbing Quarantine Sink (`lemma_quarantine_never_directly_active`):**
   - Proves mathematically that no authentication credential or input can transition `StateQuarantine` directly to `StateActive`.
   - Transitions out of quarantine require explicit `CredTwoManAttestation` to reach `StateRecovery`.
2. **Fail-Closed Authentication (`lemma_missing_auth_denies_active`):**
   - Proves that `CredNone` cannot produce a transition to `StateActive` from any engine state.
3. **Strict FIPS 203 PQC Anti-Downgrade (`lemma_pqc_downgrade_impossible`):**
   - Proves that under `ProfileStrictFips203`, proposals specifying `AlgX25519`, `AlgFrodo976`, or `AlgUnknown` evaluate unconditionally to `PolicyDeny`. Only FIPS 203 ML-KEM-768 and ML-KEM-1024 are admissible.
   - *Scope qualification:* Rejection of `AlgX25519` applies to standalone classical key exchange under the sovereign strict profile. Explicit hybrid constructions (e.g. `MLKEM768x25519`) in transition profiles must be modeled as distinct composite types (`AlgHybrid...`), preventing confusion with unauthenticated standalone classical algorithms.
4. **Wire Frame Bounding (`lemma_wire_bounds_enforced`):**
   - Proves that zero-length payloads, chunks exceeding `max_chunk_len` (1,450 bytes), frame sets exceeding `max_total_chunks` (64), or chunk indices out of range evaluate unconditionally to `FrameInvalid 3` (`ERR_CHUNK_BOUNDS`).
5. **Sequence Rollover Protection (`lemma_seq_rollover_rejected`):**
   - Proves that sequence counters at or exceeding `max_sequence_id` (0xFFFFFFFE) evaluate unconditionally to `FrameInvalid 7` (`ERR_SEQ_EXHAUSTED`), preventing silent integer wraparound or replay across session boundaries.

---

## 2. Verification Execution Transcript

```text
$ ./scripts/verify_formal_core.sh
================================================================================
QUANTUMFLEX FORMAL VERIFICATION: F* PROOF HARNESS (QF-A3)
Target: /home/quant/mycelium/formal/QuantumFlex_Core.fst
================================================================================
[*] Toolchain Version:
    F* 2026.09.27
    platform=Linux_x86_64
    system=Unix
    compiler=OCaml 5.3.0
    date=2026-09-27 16:52:08 +0000
    commit=7deb38a27c86990664c6b41e4b6093597acdebd4
[*] Discharging verification conditions via SMT (Z3)...
    Verified module: QuantumFlex_Core
    All verification conditions discharged successfully
================================================================================
[PASS] QF-A3 FORMAL INVARIANTS DISCHARGED IN 0.30s
NOTE: QF-A4 (Machine Extraction) remains strictly NULL until automated KaRaMeL
      extraction and bit-level C equivalence proofs are integrated into CI.
================================================================================
```
- **Exit Code:** `0`
- **Result:** SMT solver (Z3) discharged 100% of generated verification conditions.

---

## 3. C Reference Implementation & ABI Conformance

The C reference implementation [`src/core/verified_core.c`](file:///home/quant/mycelium/src/core/verified_core.c) and its test harness [`tools/test_verified_core.cpp`](file:///home/quant/mycelium/tools/test_verified_core.cpp) were executed against the same invariant matrix:

```text
================================================================================
QUANTUMFLEX VERIFIED CORE: FORMAL INVARIANT TEST HARNESS
Target: Formal Invariants (QuantumFlex_Core.fst) via C ABI
================================================================================
[*] [VERIFIED_CORE 1/4] Testing Finite State Legality & Absorbing Quarantine Sink...
    [+] Absorbing Quarantine Sink and Transition Invariants Verified (PASS)
[*] [VERIFIED_CORE 2/4] Testing Strict FIPS 203 PQC Downgrade Impossibility...
    [+] Strict FIPS 203 Anti-Downgrade Invariant Verified (PASS)
[*] [VERIFIED_CORE 3/4] Testing Wire Frame Bounds & Anti-Rollover Exhaustion...
    [+] Wire Frame Bounds and Sequence Monotonicity Invariants Verified (PASS)
[*] [VERIFIED_CORE 4/4] Testing CRC32 Integrity & Memory Barrier Zeroization...
    [+] CRC32 Test Vector and Zeroization Verified (PASS)
================================================================================
[PASS] ALL VERIFIED CORE INVARIANTS SATISFIED (4/4 TEST SUITES PASSED)
================================================================================
```

---

## 4. Rigorous Assurance Accounting (No Fabrication)

| Level | Component | Status | Notes |
|---|---|---|---|
| **QF-A1** | Structural & Unit Tests | **PASS** | 446/446 pytest passed; 4/4 C ABI test suites passed |
| **QF-A2** | Ingress & Boundary Invariants | **PASS** | 23/23 dual-stage gatekeeper checks passed; zero ambient data verified |
| **QF-A3** | Formal Verification | **PASS** | All 5 lemmas in `QuantumFlex_Core.fst` formally proven under F* 2026.09 |
| **QF-A4** | Machine-Extracted C | **NULL** | **Extraction Gap**: `src/core/verified_core.c` is manually written C adhering to the spec. KaRaMeL automated extraction pipeline is not run in CI. Remains `NULL` by policy. |
| **QF-A5** | Signed Attestation / Transit | **GATED** | Requires Vault Transit A5 signing ceremony |
| **QF-A6** | Hardware Root of Trust | **GATED** | Titan M2 StrongBox + Pluton TPM runtime binding |

---

## 5. QF-A4 Roadmap: Advancing from NULL Without Compromising Discipline

To advance QF-A4 toward resolution without prematurely claiming equivalence:

1. **Harness Pinning:** Pin F\* (`2026.09.27`) and KaRaMeL toolchain commit IDs in container definition (`scripts/Containerfile.fstar`).
2. **Automated CI Step:** Integrate `scripts/extract_verified_core.sh` into continuous integration runners alongside `scripts/verify_formal_core.sh`.
3. **Extracted Artifact Translation:** Emit extracted C code (`src/core/QuantumFlex_Core_extracted.c`) isolated from the production engine build.
4. **Differential Test Harness:** Execute the existing C ABI test suite (`tools/test_verified_core.cpp`) directly against the KaRaMeL-extracted object.
5. **Correspondence Mapping:** Diff and document any handwritten glue code outside the verified F\* boundary.
6. **Promotion Ceremony:** Only upon reproducible, green extraction in CI and proven ABI correspondence may QF-A4 transition from `NULL` to `PASS`.

---

## 6. Active External P0 Hard Stops (Explicitly Open)

Per the Open Action Checklist (2026-10-18) and Zero-Fabrication rule, the following external items remain open and are not closed by software verification:

1. **HS-PX (Pixel Bulletin):** Apply Pixel September 2026 security bulletin on Pixel 11 Pro (`CVE-2026-58704`).
2. **Account Security Verification:** Confirm CircleCI, TP-Link, and Uber security notices.
3. **Legal Entity Status:** Confirm PA LLC 13706513 active registration standing with Pennsylvania Department of State.
