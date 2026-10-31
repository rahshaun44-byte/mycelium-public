# Mycelium — QuantumFlex Engine & Coordination Architecture

> **Status:** Research prototype, published for study and review, not for production use. All experimental post-quantum key establishment modules (FrodoKEM-976 and ML-KEM-768) are formally **retired**. There are no claims of end-to-end post-quantum cryptographic protection, wire-level PQ payload encryption, or FIPS 140-3 validation. Canonical cryptographic runtime definitions and physical silicon evidence reside in [`quantumflex`](https://github.com/rahshaun44-byte/quantumflex). See [`STATUS.md`](STATUS.md) and [`HANDOFF.md`](HANDOFF.md).

---

## Overview

**Mycelium** is the coordination, admission, policy enforcement, and telemetry engine for the QuantumFlex architecture. It governs and consumes the standalone [`QuantumFlex::runtime`](quantumflex/README.md) library across mutual TLS (mTLS) boundaries.

The system enforces fail-closed state transitions, verifiable audit logging, and automated admission policies:

- **Host Engine & IPC Server** (`src/core/ipc_server.cpp`): Coordinates node communication over mTLS.
- **QuantumFlex Runtime Integration**: Admits and links the `QuantumFlex::runtime` package (`quantumflex/`) via SHA-256 receipt verification (`cmake/AdmitQuantumFlex.cmake`).
- **Cryptographic Retirement**: FrodoKEM-976 and ML-KEM-768 are formally retired. Hand-written Frodo matrix math is unaudited research code quarantined behind `-DQUANTUMFLEX_ENABLE_LEGACY_FRODO_RESEARCH=OFF`.
- **Fail-Closed Admission Gates**: OPA/Rego-based policy enforcement across runtime and execution boundaries.
- **Cryptographic Evidence & Provenance**: SHA-256 hash-chained ledger and CycloneDX v1.5 Cryptographic Bill of Materials (CBOM).

**What this is not:**
- It is **not** a production-ready cryptographic appliance.
- It does **not** employ active post-quantum key establishment on the live wire path; FrodoKEM-976 and ML-KEM-768 are formally retired.
- It does **not** encrypt application stream payloads with post-quantum secrets, nor does it override the TLS handshake's negotiated cipher group.
- It carries **no** FIPS 140-3 certifications or independent audit seals.

---

## Architecture

```text
                     Client / Consumer
                             │
                    mutual TLS (OpenSSL)
                             │
                   QFXK Frame Reassembly
              (quantumflex/src/wire/wire_framing.cpp)
                             │
                 IpcServer::handle_framed_message
                    (src/core/ipc_server.cpp)
                             │
              ┌──────────────┴──────────────┐
              │                             │
         0x12 / 0x13                   Anything Else
              │                             │
        MLKem768Engine                 0x7F REJECT
      (OpenSSL ML-KEM-768)        (Fail-Closed Drop)
              │
         0x14 CONFIRM
  HMAC-SHA256(ss, label || ct)
```

### Live Key Exchange Protocol

| Type | Direction | Payload | Description |
| :--- | :--- | :--- | :--- |
| `0x12` | Request | Empty | Client requests server ML-KEM-768 encapsulation key |
| `0x12` | Response | 1,184 bytes | Server ML-KEM-768 encapsulation key |
| `0x13` | Request | 1,088 bytes | Client sends ML-KEM-768 ciphertext |
| `0x14` | Response | 32 bytes | Server key confirmation tag |
| `0x7F` | Response | Empty | Rejection: malformed frame, unsupported type, or provider error |

Confirmation tag derivation:
$$\text{Tag} = \text{HMAC-SHA256}(\text{shared\_secret}, \text{"QuantumFlex-ML-KEM-768-server-confirm-v1"} \parallel \text{ciphertext})$$

The server zeroizes its copy of the ephemeral shared secret immediately following confirmation tag calculation. Legacy message types (`0x02` / `0x03`) are unconditionally rejected without fallback.

### QFXK Wire Framing (Implemented vs Legacy Claims)

The binary header is 16 bytes in network byte order: `magic` (`0x5146584B` / `"QFXK"`), `version` (`1`), `type`, `sequence_id`, `payload_len`, and `flags` (must be `0`).

- **Implemented (C++ `QuantumFlexReassemblyPool`):** Buffers incoming partial reads from a TLS stream until a complete frame is assembled. Rejects invalid magic, bad version, non-zero flags, or payloads exceeding 16 KiB. Tracks up to 100 concurrent sessions, evicting oldest on saturation.
- **Not Implemented on Live Path:** The C++ engine does **not** support multi-chunk fragmentation, frame reordering, duplicate detection, or CRC32 verification on the live wire path. Mutual TLS already provides stream ordering and message integrity; ML-KEM messages fit within a single frame. Historical multi-chunk and CRC handling belonged exclusively to prototype client test scripts (`scripts/qf_hybrid_gatekeeper.py`).

---

## Legacy Research Code: X25519 + FrodoKEM-976

`HybridKemEngine` (`quantumflex/src/crypto/hybrid_kem.cpp`) combines X25519 with FrodoKEM-976 via HKDF.

> [!WARNING]
> **FrodoKEM-976 Hand-Written Implementation Notice:**
> The FrodoKEM-976 matrix arithmetic in `quantumflex/src/crypto/frodo976.cpp` is a hand-written research prototype that has **never been independently audited**. It is not sourced from a verified or reference distribution (such as liboqs). The live server does **not** select or accept this path. It exists solely for historical research analysis. Do not use this implementation in any production or security-sensitive context.

A future hybrid exchange on the live path (X25519 + ML-KEM-768) is planned for **v2**, pending adoption of a reviewed combiner specification.

---

## Supporting Systems

- **CEDRUS Artifact Validation Gate** (`scripts/cedrus_artifact_gate.py`): Requires strict presence of `BUNDLE_PATH`, `SIG_PATH`, `PUBKEY_PATH`, and `VERIFIER_BIN`. Halts immediately with `DATA NOT FOUND` on any missing artifact; never generates synthetic verification vectors.
- **Cryptographic Inventory (CBOM)** (`scripts/generate_cbom.py`): Emits CycloneDX v1.5 CBOM tracking algorithms, binary digests, policy hashes, and KEM selections.
- **OPA Policy Enforcement** (`sentinel/policies/`): Rego policy engines enforcing algorithm boundaries (`fips_strict`, `iso_strict`, `agility`).
- **Sentinel & Host Telemetry**: Monitored daemon pipelines for system homeostasis and invariant adherence.

---

## Build & Installation

### Requirements
- CMake 3.20+
- C++20 compliant compiler (`g++` or `clang++`)
- OpenSSL **3.5+** (native ML-KEM support required)
- `libpqxx`, `sqlite3`, `libsystemd` (required for full Mycelium engine)
- Python 3.14 (used for local audit tooling and test lockfile)

### 1. Build Standalone Runtime (`quantumflex/`)
The cryptographic runtime library can be built independently without database dependencies:
```bash
cmake -S quantumflex -B quantumflex/build \
    -DOPENSSL_ROOT_DIR=/opt/openssl-3.5 \
    -DCMAKE_BUILD_RPATH=/opt/openssl-3.5/lib64
cmake --build quantumflex/build -j"$(nproc)"
```

### 2. Build Mycelium Engine
```bash
cmake -S . -B build_check \
    -DOPENSSL_ROOT_DIR=/opt/openssl-3.5 \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build_check -j"$(nproc)"
```

Production builds enforce attested runtime admission via `-DQUANTUMFLEX_REQUIRE_ATTESTED=ON`, verifying `QuantumFlexAdmission.json` SHA-256 receipts before linking.

---

## Testing & Verification

### Live Path Tests
```bash
# Core runtime C++ tests
./quantumflex/build/test_mlkem768
./quantumflex/build/test_wire_framing
./quantumflex/build/test_wire_fuzz_negative

# Engine integration over mTLS
QF_TEST_BUILD_DIR=build_check python3 -m pytest tests/test_mlkem_ipc.py
```

### Policy & Python Integration Tests
```bash
python3 -m pytest tests/
```

### Verification Status Matrix

| Subsystem / Vector | Status | Evidence / Notes |
| :--- | :--- | :--- |
| **ML-KEM-768 Exchange & Confirmation** | Implemented | Verified via `test_mlkem768` and `test_mlkem_ipc.py` over mTLS |
| **Fail-Closed Type Rejection (`0x7F`)** | Implemented | Legacy Frodo types (`0x02`/`0x03`) and unknown types rejected |
| **QFXK Single-Frame Reassembly** | Implemented | Verified via `test_wire_framing` and `test_wire_fuzz_negative` |
| **QFXK Multi-Frame / CRC on Live Path** | **Not Implemented** | TLS provides stream ordering; not present in C++ engine |
| **X25519 + FrodoKEM Hybrid** | **Legacy Research Only** | Un-audited hand-written math; server does not select |
| **CEDRUS Gate & CBOM Generator** | Implemented | Verifies required artifacts; fails closed on missing assets |
| **GitHub Actions CI** | In Progress | Configured for containerized OpenSSL 3.5; local passes verified |
| **Independent Cryptographic Audit** | **Not Done** | **Hard Stop gate** before any production claims |

---

## Security Model & Hard Stop Invariants

1. **Fail-Closed Default**: Any condition, malformed frame, provider failure, or missing evidence immediately drops session state and rejects transaction flow (`0x7F`).
2. **Zero Cryptographic Theater**: No claims of FIPS 140-3 certification, full-wire PQ encryption, or quantum immunity.
3. **Receipt-Bound Admission**: Runtime linking requires cryptographic hash-receipt verification (`QuantumFlexAdmission.json`).
4. **Hard Stop Evaluation**: Missing artifacts, un-audited primitives, or unverified claims halt execution immediately.

---

## License & Security Contact

- **License**: Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
- **Security Contact**: Disclose vulnerabilities privately following instructions in [`SECURITY.md`](SECURITY.md).
