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
- Not QF-A5 Ed25519 signing of the runtime (that still needs the external release key).
- Not deletion of mycelium coordination (`src/core/`, policies, intake).
- Not a FIPS 140-3 claim.

## Collapse step 3 — admission

Mycelium *admits* QuantumFlex. A prefix that cannot present a matching hash
receipt does not get to link.

- Install writes `lib/cmake/QuantumFlex/QuantumFlexAdmission.json` (SHA-256 of
  the two static libs and the five public headers). `signed: false` is honest:
  this is a binding, not a signature.
- `QUANTUMFLEX_REQUIRE_ATTESTED=ON` fail-closes unless `find_package` hits a
  prefix whose receipt verifies. In-tree `add_subdirectory` is not an attested
  path.
- Default DEV still builds in-tree and writes
  `build_check/QuantumFlexAdmission.dev.json` (source hashes — evidence, not
  authority).
- A found prefix with a *mismatched* receipt is FATAL even in DEV (tamper).
- A found prefix with *no* receipt is ignored in DEV (in-tree wins) and FATAL
  when ATTESTED.

```bash
cmake -S quantumflex -B quantumflex/build -DCMAKE_INSTALL_PREFIX=/opt/quantumflex
cmake --build quantumflex/build
cmake --install quantumflex/build

cmake -S . -B build_check \
    -DQUANTUMFLEX_REQUIRE_ATTESTED=ON \
    -DCMAKE_PREFIX_PATH=/opt/quantumflex
```

`python3 scripts/test_quantumflex_admission.py` exercises DEV / ATTESTED /
tamper.
