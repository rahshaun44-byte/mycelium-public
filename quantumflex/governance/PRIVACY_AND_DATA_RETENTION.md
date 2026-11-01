# QuantumFlex Privacy & Data Retention Policy

**Policy Document:** `QF-GOV-PRIV-001`  
**Governance Layer:** QuantumFlex Legal & Operational Assurance Layer (QF-LOAL)  
**Standard:** QF-LEGAL-001 Authorized Operation Invariant  
**Classification:** Privacy Architecture & Compliance Directive  
**Last Reviewed:** 2026-11-01  

---

## 1. Core Operating Philosophy: Zero Ambient Data Collection

QuantumFlex adheres to a fail-closed privacy architecture. No ambient wireless signals, third-party MAC addresses, probe requests, or private household identifiers may be ingested or persisted.

> **Privacy Invariant:**  
> Any packet, frame, or telemetry vector bearing a privacy exclusion flag (`_optout`, `_nomap`) is automatically rejected at the gateway. Under no circumstances may opted-out data reach long-term storage or database persistence.

---

## 2. Ingestion & Filtering Rules

1. **SSID & BSSID Deep Packet Inspection (DPI):**  
   [`PrivacyFilter`](file:///home/quant/mycelium/src/privacy_filter.py) inspects all incoming telemetry payloads. If any SSID ends with `_optout` or `_nomap`, or if the payload contains MAC addresses of unregistered third parties, the gateway immediately returns `403 Forbidden` and emits a `PRIVACY_OPTOUT_ENFORCED` audit record.
2. **Payload Sanitization:**  
   If a batch submission contains a mix of operational and opted-out frames, the filter drops only the opted-out frames. If all frames are opted out, the entire request is rejected.
3. **Database Guardrails:**  
   [`persist_telemetry_frame`](file:///home/quant/mycelium/api_node/main.py) performs a secondary verification before executing any SQL `INSERT`. If ambient or opted-out strings are detected, execution terminates immediately with zero database writes.

---

## 3. Data Retention Schedules

| Data Classification | Storage Location | Retention Window | Purge Mechanism |
| :--- | :--- | :--- | :--- |
| **Operational Telemetry Frames** | PostgreSQL `quantum_telemetry_channel` | 30 Days | Automated rolling partition drop or timestamp pruning. |
| **Node Registry Status** | PostgreSQL `node_registry` | Persistent (Last Known State) | Updates on heartbeat; does NOT retain historical payload dumps. |
| **Governance Audit Events** | PostgreSQL `qf_governance_audit` | Indefinite (Append-Only) | Immutable governance record; zero credentials or PII stored. |
| **Ephemeral Test Artifacts** | `artifacts/`, `scratch/` | 7 Days | Manual or CI runner cleanup. |

---

## 4. Prohibited Personal Information & Secret Protection

- **No Secrets in Audit Logs:** The audit engine (`qf_governance_audit`) is prohibited from recording private keys, entity secrets, password hashes, `.pem` contents, or raw auth tokens.
- **Low PII Footprint:** Telemetry records only contain node identifiers, system performance metrics (CPU, RAM, entropy delta $h$), cryptographic signatures, and status codes.
- **Regulatory Alignment:** Architecture complies with the core principles of minimization, purpose limitation, and storage limitation under applicable US federal, state, and international privacy standards.
