# QuantumFlex Software Provenance Policy (SPP)

**Policy Document:** `QF-GOV-SPP-001`  
**Governance Layer:** QuantumFlex Legal & Operational Assurance Layer (QF-LOAL)  
**Standard:** QF-LEGAL-001 Authorized Operation Invariant  
**Classification:** Software Supply Chain Integrity & Cryptographic Provenance  
**Last Reviewed:** 2026-11-01  

---

## 1. Supply Chain Architecture & Admission Gates

QuantumFlex enforces three continuous cryptographic admission gates (QF-A4, QF-A5, QF-A6) to ensure that no unverified or tampered binary or script can execute on any substrate node.

```text
[SOURCE / COMPILATION] ──► [QF-A4: Package Admission]
                                    │ (Deterministic Tarball & Hash Match)
                                    ▼
                           [QF-A5: Provenance Ceremony]
                                    │ (Ed25519 Authority Signature & Manifest)
                                    ▼
                           [QF-A6: TOCTOU-Immune Runtime Pinning]
                                    │ (Pluton TPM / OOB Titan-M3 Attestation)
                                    ▼
                           [EXECUTION ADMISSION]
```

---

## 2. Gate Verification Requirements

1. **QF-A4 Package Admission:**  
   Every distributed release or update package must match the cryptographic SHA-256 registered in the signed `QuantumFlexAdmission.dev.json` receipt.
2. **QF-A5 Provenance Signing:**  
   Manifests (`PROVENANCE_MANIFEST.json`) must be cryptographically signed by the official offline release signing key (`release_signing_key.pub`). Signature verification uses standard Ed25519 public key cryptography.
3. **QF-A6 Runtime Pinning (TOCTOU-Immune):**  
   Binaries are pinned via Linux file descriptor pinning (`qf-runtime-admit`), guaranteeing that the file descriptor opened and cryptographically attested is the exact descriptor executed (`EXECUTED_FD == VERIFIED_FD`).

---

## 3. Mobile OTA Distribution Verification

For mobile assets (`qflex_cli.py`, `setup-mobile.sh`, and `qf-cockpit.apk`):
1. **Manifest Integrity:** Every artifact has a corresponding `<artifact>.manifest.json` and Ed25519 signature `<artifact>.sig`.
2. **Source Checksum Verification:** Endpoints serving mobile artifacts must emit headers including `X-QuantumFlex-SHA256` and `ETag`. Downstream clients (Termux CLI or Cockpit Webview) must verify byte hashes prior to staging or execution.
3. **Quarantine On Mismatch:** If an artifact's runtime hash fails to match the manifest hash or if the signature is invalid, the artifact is immediately placed into quarantine and a `HARDWARE_ATTESTATION_FAILED` or `SOFTWARE_PROVENANCE_MISMATCH` audit event is emitted.
