#include "quantum-flex/verified_core.h"
#include <openssl/crypto.h>
#include <string.h>

/* =========================================================================
   QUANTUMFLEX VERIFIED CORE REFERENCE IMPLEMENTATION
   Strictly maps to formal invariants in formal/QuantumFlex_Core.fst
   ========================================================================= */

qf_verdict_t qf_core_eval_transition(
    qf_engine_state_t current,
    qf_engine_state_t target,
    qf_auth_cred_t cred
) {
    /* Boot / Genesis */
    if (current == QF_STATE_UNINITIALIZED && target == QF_STATE_LOCKED) {
        return QF_VERDICT_ALLOW;
    }

    /* Unseal / Activation */
    if (current == QF_STATE_LOCKED && target == QF_STATE_ACTIVE) {
        if (cred == QF_CRED_SHAMIR_THRESHOLD || cred == QF_CRED_MTLS_CERT) {
            return QF_VERDICT_ALLOW;
        }
        return QF_VERDICT_DENY; /* Missing auth cannot unlock */
    }

    /* Active -> Quarantine triggered on any invariant violation */
    if (current == QF_STATE_ACTIVE && target == QF_STATE_QUARANTINE) {
        return QF_VERDICT_ALLOW;
    }

    /* Active -> Locked on operator unmount */
    if (current == QF_STATE_ACTIVE && target == QF_STATE_LOCKED) {
        if (cred == QF_CRED_MTLS_CERT) {
            return QF_VERDICT_ALLOW;
        }
        return QF_VERDICT_DENY;
    }

    /* ABSORBING QUARANTINE SINK (Theorem 1):
       Quarantine can NEVER transition directly to Active.
       Quarantine can ONLY transition to Recovery via Two-Man Attestation. */
    if (current == QF_STATE_QUARANTINE && target == QF_STATE_RECOVERY) {
        if (cred == QF_CRED_TWO_MAN_ATTESTATION) {
            return QF_VERDICT_ALLOW;
        }
        return QF_VERDICT_DENY;
    }

    /* Recovery -> Locked upon complete zeroization and ledger attestation */
    if (current == QF_STATE_RECOVERY && target == QF_STATE_LOCKED) {
        if (cred == QF_CRED_MTLS_CERT) {
            return QF_VERDICT_ALLOW;
        }
        return QF_VERDICT_DENY;
    }

    /* All other transitions strictly forbidden */
    return QF_VERDICT_DENY;
}

qf_verdict_t qf_core_eval_pqc_proposal(
    qf_pqc_profile_t profile,
    qf_pqc_alg_t proposal
) {
    if (profile == QF_PROFILE_STRICT_FIPS203) {
        /* Strictly FIPS 203 approved primitives only; zero downgrade */
        if (proposal == QF_ALG_ML_KEM_768 || proposal == QF_ALG_ML_KEM_1024) {
            return QF_VERDICT_ALLOW;
        }
        return QF_VERDICT_DENY;
    }

    if (profile == QF_PROFILE_AGILE_TRANSITION) {
        if (proposal == QF_ALG_ML_KEM_768 ||
            proposal == QF_ALG_ML_KEM_1024 ||
            proposal == QF_ALG_FRODO_976) {
            return QF_VERDICT_ALLOW;
        }
        return QF_VERDICT_DENY;
    }

    /* Legacy or unknown profiles fail closed */
    return QF_VERDICT_DENY;
}

qf_wire_error_t qf_core_eval_wire_bounds(
    uint16_t chunk_len,
    uint16_t chunk_idx,
    uint16_t total_chunks,
    uint32_t seq_id
) {
    /* Chunk length bounds: 1 <= chunk_len <= 1450 */
    if (chunk_len == 0 || chunk_len > QF_WIRE_MAX_CHUNK_LEN) {
        return QF_WIRE_ERR_CHUNK_BOUNDS;
    }

    /* Total chunks bounds: 1 <= total_chunks <= 64 */
    if (total_chunks == 0 || total_chunks > QF_WIRE_MAX_TOTAL_CHUNKS) {
        return QF_WIRE_ERR_CHUNK_BOUNDS;
    }

    /* Index bound: 0 <= chunk_idx < total_chunks */
    if (chunk_idx >= total_chunks) {
        return QF_WIRE_ERR_CHUNK_BOUNDS;
    }

    /* Monotonic sequence bound: no silent wraparound past 2^32 - 2 */
    if (seq_id >= QF_WIRE_MAX_SEQ_ID) {
        return QF_WIRE_ERR_SEQ_EXHAUSTED;
    }

    return QF_WIRE_OK;
}

static const uint32_t crc32_table[16] = {
    0x00000000, 0x1DB71064, 0x3B6E20C8, 0x26D930AC,
    0x76DC4190, 0x6B6B51F4, 0x4DB26158, 0x5005713C,
    0xEDB88320, 0xF00F9344, 0xD6D6A3E8, 0xCB61B38C,
    0x9B64C2B0, 0x86D3D2D4, 0xA00AE278, 0xBDBDF21C
};

uint32_t qf_core_compute_crc32(const uint8_t *data, size_t len) {
    if (!data || len == 0) {
        return 0;
    }
    uint32_t crc = 0xFFFFFFFFU;
    for (size_t i = 0; i < len; ++i) {
        uint8_t byte = data[i];
        crc = (crc >> 4) ^ crc32_table[(crc ^ (byte & 0x0F)) & 0x0F];
        crc = (crc >> 4) ^ crc32_table[(crc ^ (byte >> 4)) & 0x0F];
    }
    return ~crc;
}

void qf_core_zeroize(void *buf, size_t len) {
    if (!buf || len == 0) {
        return;
    }
#if defined(OPENSSL_VERSION_NUMBER)
    OPENSSL_cleanse(buf, len);
#else
    volatile unsigned char *p = (volatile unsigned char *)buf;
    while (len--) {
        *p++ = 0;
    }
    __asm__ __volatile__("" : : "r"(buf) : "memory");
#endif
}
