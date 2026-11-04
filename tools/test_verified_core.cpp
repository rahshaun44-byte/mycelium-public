#include "quantum-flex/verified_core.h"
#include <cassert>
#include <iostream>

void test_state_machine_invariants() {
    std::cout << "[*] [VERIFIED_CORE 1/3] Testing Finite State Legality & Invariants (Theorems 1-5)...\n";

    // 1. Absorbing Terminal Sink (Theorem 1)
    qf_transition_result_t res = qf_core_step_fsm(QF_STATE_COLLAPSED, QF_VERDICT_COMPLIANT, QF_CRED_OPERATOR_ATTESTATION, 0);
    assert(res.next_state == QF_STATE_COLLAPSED);
    assert(res.permitted == false);

    // 2. Uninitialized -> Active on compliant verdict; Quarantine on non-compliant
    res = qf_core_step_fsm(QF_STATE_UNINITIALIZED, QF_VERDICT_COMPLIANT, QF_CRED_NONE, 0);
    assert(res.next_state == QF_STATE_ACTIVE);
    assert(res.permitted == true);

    res = qf_core_step_fsm(QF_STATE_UNINITIALIZED, QF_VERDICT_DEGRADED, QF_CRED_NONE, 0);
    assert(res.next_state == QF_STATE_QUARANTINE);
    assert(res.permitted == false);

    // 3. Active state transitions
    res = qf_core_step_fsm(QF_STATE_ACTIVE, QF_VERDICT_COMPLIANT, QF_CRED_NONE, 0);
    assert(res.next_state == QF_STATE_ACTIVE);
    assert(res.permitted == true);

    res = qf_core_step_fsm(QF_STATE_ACTIVE, QF_VERDICT_DEGRADED, QF_CRED_NONE, 0);
    assert(res.next_state == QF_STATE_QUARANTINE);
    assert(res.permitted == false);

    res = qf_core_step_fsm(QF_STATE_ACTIVE, QF_VERDICT_SUPERVISOR_UNREACHABLE, QF_CRED_NONE, 0);
    assert(res.next_state == QF_STATE_QUARANTINE);
    assert(res.permitted == false);

    res = qf_core_step_fsm(QF_STATE_ACTIVE, QF_VERDICT_TOXIC, QF_CRED_NONE, 0);
    assert(res.next_state == QF_STATE_COLLAPSED);
    assert(res.permitted == false);

    // 4. Quarantine state & retry budget ceiling (Theorem 2 & 3)
    res = qf_core_step_fsm(QF_STATE_QUARANTINE, QF_VERDICT_COMPLIANT, QF_CRED_NONE, 0);
    assert(res.next_state == QF_STATE_RECOVERY);
    assert(res.permitted == false);

    res = qf_core_step_fsm(QF_STATE_QUARANTINE, QF_VERDICT_DEGRADED, QF_CRED_NONE, 0);
    assert(res.next_state == QF_STATE_QUARANTINE);
    assert(res.retries_out == 1);
    assert(res.permitted == false);

    // Exceeding retry ceiling collapses state
    res = qf_core_step_fsm(QF_STATE_QUARANTINE, QF_VERDICT_DEGRADED, QF_CRED_NONE, QF_MAX_QUARANTINE_RETRIES);
    assert(res.next_state == QF_STATE_COLLAPSED);
    assert(res.permitted == false);

    // 5. Recovery state requires Operator or Two-Man attestation (Theorem 4 & 5)
    res = qf_core_step_fsm(QF_STATE_RECOVERY, QF_VERDICT_COMPLIANT, QF_CRED_NONE, 0);
    assert(res.next_state == QF_STATE_RECOVERY);
    assert(res.permitted == false);

    res = qf_core_step_fsm(QF_STATE_RECOVERY, QF_VERDICT_COMPLIANT, QF_CRED_OPERATOR_ATTESTATION, 0);
    assert(res.next_state == QF_STATE_ACTIVE);
    assert(res.permitted == true);

    res = qf_core_step_fsm(QF_STATE_RECOVERY, QF_VERDICT_COMPLIANT, QF_CRED_TWO_MAN_ATTESTATION, 0);
    assert(res.next_state == QF_STATE_ACTIVE);
    assert(res.permitted == true);

    res = qf_core_step_fsm(QF_STATE_RECOVERY, QF_VERDICT_TOXIC, QF_CRED_OPERATOR_ATTESTATION, 0);
    assert(res.next_state == QF_STATE_COLLAPSED);
    assert(res.permitted == false);

    std::cout << "    [+] Absorbing Sink, Retry Ceilings, and Attestation Gates Verified (PASS)\n";
}

void test_crypto_policy_invariants() {
    std::cout << "[*] [VERIFIED_CORE 2/3] Testing Cryptographic Policy & Anti-Downgrade (Theorems 6-7)...\n";

    // 1. Revoked asset rejection (Theorem 6)
    qf_policy_criteria_t policy = { QF_CRYPTO_STANDARD_CLASSICAL, false };
    qf_crypto_asset_descriptor_t asset = { 1, QF_CRYPTO_POST_QUANTUM_FIPS, true };
    assert(qf_core_eval_crypto_asset(policy, asset) == QF_VERDICT_TOXIC);

    // When allow_revoked is explicitly true
    policy.allow_revoked = true;
    assert(qf_core_eval_crypto_asset(policy, asset) == QF_VERDICT_COMPLIANT);

    // 2. Strict Post-Quantum FIPS requirement (Theorem 7)
    policy.min_required_level = QF_CRYPTO_POST_QUANTUM_FIPS;
    policy.allow_revoked = false;
    asset.is_revoked = false;

    asset.security_level = QF_CRYPTO_POST_QUANTUM_FIPS;
    assert(qf_core_eval_crypto_asset(policy, asset) == QF_VERDICT_COMPLIANT);

    asset.security_level = QF_CRYPTO_STANDARD_CLASSICAL;
    assert(qf_core_eval_crypto_asset(policy, asset) == QF_VERDICT_DEGRADED);

    asset.security_level = QF_CRYPTO_LEGACY_DEPRECATED;
    assert(qf_core_eval_crypto_asset(policy, asset) == QF_VERDICT_DEGRADED);

    // 3. Standard Classical requirement
    policy.min_required_level = QF_CRYPTO_STANDARD_CLASSICAL;
    asset.security_level = QF_CRYPTO_LEGACY_DEPRECATED;
    assert(qf_core_eval_crypto_asset(policy, asset) == QF_VERDICT_DEGRADED);

    asset.security_level = QF_CRYPTO_STANDARD_CLASSICAL;
    assert(qf_core_eval_crypto_asset(policy, asset) == QF_VERDICT_COMPLIANT);

    asset.security_level = QF_CRYPTO_POST_QUANTUM_FIPS;
    assert(qf_core_eval_crypto_asset(policy, asset) == QF_VERDICT_COMPLIANT);

    std::cout << "    [+] Revocation Toxicity and PQC Anti-Downgrade Invariants Verified (PASS)\n";
}

void test_wire_bounds_invariants() {
    std::cout << "[*] [VERIFIED_CORE 3/3] Testing Wire Frame Bounds & Anti-Rollover (Theorems 8-9)...\n";

    // Nominal valid frames
    qf_wire_frame_meta_t f = { 1024, 0, 10, 100 };
    assert(qf_core_eval_wire_bounds(f).tag == QF_WIRE_FRAME_VALID);

    f = { 1450, 0, 1, 1 };
    assert(qf_core_eval_wire_bounds(f).tag == QF_WIRE_FRAME_VALID);

    f = { 1, 63, 64, 0 };
    assert(qf_core_eval_wire_bounds(f).tag == QF_WIRE_FRAME_VALID);

    // Out-of-bounds chunk_len
    f = { 0, 0, 10, 1 };
    assert(qf_core_eval_wire_bounds(f).tag == QF_WIRE_FRAME_INVALID);

    f = { 1451, 0, 10, 1 };
    assert(qf_core_eval_wire_bounds(f).tag == QF_WIRE_FRAME_INVALID);

    // Out-of-bounds total_chunks
    f = { 100, 0, 0, 1 };
    assert(qf_core_eval_wire_bounds(f).tag == QF_WIRE_FRAME_INVALID);

    f = { 100, 0, 65, 1 };
    assert(qf_core_eval_wire_bounds(f).tag == QF_WIRE_FRAME_INVALID);

    // Chunk index out of range
    f = { 100, 10, 10, 1 };
    assert(qf_core_eval_wire_bounds(f).tag == QF_WIRE_FRAME_INVALID);

    f = { 100, 11, 10, 1 };
    assert(qf_core_eval_wire_bounds(f).tag == QF_WIRE_FRAME_INVALID);

    // Sequence exhaustion (Theorems 8-9: silent wraparound forbidden)
    f = { 100, 0, 10, 0xFFFFFFFDu };
    assert(qf_core_eval_wire_bounds(f).tag == QF_WIRE_FRAME_VALID);

    f = { 100, 0, 10, 0xFFFFFFFEu };
    assert(qf_core_eval_wire_bounds(f).tag == QF_WIRE_FRAME_INVALID);

    f = { 100, 0, 10, 0xFFFFFFFFu };
    assert(qf_core_eval_wire_bounds(f).tag == QF_WIRE_FRAME_INVALID);

    std::cout << "    [+] Wire Frame Bounds and Sequence Monotonicity Invariants Verified (PASS)\n";
}

int main() {
    std::cout << "================================================================================\n";
    std::cout << "QUANTUMFLEX VERIFIED CORE: FORMAL INVARIANT TEST HARNESS\n";
    std::cout << "Target: Formal Invariants (QuantumFlex_Core.fst) via C ABI\n";
    std::cout << "================================================================================\n";

    test_state_machine_invariants();
    test_crypto_policy_invariants();
    test_wire_bounds_invariants();

    std::cout << "================================================================================\n";
    std::cout << "[PASS] ALL VERIFIED CORE INVARIANTS SATISFIED (3/3 TEST SUITES PASSED)\n";
    std::cout << "================================================================================\n";
    return 0;
}
