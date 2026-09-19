# Crypto library carve-out (collapse step 1)

Mycelium *governs* cryptography (provenance, admission, policy). It should not
*implement* it. This change is the first executable layer of that split.

## What landed

`src/crypto/` is now a self-contained static library target, `qflex_crypto`
(CMake alias `qflex::crypto`), with no upward dependency on `src/core`.

Public headers (kept stable on purpose):

- `include/quantum-flex/hybrid_kem.hpp`
- `include/quantum-flex/crypto_signer.hpp`
- `include/quantum-flex/crypto_hasher.hpp`
- `include/quantum-flex/crypto_shamir.hpp`

`quantum_flex_engine`, `qf_genesis_tool`, and the crypto test binaries link
that library instead of compiling `src/crypto/*.cpp` into each target. New
crypto `.cpp` files are added to `src/crypto/CMakeLists.txt` (the old
`file(GLOB ... src/crypto/*.cpp)` into the engine is gone).

`src/core/wire_framing.cpp` (QFXK) is still coordination-side transport. It
moves *with* the KEM engine in a later layer, not this one.

## Isolation check

`src/crypto/*.cpp` includes only its own headers plus OpenSSL and the C++
standard library. `LocalNode` / `IpcServer` / `BaeNode` consume
`HybridSigner` / `HybridKemEngine` / `Hasher` through those public headers.

## What this is not

- Not a move into the `qflex` repo.
- Not a `find_package` / attested artifact.
- Not deletion of the in-repo sources.
- Not a FIPS 140-3 claim.

Those are later layers: rehome → publish attested build → mycelium admits
the artifact → delete copies → lock `qflex → attested build → mycelium
admission`.

## Timing tests

`test_zeroization` and `test_dudect_timing` used to compile a second copy of
the crypto sources at `-O3` into the test binary. They now link `qflex_crypto`.
When `CMAKE_BUILD_TYPE` is unset, the library is built at `-O2` so those tests
still exercise optimized primitives rather than an accidental debug artifact.
