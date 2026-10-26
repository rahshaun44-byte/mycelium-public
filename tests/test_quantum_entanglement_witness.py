"""
QuantumFlex Track 4: Entanglement Witness & Complementary-Basis Test Suite
==========================================================================
Proves:
  1. Multi-basis Bell state measurements (Z ⊗ Z and X ⊗ X) yield negative witness expectation.
  2. The acceptance gate strictly requires the Upper Confidence Bound (UCB) < 0.0.
  3. A classical state with 100% same-bit correlation (separable mixture) is REJECTED by the witness.
  4. Finite shot statistical noise that fails UCB < 0.0 is REJECTED even if point estimate is negative.
  5. Cryptographic tampering of witness counts or digests is rejected fail-closed.
  6. End-to-end integration with QuantumFlexUSDCSettler dry-run lifecycle.
"""

import json
import pytest
from api_node.circle_usdc_settlement import QuantumFlexUSDCSettler, QuantumSettlementLifecycle
from api_node.quantum_entanglement_witness import (
    build_complementary_bell_circuits,
    calculate_pauli_expectation,
    evaluate_entanglement_witness,
    run_local_reference_experiment,
    build_witness_proof_package
)


def test_complementary_circuits_structure():
    """Verify that both Z⊗Z and X⊗X circuits are correctly synthesized with appropriate gates."""
    circuits = build_complementary_bell_circuits()
    assert "zz" in circuits
    assert "xx" in circuits

    qc_zz = circuits["zz"]
    qc_xx = circuits["xx"]

    # Both circuits use 2 qubits and 2 classical bits
    assert qc_zz.num_qubits == 2
    assert qc_zz.num_clbits == 2
    assert qc_xx.num_qubits == 2
    assert qc_xx.num_clbits == 2

    # Verify gates
    ops_zz = qc_zz.count_ops()
    assert ops_zz["h"] == 1      # 1 Hadamard on qubit 0 to create superposition
    assert ops_zz["cx"] == 1     # 1 CNOT to create Bell pair
    assert ops_zz["measure"] == 2

    ops_xx = qc_xx.count_ops()
    assert ops_xx["h"] == 3      # 1 initial H + 2 measurement basis rotation Hadamards
    assert ops_xx["cx"] == 1     # 1 CNOT
    assert ops_xx["measure"] == 2


def test_ideal_bell_state_local_simulation_proves_entanglement():
    """
    Executes the Bell circuits locally via Qiskit's StatevectorSampler.
    For an ideal |Φ⁺⟩ state:
      ⟨ZZ⟩ ≈ 1.0, ⟨XX⟩ ≈ 1.0 ==> ⟨W⟩ ≈ -0.5
      Upper Confidence Bound (UCB) at 99% confidence must be < 0.0.
    """
    witness_result, proof = run_local_reference_experiment(shots=2048, confidence_level=0.99)

    assert witness_result.shots_zz == 2048
    assert witness_result.shots_xx == 2048

    # Check expectations are close to ideal +1.0
    assert witness_result.exp_zz > 0.95
    assert witness_result.exp_xx > 0.95

    # Check witness expectation is strongly negative (theoretical ideal is -0.5)
    assert witness_result.witness_expectation < -0.45
    assert witness_result.witness_std_err >= 0.0

    # Upper Confidence Bound (99%) must be strictly negative
    assert witness_result.witness_ucb < -0.40
    assert witness_result.is_entangled is True
    assert witness_result.rejection_reason is None

    # Verify that QuantumFlexUSDCSettler accepts this genuine entanglement proof
    assert QuantumFlexUSDCSettler.verify_quantum_proof(proof) is True

    settler = QuantumFlexUSDCSettler()
    res = settler.execute_micro_settlement("0xRecipient111", "25.00", proof)
    assert res["status"] == "PROOF_VERIFIED_DRY_RUN"
    assert res["lifecycle_stage"] == QuantumSettlementLifecycle.PROOF_VERIFIED.value
    assert res["submitted"] is False


def test_classical_separable_mixture_with_100_percent_correlation_is_rejected():
    """
    Adversarial Counterexample:
    Consider the classical mixed state:
        ρ_classical = 1/2 |00⟩⟨00| + 1/2 |11⟩⟨11|
    
    In the computational basis (Z ⊗ Z):
      Counts: 50% '00', 50% '11', 0% '01', 0% '10'.
      Same-bit correlation = 100%!
      ⟨ZZ⟩ = (512 - 0 - 0 + 512) / 1024 = +1.0.

    In the complementary basis (X ⊗ X):
      Measuring |00⟩ in X yields uniform distribution over all 4 outcomes.
      Measuring |11⟩ in X yields uniform distribution over all 4 outcomes.
      Counts: 25% '00', 25% '01', 25% '10', 25% '11'.
      ⟨XX⟩ = (256 - 256 - 256 + 256) / 1024 = 0.0.

    Witness calculation:
      ⟨W⟩ = (1 - 1.0 - 0.0) / 2 = 0.0  (Non-negative! Separable bound satisfied).
      UCB = 0.0 + z * SE > 0.0.

    Assertion:
      The witness MUST certify this state as NOT entangled and REJECT it from settlement,
      proving that same-bit correlation alone is insufficient.
    """
    counts_zz_classical = {"00": 512, "11": 512, "01": 0, "10": 0}
    counts_xx_classical = {"00": 256, "01": 256, "10": 256, "11": 256}

    result = evaluate_entanglement_witness(counts_zz_classical, counts_xx_classical, confidence_level=0.99)

    assert result.exp_zz == 1.0
    assert result.exp_xx == 0.0
    assert result.witness_expectation == 0.0
    assert result.witness_ucb > 0.0
    assert result.is_entangled is False
    assert "classical/separable" in result.rejection_reason

    # Package as proof and verify settler rejection
    proof = build_witness_proof_package(
        backend_name="simulated_classical_mixture",
        job_id="classical-separable-test",
        counts_zz=counts_zz_classical,
        counts_xx=counts_xx_classical,
        witness_result=result
    )

    # Settler must reject the classical state
    assert QuantumFlexUSDCSettler.verify_quantum_proof(proof) is False

    settler = QuantumFlexUSDCSettler()
    exec_res = settler.execute_micro_settlement("0xRecipient111", "25.00", proof)
    assert exec_res["status"] == "REJECTED"
    assert exec_res["lifecycle_stage"] == QuantumSettlementLifecycle.REJECTED.value
    assert exec_res["submitted"] is False


def test_noisy_state_with_negative_mean_but_nonnegative_ucb_is_rejected():
    """
    Statistical Rigor Test:
    A noisy QPU run where the sample mean ⟨Ŵ⟩ is slightly negative (-0.02),
    but due to small sample size or high noise, the Upper Confidence Bound (UCB) ≥ 0.0.
    
    Assertion:
      Must be REJECTED. A point estimate below zero is NOT sufficient without
      the upper confidence bound ruling out classical states.
    """
    # ZZ with moderate correlation: 65% even, 35% odd ==> exp_zz = 0.30
    counts_zz = {"00": 33, "11": 32, "01": 17, "10": 18}  # Total 100
    # XX with moderate correlation: 87% even, 13% odd ==> exp_xx = 0.74
    counts_xx = {"00": 44, "11": 43, "01": 7, "10": 6}    # Total 100

    # ⟨W⟩ = (1 - 0.30 - 0.74)/2 = (1 - 1.04)/2 = -0.02 (Negative point estimate!)
    result = evaluate_entanglement_witness(counts_zz, counts_xx, confidence_level=0.99)

    assert result.witness_expectation < 0.0  # Point estimate IS negative!
    assert result.witness_ucb >= 0.0        # But UCB is positive due to standard error!
    assert result.is_entangled is False
    assert "Upper confidence bound" in result.rejection_reason

    proof = build_witness_proof_package(
        backend_name="noisy_mock_qpu",
        job_id="noisy-insufficient-shots",
        counts_zz=counts_zz,
        counts_xx=counts_xx,
        witness_result=result
    )

    assert QuantumFlexUSDCSettler.verify_quantum_proof(proof) is False


def test_tampered_payload_or_mismatched_hash_is_rejected():
    """Any alteration of counts, expectation values, or digest hash fails closed."""
    _, proof = run_local_reference_experiment(shots=1024)

    # 1. Alter block hash
    proof_tampered_hash = dict(proof, block_hash="00" * 32)
    assert QuantumFlexUSDCSettler.verify_quantum_proof(proof_tampered_hash) is False

    # 2. Alter non-zero entropy
    proof_tampered_entropy = dict(proof, zero_entropy=0.5)
    assert QuantumFlexUSDCSettler.verify_quantum_proof(proof_tampered_entropy) is False

    # 3. Alter canonical payload internally
    payload_data = json.loads(proof["canonical_payload"])
    payload_data["witness_expectation"] = -0.999  # Tampered field
    tampered_payload_str = json.dumps(payload_data, sort_keys=True, separators=(",", ":"))
    proof_tampered_payload = dict(proof, canonical_payload=tampered_payload_str)
    assert QuantumFlexUSDCSettler.verify_quantum_proof(proof_tampered_payload) is False


def test_insufficient_sample_size_rejected():
    """Sample sizes under MINIMUM_SHOTS (100) are rejected fail-closed to prevent zero-error collapse."""
    tiny_counts_zz = {"00": 5, "11": 5}
    tiny_counts_xx = {"00": 5, "11": 5}

    result = evaluate_entanglement_witness(tiny_counts_zz, tiny_counts_xx, confidence_level=0.99)
    assert result.is_entangled is False
    assert "Insufficient sample size" in result.rejection_reason
    assert result.witness_ucb >= 0.0
