# QF-M6-C — Supply-Chain Integrity & Conjunctive Release Provenance (`QF-RELEASE-01`)

**Control ID:** `QF-RELEASE-01`  
**Phase:** `M6-C` (Unblocked by `M6-A` Cryptographic Modernization & `M6-B` Key Sovereignty)  
**Historical Infrastructure Baseline Preserved:** `8131899` ([`build_check/qf_m5_signed_admission_receipt.json`](file:///home/quant/mycelium/build_check/qf_m5_signed_admission_receipt.json))  
**Authoritative Implementation:** [`src/admission_receipt.py`](file:///home/quant/mycelium/src/admission_receipt.py)  
**Adversarial Test Suite:** [`tests/test_admission_receipt.py`](file:///home/quant/mycelium/tests/test_admission_receipt.py)

---

## 1. Governing Principle & Scope

In strict adherence to the **Consolidation Principle**:

> *"Strengthen the existing system. Do not expand its infrastructure footprint without operational necessity. One capability, one authoritative implementation, one verification path, one accountable owner."*

`QF-M6-C` (`QF-RELEASE-01`) consolidates **Reproducible Build Verification**, **SLSA v1.0 / in-toto v1 Provenance Attestations**, and **Signed CycloneDX 1.6 SBOM + CBOM Inventories** directly into [`src/admission_receipt.py`](file:///home/quant/mycelium/src/admission_receipt.py) without external build servers, container registries, or network daemons.

---

## 2. Four Acceptance Gates & Evidence Schemas

### Gate 1: Independent Reproducible Build Verification

Function: [`verify_reproducible_build_artifacts`](file:///home/quant/mycelium/src/admission_receipt.py)

Given a primary source/build tree $R_{\text{primary}}$ and an independent clean-room rebuild tree $R_{\text{rebuild}}$ over the required release artifacts $\mathcal{A}$:

$$\forall a \in \mathcal{A}: \quad \text{SHA256}(R_{\text{primary}}[a]) = \text{SHA256}(R_{\text{rebuild}}[a]) \;\land\; \text{SHA384}(R_{\text{primary}}[a]) = \text{SHA384}(R_{\text{rebuild}}[a])$$

Any missing file, extra byte, or digest divergence between the primary build and independent rebuild raises `PermissionError` (`[QF-RELEASE-01] Reproducible build verification FAILED`).

---

### Gate 2: Signed CycloneDX 1.6 SBOM & CBOM Inventories

Functions: [`build_signed_cyclonedx_16_inventories`](file:///home/quant/mycelium/src/admission_receipt.py), [`verify_signed_cyclonedx_16_inventory`](file:///home/quant/mycelium/src/admission_receipt.py)

Both the **Software Bill of Materials (SBOM)** and **Cryptographic Bill of Materials (CBOM)** are generated as deterministic CycloneDX 1.6 JSON documents (`bomFormat: "CycloneDX"`, `specVersion: "1.6"`), bound to the release `manifest_root_sha256` and `manifest_root_sha384`, and wrapped in a hybrid `Ed25519 + NIST FIPS 204 ML-DSA-65` cryptographic seal (`qf.cyclonedx_envelope.v1`):

- **SBOM (`inventory_type: "SBOM"`):** Enumerates every release artifact component in `components[]` with dual `SHA-256` and `SHA-384` hashes and binds `metadata.component` to `release_version`, `git_commit`, and `manifest_root_sha256` / `manifest_root_sha384`.
- **CBOM (`inventory_type: "CBOM"`):** Enumerates all active cryptographic primitives in `components[]` (`type: "cryptographic-asset"`):
  - `Ed25519` (RFC 8032 classical signature)
  - `ML-DSA-65` (NIST FIPS 204, OID `2.16.840.1.101.3.4.3.18` post-quantum signature)
  - `ML-KEM-768` (NIST FIPS 203 post-quantum key establishment)
  - `SHA-256` & `SHA-384` (NIST FIPS 180-4 dual hash agility)
- **Dual Binding in `qf.admission_receipt.v2`:** The admission payload binds both `sbom` (`path`, `sha256`, `sha384`) and `cbom` (`path`, `sha256`, `sha384`).

---

### Gate 3: SLSA v1.0 / in-toto v1 Provenance Attestation

Functions: [`build_signed_slsa_provenance_v1`](file:///home/quant/mycelium/src/admission_receipt.py), [`verify_signed_slsa_provenance_v1`](file:///home/quant/mycelium/src/admission_receipt.py)

Produces a hybrid-signed (`Ed25519 + ML-DSA-65`) envelope (`qf.slsa_provenance_envelope.v1`) over a canonical in-toto v1 Statement:

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    {
      "name": "<artifact_rel_path>",
      "digest": {
        "sha256": "<hex>",
        "sha384": "<hex>"
      }
    }
  ],
  "predicateType": "https://slsa.dev/provenance/v1",
  "predicate": {
    "buildDefinition": {
      "buildType": "https://quantumflex.internal/slsa/reproducible-local-build/v1",
      "externalParameters": {
        "release_version": "QF-M6.0.0",
        "git_commit": "<40-hex-sha>",
        "git_branch": "<branch>",
        "key_environment": "prod",
        "anti_rollback_counter": 2,
        "reproducible_build_verified": true
      },
      "internalParameters": {
        "node_id": "qfx-yoga",
        "historical_m5_baseline_commit": "8131899"
      },
      "resolvedDependencies": [
        {
          "uri": "file://sbom",
          "digest": { "sha256": "<sbom_sha256>", "sha384": "<sbom_sha384>" }
        },
        {
          "uri": "file://cbom",
          "digest": { "sha256": "<cbom_sha256>", "sha384": "<cbom_sha384>" }
        }
      ]
    },
    "runDetails": {
      "builder": {
        "id": "urn:quantumflex:builder:qfx-yoga:sovereign-core"
      }
    }
  }
}
```

---

### Gate 4: Conjunctive Admission Enforcement (`M6-A` $\land$ `M6-B` $\land$ `M6-C`)

When `enforce_supply_chain_integrity=True` (or when any `M6-C` supply-chain evidence is supplied to [`verify_hybrid_admission_receipt_v2`](file:///home/quant/mycelium/src/admission_receipt.py)):

$$\text{Valid}_{\text{M6-C}} \iff \text{Valid}_{\text{M6-A}} \land \text{Valid}_{\text{M6-B}} \land \text{Valid}_{\text{ReproBuild}} \land \text{Valid}_{\text{SBOM}} \land \text{Valid}_{\text{CBOM}} \land \text{Valid}_{\text{SLSA}}$$

---

## 3. Adversarial Test Matrix (Design Before Implementation)

| Vector ID | Adversarial Scenario | Expected Fail-Closed Outcome |
| :--- | :--- | :--- |
| **`TV-M6C-01`** | Nominal full chain (`M6-A` Hybrid Seal + `M6-B` Root Delegation/KRL + `M6-C` Repro Build + Signed SBOM/CBOM + Signed SLSA v1.0 Provenance) | `True` (Admitted) |
| **`TV-M6C-02`** | Unexplained 1-byte difference between primary artifact and independent rebuild tree | `PermissionError` (`Reproducible build verification FAILED`) |
| **`TV-M6C-03`** | Missing SLSA provenance, missing signed SBOM, or missing signed CBOM when `enforce_supply_chain_integrity=True` | `PermissionError` (`Incomplete supply-chain evidence`) |
| **`TV-M6C-04`** | In-toto subject digest substitution (provenance subject `sha256` or `sha384` differs from release receipt artifact map) | `PermissionError` (`SLSA subject digest mismatch`) |
| **`TV-M6C-05`** | Provenance commit/version replay (validly signed SLSA provenance from an older commit or lower `anti_rollback_counter` replayed against a new receipt) | `PermissionError` (`SLSA provenance parameter mismatch`) |
| **`TV-M6C-06`** | Tampered `ML-DSA-65` post-quantum signature on SLSA provenance envelope (while `Ed25519` remains valid) | `PermissionError` (`ML-DSA-65 signature verification FAILED`) |
| **`TV-M6C-07`** | CycloneDX 1.6 SBOM or CBOM component hash substitution or manifest root mismatch | `PermissionError` (`CycloneDX inventory manifest_root_sha256 mismatch`) |
| **`TV-M6C-08`** | Tampered `Ed25519` or `ML-DSA-65` signature on signed CycloneDX SBOM/CBOM envelope | `PermissionError` (`signature verification FAILED`) |
| **`TV-M6C-09`** | Evidence cross-binding failure (individually authentic documents referring to mismatched releases or resolvedDependencies digest divergence) | `PermissionError` (`[QF-RELEASE-01] Evidence cross-binding mismatch`) |
| **`TV-M6C-10`** | Untrusted builder identity (SLSA provenance builder ID does not match authorized builder allowlist) | `PermissionError` (`[QF-RELEASE-01] Untrusted builder identity`) |

