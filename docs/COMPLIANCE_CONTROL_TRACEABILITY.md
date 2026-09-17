# QuantumFlex Federal Compliance & Control Traceability Matrix

**Target Compliance Frameworks:**  
- **NIST SP 800-53 Revision 5**: Security and Privacy Controls for Information Systems and Organizations  
- **OMB Memorandum M-26-15**: Migrating to Post-Quantum Cryptography (PQC)  
- **NIST FIPS 203**: Module-Lattice-Based Key-Encapsulation Mechanism Standard (ML-KEM)  
- **NIST FIPS 204**: Module-Lattice-Based Digital Signature Standard (ML-DSA)  

---

## 1. Compliance Scope & Demarcation Baseline

To ensure absolute audit integrity and prevent overclaiming compliance, the following distinctions are formally established:

| Standard | Scope of This Implementation | What is NOT Claimed |
| :--- | :--- | :--- |
| **NIST FIPS 203** | Native algorithmic execution of ML-KEM-768 via OpenSSL 3.5.8 default provider; wire framing message types `0x12`, `0x13`, and `0x14`. | Does NOT claim FIPS 140-3 module validation. |
| **NIST FIPS 140-3** | OpenSSL default provider execution is delineated from CMVP-validated modules. | FIPS 140-3 cryptographic module validation is **NOT ESTABLISHED** (no CMVP certificate or `fips.so` loaded). |
| **OMB M-26-15** | Implements automated cryptographic inventory (CycloneDX CBOM) and agility with fail-closed strict policy (`fips_strict` fallback: `NONE`). | Does not claim federal agency authority-to-operate (ATO) without system-level certification. |

---

## 2. NIST SP 800-53 Rev 5 Control Mapping

| Control ID | Control Name | QuantumFlex Technical Enforcement Mechanism | Evidence & Test Verification |
| :--- | :--- | :--- | :--- |
| **SC-13** | **Cryptographic Protection** | 1. Native OpenSSL 3.5 ML-KEM-768 implementation in C++ engine.<br>2. Strict fallback policy (`NONE`) prevents stepping down to ML-KEM-512 or FrodoKEM upon family compromise.<br>3. Ephemeral shared secrets zeroized via `OPENSSL_cleanse()`. | - `build_check/test_mlkem768`<br>- `build_check/test_zeroization`<br>- `tests/test_strict_pqc.py`<br>- `pqc-immune-daemon/membrane_health.rego` |
| **SC-28** | **Protection of Information at Rest** | 1. Ledger state encrypted and authenticated with dynamic reconstruction salt.<br>2. Dynamic salt split via Shamir Secret Sharing in GF(256) ($k=3, n=5$).<br>3. Zeroization of dynamic salt upon service lock. | - `src/core/local_node.cpp`<br>- `tools/genesis_tool.cpp`<br>- `tests/test_adversarial_failure_modes.py::test_engine_cold_restart_boots_locked` |
| **IA-2 / IA-3** | **Identification and Authentication** | 1. Mutual TLS (TLS 1.3) required on port 9444.<br>2. Common Name (CN) authorization restricts `SET_HARVESTER_KEY` to `quantum-admin` and `operator`.<br>3. API key authentication on HTTP endpoints (`/ingest`, `/webhook/ingest`, Athena, Bot). | - `src/core/ipc_server.cpp`<br>- `tests/test_adversarial_failure_modes.py::test_ipc_unauthorized_mutation_rejected`<br>- `tests/test_adversarial_failure_modes.py::test_api_node_ingest_unauthenticated` |
| **SI-7** | **Software, Firmware, and Information Integrity** | 1. Append-only tamper-evident ledger state roots (SHA-256).<br>2. Invariant Gatekeeper verifies OPA WebAssembly policies in-process.<br>3. Policy gate fails closed on corrupted/tampered ledger or missing inventory. | - `sentinel/policies/reserve_invariant.rego`<br>- `sentinel/policies/wasm_gatekeeper.py`<br>- `tests/test_adversarial_failure_modes.py::test_policy_rejects_empty_cbom_inventory` |
| **AC-3 / AC-4** | **Access Enforcement & Information Flow** | 1. Least-privilege PostgreSQL roles (`ghostnode`, `amara_admin`, `quantum_sentinel`) without superuser attributes.<br>2. Immutability trigger on `quantum_telemetry_channel` prevents `UPDATE` and `DELETE`.<br>3. Network sockets bound exclusively to loopback (`127.0.0.1`). | - `setup_databases.sql`<br>- `setup_quantum_flex_schema.sql`<br>- `scripts/audit_deployed_permissions.sh` |
| **SI-4 / SC-7** | **Information System Monitoring & Boundary Protection** | 1. Inbound unverified files routed to isolated tmpfs airlock (`/dev/shm/qflex_airlock`).<br>2. Executed in disposable Podman container with dropped capabilities and read-only rootfs.<br>3. EWMA Lif Sentinel monitors and accounts for malformed wire frames. | - `run_sentinel.py`<br>- `sentinel/quarantine_chamber.py`<br>- `tests/test_ghost_node_tmpfs.py` |
| **CM-8** | **Information System Component Inventory** | Automated CycloneDX CBOM generation tracking post-quantum algorithms, libraries, and protocols across the software stack. | - `pqc-immune-daemon/immune_daemon.py::generate_cbom`<br>- `pytest pqc-immune-daemon/test_immune_daemon.py` |

---

## 3. Failure Mode & Boundary Testing Evidence

The following table records the empirical evidence demonstrating safe outcomes under failure:

| Failure Mode | Test Case | Observed Outcome | Safe Result Verified |
| :--- | :--- | :--- | :--- |
| **Missing API Key Configuration** | `test_api_node_ingest_unauthenticated` | HTTP 401 Unauthorized | Admitted = False; no unauthenticated execution. |
| **Rogue / Untrusted CA on mTLS** | `test_ipc_untrusted_ca_rejected` | TLS Handshake Failure (`SSLError`) | Connection dropped before application processing. |
| **Unauthorized Admin Mutation** | `test_ipc_unauthorized_mutation_rejected` | `ERR|UNAUTHORIZED_HARVESTER_MUTATION` | Harvester key unchanged; EWMA drop recorded. |
| **Slowloris / Handshake Stall** | `test_ipc_slowloris_stall_enforces_deadline` | Socket terminated at 5.0s | Unblocking listener; subsequent valid client served. |
| **Split `QF` Wire Header** | `test_ipc_fragmented_magic_bytes_succeeds` | Reassembled into binary frame (`0x12`) | Valid client correctly served despite fragmentation. |
| **Cold Daemon Restart** | `test_engine_cold_restart_boots_locked` | `ERR|NODE_LOCKED` | Rejects telemetry fail-closed until SSS unseal. |
| **Empty CBOM Inventory** | `test_policy_rejects_empty_cbom_inventory` | `node_status: TOXIC` | Empty inventory cannot pass as COMPLIANT. |
| **Non-Hex / Zero TPM Anchor** | `test_policy_rejects_non_hex_or_placeholder_tpm` | `verdict: DENY` | Hardware anchor required; placeholders rejected. |
| **Negative Reserve Obligation** | `test_policy_rejects_negative_numeric_reserves` | `verdict: DENY` | Solvency gate enforces non-negative physical bounds. |
| **OPA Service Downtime** | `test_opa_service_unavailable_fails_closed` | `verdict: DENY` | Fails closed on unreachable sidecar. |
