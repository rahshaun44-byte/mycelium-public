cmake_minimum_required(VERSION 3.20)
project(QuantumFlex VERSION 2.2.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

find_package(Threads REQUIRED)

if(WIN32)
    message(STATUS "Configuring Quantum Flex for Windows Native (MSVC/Win32)")

    # Target Windows Event Log API
    set(WEVTAPI_LIB "wevtapi.lib")

    # PostgreSQL Library and Include paths
    set(PG_DIR "C:/Program Files/PostgreSQL/15")
    if(EXISTS "${PG_DIR}")
        set(POSTGRESQL_INCLUDE_DIR "${PG_DIR}/include")
        set(POSTGRESQL_LIB "${PG_DIR}/lib/libpq.lib")
    endif()

    add_executable(sentinel_push sentinel_push.cpp)
    target_include_directories(sentinel_push PRIVATE
        ${POSTGRESQL_INCLUDE_DIR}
        ${CMAKE_SOURCE_DIR}/include
    )
    target_link_libraries(sentinel_push PRIVATE
        ${WEVTAPI_LIB}
        ${POSTGRESQL_LIB}
        Threads::Threads
    )

    if(EXISTS "${CMAKE_SOURCE_DIR}/sentinel_smoke.cpp")
        add_executable(sentinel_smoke sentinel_smoke.cpp)
        target_link_libraries(sentinel_smoke PRIVATE ${WEVTAPI_LIB})
    endif()

else()
    message(STATUS "Configuring Quantum Flex for Linux (Systemd)")

    find_package(PkgConfig REQUIRED)
    pkg_check_modules(PQXX REQUIRED libpqxx)
    pkg_check_modules(SQLITE3 REQUIRED sqlite3)
    pkg_check_modules(SYSTEMD REQUIRED libsystemd)
    find_package(OpenSSL REQUIRED)

    file(GLOB ENGINE_CORE_SOURCES CONFIGURE_DEPENDS "src/core/*.cpp")
    file(GLOB ENGINE_CRYPTO_SOURCES CONFIGURE_DEPENDS "src/crypto/*.cpp")

    if(EXISTS "${CMAKE_SOURCE_DIR}/src/main.cpp")
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
    endif()

    add_executable(sentinel_push sentinel_push.cpp)
    target_include_directories(sentinel_push PRIVATE ${SYSTEMD_INCLUDE_DIRS} ${OPENSSL_INCLUDE_DIR})
    target_link_libraries(sentinel_push PRIVATE ${SYSTEMD_LIBRARIES} OpenSSL::SSL OpenSSL::Crypto)
endif()
