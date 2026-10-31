# QF-M6-B — Key Sovereignty & Two-Tier Cryptographic Hierarchy (`QF-KEY-01`)

**Control ID:** `QF-KEY-01`  
**Phase:** `M6-B` (Unblocked by `M6-A` Cryptographic Modernization)  
**Authoritative Implementation:** [`src/admission_receipt.py`](file:///home/quant/mycelium/src/admission_receipt.py)  
**Test Suite:** [`tests/test_admission_receipt.py`](file:///home/quant/mycelium/tests/test_admission_receipt.py)

---

## 1. Governing Principle

In accordance with the **Consolidation Principle** (*"One capability, one authoritative implementation, one verification path, one accountable owner"*), `QF-M6-B` implements **Key Sovereignty (`QF-KEY-01`)** directly inside [`src/admission_receipt.py`](file:///home/quant/mycelium/src/admission_receipt.py) without introducing external PKI daemons or network dependencies.

---

## 2. Two-Tier Sovereign Key Hierarchy

```
┌───────────────────────────────────────────────────────────────────────────┐
│ Tier 0: Offline Root of Trust (Cold Storage / Offline Ceremony Only)      │
│   • Hybrid Classical + Post-Quantum Root Keypair:                         │
│     - Ed25519 Root Key + NIST FIPS 204 ML-DSA-65 Root Key                 │
│   • Never used for daily development or automated builds                  │
│   • Sole authority to issue:                                              │
│     1. Key Delegation Certificates (`qf.key_delegation_cert.v1`)          │
│     2. Key Revocation Lists (`qf.key_revocation_list.v1`)                 │
└─────────────────────────────────────┬─────────────────────────────────────┘
                                      │ Conjunctive Root Seal
                                      │ (Ed25519_Root ∧ ML-DSA-65_Root)
                                      ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ Tier 1: Environment-Scoped Release Signing Keys (`dev` | `test` | `prod`) │
│   • Bound by Root Delegation Certificate to ONE environment (`prod` etc.) │
│   • Hybrid Classical + Post-Quantum Release Keypair:                      │
│     - Ed25519 Release Key + NIST FIPS 204 ML-DSA-65 Release Key           │
│   • Enforces 0600 file permissions and explicit human operator ceremony   │
└───────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Strict Environment Separation (`dev` / `test` / `prod`)

Every delegated release keypair is cryptographically bound to a single `key_environment` in its Root-signed delegation certificate (`qf.key_delegation_cert.v1`):

- **`dev`**: Local development experiments; rejected by `prod` release verification.
- **`test`**: Automated CI and adversarial test suites; rejected by `prod` release verification.
- **`prod`**: Sovereign release ceremony only (`I_AUTHORIZE_QF_A5_SIGNING`); requires offline Root delegation for `"prod"`.

---

## 4. Schemas & Conjunctive Verification Equations

### 4.1 Key Delegation Certificate (`qf.key_delegation_cert.v1`)

Issued by the Tier 0 Offline Root to authorize a Tier 1 Release Signing Keypair for a specific environment and validity window $[t_{\text{not\_before}}, t_{\text{not\_after}}]$:

- `schema`: `"qf.key_delegation_cert.v1"`
- `cert_id`: Unique certificate identifier (e.g., `"QF-CERT-PROD-2026-001"`)
- `key_environment`: `"dev" | "test" | "prod"`
- `not_before_unix` / `not_after_unix`: Validity window bound against the release receipt's `issued_at_unix`
- `delegated_ed25519_public_key_raw_b64` & `delegated_ed25519_fingerprint_sha256`
- `delegated_mldsa65_public_key_pem_b64` & `delegated_mldsa65_fingerprint_sha256`
- `root_cryptographic_seal`: Conjunctive `Ed25519` + `ML-DSA-65` signatures by the Offline Root of Trust.

### 4.2 Key Revocation List (`qf.key_revocation_list.v1`)

Issued by the Tier 0 Offline Root to revoke retired or compromised release keys or delegation certificates:

- `schema`: `"qf.key_revocation_list.v1"`
- `krl_sequence`: Strictly increasing monotonic sequence number ($s_{\text{krl}} \ge s_{\text{min}}$) to prevent stale KRL replay
- `issued_at_unix`: KRL issuance timestamp
- `revoked_cert_ids`: List of revoked `cert_id` strings
- `revoked_ed25519_fingerprints_sha256`: List of revoked Ed25519 public key SHA-256 fingerprints
- `revoked_mldsa65_fingerprints_sha256`: List of revoked ML-DSA-65 public key SHA-256 fingerprints
- `root_cryptographic_seal`: Conjunctive `Ed25519` + `ML-DSA-65` signatures by the Offline Root of Trust.

### 4.3 Sovereign Chain Verification Invariant

When verifying a release under `QF-KEY-01`:

$$\text{Valid}_{\text{Chain}} \iff \text{Valid}_{\text{RootSeal}}(\text{Cert}) \land \text{Valid}_{\text{RootSeal}}(\text{KRL}) \land (\text{Env}_{\text{Cert}} = \text{Env}_{\text{Receipt}} = \text{Env}_{\text{Expected}}) \land (t_{\text{not\_before}} \le t_{\text{receipt}} \le t_{\text{not\_after}}) \land (\text{Key}_{\text{Receipt}} \notin \text{KRL})$$

If any condition fails, [`verify_key_sovereignty_chain`](file:///home/quant/mycelium/src/admission_receipt.py) and [`verify_hybrid_admission_receipt_v2`](file:///home/quant/mycelium/src/admission_receipt.py) raise `PermissionError` immediately (fail-closed).
