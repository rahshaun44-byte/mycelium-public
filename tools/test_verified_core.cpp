#include "quantum-flex/verified_core.h"
#include <cassert>
#include <iostream>
#include <vector>

void test_state_machine_invariants() {
    std::cout << "[*] [VERIFIED_CORE 1/4] Testing Finite State Legality & Absorbing Quarantine Sink...\n";

    // Uninitialized -> Locked
    assert(qf_core_eval_transition(QF_STATE_UNINITIALIZED, QF_STATE_LOCKED, QF_CRED_NONE) == QF_VERDICT_ALLOW);

    // Locked -> Active without credentials MUST FAIL (Theorem 2)
    assert(qf_core_eval_transition(QF_STATE_LOCKED, QF_STATE_ACTIVE, QF_CRED_NONE) == QF_VERDICT_DENY);
    // Locked -> Active with Shamir or mTLS succeeds
    assert(qf_core_eval_transition(QF_STATE_LOCKED, QF_STATE_ACTIVE, QF_CRED_SHAMIR_THRESHOLD) == QF_VERDICT_ALLOW);
    assert(qf_core_eval_transition(QF_STATE_LOCKED, QF_STATE_ACTIVE, QF_CRED_MTLS_CERT) == QF_VERDICT_ALLOW);

    // Active -> Quarantine succeeds
    assert(qf_core_eval_transition(QF_STATE_ACTIVE, QF_STATE_QUARANTINE, QF_CRED_NONE) == QF_VERDICT_ALLOW);

    // ABSORBING QUARANTINE SINK (Theorem 1): Quarantine -> Active MUST FAIL under any credential
    assert(qf_core_eval_transition(QF_STATE_QUARANTINE, QF_STATE_ACTIVE, QF_CRED_NONE) == QF_VERDICT_DENY);
    assert(qf_core_eval_transition(QF_STATE_QUARANTINE, QF_STATE_ACTIVE, QF_CRED_MTLS_CERT) == QF_VERDICT_DENY);
    assert(qf_core_eval_transition(QF_STATE_QUARANTINE, QF_STATE_ACTIVE, QF_CRED_SHAMIR_THRESHOLD) == QF_VERDICT_DENY);
    assert(qf_core_eval_transition(QF_STATE_QUARANTINE, QF_STATE_ACTIVE, QF_CRED_TWO_MAN_ATTESTATION) == QF_VERDICT_DENY);

    // Quarantine -> Recovery REQUIRES Two-Man Attestation
    assert(qf_core_eval_transition(QF_STATE_QUARANTINE, QF_STATE_RECOVERY, QF_CRED_NONE) == QF_VERDICT_DENY);
    assert(qf_core_eval_transition(QF_STATE_QUARANTINE, QF_STATE_RECOVERY, QF_CRED_MTLS_CERT) == QF_VERDICT_DENY);
    assert(qf_core_eval_transition(QF_STATE_QUARANTINE, QF_STATE_RECOVERY, QF_CRED_TWO_MAN_ATTESTATION) == QF_VERDICT_ALLOW);

    // Recovery -> Locked requires mTLS authorization
    assert(qf_core_eval_transition(QF_STATE_RECOVERY, QF_STATE_LOCKED, QF_CRED_NONE) == QF_VERDICT_DENY);
    assert(qf_core_eval_transition(QF_STATE_RECOVERY, QF_STATE_LOCKED, QF_CRED_MTLS_CERT) == QF_VERDICT_ALLOW);

    std::cout << "    [+] Absorbing Quarantine Sink and Transition Invariants Verified (PASS)\n";
}

void test_pqc_downgrade_invariants() {
    std::cout << "[*] [VERIFIED_CORE 2/4] Testing Strict FIPS 203 PQC Downgrade Impossibility...\n";

    // Strict FIPS 203 Profile
    assert(qf_core_eval_pqc_proposal(QF_PROFILE_STRICT_FIPS203, QF_ALG_ML_KEM_768) == QF_VERDICT_ALLOW);
    assert(qf_core_eval_pqc_proposal(QF_PROFILE_STRICT_FIPS203, QF_ALG_ML_KEM_1024) == QF_VERDICT_ALLOW);

    // Down-negotiation MUST FAIL (Theorem 3)
    assert(qf_core_eval_pqc_proposal(QF_PROFILE_STRICT_FIPS203, QF_ALG_FRODO_976) == QF_VERDICT_DENY);
    assert(qf_core_eval_pqc_proposal(QF_PROFILE_STRICT_FIPS203, QF_ALG_X25519) == QF_VERDICT_DENY);
    assert(qf_core_eval_pqc_proposal(QF_PROFILE_STRICT_FIPS203, QF_ALG_UNKNOWN) == QF_VERDICT_DENY);

    // Agile Profile allows Frodo transition but rejects unapproved/classical
    assert(qf_core_eval_pqc_proposal(QF_PROFILE_AGILE_TRANSITION, QF_ALG_ML_KEM_768) == QF_VERDICT_ALLOW);
    assert(qf_core_eval_pqc_proposal(QF_PROFILE_AGILE_TRANSITION, QF_ALG_FRODO_976) == QF_VERDICT_ALLOW);
    assert(qf_core_eval_pqc_proposal(QF_PROFILE_AGILE_TRANSITION, QF_ALG_X25519) == QF_VERDICT_DENY);

    std::cout << "    [+] Strict FIPS 203 Anti-Downgrade Invariant Verified (PASS)\n";
}

void test_wire_bounds_invariants() {
    std::cout << "[*] [VERIFIED_CORE 3/4] Testing Wire Frame Bounds & Anti-Rollover Exhaustion...\n";

    // Nominal frame
    assert(qf_core_eval_wire_bounds(1400, 0, 64, 100) == QF_WIRE_OK);
    assert(qf_core_eval_wire_bounds(1, 63, 64, 0) == QF_WIRE_OK);

    // Out-of-bounds chunk_len (Theorem 4)
    assert(qf_core_eval_wire_bounds(0, 0, 10, 1) == QF_WIRE_ERR_CHUNK_BOUNDS);
    assert(qf_core_eval_wire_bounds(1451, 0, 10, 1) == QF_WIRE_ERR_CHUNK_BOUNDS);

    // Out-of-bounds total_chunks
    assert(qf_core_eval_wire_bounds(100, 0, 0, 1) == QF_WIRE_ERR_CHUNK_BOUNDS);
    assert(qf_core_eval_wire_bounds(100, 0, 65, 1) == QF_WIRE_ERR_CHUNK_BOUNDS);

    // Chunk index out of range
    assert(qf_core_eval_wire_bounds(100, 10, 10, 1) == QF_WIRE_ERR_CHUNK_BOUNDS);
    assert(qf_core_eval_wire_bounds(100, 11, 10, 1) == QF_WIRE_ERR_CHUNK_BOUNDS);

    // Monotonic sequence exhaustion past 2^32 - 2 (Theorem 5: silent wraparound forbidden)
    assert(qf_core_eval_wire_bounds(100, 0, 10, 0xFFFFFFFD) == QF_WIRE_OK);
    assert(qf_core_eval_wire_bounds(100, 0, 10, 0xFFFFFFFE) == QF_WIRE_ERR_SEQ_EXHAUSTED);
    assert(qf_core_eval_wire_bounds(100, 0, 10, 0xFFFFFFFF) == QF_WIRE_ERR_SEQ_EXHAUSTED);

    std::cout << "    [+] Wire Frame Bounds and Sequence Monotonicity Invariants Verified (PASS)\n";
}

void test_crc32_and_zeroization() {
    std::cout << "[*] [VERIFIED_CORE 4/4] Testing CRC32 Integrity & Memory Barrier Zeroization...\n";

    // Test vector: standard IEEE 802.3 CRC32 for "123456789" is 0xCBF43926
    const uint8_t test_vec[] = "123456789";
    uint32_t computed = qf_core_compute_crc32(test_vec, 9);
    assert(computed == 0xCBF43926U);

    // Test zeroization
    uint8_t buffer[128];
    for (size_t i = 0; i < sizeof(buffer); ++i) {
        buffer[i] = static_cast<uint8_t>(i + 1);
    }
    qf_core_zeroize(buffer, sizeof(buffer));
    for (size_t i = 0; i < sizeof(buffer); ++i) {
        assert(buffer[i] == 0x00);
    }

    std::cout << "    [+] CRC32 Test Vector and Zeroization Verified (PASS)\n";
}

int main() {
    std::cout << "================================================================================\n";
    std::cout << "QUANTUMFLEX VERIFIED CORE: FORMAL INVARIANT TEST HARNESS\n";
    std::cout << "Target: Formal Invariants (QuantumFlex_Core.fst) via C ABI\n";
    std::cout << "================================================================================\n";

    test_state_machine_invariants();
    test_pqc_downgrade_invariants();
    test_wire_bounds_invariants();
    test_crc32_and_zeroization();

    std::cout << "================================================================================\n";
    std::cout << "[PASS] ALL VERIFIED CORE INVARIANTS SATISFIED (4/4 TEST SUITES PASSED)\n";
    std::cout << "================================================================================\n";
    return 0;
}
