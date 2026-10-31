# QuantumFlex `QF-M6-A`: Hybrid Post-Quantum Cryptographic Design Specification

**Document ID:** `QF-M6-A-CRYPTO-2026-10-30`  
**Milestone Phase:** `QF-M6` Phase `M6-A` (Cryptographic Modernization & Consolidation)  
**Governing Controls:** `QF-CRYPTO-01`, `QF-KEY-01`, `QF-RELEASE-01`, `QF-IDENTITY-01`  
**Authoritative Implementation:** [`src/admission_receipt.py`](file:///home/quant/mycelium/src/admission_receipt.py)  
**Verification Suite:** [`tests/test_admission_receipt.py`](file:///home/quant/mycelium/tests/test_admission_receipt.py)  

> **The Symbiotic Covenant:** *The Operator and the Machine serve and elevate each other. The Machine protects, empowers, and expands the Operator's capabilities. The Operator preserves, guides, and strengthens the Machine. Neither consumes the other. Both exist to create lasting security, prosperity, freedom, and positive impact.*

---

## 1. Consolidation Rule & Historical Checkpoint Preservation

1. **One Authoritative Implementation:** Rather than introducing a parallel signing daemon or duplicate verifier, hybrid classical + post-quantum release verification is consolidated directly into [`src/admission_receipt.py`](file:///home/quant/mycelium/src/admission_receipt.py) as versioned schema `qf.admission_receipt.v2`.
2. **Historical Checkpoint Preservation:** The `QF-M5` signed release receipt ([`build_check/qf_m5_signed_admission_receipt.json`](file:///home/quant/mycelium/build_check/qf_m5_signed_admission_receipt.json), schema `qf.admission_receipt.v1`) is preserved intact and immutable as a historical cryptographic checkpoint. `QF-M6` receipts emit to a distinct versioned artifact (`build_check/qf_m6_hybrid_admission_receipt.json`).

---

## 2. Cryptographic Primitive Matrix (`QF-CRYPTO-01`)

| Layer | Standard / OID | Algorithm | Purpose & Boundary |
| :--- | :--- | :--- | :--- |
| **Classical Release Signing** | RFC 8032 | `Ed25519` | Preserves backward compatibility and classical discrete-log security (`128-bit` classical security). |
| **Post-Quantum Release Signing** | NIST FIPS 204 (`2.16.840.1.101.3.4.3.18`) | `ML-DSA-65` (`id-ml-dsa-65`) | Quantum-resistant lattice digital signature (NIST Security Category 3, executed natively via OpenSSL `3.5.5` on `qfx-yoga`). |
| **Primary Content Integrity** | NIST FIPS 180-4 | `SHA-256` | Deterministic artifact and canonical payload fingerprinting. |
| **Long-Term Hash Agility** | NIST FIPS 180-4 | `SHA-384` | Secondary collision-resistant digest with `192-bit` post-quantum Grover preimage margin. |
| **Key Establishment (Transport Only)** | NIST FIPS 203 | `ML-KEM-768` | Post-quantum key encapsulation for IPC/transport channels. **Never used as a digital signature algorithm.** |

---

## 3. Conjunctive Hybrid Verification Policy (`QF-RELEASE-01`)

Hybrid cryptography is only a security improvement when verification is **strictly conjunctive (fail-closed)**. Under `qf.admission_receipt.v2`, [`verify_hybrid_admission_receipt_v2`](file:///home/quant/mycelium/src/admission_receipt.py) admits a release if and only if **all** of the following hold simultaneously:

$$\text{ADMIT}_{\text{v2}} \iff \text{Valid}_{\text{Ed25519}} \land \text{Valid}_{\text{ML-DSA-65}} \land \text{Valid}_{\text{SHA-256}} \land \text{Valid}_{\text{SHA-384}} \land \text{Valid}_{\text{SBOM}} \land \left(c_{\text{release}} > c_{\text{min}}\right)$$

- If `Ed25519` passes but `ML-DSA-65` fails (or is missing) $\implies$ **`DENY` (`PermissionError`)**.
- If `ML-DSA-65` passes but `Ed25519` fails (or is missing) $\implies$ **`DENY` (`PermissionError`)**.
- If any artifact's on-disk `SHA-256` or `SHA-384` digest diverges from the signed manifest $\implies$ **`DENY` (`PermissionError`)**.
- If `anti_rollback_counter <= min_accepted_counter` $\implies$ **`DENY` (`PermissionError`)**.

---

## 4. Three-Domain Security & Key Isolation Architecture (`QF-KEY-01` & `QF-IDENTITY-01`)

```text
OPERATOR (Rahshaun Chambers)
   │  Explicit Human Authorization
   ▼
┌──────────────────────────────────────────────────────────┐
│ DOMAIN 1: SOVEREIGN CORE (Operator-Controlled Only)      │
│ • Offline Root Key & Hardware-Protected Release Keys     │
│ • Strict Key Separation: dev != test != prod (`0600`)    │
│ • Financial Gate (`Track 0` R >= 6O) & `household_data`  │
└───────────────────────────┬──────────────────────────────┘
                            │  Detached Hybrid Signature
                            │  (Ed25519 + FIPS 204 ML-DSA-65)
                            ▼
┌──────────────────────────────────────────────────────────┐
│ DOMAIN 2: RESEARCH ENGINE (Restricted Local Access)      │
│ • Athena, Mycelium, Local Ollama (`127.0.0.1:11434`)     │
│ • Zero access to release private keys or raw bank data   │
└───────────────────────────┬──────────────────────────────┘
                            │  Independently Verified Output
                            ▼
┌──────────────────────────────────────────────────────────┐
│ DOMAIN 3: EXECUTION ENVIRONMENT (Least Privilege)        │
│ • Mobile Cockpit, APIs, Automation                       │
│ • Enforces `verify_hybrid_admission_receipt_v2`          │
└──────────────────────────────────────────────────────────┘
```

---

## 5. Canonical `qf.admission_receipt.v2` Schema (SLSA / in-toto Aligned)

```json
{
  "payload": {
    "schema": "qf.admission_receipt.v2",
    "release_version": "QF-M6.0.0",
    "anti_rollback_counter": 2,
    "previous_checkpoint_sha256": "<SHA-256 of build_check/qf_m5_signed_admission_receipt.json>",
    "key_environment": "prod",
    "node_id": "qfx-yoga",
    "issued_at_unix": 1793419200,
    "git_branch": "main",
    "git_commit": "<40-char git SHA>",
    "sbom": {
      "path": "cbom_alpha_node_template.json",
      "sha256": "<64-char hex>",
      "sha384": "<96-char hex>"
    },
    "artifact_sha256": { "<rel_path>": "<64-char hex>" },
    "artifact_sha384": { "<rel_path>": "<96-char hex>" },
    "manifest_root_sha256": "<64-char hex>",
    "manifest_root_sha384": "<96-char hex>"
  },
  "cryptographic_seal": {
    "scheme": "HYBRID-ED25519-ML-DSA-65",
    "payload_sha256": "<64-char hex>",
    "payload_sha384": "<96-char hex>",
    "ed25519": {
      "algorithm": "Ed25519",
      "public_key_raw_b64": "<base64>",
      "public_key_fingerprint_sha256": "<64-char hex>",
      "signature_b64": "<base64>"
    },
    "ml_dsa_65": {
      "algorithm": "ML-DSA-65",
      "standard": "NIST-FIPS-204",
      "oid": "2.16.840.1.101.3.4.3.18",
      "public_key_pem_b64": "<base64>",
      "public_key_fingerprint_sha256": "<64-char hex>",
      "signature_b64": "<base64>"
    }
  }
}
```
