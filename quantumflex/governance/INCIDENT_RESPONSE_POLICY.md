# QuantumFlex Incident Response & Revocation Policy (IRP)

**Policy Document:** `QF-GOV-IRP-001`  
**Governance Layer:** QuantumFlex Legal & Operational Assurance Layer (QF-LOAL)  
**Standard:** QF-LEGAL-001 Authorized Operation Invariant  
**Classification:** Incident Response, Forensic Preservation & Revocation  
**Last Reviewed:** 2026-11-01  

---

## 1. Incident Classification Framework

QuantumFlex defines four severity tiers for operational or security incidents:

| Severity Level | Definition | Example Triggers | Immediate Containment Action |
| :--- | :--- | :--- | :--- |
| **SEV-1 (Critical)** | Hardware compromise, physical device theft, private key exposure, or invariant breach. | Lost Pixel 11 Pro, exposed `.secret` file, unauthorized mutating API request. | Immediate revocation of device in `qf_device_authorization`, circuit breaker tripped (`/hardstop`), emergency quorum rotation. |
| **SEV-2 (High)** | Software provenance failure, OPA policy violation, or unauthorized network connection. | Hash mismatch in OTA payload, signature validation failure, unverified binary execution attempt. | Device quarantined (`SUSPENDED`), execution halted, event recorded in `qf_governance_audit`. |
| **SEV-3 (Medium)** | Telemetry privacy violation or ambient data ingress attempt. | SSID ending in `_optout` or unverified MAC address received at gateway. | Payload rejected (`403 Forbidden`), `PRIVACY_OPTOUT_ENFORCED` audit event emitted. |
| **SEV-4 (Low)** | Stale heartbeat or edge node network sleep. | Node unresponsive for >300s. | State transitions to `HOLD_ACTIVE` / `OFFLINE` in `node_registry`. (Note: Missing heartbeat is **NOT** treated as revocation). |

---

## 2. Dynamic Revocation Procedure

When a device must be revoked (e.g. lost phone, compromised key):
1. **Database Update:**  
   The Chief Architect or automated gatekeeper executes:
   ```sql
   UPDATE qf_device_authorization 
   SET authorization_status = 'REVOKED', revoked_at = NOW() 
   WHERE node_id = :compromised_node_id;
   ```
2. **Immediate Lockout:**  
   Because every privileged endpoint checks `qf_device_authorization` on every incoming request, revocation takes effect immediately for all subsequent calls. Even if an active TCP/WireGuard session is open, subsequent requests return `403 Forbidden`.
3. **Audit Trail Generation:**  
   An immutable record is appended to `qf_governance_audit` with `event_type = 'DEVICE_AUTHORIZATION_REVOKED'` and the cryptographic rationale.

---

## 3. Evidence Preservation & Forensic Logging

1. **Ghost Sink Redirection:**  
   Anomalous or attacking traffic is routed to the Ghost Sink shock absorber, capturing telemetry payloads for offline forensic analysis without allowing malicious data to contaminate operational tables.
2. **Append-Only Auditing:**  
   All security decisions, access grants, denials, and policy evaluations are committed to `qf_governance_audit` with SHA-256 evidence hashes. Audit records are protected with append-only database roles (`qf_writer`).
