# QuantumFlex Authorized Operations Policy (AOP)

**Policy Document:** `QF-GOV-AOP-001`  
**Governance Layer:** QuantumFlex Legal & Operational Assurance Layer (QF-LOAL)  
**Standard:** QF-LEGAL-001 Authorized Operation Invariant  
**Classification:** Operational Security & Legal Compliance Policy  
**Last Reviewed:** 2026-11-01  

---

## 1. Objective & Principle of Least Privilege

This policy governs the exact operational permissions and systems accessibility granted to each device and operator in the QuantumFlex substrate.

> **Enforcement Rule:**  
> Access to any endpoint, mutation API, file transfer, or smart contract execution is denied by default. No operation executes unless explicitly declared in the device's `permitted_operations` JSON array in `qf_device_authorization`.

---

## 2. Permitted Operations Matrix

| Device ID | Role | Permitted Operational Scope (`permitted_operations`) | Prohibited Operations |
| :--- | :--- | :--- | :--- |
| **`qfx-yoga`** | Primary Host & Engine Orchestrator | `["*"]` (Full administrative, compilation, local LLM inference, smart contract dispatch, invariant gating) | Cloud LLM inference ($0.00 spend invariant), destructive unconfirmed file wipes (`rm -rf`). |
| **`qfx-pixel`** | Tactical HUD & Mobile Sentinel | `["telemetry:heartbeat", "telemetry:submit", "chat:read", "draft:approve", "mesh:status", "ota:download"]` | Direct on-chain settlement submission without Yoga confirmation, local server binding on public WAN ports. |
| **`g6pro`** | Auxiliary Compute (Standby) | `[]` (Zero operations permitted) | Any network egress, database write operations, shard custody participation. |
| **`qflex`** | Auxiliary Compute (Pending) | `[]` (Zero operations permitted until admission) | Telemetry ingestion, API access. |

---

## 3. Critical Privilege Pipeline

Every incoming mutation or sensitive data access request must traverse the seven-stage verification pipeline:

```text
REQUEST
   │
   ▼
[Stage 1: IDENTIFY DEVICE]
   │ (Extract X-QF-Device or client token)
   ▼
[Stage 2: VERIFY CRYPTOGRAPHIC IDENTITY]
   │ (Validate ECDSA P-256 signature against pinned device PEM)
   ▼
[Stage 3: CHECK AUTHORIZATION REGISTRY]
   │ (Query qf_device_authorization: status must be 'AUTHORIZED' and not expired)
   ▼
[Stage 4: CHECK PERMITTED OPERATION]
   │ (Verify requested_operation in permitted_operations)
   ▼
[Stage 5: CHECK CONSENT / LAWFUL PURPOSE]
   │ (Validate purpose against permitted_purposes; verify consent record)
   │
   ├── FAILURE ──► [DENY + LOG AUDIT EVENT]
   │
   ▼
[Stage 6: CHECK SOFTWARE PROVENANCE]
   │ (Validate binary SHA-256 matches signed release manifest)
   │
   ├── FAILURE ──► [QUARANTINE DEVICE + AUDIT]
   │
   ▼
[Stage 7: AUTHORIZE OPERATION]
   (Execute with append-only audit emission)
```

---

## 4. Prohibited Cross-Border & Third-Party Actions

1. **Zero Third-Party Intrusion:** Nodes are strictly prohibited from scanning, attacking, accessing, or authenticating against third-party endpoints or non-consensual networks.
2. **Zero Cloud Spend Invariant ($0.00):** No node may redirect LLM inference queries to commercial paid API services (OpenAI, Anthropic, Google Cloud Vertex). Inference is strictly confined to local loopback Ollama (`127.0.0.1:11434`).
3. **Fail-Closed Financial Settlement:** Mutating smart contract operations require deterministic UUID v4 idempotency derived from block hashes (`sha256(blockHash)`) and 6-decimal USDC scaling (`1_000_000n`).
