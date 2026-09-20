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
