#ifndef QUANTUM_FLEX_VERIFIED_CORE_H
#define QUANTUM_FLEX_VERIFIED_CORE_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* =========================================================================
   QUANTUMFLEX VERIFIED CORE C ABI
   Formally Specified Invariants with Tested C Enforcement Implementation
   
   Assurance Mapping:
     - Property Specification: QF-A3 Formally Specified (formal/QuantumFlex_Core.fst)
     - C ABI & Implementation: QF-A1 Tested / QF-A2 Policy-Enforced
     - KaRaMeL Machine Extraction: NULL (Gap admitted; manual C reference)
   ========================================================================= */

/* --- Finite State Machine Invariants --- */
typedef enum {
    QF_STATE_UNINITIALIZED = 0,
    QF_STATE_LOCKED        = 1,
    QF_STATE_ACTIVE        = 2,
    QF_STATE_QUARANTINE    = 3,
    QF_STATE_RECOVERY      = 4
} qf_engine_state_t;

typedef enum {
    QF_CRED_NONE                = 0,
    QF_CRED_MTLS_CERT           = 1,
    QF_CRED_SHAMIR_THRESHOLD    = 2,
    QF_CRED_TWO_MAN_ATTESTATION = 3
} qf_auth_cred_t;

typedef enum {
    QF_VERDICT_DENY  = 0,
    QF_VERDICT_ALLOW = 1
} qf_verdict_t;

/* --- Cryptographic Agility & Strict FIPS 203 Invariants --- */
typedef enum {
    QF_PROFILE_STRICT_FIPS203   = 1,
    QF_PROFILE_AGILE_TRANSITION = 2,
    QF_PROFILE_LEGACY_CLASSICAL = 3
} qf_pqc_profile_t;

typedef enum {
    QF_ALG_ML_KEM_768  = 1,
    QF_ALG_ML_KEM_1024 = 2,
    QF_ALG_FRODO_976   = 3,
    QF_ALG_X25519      = 4,
    QF_ALG_UNKNOWN     = 255
} qf_pqc_alg_t;

/* --- Wire Protocol Constants & Bounds --- */
#define QF_WIRE_MAX_CHUNK_LEN      1450
#define QF_WIRE_MAX_TOTAL_CHUNKS   64
#define QF_WIRE_MAX_SEQ_ID         0xFFFFFFFEU /* 2^32 - 2, no silent wraparound */
#define QF_WIRE_MAGIC_BE           0x5146584BU /* "QFXK" */

typedef enum {
    QF_WIRE_OK                 = 0,
    QF_WIRE_ERR_MAGIC          = 1,
    QF_WIRE_ERR_LENGTH         = 2,
    QF_WIRE_ERR_CHUNK_BOUNDS   = 3,
    QF_WIRE_ERR_CRC_MISMATCH   = 4,
    QF_WIRE_ERR_TIMEOUT        = 5,
    QF_WIRE_ERR_TABLE_FULL     = 6,
    QF_WIRE_ERR_SEQ_EXHAUSTED  = 7,
    QF_WIRE_ERR_DECAP_FAILED   = 8
} qf_wire_error_t;

/* --- Core Invariant Verification APIs --- */

/**
 * Validates state transition legality according to Theorem 1 & 2.
 * Enforces absorbing quarantine sink and mandatory credentials.
 */
qf_verdict_t qf_core_eval_transition(
    qf_engine_state_t current,
    qf_engine_state_t target,
    qf_auth_cred_t cred
);

/**
 * Validates PQC algorithm negotiation according to Theorem 3.
 * Enforces strict FIPS 203 downgrade impossibility.
 */
qf_verdict_t qf_core_eval_pqc_proposal(
    qf_pqc_profile_t profile,
    qf_pqc_alg_t proposal
);

/**
 * Validates wire frame bounds according to Theorem 4 & 5.
 * Enforces chunk limits and strictly forbids silent sequence wraparound.
 */
qf_wire_error_t qf_core_eval_wire_bounds(
    uint16_t chunk_len,
    uint16_t chunk_idx,
    uint16_t total_chunks,
    uint32_t seq_id
);

/**
 * Computes standard IEEE 802.3 CRC32 checksum.
 */
uint32_t qf_core_compute_crc32(const uint8_t *data, size_t len);

/**
 * Memory zeroization with compiler barrier.
 */
void qf_core_zeroize(void *buf, size_t len);

#ifdef __cplusplus
}
#endif

#endif /* QUANTUM_FLEX_VERIFIED_CORE_H */
