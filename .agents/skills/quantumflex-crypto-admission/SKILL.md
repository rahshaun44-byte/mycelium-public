---
name: quantumflex-crypto-admission
description: >-
  Cryptographic admission, provenance verification (QF-A4/A5/A6), signing ceremonies,
  CBOM generation, Vault Transit A5 signer, and fail-closed integrity gates.
---

# QuantumFlex Cryptographic Admission & Provenance Playbook

This skill provides procedures for verifying and maintaining the three-tiered cryptographic admission, CBOM generation, and provenance system in QuantumFlex.

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

## 2. Verification Commands & Test Matrices

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

### Cryptographic Bill of Materials (CBOM) Generation:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/generate_cbom.py
```

---

## 3. Re-Signing & Admission Export Workflow

When creating a new attested release of the C++ engine or runtime:

1. **Generate Canonical Provenance Manifest:**
   ```bash
   python3 scripts/generate_provenance_manifest.py
   ```
2. **Sign the Admission Receipt:**
   ```bash
   python3 scripts/sign_quantumflex_admission.py --receipt build_check/QuantumFlexAdmission.json --key <signing_key>
   ```
3. **Sign the Runtime Binding:**
   ```bash
   python3 scripts/sign_quantumflex_runtime.py --binding build_check/QuantumFlexRuntimeBinding.json --key <signing_key>
   ```

---

## 4. Post-Quantum Cryptography & Immune Daemon

The PQC immune daemon (`pqc-immune-daemon/immune_daemon.py`) monitors algorithm health:
- Periodically snapshots the active PQC algorithm to an OPA policy engine (`sentinel/policies/membrane_health.rego`).
- If OPA evaluates the algorithm as `TOXIC`, atomically rewrites `crypto_provider.conf` and signals running workers to renegotiate with fallback algorithms.
- **Fail-Closed Principle:** If OPA is unreachable, the algorithm is immediately treated as toxic.
