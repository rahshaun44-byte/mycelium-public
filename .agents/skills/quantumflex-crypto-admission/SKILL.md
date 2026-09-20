---
name: quantumflex-crypto-admission
description: >-
  Cryptographic admission, provenance verification (QF-A4/A5/A6), signing ceremonies,
  and fail-closed integrity gates in the QuantumFlex sovereign operating system.
---

# QuantumFlex Cryptographic Admission & Provenance Playbook

This skill provides procedures for verifying and maintaining the three-tiered admission and provenance system in QuantumFlex.

---

## 1. The Three Admission Planes

1. **QF-A4 (Byte Hash Integrity):**
   - SHA-256 digest verification of all release artifacts against `release/PROVENANCE_MANIFEST.json`.
2. **QF-A5 (Ed25519 Detached Provenance):**
   - Cryptographic signature verification of the manifest against the pinned external trust anchor (`~/.local/libexec/quantumflex/release_signing_key.pub`).
   - Evaluated by the external host judge: `~/.local/libexec/quantumflex/verify-provenance`.
3. **QF-A6 (Runtime `fexecve` Descriptor Binding):**
   - Prevents Time-of-Check to Time-of-Use (TOCTOU) substitution attacks by binding open file descriptors (`EXECUTED_FD == VERIFIED_FD`).

---

## 2. Verification Commands

### Host Provenance Pre-Flight:
```bash
~/.local/libexec/quantumflex/verify-provenance /home/quant/mycelium
```
*Expected Output:* `VERDICT: TRUSTED -> ALLOW (QF-A5 Provenance-Authenticated verified)`

### 7-Case Admission Integrity Matrix:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/test_quantumflex_admission.py
```

### 10-Case Runtime Binding Adversarial Matrix:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/test_quantumflex_runtime_admission.py
```

### Signing Ceremony Invariant Tests:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/test_signing_ceremony.py
```

---

## 3. Re-Signing & Admission Export

When building a new attested release of the C++ engine or runtime:
1. Generate the updated canonical provenance manifest:
   ```bash
   python3 scripts/generate_provenance_manifest.py
   ```
2. Sign the admission receipt:
   ```bash
   python3 scripts/sign_quantumflex_admission.py --receipt build_check/QuantumFlexAdmission.json --key <signing_key>
   ```
3. Sign the runtime binding:
   ```bash
   python3 scripts/sign_quantumflex_runtime.py --binding build_check/QuantumFlexRuntimeBinding.json --key <signing_key>
   ```
