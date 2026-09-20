> **Cryptographic posture update (2026-09-15):** `fips_strict` is an algorithm policy, not a FIPS 140-3 validation claim. Migrated C++ IPC uses native ML-KEM-768; legacy Frodo message types are rejected. Runtime deployment and module validation must be verified separately. See [migration and verification notes](docs/MLKEM_STRICT_MIGRATION.md). Older walkthroughs and benchmark claims are historical, not current attestations.

# Quantum Flex — PQC Hybrid KEM Gateway & Cryptographic Agility Framework

## Overview

Quantum Flex is a post-quantum cryptography (PQC) transition framework focused on hybrid key establishment, secure wire transport, cryptographic inventory, and fail-closed validation workflows.

The project implements a hybrid KEM architecture combining:
- **FrodoKEM-976** — post-quantum lattice-based key encapsulation
- **X25519** — classical elliptic-curve key exchange
- **HKDF-based hybrid secret derivation**
- **QFXK binary wire framing protocol**
- **Gatekeeper session management**
- **Cryptographic artifact provenance validation**
- **CycloneDX CBOM generation**

The design goal is to provide a controlled migration path from classical cryptography toward post-quantum cryptographic deployments while maintaining interoperability, bounded resource usage, and explicit validation states.

---

## Architecture

```text
                 Applications
                      |
                      |
              Quantum Flex Gateway
                      |
        +-------------+-------------+
        |                           |
 Legacy Command Path          QFXK Protocol Path
        |                           |
        |                    Wire Reassembly
        |                           |
        |                 Hybrid KEM Processing
        |                           |
        |              FrodoKEM-976 + X25519
        |                           |
        +-------------+-------------+
                      |
                 HKDF Combiner
                      |
              Derived Session Secret
```

### Supporting Systems:
- **CEDRUS Artifact Gate**
- **Cryptographic Inventory / CBOM Generator**
- **Security Policy Controls**
- **Fuzz and Negative Testing Framework**

---

## Features

### Hybrid KEM Engine

Implemented hybrid key establishment using:

```text
FrodoKEM-976
      +
X25519
      |
      v
HKDF Hybrid Combiner
      |
      v
Session Secret
```

**Security Properties:**
- Dual cryptographic contribution
- Transcript-bound key derivation
- Constant-time error accumulation
- Fail-closed decapsulation handling
- Low-order X25519 input rejection

### QFXK Wire Framing Protocol

Large PQC messages exceed normal network MTU sizes. Quantum Flex provides a bounded fragmentation and reassembly layer.

#### Frame Structure
```text
+--------+----------+
| Header | Payload  |
+--------+----------+
```

**Header Fields (16-Byte Big-Endian):**
- Magic identifier (`0x5146584B` / `"QFXK"`)
- Message type
- Flags
- Sequence identifier
- Chunk count
- Chunk length
- CRC32 checksum

**Capabilities:**
- MTU-aware fragmentation
- Out-of-order reassembly
- CRC corruption detection
- Duplicate protection
- Session timeout cleanup
- Bounded memory usage ($\le 64$ sessions)

### Gatekeeper Subsystem

The Gatekeeper provides a protocol-aware security boundary.

**Supported Modes:**

#### QFXK Binary Mode
Handles:
- KEM public keys
- KEM ciphertext transport
- Fragment reassembly
- Hybrid decapsulation
- Session establishment

#### Legacy Command Mode
Maintains compatibility with existing command paths:
- `INIT|`
- `UNLOCK|`
- `TELEMETRY|`

### CEDRUS Artifact Validation Gate

Quantum Flex includes an evidence validation workflow designed to prevent false-positive verification states.

**Required Artifacts:**
- `BUNDLE_PATH`
- `SIG_PATH`
- `PUBKEY_PATH`
- `VERIFIER_BIN`

**Behavior:**
```text
Missing artifact
        |
        v
DATA NOT FOUND
        |
        v
STOP
```

*The validation pipeline does not generate synthetic verification vectors.*

### Cryptographic Inventory (CBOM)

The project includes automated Cryptographic Bill of Materials generation.

**Tracked Information Includes:**
- Cryptographic algorithms
- Binary hashes
- Policy file hashes
- Network surfaces
- Signature schemes
- KEM selections
- Migration metadata

**Output Format:** CycloneDX v1.5 CBOM ([`docs/cbom_alpha_node_template.json`](docs/cbom_alpha_node_template.json))

---

## Verification Results

### Hybrid KEM Tests
**5/5 invariants passed**

Validated:
- Shared secret agreement
- Corrupted ciphertext rejection
- Low-order point rejection (RFC 7748 §6.1)
- Tampered key divergence
- Serialization round-trip accuracy

### Wire Framing Tests
**4/4 invariants passed**

Validated:
- Header parsing
- Multi-frame reassembly
- CRC corruption detection
- Duplicate frame handling

### Gatekeeper Client Tests
**5/5 invariants passed**

Validated:
- Fragmentation and recovery
- Corruption detection
- Out-of-order resilience
- Timeout cleanup
- Hybrid encapsulation

### Negative Testing

Additional validation includes:
- malformed frame rejection
- table exhaustion handling
- invalid chunk bounds
- message type mismatch detection
- X25519 malformed input testing
- HKDF transcript binding verification

---

## Build

### Requirements:
- CMake 3.16+
- C++ compiler with C++17 support
- OpenSSL development libraries (3.0+)
- Python 3 environment

### Build:
```bash
cmake -S . -B build_check -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build_check -j$(nproc)
```

---

## Testing

Run hybrid KEM tests:
```bash
./build_check/test_hybrid_kem
```

Run wire framing tests:
```bash
./build_check/test_wire_framing
```

Run negative fuzz and table saturation tests:
```bash
./build_check/test_wire_fuzz_negative
```

Run Python validation:
```bash
./venv/bin/python ./scripts/qf_hybrid_gatekeeper.py --test-unit
```

Run Wycheproof X25519 tests:
```bash
./venv/bin/python ./scripts/test_wycheproof_x25519.py
```

Run artifact gate:
```bash
./scripts/cedrus_artifact_gate.py
```

---

## Security Model

Quantum Flex assumes:
- active network attackers
- harvest-now-decrypt-later threats
- malformed protocol inputs
- cryptographic downgrade attempts
- resource exhaustion attempts

**Security Boundaries:**
- KEM provides key establishment
- Authentication is provided through configured identity mechanisms
- Missing validation evidence results in rejection
- Unknown states fail closed

---

## Repository Structure

```text
.
├── quantumflex/                  # independently buildable runtime (crypto + QFXK)
│   ├── include/quantum-flex/     # hybrid_kem.hpp, wire_framing.hpp, signers
│   ├── src/crypto/  src/wire/
│   └── tests/
│
├── include/quantum-flex/         # mycelium coordination headers (ipc, ledger, node)
├── src/core/                     # engine coordination (no crypto .cpp)
│
├── scripts/
│   ├── qf_hybrid_gatekeeper.py   # mycelium client of the runtime
│   ├── cedrus_artifact_gate.py
│   ├── test_wycheproof_x25519.py
│   └── generate_cbom.py
│
└── docs/
    ├── CRYPTO_LIBRARY_CARVEOUT.md
    ├── QFXK_WIRE_PROTOCOL_SPEC.md
    └── SECURITY.md
```

---

## Development Status

### Current Status:
- Hybrid KEM implementation: Complete
- Wire framing subsystem: Complete
- Gatekeeper integration: Complete
- Negative testing: Complete
- CBOM generation: Complete
- Security documentation: Complete

### Future Work:
- External cryptographic review
- Additional interoperability testing
- Extended fuzzing campaigns
- Deployment validation

---

## License

QuantumFlex Software License. See [`LICENSE`](LICENSE) for terms.

---

## Security Contact

For vulnerability reports, please follow the disclosure process documented in:

[SECURITY.md](SECURITY.md)
