# Crypto → QuantumFlex rehome (collapse step 2)

Mycelium *governs* cryptography. QuantumFlex *implements* it.

## What landed

`quantumflex/` is an independently buildable CMake package (no libpqxx, no
sqlite, no systemd):

| Target | Contents |
| --- | --- |
| `QuantumFlex::crypto` | hasher, shamir, hybrid signer, ML-KEM / hybrid KEM |
| `QuantumFlex::wire` | QFXK codec (moved *with* the KEM) |
| `QuantumFlex::runtime` | both — what `quantum_flex_engine` links |

Public include path is unchanged: `#include "quantum-flex/hybrid_kem.hpp"`.

Mycelium `find_package(QuantumFlex)` first; if no installed artifact exists it
`add_subdirectory(quantumflex)`. That is the admission-shaped seam: an attested
install later wins without rewriting the engine.

`qflex::crypto` remains an alias of `QuantumFlex::crypto` so the step-1 name
still resolves.

## Isolation

`wire_framing.cpp` previously included mycelium's `verified_core.h` solely for
`QF_WIRE_MAX_SEQ_ID`. The codec now owns `quantumflex::wire::MAX_SEQ_ID` (same
numeric bound). The C ABI constant stays in mycelium's verified-core header;
the two values are documented as a pair, not a compile-time dependency.

`src/crypto/` is gone. Crypto/wire tests live under `quantumflex/tests/`.
`test_verified_core` stays in mycelium (formal C ABI).

## What this is not

- Not a push to a sister GitHub repo (none is visible to this principal).
- Not provenance attestation of the installed artifact (next layer).
- Not deletion of mycelium coordination (`src/core/`, policies, intake).
- Not a FIPS 140-3 claim.
