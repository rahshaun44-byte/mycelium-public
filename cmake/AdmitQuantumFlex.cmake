# Mycelium admits QuantumFlex. Implementation does not get a silent link.
#
# Rules:
#   1. Found prefix + verifying receipt     -> use installed package
#   2. Found prefix + mismatched receipt    -> FATAL (tamper), even in DEV
#   3. Found prefix + no receipt            -> ignore prefix in DEV; FATAL if ATTESTED
#   4. Not found                            -> add_subdirectory in DEV; FATAL if ATTESTED
#
# QUANTUMFLEX_REQUIRE_ATTESTED=ON is the production lock.

option(QUANTUMFLEX_REQUIRE_ATTESTED
    "Fail-closed: require find_package(QuantumFlex) plus a verifying admission receipt"
    OFF)

option(QUANTUMFLEX_PREFER_INSTALLED
    "Try find_package before in-tree DEV"
    OFF)

function(_quantumflex_verify_receipt receipt prefix out_ok out_reason)
    set(${out_ok} FALSE PARENT_SCOPE)
    set(${out_reason} "unverified" PARENT_SCOPE)

    if(NOT EXISTS "${receipt}")
        set(${out_reason} "missing receipt at ${receipt}" PARENT_SCOPE)
        return()
    endif()

    file(READ "${receipt}" _json)
    string(JSON _schema ERROR_VARIABLE _err GET "${_json}" schema)
    if(_err OR NOT _schema STREQUAL "QuantumFlexAdmission/v1")
        set(${out_reason} "unsupported or missing schema in ${receipt}" PARENT_SCOPE)
        return()
    endif()

    string(JSON _n ERROR_VARIABLE _err LENGTH "${_json}" artifacts)
    if(_err OR _n STREQUAL "0")
        set(${out_reason} "empty artifact set in ${receipt}" PARENT_SCOPE)
        return()
    endif()

    math(EXPR _last "${_n} - 1")
    foreach(_i RANGE ${_last})
        string(JSON _rel GET "${_json}" artifacts ${_i} path)
        string(JSON _expected GET "${_json}" artifacts ${_i} sha256)
        set(_abs "${prefix}/${_rel}")
        if(NOT EXISTS "${_abs}")
            set(${out_reason} "receipt names missing file ${_abs}" PARENT_SCOPE)
            return()
        endif()
        file(SHA256 "${_abs}" _actual)
        if(NOT _actual STREQUAL _expected)
            set(${out_reason} "sha256 mismatch for ${_rel}" PARENT_SCOPE)
            return()
        endif()
    endforeach()

    set(${out_ok} TRUE PARENT_SCOPE)
    set(${out_reason} "verified ${receipt}" PARENT_SCOPE)
endfunction()

function(_quantumflex_write_dev_receipt)
    set(_src "${CMAKE_SOURCE_DIR}/quantumflex")
    set(_files
        include/quantum-flex/hybrid_kem.hpp
        include/quantum-flex/crypto_signer.hpp
        include/quantum-flex/crypto_hasher.hpp
        include/quantum-flex/crypto_shamir.hpp
        include/quantum-flex/wire_framing.hpp
        src/crypto/crypto_hasher.cpp
        src/crypto/crypto_shamir.cpp
        src/crypto/crypto_signer.cpp
        src/crypto/hybrid_kem.cpp
        src/wire/wire_framing.cpp
    )
    set(_json "{\n")
    string(APPEND _json "  \"schema\": \"QuantumFlexAdmission/v1\",\n")
    string(APPEND _json "  \"package\": \"QuantumFlex\",\n")
    string(APPEND _json "  \"mode\": \"DEV\",\n")
    string(APPEND _json "  \"binding\": \"sha256\",\n")
    string(APPEND _json "  \"signed\": false,\n")
    string(APPEND _json "  \"note\": \"In-tree source hashes. Evidence, not authority. Not an attested install.\",\n")
    string(APPEND _json "  \"artifacts\": [\n")
    set(_first TRUE)
    foreach(_rel IN LISTS _files)
        set(_abs "${_src}/${_rel}")
        if(NOT EXISTS "${_abs}")
            continue()
        endif()
        file(SHA256 "${_abs}" _hash)
        file(SIZE "${_abs}" _size)
        if(_first)
            set(_first FALSE)
        else()
            string(APPEND _json ",\n")
        endif()
        string(APPEND _json "    {\"path\": \"quantumflex/${_rel}\", \"sha256\": \"${_hash}\", \"size_bytes\": ${_size}}")
    endforeach()
    string(APPEND _json "\n  ]\n}\n")
    file(WRITE "${CMAKE_BINARY_DIR}/QuantumFlexAdmission.dev.json" "${_json}")
endfunction()

function(quantumflex_admit)
    # DEV-only fast path: never touch an install unless explicitly requested
    if(NOT QUANTUMFLEX_REQUIRE_ATTESTED AND NOT QUANTUMFLEX_PREFER_INSTALLED)
        add_subdirectory(quantumflex)
        _quantumflex_write_dev_receipt()
        message(STATUS
            "QuantumFlex admission: DEV (unattested in-tree source). "
            "Receipt: ${CMAKE_BINARY_DIR}/QuantumFlexAdmission.dev.json")
        return()
    endif()

    find_package(QuantumFlex ${PROJECT_VERSION} QUIET CONFIG)

    if(NOT QuantumFlex_FOUND)
        if(QUANTUMFLEX_REQUIRE_ATTESTED)
            message(FATAL_ERROR
                "QuantumFlex admission FAIL-CLOSED: find_package(QuantumFlex) missed. "
                "Build the runtime (`cmake -S quantumflex`), install it, and pass CMAKE_PREFIX_PATH. "
                "In-tree add_subdirectory is not an attested path.")
        endif()
        add_subdirectory(quantumflex)
        _quantumflex_write_dev_receipt()
        message(STATUS
            "QuantumFlex admission: DEV (unattested in-tree source). "
            "Receipt: ${CMAKE_BINARY_DIR}/QuantumFlexAdmission.dev.json")
        return()
    endif()

    get_filename_component(_qf_prefix "${QuantumFlex_DIR}/../../.." ABSOLUTE)
    if(DEFINED QuantumFlex_ADMISSION_RECEIPT AND EXISTS "${QuantumFlex_ADMISSION_RECEIPT}")
        set(_receipt "${QuantumFlex_ADMISSION_RECEIPT}")
    else()
        set(_receipt "${QuantumFlex_DIR}/QuantumFlexAdmission.json")
    endif()

    # --- QF-A4: Artifact Receipt Integrity ---
    _quantumflex_verify_receipt("${_receipt}" "${_qf_prefix}" _receipt_ok _receipt_reason)

    if(NOT _receipt_ok)
        if(QUANTUMFLEX_REQUIRE_ATTESTED)
            message(FATAL_ERROR
                "QuantumFlex admission FAIL-CLOSED: artifact receipt rejected (${_receipt_reason}). "
                "Rebuild and install quantumflex so lib/cmake/QuantumFlex/QuantumFlexAdmission.json verifies.")
        endif()

        # Prefer-installed but bad receipt: do NOT add_subdirectory (targets already imported)
        message(FATAL_ERROR
            "QuantumFlex admission FAIL-CLOSED: install present but receipt invalid (${_receipt_reason}). "
            "Remove it from CMAKE_PREFIX_PATH / ~/.local, or reinstall with a valid QuantumFlexAdmission.json. "
            "In-tree fallback is impossible after find_package imported targets.")
    endif()

    # --- QF-A5: External Provenance Authority ---
    if(DEFINED QUANTUMFLEX_PROVENANCE_VERIFIER)
        set(_qf_external_verifier "${QUANTUMFLEX_PROVENANCE_VERIFIER}")
    else()
        set(_qf_external_verifier "$ENV{HOME}/.local/libexec/quantumflex/verify-provenance")
    endif()

    get_filename_component(_receipt_dir "${_receipt}" DIRECTORY)
    set(_qf_provenance "${_receipt_dir}/QuantumFlexAdmission.provenance.json")
    set(_qf_provenance_sig "${_receipt_dir}/QuantumFlexAdmission.provenance.sig")

    if(NOT EXISTS "${_qf_external_verifier}")
        message(FATAL_ERROR
            "QuantumFlex admission FAIL-CLOSED: external provenance verifier missing at ${_qf_external_verifier}")
    endif()

    if(NOT EXISTS "${_qf_provenance}")
        message(FATAL_ERROR
            "QuantumFlex admission FAIL-CLOSED: provenance manifest missing at ${_qf_provenance}")
    endif()

    if(NOT EXISTS "${_qf_provenance_sig}")
        message(FATAL_ERROR
            "QuantumFlex admission FAIL-CLOSED: provenance signature missing at ${_qf_provenance_sig}")
    endif()

    execute_process(
        COMMAND
            "${_qf_external_verifier}"
            "--prefix" "${_qf_prefix}"
            "--receipt" "${_receipt}"
            "--manifest" "${_qf_provenance}"
            "--signature" "${_qf_provenance_sig}"
        RESULT_VARIABLE _qf_prov_rc
        OUTPUT_VARIABLE _qf_prov_out
        ERROR_VARIABLE _qf_prov_err
    )

    if(NOT _qf_prov_rc EQUAL 0)
        message(FATAL_ERROR
            "QuantumFlex admission FAIL-CLOSED: external provenance verification rejected package: ${_qf_prov_out} ${_qf_prov_err}")
    endif()

    message(STATUS "QuantumFlex admission: ATTESTED (${_receipt_reason})")
    return()
endfunction()
