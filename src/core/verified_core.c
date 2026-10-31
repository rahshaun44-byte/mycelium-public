#include "quantum-flex/verified_core.h"
#include <string.h>

/* =========================================================================
   QUANTUMFLEX VERIFIED CORE REFERENCE IMPLEMENTATION
   Strictly maps to formal invariants in formal/QuantumFlex_Core.fst
   ========================================================================= */

qf_transition_result_t qf_core_step_fsm(
    qf_engine_state_t   current,
    qf_policy_verdict_t verdict,
    qf_auth_cred_t      cred,
    uint16_t            retries
) {
    qf_transition_result_t res;
    res.next_state = current;
    res.retries_out = retries;
    res.permitted = false;

    /* ABSORBING TERMINAL SINK (Theorem 1) */
    if (current == QF_STATE_COLLAPSED) {
        res.next_state = QF_STATE_COLLAPSED;
        res.retries_out = retries;
        res.permitted = false;
        return res;
    }

    /* UNINITIALIZED: Enters Active only on verified policy compliance */
    if (current == QF_STATE_UNINITIALIZED) {
        if (verdict == QF_VERDICT_COMPLIANT) {
            res.next_state = QF_STATE_ACTIVE;
            res.retries_out = 0;
            res.permitted = true;
        } else {
            res.next_state = QF_STATE_QUARANTINE;
            res.retries_out = 0;
            res.permitted = false;
        }
        return res;
    }

    /* ACTIVE: Normal operation. Violations trigger Quarantine or Collapse */
    if (current == QF_STATE_ACTIVE) {
        if (verdict == QF_VERDICT_COMPLIANT) {
            res.next_state = QF_STATE_ACTIVE;
            res.retries_out = 0;
            res.permitted = true;
        } else if (verdict == QF_VERDICT_DEGRADED || verdict == QF_VERDICT_SUPERVISOR_UNREACHABLE) {
            res.next_state = QF_STATE_QUARANTINE;
            res.retries_out = 0;
            res.permitted = false;
        } else if (verdict == QF_VERDICT_TOXIC) {
            res.next_state = QF_STATE_COLLAPSED;
            res.retries_out = 0;
            res.permitted = false;
        }
        return res;
    }

    /* QUARANTINE: Errors increment retry budget. Recovery mandates StateRecovery (Theorem 2 & 3) */
    if (current == QF_STATE_QUARANTINE) {
        if (verdict == QF_VERDICT_COMPLIANT) {
            res.next_state = QF_STATE_RECOVERY;
            res.retries_out = 0;
            res.permitted = false;
        } else if (verdict == QF_VERDICT_TOXIC) {
            res.next_state = QF_STATE_COLLAPSED;
            res.retries_out = retries;
            res.permitted = false;
        } else {
            if (retries >= QF_MAX_QUARANTINE_RETRIES) {
                res.next_state = QF_STATE_COLLAPSED;
                res.retries_out = retries;
                res.permitted = false;
            } else {
                res.next_state = QF_STATE_QUARANTINE;
                res.retries_out = (uint16_t)(retries + 1);
                res.permitted = false;
            }
        }
        return res;
    }

    /* RECOVERY: Post-quarantine clearance. Active requires operator credentials (Theorem 4) */
    if (current == QF_STATE_RECOVERY) {
        if (verdict == QF_VERDICT_COMPLIANT &&
            (cred == QF_CRED_OPERATOR_ATTESTATION || cred == QF_CRED_TWO_MAN_ATTESTATION)) {
            res.next_state = QF_STATE_ACTIVE;
            res.retries_out = 0;
            res.permitted = true;
        } else if (verdict == QF_VERDICT_TOXIC) {
            res.next_state = QF_STATE_COLLAPSED;
            res.retries_out = 0;
            res.permitted = false;
        } else {
            res.next_state = QF_STATE_RECOVERY;
            res.retries_out = 0;
            res.permitted = false;
        }
        return res;
    }

    return res;
}

qf_policy_verdict_t qf_core_eval_crypto_asset(
    qf_policy_criteria_t         policy,
    qf_crypto_asset_descriptor_t asset
) {
    if (asset.is_revoked && !policy.allow_revoked) {
        return QF_VERDICT_TOXIC;
    }
    if (policy.min_required_level == QF_CRYPTO_POST_QUANTUM_FIPS) {
        if (asset.security_level == QF_CRYPTO_POST_QUANTUM_FIPS) {
            return QF_VERDICT_COMPLIANT;
        }
        return QF_VERDICT_DEGRADED;
    }
    if (policy.min_required_level == QF_CRYPTO_STANDARD_CLASSICAL) {
        if (asset.security_level == QF_CRYPTO_LEGACY_DEPRECATED) {
            return QF_VERDICT_DEGRADED;
        }
        return QF_VERDICT_COMPLIANT;
    }
    return QF_VERDICT_COMPLIANT;
}

qf_frame_verdict_t qf_core_eval_wire_bounds(qf_wire_frame_meta_t frame) {
    qf_frame_verdict_t v;
    if (frame.chunk_len == 0 || frame.chunk_len > QF_WIRE_MAX_CHUNK_LEN) {
        v.tag = QF_WIRE_FRAME_INVALID;
        v.reason = 3;
        return v;
    }
    if (frame.total_chunks == 0 || frame.total_chunks > QF_WIRE_MAX_TOTAL_CHUNKS) {
        v.tag = QF_WIRE_FRAME_INVALID;
        v.reason = 3;
        return v;
    }
    if (frame.chunk_idx >= frame.total_chunks) {
        v.tag = QF_WIRE_FRAME_INVALID;
        v.reason = 3;
        return v;
    }
    if (frame.seq_id >= QF_WIRE_MAX_SEQ_ID) {
        v.tag = QF_WIRE_FRAME_INVALID;
        v.reason = 7;
        return v;
    }
    v.tag = QF_WIRE_FRAME_VALID;
    v.reason = 0;
    return v;
}
