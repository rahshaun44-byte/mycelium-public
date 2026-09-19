# QuantumFlex runtime

This directory is the **product-runtime library**: cryptographic primitives
and the QFXK wire codec. It is not mycelium (coordination, policy, admission,
telemetry). Mycelium *governs and consumes* this package; it does not implement
it.

```text
QuantumFlex::crypto   hasher, shamir, hybrid signer, ML-KEM / hybrid KEM
QuantumFlex::wire     QFXK frame codec + reassembly pool
QuantumFlex::runtime  both (what the engine links)
```

Public headers stay at `include/quantum-flex/*.hpp` so existing
`#include "quantum-flex/hybrid_kem.hpp"` lines do not move.

## Build (standalone)

Needs OpenSSL 3.5+ with native ML-KEM. Does **not** need libpqxx, sqlite, or
libsystemd.

```bash
cmake -S quantumflex -B quantumflex/build \
    -DOPENSSL_ROOT_DIR=/opt/openssl-3.5 \
    -DCMAKE_BUILD_RPATH=/opt/openssl-3.5/lib64
cmake --build quantumflex/build -j"$(nproc)"
./quantumflex/build/test_hybrid_kem
./quantumflex/build/test_known_answer_vectors
./quantumflex/build/test_mlkem768
```

`cmake --install` writes a `QuantumFlexConfig.cmake` so a consumer can
`find_package(QuantumFlex)`. It also writes `QuantumFlexAdmission.json` next to
that file — SHA-256 of the installed libs and public headers. Mycelium
`find_package`s first and **verifies the receipt** before linking. A mismatch
is fail-closed. In-tree `add_subdirectory` is DEV only; production configures
with `-DQUANTUMFLEX_REQUIRE_ATTESTED=ON`.

The receipt is a hash binding (`signed: false`). QF-A5 Ed25519 over the receipt
is a separate operator ceremony with the external release key.

## What this is not

Not a FIPS 140-3 module. Not mycelium admission/policy. Not a second copy of
the mycelium tree. A later git subtree split can land this directory in a
sister `quantumflex` / `qflex` repository without rewriting the CMake package.
