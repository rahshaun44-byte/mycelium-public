cmake_minimum_required(VERSION 3.20)
project(QuantumFlex VERSION 2.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(PkgConfig REQUIRED)
pkg_check_modules(PQXX REQUIRED libpqxx)
pkg_check_modules(SQLITE3 REQUIRED sqlite3)
pkg_check_modules(SYSTEMD REQUIRED libsystemd)

find_package(OpenSSL REQUIRED)
find_package(Threads REQUIRED)

file(GLOB ENGINE_CORE_SOURCES CONFIGURE_DEPENDS "src/core/*.cpp")
file(GLOB ENGINE_CRYPTO_SOURCES CONFIGURE_DEPENDS "src/crypto/*.cpp")

add_executable(quantum_flex_engine
    src/main.cpp
    ${ENGINE_CORE_SOURCES}
    ${ENGINE_CRYPTO_SOURCES}
)

target_include_directories(quantum_flex_engine PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${PQXX_INCLUDE_DIRS}
    ${SQLITE3_INCLUDE_DIRS}
    ${OPENSSL_INCLUDE_DIR}
    ${SYSTEMD_INCLUDE_DIRS}
)

target_link_libraries(quantum_flex_engine PRIVATE
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
    src/crypto/crypto_shamir.cpp
)
target_include_directories(qf_genesis_tool PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${OPENSSL_INCLUDE_DIR}
)
target_link_libraries(qf_genesis_tool PRIVATE OpenSSL::Crypto)

# ── Test Executables ────────────────────────────────────────────────────────
add_executable(test_hybrid_kem
    tools/test_hybrid_kem.cpp
    src/crypto/hybrid_kem.cpp
)
target_include_directories(test_hybrid_kem PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${OPENSSL_INCLUDE_DIR}
)
target_link_libraries(test_hybrid_kem PRIVATE OpenSSL::Crypto)

add_executable(test_wire_framing
    tools/test_wire_framing.cpp
    src/core/wire_framing.cpp
)
target_include_directories(test_wire_framing PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${OPENSSL_INCLUDE_DIR}
)
target_link_libraries(test_wire_framing PRIVATE OpenSSL::Crypto)

add_executable(test_wire_fuzz_negative
    tools/test_wire_fuzz_negative.cpp
    src/core/wire_framing.cpp
)
target_include_directories(test_wire_fuzz_negative PRIVATE
    ${CMAKE_SOURCE_DIR}/include
    ${OPENSSL_INCLUDE_DIR}
)
target_link_libraries(test_wire_fuzz_negative PRIVATE OpenSSL::Crypto)
