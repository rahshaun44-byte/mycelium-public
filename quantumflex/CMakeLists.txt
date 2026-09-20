# QuantumFlex runtime — independently buildable crypto + QFXK wire package.
#
# Standalone:
#   cmake -S quantumflex -B quantumflex/build -DOPENSSL_ROOT_DIR=/opt/openssl-3.5
#   cmake --build quantumflex/build
#
# Consumed by mycelium via add_subdirectory (default) or find_package(QuantumFlex)
# if an installed/attested copy is on CMAKE_PREFIX_PATH.

cmake_minimum_required(VERSION 3.20)

if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
    project(quantumflex VERSION 2.1.0 LANGUAGES CXX)
    set(QUANTUMFLEX_STANDALONE ON)
else()
    set(QUANTUMFLEX_STANDALONE OFF)
    if(NOT PROJECT_VERSION)
        set(PROJECT_VERSION 2.1.0)
    endif()
endif()

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

option(QUANTUMFLEX_BUILD_TESTS "Build QuantumFlex crypto and wire tests" ON)
option(QUANTUMFLEX_INSTALL "Install QuantumFlex CMake package" ${QUANTUMFLEX_STANDALONE})

# Keep test binaries next to the engine in a mycelium build; in a standalone
# build CMAKE_BINARY_DIR is quantumflex/build.
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR})

if(NOT OpenSSL_FOUND)
    find_package(OpenSSL 3.5 REQUIRED)
endif()

# ── crypto primitives ──────────────────────────────────────────────────────
add_library(quantumflex_crypto STATIC
    src/crypto/crypto_hasher.cpp
    src/crypto/crypto_shamir.cpp
    src/crypto/crypto_signer.cpp
    src/crypto/hybrid_kem.cpp
)
add_library(QuantumFlex::crypto ALIAS quantumflex_crypto)
add_library(qflex::crypto ALIAS quantumflex_crypto)

set_target_properties(quantumflex_crypto PROPERTIES
    OUTPUT_NAME quantumflex_crypto
    POSITION_INDEPENDENT_CODE ON
    EXPORT_NAME crypto
)

target_include_directories(quantumflex_crypto
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

# hybrid_kem.hpp includes <openssl/evp.h> in the public API (MLKem768Engine).
target_link_libraries(quantumflex_crypto
    PUBLIC
        OpenSSL::Crypto
        OpenSSL::SSL
)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    target_compile_options(quantumflex_crypto PRIVATE -O2)
endif()

# ── QFXK wire codec (moves with the KEM; no verified_core / src/core dep) ──
add_library(quantumflex_wire STATIC
    src/wire/wire_framing.cpp
)
add_library(QuantumFlex::wire ALIAS quantumflex_wire)

set_target_properties(quantumflex_wire PROPERTIES
    OUTPUT_NAME quantumflex_wire
    POSITION_INDEPENDENT_CODE ON
    EXPORT_NAME wire
)

target_include_directories(quantumflex_wire
    PUBLIC
        $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
        $<INSTALL_INTERFACE:include>
)

target_link_libraries(quantumflex_wire
    PUBLIC
        OpenSSL::Crypto
)

# Convenience: crypto + wire. Mycelium's engine links this one target.
add_library(quantumflex_runtime INTERFACE)
add_library(QuantumFlex::runtime ALIAS quantumflex_runtime)
target_link_libraries(quantumflex_runtime INTERFACE quantumflex_crypto quantumflex_wire)

# ── tests ──────────────────────────────────────────────────────────────────
if(QUANTUMFLEX_BUILD_TESTS)
    function(quantumflex_add_test name)
        add_executable(${name} ${ARGN})
        target_include_directories(${name} PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)
        target_link_libraries(${name} PRIVATE QuantumFlex::runtime)
        target_compile_options(${name} PRIVATE -UNDEBUG)
    endfunction()

    quantumflex_add_test(test_hybrid_kem tests/test_hybrid_kem.cpp)
    quantumflex_add_test(test_known_answer_vectors tests/test_known_answer_vectors.cpp)
    quantumflex_add_test(test_wire_framing tests/test_wire_framing.cpp)
    quantumflex_add_test(test_wire_fuzz_negative tests/test_wire_fuzz_negative.cpp)
    quantumflex_add_test(test_mlkem768 tests/test_mlkem768.cpp)

    quantumflex_add_test(test_zeroization tests/test_zeroization.cpp)
    target_compile_options(test_zeroization PRIVATE -O3)

    quantumflex_add_test(test_dudect_timing tests/test_dudect_timing.cpp)
    target_compile_options(test_dudect_timing PRIVATE -O3)
endif()

# ── install / find_package ─────────────────────────────────────────────────
if(QUANTUMFLEX_INSTALL)
    include(CMakePackageConfigHelpers)
    include(GNUInstallDirs)

    install(TARGETS quantumflex_crypto quantumflex_wire
        EXPORT QuantumFlexTargets
        ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
        LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
        INCLUDES DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
    )

    install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})

    install(EXPORT QuantumFlexTargets
        FILE QuantumFlexTargets.cmake
        NAMESPACE QuantumFlex::
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/QuantumFlex
    )

    configure_package_config_file(
        ${CMAKE_CURRENT_SOURCE_DIR}/cmake/QuantumFlexConfig.cmake.in
        ${CMAKE_CURRENT_BINARY_DIR}/QuantumFlexConfig.cmake
        INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/QuantumFlex
    )

    write_basic_package_version_file(
        ${CMAKE_CURRENT_BINARY_DIR}/QuantumFlexConfigVersion.cmake
        VERSION ${PROJECT_VERSION}
        COMPATIBILITY SameMajorVersion
    )

    install(FILES
        ${CMAKE_CURRENT_BINARY_DIR}/QuantumFlexConfig.cmake
        ${CMAKE_CURRENT_BINARY_DIR}/QuantumFlexConfigVersion.cmake
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/QuantumFlex
    )

    # Hash-bind the installed libs+headers. Unsigned; QF-A5 signing is a
    # separate operator ceremony with the external release key.
    set(QF_SOURCE_COMMIT "UNKNOWN")
    execute_process(
        COMMAND git rev-parse HEAD
        WORKING_DIRECTORY ${CMAKE_SOURCE_DIR}
        OUTPUT_VARIABLE QF_SOURCE_COMMIT
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
    )
    configure_file(
        ${CMAKE_CURRENT_SOURCE_DIR}/cmake/EmitAdmission.cmake.in
        ${CMAKE_CURRENT_BINARY_DIR}/EmitAdmission.cmake
        @ONLY
    )
    install(SCRIPT ${CMAKE_CURRENT_BINARY_DIR}/EmitAdmission.cmake)
endif()
