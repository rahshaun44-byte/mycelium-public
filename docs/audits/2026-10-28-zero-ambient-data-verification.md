# QuantumFlex Security Verification Dossier
**Invariant: Zero Ambient Data & Database Role-Separated Telemetry Ingestion**  
**Date:** 2026-10-28 (20:58 EDT)  
**Host Engine:** `qfx-yoga` (Lenovo Yoga 7 2-in-1 14AKP10, Ubuntu 26.04.1 LTS, Microsoft Pluton TPM 2.0)  
**Base Commit Revision:** `3916bff0f282b375b89e229f1cbb7287ed1fec09`  
**Status:** **VERIFIED (Active Host Scope & Telemetry Ingestion Pipeline)**

---

## 1. Executive Summary & Invariant Grounding

This dossier establishes the formal, reproducible verification record for the **Zero Ambient Data Invariant** and **Database Least-Privilege Role Separation** across the QuantumFlex telemetry architecture.

QuantumFlex is designed strictly for **Post-Quantum Cryptographic (PQC) state certification, hardware TPM 2.0 attestation, and local neural memory orchestration**. Ambient wireless network discovery, neighbor SSID/BSSID sniffing, and personal identity harvesting are strictly prohibited from collection, processing, and persistence.

---

## 2. Hardware Topology & Network State Truth

* **Topology Invariant**:
  - `qfx-yoga`: Primary Host Engine & API Gateway (`100.64.1.31`).
  - `qfx-pixel`: Pixel 11 Pro / Titan M2 StrongBox (`100.64.1.12`).
  - `g6pro`: HP ProBook 450 G6, KRaft Kafka Broker (`100.64.1.19`).
* **Host Wireless Radio State (`qfx-yoga`)**:
  - `nmcli radio wifi` -> **`disabled`**
  - Device `wlp3s0` -> **`unavailable`** (interface `state DOWN`, 0 bytes / 0 packets transmitted)
  - Active Connectivity: Strictly USB-C Gigabit Ethernet (`enx92941320a979: connected`) and Tailscale mesh overlay (`tailscale0`).

---

## 3. Implemented Security Controls

### A. Deep Packet Inspection & Prohibited Identifiers (`src/privacy_filter.py`)
* **Core Telemetry Policy**:
  ```python
  QUANTUMFLEX_TELEMETRY_POLICY = {
      "wifi_scanning_enabled": False,
      "neighbor_network_collection_enabled": False,
      "ssid_collection_enabled": False,
      "bssid_collection_enabled": False,
      "personal_data_collection_enabled": False,
      "raw_payload_logging_enabled": False,
      "fail_closed": True,
  }
  ```
* **Prohibited Denylist**: Blocks direct identifiers (`ssid`, `bssid`, `mac_address`, `access_points`, `nearby_aps`, `wifi_networks`, `scan_results`), ambient discovery tags (`neighbor_networks`, `wifi_scan`, `ambient_radio`), and personal tracking fields (`gps_track`, `imei`, `imsi`, `phone_number`, `email`).
* **Normalization Engine**: `re.sub(r'[^a-z0-9]', '', str(k).lower())` normalizes casing and delimiter variations (`Nearby-APs`, `nearby_aps`, `BSSID`, `SSID`).
* **Strict Operational Allowlist (`ALLOWED_OPERATIONAL_FIELDS`)**:
  In addition to the denylist, `PrivacyFilter.is_strictly_authorized_operational_data()` validates that every key strictly belongs to approved host vitals (`node_id`, `hostname`, `cpu_load_1m`, `ram_used_pct`, `temp_c`, `configured_kem`, `runtime_kem`, `tpm`, `status`, etc.). Any unknown or foreign sensor attributes (e.g., `ambient_light`, `nearby_devices`, `microphone_volume`) are rejected.
* **DoS / Recursion Protection**: Objects with nesting depth $> 10$ fail closed immediately.
* **JSON Unpacking**: Embedded JSON strings are unpacked and inspected recursively.

### B. Ingestion & Persistence Boundary (`api_node/main.py`)
* **DPI Edge Rejection**: `/api/v1/telemetry/submit` rejects prohibited identifiers with `HTTP 403 Forbidden` prior to cryptographic signature verification or persistence.
* **Atomic Batch Rejection**: Multi-frame batches containing any prohibited field are rejected in their entirety.
* **No Diagnostic Leakage**: Rejected payloads are never mirrored in logs or error traces.
* **Persistence Safeguard**: `persist_telemetry_frame()` runs `contains_prohibited_ambient_data()` before database connection acquisition.

### C. PostgreSQL Role Isolation & Credential Custody
* **`qf_writer`**: `NOSUPERUSER`, `INSERT`-only on `quantum_telemetry_channel` and `telemetry_log`. Sequences: `USAGE, SELECT`.
* **`qf_verifier`**: `NOSUPERUSER`, `SELECT`-only, enforced `default_transaction_read_only = on`.
* **Ledger Immutability Trigger**: `qf_reject_ledger_mutation()` raises exception `42501` on any `UPDATE`, `DELETE`, or `TRUNCATE`.
* **Credential Storage**: `~/.config/quantumflex/db_roles.env` (permissions strictly `0600`, parent `0700`). Loaded via `src/db_credentials.py` which rejects permissions wider than `0600` and disallows administrative accounts.

---

## 4. Empirical Evidence & Verification Results

### 1. Automated Test Suite (39/39 Passed in 0.47s)
```text
tests/test_privacy_filter.py ...........                                 [ 28%]
tests/test_telemetry_wiring_proof.py ......................              [ 84%]
tests/test_db_acl_separation.py ......                                   [100%]
============================== 39 passed in 0.47s ==============================
```

### 2. Live API Service Probes (`PID 106734` on `127.0.0.1:8080`)
* **Adversarial Ambient Probe**: Signed Ed25519 payload containing `{"ssid": "RogueAP"}`:
  ```text
  Response: HTTP 403 Forbidden -> {"detail":"Forbidden: Prohibited ambient network or personal tracking identifiers detected"}
  ```
* **Legitimate Host Operational Probe**: Signed Ed25519 payload containing host vitals (CPU load `0.22`, RAM `46.5%`, Temp `39°C`, `ML-KEM-768`):
  ```text
  Response: HTTP 200 OK -> {"status":"VERIFIED","trust_score":100,"node_id":"qfx-live-node","seq":1}
  ```
* **Verifier Catalog Read**:
  ```text
  Database ID: 67 | Node ID: qfx-live-node | Timestamp: 1700000000
  Payload: {"cpu_load_1m": 0.22, "ram_used_pct": 46.5, "temp_c": 39.0, "configured_kem": "ML-KEM-768", "runtime_kem": "ML-KEM-768", "status": "PULSE_OK"}
  ```

### 3. Deployed Permissions & Socket Auditor
* Script: `scripts/audit_deployed_permissions.sh`
* Ports: All application listeners (`5432`, `8000`, `8001`, `8080`, `8181`, `9000`, `9444`, `11434`) strictly bound to loopback (`127.0.0.1`) and Tailscale overlay (`100.64.1.31`).
* Result: **0 Failures**.

---

## 5. Scope & Audit Qualifications

1. **Host-Specific Radio State**: The verified Wi-Fi disablement reflects the physical state of `qfx-yoga`. Multi-node producers (`g6pro`, `qfx-pixel`) must maintain matching zero-ambient collection policies.
2. **Dual-Layer Guardrails**: Both a normalized denylist (rejecting direct/ambient/personal identifiers) and an immutable schema allowlist (`ALLOWED_OPERATIONAL_FIELDS`) are active in `PrivacyFilter`.
3. **Retention Scope**: Verified for the active PostgreSQL database, local Ghost Sink logs, and HTTP ingestion routes. Secondary pipelines (offline archives, staging tables) must undergo matching audits upon provisioning.
4. **Test Artifact Isolation**: Live probe record `id=67` (`qfx-live-node`) uses an isolated test identifier and does not collide with production sequence numbers or trust records on real nodes (`qfx-yoga`, `g6pro`, `qfx-pixel`).
5. **Dossier Tracking**: Documented under `docs/audits/2026-10-28-zero-ambient-data-verification.md` for permanent inclusion in the QuantumFlex repository audit history.
