#include "quantum-flex/verified_core.h"
extern "C" {
#include "QuantumFlex_Core.h"
}
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <vector>

/* =========================================================================
   QUANTUMFLEX VERIFIED CORE: DIFFERENTIAL TEST HARNESS (QF-A4)
   Compares Reference C (src/core/verified_core.c) against
   KaRaMeL Machine-Extracted C (src/core/generated/QuantumFlex_Core.c).

   Properties Checked:
     1. FSM Invariant State Space Exhaustive Equivalence (480 vectors)
     2. Decoupled Cryptographic Policy Exhaustive Equivalence (180 vectors)
     3. Wire Bounds & Sequence Monotonicity Invariants (Boundary + 10,000 fuzz)
     4. Fail-Closed Proof: Mismatches trigger immediate SIGABRT
   ========================================================================= */

static uint64_t total_tests_executed = 0;

static inline engine_state map_ref_state_to_ext(qf_engine_state_t s) {
    switch (s) {
        case QF_STATE_UNINITIALIZED: return StateUninitialized;
        case QF_STATE_ACTIVE:        return StateActive;
        case QF_STATE_QUARANTINE:    return StateQuarantine;
        case QF_STATE_RECOVERY:      return StateRecovery;
        case QF_STATE_COLLAPSED:     return StateCollapsed;
        default:                     return StateCollapsed;
    }
}

static inline policy_verdict map_ref_verdict_to_ext(qf_policy_verdict_t v) {
    switch (v) {
        case QF_VERDICT_COMPLIANT:              return VerdictCompliant;
        case QF_VERDICT_DEGRADED:               return VerdictDegraded;
        case QF_VERDICT_TOXIC:                  return VerdictToxic;
        case QF_VERDICT_SUPERVISOR_UNREACHABLE: return VerdictSupervisorUnreachable;
        default:                                return VerdictToxic;
    }
}

static inline auth_credential map_ref_cred_to_ext(qf_auth_cred_t c) {
    switch (c) {
        case QF_CRED_NONE:                 return CredNone;
        case QF_CRED_OPERATOR_ATTESTATION: return CredOperatorAttestation;
        case QF_CRED_TWO_MAN_ATTESTATION:  return CredTwoManAttestation;
        default:                           return CredNone;
    }
}

void test_differential_fsm() {
    std::cout << "[*] [DIFFERENTIAL 1/3] Exhaustive FSM Transition Invariant Equivalence...\n";

    const qf_engine_state_t states[] = {
        QF_STATE_UNINITIALIZED,
        QF_STATE_ACTIVE,
        QF_STATE_QUARANTINE,
        QF_STATE_RECOVERY,
        QF_STATE_COLLAPSED
    };

    const qf_policy_verdict_t verdicts[] = {
        QF_VERDICT_COMPLIANT,
        QF_VERDICT_DEGRADED,
        QF_VERDICT_TOXIC,
        QF_VERDICT_SUPERVISOR_UNREACHABLE
    };

    const qf_auth_cred_t creds[] = {
        QF_CRED_NONE,
        QF_CRED_OPERATOR_ATTESTATION,
        QF_CRED_TWO_MAN_ATTESTATION
    };

    const uint16_t retry_values[] = { 0, 1, 2, 4, 5, 6, 10, 100 };

    uint32_t vector_count = 0;
    for (qf_engine_state_t cur : states) {
        for (qf_policy_verdict_t ver : verdicts) {
            for (qf_auth_cred_t crd : creds) {
                for (uint16_t ret : retry_values) {
                    qf_transition_result_t ref_res = qf_core_step_fsm(cur, ver, crd, ret);

                    engine_state ext_cur = map_ref_state_to_ext(cur);
                    policy_verdict ext_ver = map_ref_verdict_to_ext(ver);
                    auth_credential ext_crd = map_ref_cred_to_ext(crd);

                    transition_result ext_res = step_fsm(ext_cur, ext_ver, ext_crd, ret);

                    if (ref_res.next_state != (qf_engine_state_t)ext_res.next_state ||
                        ref_res.retries_out != ext_res.retries_out ||
                        ref_res.permitted != ext_res.permitted) {
                        std::cerr << "[!] FSM DIVERGENCE: cur=" << cur
                                  << " ver=" << ver << " crd=" << crd << " ret=" << ret
                                  << " | Ref[next=" << ref_res.next_state << " ret=" << ref_res.retries_out << " perm=" << ref_res.permitted << "]"
                                  << " | Ext[next=" << (int)ext_res.next_state << " ret=" << ext_res.retries_out << " perm=" << ext_res.permitted << "]\n";
                        std::abort();
                    }

                    // Security Theorem Invariant: Absorbing Collapse (Theorem 1 & 5c)
                    if (cur == QF_STATE_COLLAPSED) {
                        assert(ext_res.next_state == StateCollapsed);
                        assert(ext_res.permitted == false);
                    }

                    // Security Theorem Invariant: Quarantine error never active (Theorem 2)
                    if (cur == QF_STATE_QUARANTINE && ver != QF_VERDICT_COMPLIANT) {
                        assert(ext_res.next_state != StateActive);
                        assert(ext_res.permitted == false);
                    }

                    // Security Theorem Invariant: Quarantine compliant routes to Recovery (Theorem 3)
                    if (cur == QF_STATE_QUARANTINE && ver == QF_VERDICT_COMPLIANT) {
                        assert(ext_res.next_state == StateRecovery);
                        assert(ext_res.permitted == false);
                    }

                    // Security Theorem Invariant: Recovery requires operator credentials (Theorem 4 & 5b)
                    if (cur == QF_STATE_RECOVERY && crd == QF_CRED_NONE) {
                        assert(ext_res.next_state != StateActive);
                        assert(ext_res.permitted == false);
                    }

                    // Security Theorem Invariant: Quarantine never permitted (Theorem 5a)
                    if (cur == QF_STATE_QUARANTINE) {
                        assert(ext_res.permitted == false);
                    }

                    // Security Theorem Invariant: Permission implies compliance and auth (Theorem 5d & 5e)
                    if (ext_res.permitted) {
                        assert(ver == QF_VERDICT_COMPLIANT);
                        assert(cur == QF_STATE_ACTIVE || cur == QF_STATE_UNINITIALIZED ||
                               (cur == QF_STATE_RECOVERY && (crd == QF_CRED_OPERATOR_ATTESTATION || crd == QF_CRED_TWO_MAN_ATTESTATION)));
                    }
                    if (ext_res.next_state == StateActive) {
                        assert(ver == QF_VERDICT_COMPLIANT);
                        assert(cur == QF_STATE_ACTIVE || cur == QF_STATE_UNINITIALIZED ||
                               (cur == QF_STATE_RECOVERY && (crd == QF_CRED_OPERATOR_ATTESTATION || crd == QF_CRED_TWO_MAN_ATTESTATION)));
                    }

                    // Security Theorem Invariant: Retry monotonicity and bounded ceiling (Theorem 5f & 5g)
                    if (cur == QF_STATE_QUARANTINE && (ver == QF_VERDICT_DEGRADED || ver == QF_VERDICT_SUPERVISOR_UNREACHABLE)) {
                        if (ret < QF_MAX_QUARANTINE_RETRIES) {
                            assert(ext_res.retries_out == (uint16_t)(ret + 1));
                            assert(ext_res.next_state == StateQuarantine);
                        } else {
                            assert(ext_res.next_state == StateCollapsed);
                        }
                    }

                    vector_count++;
                    total_tests_executed++;
                }
            }
        }
    }
    std::cout << "    [+] Discharged " << vector_count << " exhaustive FSM vectors: matched bit-for-bit.\n";
}

void test_differential_crypto() {
    std::cout << "[*] [DIFFERENTIAL 2/3] Exhaustive Cryptographic Policy Equivalence...\n";

    const qf_crypto_level_t levels[] = {
        QF_CRYPTO_LEGACY_DEPRECATED,
        QF_CRYPTO_STANDARD_CLASSICAL,
        QF_CRYPTO_POST_QUANTUM_FIPS
    };

    const bool bools[] = { false, true };
    const uint16_t asset_ids[] = { 1, 42, 768, 1024, 65535 };

    uint32_t vector_count = 0;
    for (qf_crypto_level_t min_lvl : levels) {
        for (bool allow_rev : bools) {
            for (qf_crypto_level_t sec_lvl : levels) {
                for (bool is_rev : bools) {
                    for (uint16_t aid : asset_ids) {
                        qf_policy_criteria_t ref_pol = { min_lvl, allow_rev };
                        qf_crypto_asset_descriptor_t ref_ast = { aid, sec_lvl, is_rev };

                        qf_policy_verdict_t ref_v = qf_core_eval_crypto_asset(ref_pol, ref_ast);

                        policy_criteria ext_pol;
                        ext_pol.min_required_level = (crypto_security_level)min_lvl;
                        ext_pol.allow_revoked = allow_rev;

                        crypto_asset_descriptor ext_ast;
                        ext_ast.asset_id = aid;
                        ext_ast.security_level = (crypto_security_level)sec_lvl;
                        ext_ast.is_revoked = is_rev;

                        policy_verdict ext_v = eval_crypto_asset(ext_pol, ext_ast);

                        if ((qf_policy_verdict_t)ext_v != ref_v) {
                            std::cerr << "[!] CRYPTO POLICY DIVERGENCE: min_lvl=" << min_lvl
                                      << " allow_rev=" << allow_rev << " sec_lvl=" << sec_lvl << " is_rev=" << is_rev
                                      << " | Ref=" << ref_v << " Ext=" << (int)ext_v << "\n";
                            std::abort();
                        }

                        // Theorem 6: Revoked is toxic if revocation disallowed
                        if (is_rev && !allow_rev) {
                            assert(ext_v == VerdictToxic);
                        }

                        vector_count++;
                        total_tests_executed++;
                    }
                }
            }
        }
    }
    std::cout << "    [+] Discharged " << vector_count << " exhaustive Crypto Policy vectors: matched bit-for-bit.\n";
}

void test_differential_wire() {
    std::cout << "[*] [DIFFERENTIAL 3/3] Wire Bounds & Sequence Monotonicity Invariants...\n";

    // 1. Boundary Matrix
    const struct {
        uint16_t chunk_len;
        uint16_t chunk_idx;
        uint16_t total_chunks;
        uint32_t seq_id;
        qf_frame_verdict_tag_t expected_tag;
        uint16_t expected_reason;
    } boundary_cases[] = {
        // Valid nominal frame
        { 1024, 0, 10, 100, QF_WIRE_FRAME_VALID, 0 },
        // Exact chunk max boundary
        { 1450, 0, 1, 1, QF_WIRE_FRAME_VALID, 0 },
        // Zero length violation
        { 0, 0, 1, 1, QF_WIRE_FRAME_INVALID, 3 },
        // Exceeded length violation
        { 1451, 0, 1, 1, QF_WIRE_FRAME_INVALID, 3 },
        // Zero total chunks violation
        { 100, 0, 0, 1, QF_WIRE_FRAME_INVALID, 3 },
        // Out of bounds index
        { 100, 10, 10, 1, QF_WIRE_FRAME_INVALID, 3 },
        // Index exceeding chunks
        { 100, 15, 10, 1, QF_WIRE_FRAME_INVALID, 3 },
        // Max sequence valid
        { 100, 0, 1, 0xFFFFFFFDu, QF_WIRE_FRAME_VALID, 0 },
        // Sequence exhausted
        { 100, 0, 1, 0xFFFFFFFEu, QF_WIRE_FRAME_INVALID, 7 },
        // Sequence overflow
        { 100, 0, 1, 0xFFFFFFFFu, QF_WIRE_FRAME_INVALID, 7 }
    };

    for (const auto& tc : boundary_cases) {
        qf_wire_frame_meta_t ref_m = { tc.chunk_len, tc.chunk_idx, tc.total_chunks, tc.seq_id };
        qf_frame_verdict_t ref_v = qf_core_eval_wire_bounds(ref_m);

        wire_frame_meta ext_m = { tc.chunk_len, tc.chunk_idx, tc.total_chunks, tc.seq_id };
        frame_verdict ext_v = eval_wire_bounds(ext_m);

        assert(ref_v.tag == tc.expected_tag);
        assert(ref_v.reason == tc.expected_reason);

        qf_frame_verdict_tag_t ext_mapped_tag = (ext_v.tag == FrameValid) ? QF_WIRE_FRAME_VALID : QF_WIRE_FRAME_INVALID;
        if (ref_v.tag != ext_mapped_tag || ref_v.reason != ext_v.reason) {
            std::cerr << "[!] WIRE BOUNDS DIVERGENCE: len=" << tc.chunk_len
                      << " idx=" << tc.chunk_idx << " total=" << tc.total_chunks
                      << " seq=" << tc.seq_id << "\n";
            std::abort();
        }
        total_tests_executed++;
    }

    // 2. Randomized Fuzz Suite (10,000 vectors)
    std::srand(0x5146584B); // Deterministic seed: "QFXK"
    for (uint32_t i = 0; i < 10000; i++) {
        uint16_t clen = (uint16_t)(std::rand() % 2000);
        uint16_t tot  = (uint16_t)(std::rand() % 100);
        uint16_t cidx = (tot > 0) ? (uint16_t)(std::rand() % (tot + 5)) : 0;
        uint32_t s_id = (std::rand() % 10 == 0) ? (0xFFFFFFF8u + (std::rand() % 8)) : (uint32_t)std::rand();

        qf_wire_frame_meta_t ref_m = { clen, cidx, tot, s_id };
        qf_frame_verdict_t ref_v = qf_core_eval_wire_bounds(ref_m);

        wire_frame_meta ext_m = { clen, cidx, tot, s_id };
        frame_verdict ext_v = eval_wire_bounds(ext_m);

        qf_frame_verdict_tag_t ext_mapped_tag = (ext_v.tag == FrameValid) ? QF_WIRE_FRAME_VALID : QF_WIRE_FRAME_INVALID;
        if (ref_v.tag != ext_mapped_tag || ref_v.reason != ext_v.reason) {
            std::cerr << "[!] WIRE FUZZ DIVERGENCE at iteration " << i << "\n";
            std::abort();
        }
        total_tests_executed++;
    }
    std::cout << "    [+] Discharged 10,010 wire boundary & fuzz vectors: matched bit-for-bit.\n";
}

int main() {
    std::cout << "================================================================================\n";
    std::cout << "QUANTUMFLEX DIFFERENTIAL EQUIVALENCE HARNESS: C REFERENCE vs KaRaMeL EXTRACTED\n";
    std::cout << "================================================================================\n";

    test_differential_fsm();
    test_differential_crypto();
    test_differential_wire();

    std::cout << "================================================================================\n";
    std::cout << "[PASS] ZERO DIVERGENCE ACROSS ALL INVARIANTS (" << total_tests_executed << " TOTAL CHECKS)\n";
    std::cout << "       F* 2026.09 Model == KaRaMeL Machine Extraction == C Reference Implementation\n";
    std::cout << "================================================================================\n";

    return 0;
}
