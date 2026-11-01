# QuantumFlex Device Ownership & Legal Authorization Register

**Policy Document:** `QF-GOV-REG-001`  
**Governance Layer:** QuantumFlex Legal & Operational Assurance Layer (QF-LOAL)  
**Standard:** QF-LEGAL-001 Authorized Operation Invariant  
**Classification:** Controlled / Authoritative Architecture Standard  
**Last Reviewed:** 2026-11-01  

---

## 1. Scope & Foundational Principle

This Register establishes the formal legal ownership, operational controllership, hardware root of trust, and authorization boundaries for every physical and logical device interacting with the QuantumFlex substrate.

> **Foundational Separation Invariant:**  
> **Hardware Identity $\neq$ Cryptographic Possession $\neq$ Legal Authorization.**  
> - A hardware security module proves where a key resides under specified physical assumptions.  
> - A cryptographic signature proves possession of a private key.  
> - **Neither** establishes legal ownership, operational consent, or legal permission to access systems or process data. A device reporting `ACTIVE` in `node_registry` is merely network-reachable; it is **NOT** authorized to execute operations unless explicitly validated against `qf_device_authorization`.

---

## 2. Authorized Device Inventory

| Node Identifier | Physical Device Model | Serial / Identity Reference | Hardware Trust Anchor | Designated Owner & Operator | Legal Status | Permitted Purpose & Operational Scope |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`qfx-yoga`** | Lenovo Yoga 7 2-in-1 14AKP10 | Host Machine (Ubuntu 26.04.1 LTS) | Microsoft Pluton TPM 2.0 (PCR Quotes) | Rocky (`rocky@qfx-yoga`) | `AUTHORIZED` | Primary Host Engine, Local Ollama AI Orchestrator, Invariant Gatekeeper, Smart Contract Settlement. |
| **`qfx-pixel`** | Google Pixel 11 Pro (`grizzly`) | Attached USB / Tailnet Mesh (`PIXEL-SERIAL-REDACTED`) | Google Titan-M3 StrongBox HSM | Rocky (`rocky@qfx-pixel`) | `AUTHORIZED` | Tactical HUD, Mobile Sentinel, Out-of-Band (OOB) Quorum Signing, Telemetry Beaconing. |
| **`g6pro`** | HP ProBook 450 G6 | Tailnet Peer (`100.64.1.19`) | Unattested (Pending OS Reinstall) | Rocky (`rocky@g6pro`) | `SUSPENDED` | Standby Isolation. All Kafka & Compute duties reallocated to `qfx-yoga` and `qfx-pixel`. Zero active permissions. |
| **`qflex`** | HP Host (External Auxiliary) | Tailnet Peer (Pending) | Pending Remote Attestation | Rocky (`rocky@qflex`) | `PENDING` | Auxiliary compute awaiting formal operator identity binding and hardware attestation. |

---

## 3. Node Lifecycle & Authorization States

Every node recorded in the `qf_device_authorization` database table must occupy exactly one of the following enumerated states:

1. **`PENDING`**: Initial enrollment. Node identity and hardware descriptors recorded, but operator consent, scope definition, or cryptographic validation is incomplete. Privileged operations fail closed (`403 Forbidden`).
2. **`AUTHORIZED`**: Formally admitted. Hardware verified, software provenance validated, owner authorization documented, expiration timestamp active. Privileged operations permitted within `permitted_operations`.
3. **`SUSPENDED`**: Temporarily frozen (e.g. pending OS reinstallation, security anomaly, maintenance, or audit quarantine). All inbound operations rejected.
4. **`REVOKED`**: Permanently or indefinitely decommissioned due to credential breach, physical loss, or decommission. All future cryptographic assertions fail closed.
5. **`EXPIRED`**: Authorization term has lapsed without explicit review. Node retains network reachability but cannot execute privileged operations.

---

## 4. Hardware Attestation Integrity

- **Lenovo Yoga 7 (`qfx-yoga`):** Anchored to Microsoft Pluton TPM 2.0. Attestation validates kernel integrity and binary FD pinning via `qf-runtime-admit`.
- **Pixel 11 Pro (`qfx-pixel`):** Anchored to Google Titan-M3 StrongBox. Real-hardware property query (`ro.strongbox.model = Titan-M3`, `ro.soc.model = Tensor G6`) verified. Attestation must not fabricate or mock hardware identifiers.
- **HP ProBook (`g6pro`):** Operating system corrupted/missing. Placed in `SUSPENDED` state until physical reinstallation, kernel configuration, and cryptographic re-admission ceremony occur.

---

## 5. Audit & Modification Requirements

Any modification to device ownership, authorization status, or operational scope requires:
1. Verification of Chief Architect authority via hardware-backed signature.
2. An append-only entry written to PostgreSQL table `qf_governance_audit`.
3. Updating the signed provenance manifest.
