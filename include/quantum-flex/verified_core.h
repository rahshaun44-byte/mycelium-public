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
     - KaRaMeL Machine Extraction: QF-A4 Extracted & Verified (src/core/generated/)
   ========================================================================= */

/* --- Finite State Machine Invariants --- */
typedef enum {
    QF_STATE_UNINITIALIZED = 0,
    QF_STATE_ACTIVE        = 1,
    QF_STATE_QUARANTINE    = 2,
    QF_STATE_RECOVERY      = 3,
    QF_STATE_COLLAPSED     = 4
} qf_engine_state_t;

typedef enum {
    QF_VERDICT_COMPLIANT              = 0,
    QF_VERDICT_DEGRADED               = 1,
    QF_VERDICT_TOXIC                  = 2,
    QF_VERDICT_SUPERVISOR_UNREACHABLE = 3
} qf_policy_verdict_t;

typedef enum {
    QF_CRED_NONE                 = 0,
    QF_CRED_OPERATOR_ATTESTATION = 1,
    QF_CRED_TWO_MAN_ATTESTATION  = 2
} qf_auth_cred_t;

typedef struct {
    qf_engine_state_t next_state;
    uint16_t          retries_out;
    bool              permitted;
} qf_transition_result_t;

#define QF_MAX_QUARANTINE_RETRIES 5

/* --- Decoupled Cryptographic Policy Invariants --- */
typedef enum {
    QF_CRYPTO_LEGACY_DEPRECATED  = 0,
    QF_CRYPTO_STANDARD_CLASSICAL = 1,
    QF_CRYPTO_POST_QUANTUM_FIPS  = 2
} qf_crypto_level_t;

typedef struct {
    uint16_t          asset_id;
    qf_crypto_level_t security_level;
    bool              is_revoked;
} qf_crypto_asset_descriptor_t;

typedef struct {
    qf_crypto_level_t min_required_level;
    bool              allow_revoked;
} qf_policy_criteria_t;

/* --- Wire Protocol Constants & Bounds --- */
#define QF_WIRE_MAX_CHUNK_LEN      1450
#define QF_WIRE_MAX_TOTAL_CHUNKS   64
#define QF_WIRE_MAX_SEQ_ID         0xFFFFFFFEU

typedef enum {
    QF_WIRE_FRAME_VALID   = 0,
    QF_WIRE_FRAME_INVALID = 1
} qf_frame_verdict_tag_t;

typedef struct {
    qf_frame_verdict_tag_t tag;
    uint16_t               reason;
} qf_frame_verdict_t;

typedef struct {
    uint16_t chunk_len;
    uint16_t chunk_idx;
    uint16_t total_chunks;
    uint32_t seq_id;
} qf_wire_frame_meta_t;

/* --- Core Invariant Verification APIs --- */

/**
 * Validates state transition legality according to Theorems 1-5.
 * Enforces absorbing collapse sink, quarantine recovery routing, and operator credentials.
 */
qf_transition_result_t qf_core_step_fsm(
    qf_engine_state_t   current,
    qf_policy_verdict_t verdict,
    qf_auth_cred_t      cred,
    uint16_t            retries
);

/**
 * Validates cryptographic asset compliance according to Theorems 6-7.
 * Enforces fail-closed rejection of revoked or downgraded primitives.
 */
qf_policy_verdict_t qf_core_eval_crypto_asset(
    qf_policy_criteria_t         policy,
    qf_crypto_asset_descriptor_t asset
);

/**
 * Validates wire frame bounds according to Theorems 8-9.
 * Enforces chunk limits and strictly forbids silent sequence wraparound.
 */
qf_frame_verdict_t qf_core_eval_wire_bounds(
    qf_wire_frame_meta_t frame
);

#ifdef __cplusplus
}
#endif

#endif /* QUANTUM_FLEX_VERIFIED_CORE_H */
