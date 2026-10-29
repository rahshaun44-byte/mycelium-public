cmake_minimum_required(VERSION 3.20)
project(QuantumFlex VERSION 2.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(PkgConfig REQUIRED)
pkg_check_modules(PQXX REQUIRED libpqxx)
pkg_check_modules(SQLITE3 REQUIRED sqlite3)
pkg_check_modules(SYSTEMD REQUIRED libsystemd)

find_package(OpenSSL 3.5 REQUIRED)
find_package(Threads REQUIRED)

# Collapse step 3: mycelium admits QuantumFlex. Tampered prefixes never link.
# QUANTUMFLEX_REQUIRE_ATTESTED=ON is the production lock (no in-tree fallback).
include("${CMAKE_SOURCE_DIR}/cmake/AdmitQuantumFlex.cmake")
quantumflex_admit()

file(GLOB ENGINE_CORE_SOURCES CONFIGURE_DEPENDS "src/core/*.cpp" "src/core/*.c")

add_executable(quantum_flex_engine
    src/main.cpp
    ${ENGINE_CORE_SOURCES}
)

target_include_directories(quantum_flex_engine PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${PQXX_INCLUDE_DIRS}
    ${SQLITE3_INCLUDE_DIRS}
    ${OPENSSL_INCLUDE_DIR}
    ${SYSTEMD_INCLUDE_DIRS}
)

target_link_libraries(quantum_flex_engine PRIVATE
    QuantumFlex::runtime
    ${PQXX_LIBRARIES}
    ${SQLITE3_LIBRARIES}
    OpenSSL::SSL
    OpenSSL::Crypto
    Threads::Threads
    ${SYSTEMD_LIBRARIES}
)

add_executable(sentinel_push sentinel_push.cpp)
target_include_directories(sentinel_push PRIVATE ${SYSTEMD_INCLUDE_DIRS} ${OPENSSL_INCLUDE_DIR})
target_link_libraries(sentinel_push PRIVATE ${SYSTEMD_LIBRARIES} OpenSSL::SSL OpenSSL::Crypto)

add_executable(qf_genesis_tool
    tools/genesis_tool.cpp
)
target_include_directories(qf_genesis_tool PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${OPENSSL_INCLUDE_DIR}
)
target_link_libraries(qf_genesis_tool PRIVATE QuantumFlex::crypto)

# Coordination-only test (formal C ABI). Crypto/wire tests live under quantumflex/.
add_executable(test_verified_core
    tools/test_verified_core.cpp
    src/core/verified_core.c
)
target_include_directories(test_verified_core PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${OPENSSL_INCLUDE_DIR}
)
target_link_libraries(test_verified_core PRIVATE OpenSSL::Crypto)

# KaRaMeL Differential Verification Test (QF-A4)
find_program(KRML_EXE NAMES krml HINTS /home/quant/.local/bin)
if(KRML_EXE)
    execute_process(
        COMMAND ${KRML_EXE} -locate-include
        OUTPUT_VARIABLE KRML_INC_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    execute_process(
        COMMAND ${KRML_EXE} -locate-krmllib
        OUTPUT_VARIABLE KRML_LIB_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    if(EXISTS "${KRML_INC_DIR}" AND EXISTS "${CMAKE_SOURCE_DIR}/src/core/generated/QuantumFlex_Core.c")
        add_executable(test_differential_core
            tools/test_differential_core.cpp
            src/core/verified_core.c
            src/core/generated/QuantumFlex_Core.c
        )
        target_include_directories(test_differential_core PRIVATE
            ${CMAKE_SOURCE_DIR}/include
            ${CMAKE_SOURCE_DIR}/src/core/generated
            ${OPENSSL_INCLUDE_DIR}
        )
        target_include_directories(test_differential_core SYSTEM PRIVATE
            ${KRML_INC_DIR}
            ${KRML_LIB_DIR}/dist/minimal
        )
        target_compile_definitions(test_differential_core PRIVATE _DEFAULT_SOURCE _GNU_SOURCE)
        target_link_libraries(test_differential_core PRIVATE OpenSSL::Crypto)
    endif()
endif()
