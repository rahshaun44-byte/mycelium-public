# QuantumFlex Security & Data-Governance Statement

**Institutional Assurance for Confidential Legal, Financial, and Technical Diligence**

---

## 1. Zero-Cloud Data Sovereignty
QuantumFlex processes all client documents, embeddings, and analytical synthesis exclusively on isolated local hardware.
- **No External API Egress:** Client files are never transmitted to public cloud AI providers, third-party model APIs, or external SaaS indexing services.
- **No Model Training on Client Data:** Client materials are never used to train, fine-tune, or update shared foundation models.
- **Loopback-Enforced Execution:** Local inference endpoints are programmatically restricted to loopback interfaces (`127.0.0.1`), failing closed if any external network endpoint is configured.

---

## 2. Strict Corpus Isolation & Role Governance
Every document ingested into the QuantumFlex pipeline is assigned an explicit security classification prior to indexing:
- **Client Corpus Isolation:** Each client engagement executes within a dedicated, isolated document store.
- **Boundary Enforcement:** Automated access controls prevent cross-matter retrieval and block internal operational records from entering any client-facing index or report.
- **Idempotent Purge & Retention Control:** Upon engagement completion, client indices can be archived as a deterministic snapshot for client audit recovery or cryptographically purged upon written instruction.

---

## 3. Pre-Ingestion Privacy Sanitization
Before any document page is indexed or analyzed, an automated sanitization filter scans for and redacts sensitive ambient identifiers:
- Unrotated API keys, bearer tokens, and PEM-encoded private keys (`[REDACTED_CREDENTIAL]` / `[REDACTED_PRIVATE_KEY]`).
- Social Security Numbers and personal tax identifiers (`[REDACTED_SSN]`).
- Financial routing and bank account numbers (`[REDACTED_FAMILY_FINANCIAL_ACCT]`).
- Local workstation filesystem paths.

---

## 4. Deterministic Citation & Tamper Detection
To eliminate unverified generative claims, QuantumFlex enforces a fail-closed cryptographic verification gate (`AT-RDOS-02` / `AT-RDOS-03`):
1. **Chunk-Level SHA-256 Hashing:** Every extracted document segment is hashed with `SHA-256` at intake.
2. **Mandatory Page & Chunk Binding:** Every analytical claim in a delivered dossier must reference a valid `[chunk_id:p<page>]` identifier. Uncited claims or page mismatches cause compilation to fail closed.
3. **Corpus Merkle Root:** All verified chunk digests are combined into a deterministic `SHA-256` Merkle root recorded in the accompanying JSON Admission Receipt. Modifying even a single character in a source document alters the Merkle root and is immediately detected by independent verification.
4. **Honest Assurance Reporting:** Cryptographic receipts explicitly distinguish between locally verified provenance and hardware-signed production attestations (`signed: false` when external hardware ceremony gates are not invoked).
