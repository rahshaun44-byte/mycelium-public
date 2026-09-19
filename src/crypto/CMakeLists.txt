# qflex_crypto — collapse step 1 (carve-out)
#
# Self-contained static library of cryptographic primitives. No dependency on
# mycelium's src/core. Consumers (the engine, genesis tool, crypto tests) link
# this target instead of compiling these .cpp files themselves.
#
# Public headers (stable; do not rename during later rehome into qflex):
#   quantum-flex/hybrid_kem.hpp
#   quantum-flex/crypto_signer.hpp
#   quantum-flex/crypto_hasher.hpp
#   quantum-flex/crypto_shamir.hpp
#
# Later layers (not this target): rehome into qflex, publish an attested
# artifact, find_package from mycelium, delete the in-repo copies.

add_library(qflex_crypto STATIC
    crypto_hasher.cpp
    crypto_shamir.cpp
    crypto_signer.cpp
    hybrid_kem.cpp
)
add_library(qflex::crypto ALIAS qflex_crypto)

set_target_properties(qflex_crypto PROPERTIES
    OUTPUT_NAME qflex_crypto
    POSITION_INDEPENDENT_CODE ON
    CXX_STANDARD 20
    CXX_STANDARD_REQUIRED ON
)

target_include_directories(qflex_crypto
    PUBLIC
        $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

# hybrid_kem.hpp includes <openssl/evp.h> in the public API (MLKem768Engine).
target_link_libraries(qflex_crypto
    PUBLIC
        OpenSSL::Crypto
        OpenSSL::SSL
)

# Single compilation of the primitives. Timing/zeroization tests previously
# compiled a second copy of these sources at -O3 into the test binary; they
# now link this library. When CMAKE_BUILD_TYPE is unset (the common local
# invocation), apply -O2 so those tests still exercise optimized code rather
# than an accidental debug artifact.
if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    target_compile_options(qflex_crypto PRIVATE -O2)
endif()
