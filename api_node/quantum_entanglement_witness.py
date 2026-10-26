"""
QuantumFlex Track 4: Multi-Basis Quantum Entanglement Witness Engine
=====================================================================
Evaluates empirical quantum state fidelity and non-classical correlations
using complementary Pauli measurements (Z ⊗ Z and X ⊗ X).

Physical Rationale:
-------------------
A measurement in only the computational basis (Z ⊗ Z) measures only same-bit
correlation:
    P(00 or 11) = P(00) + P(11)
A classical statistical mixture:
    ρ_classical = 1/2 |00⟩⟨00| + 1/2 |11⟩⟨11|
yields 100% same-bit correlation (P(00 or 11) = 1.0), but contains zero
quantum coherence or entanglement.

To strictly rule out all separable / classical states, measurements must be
performed across non-commuting, complementary bases.

For the target Bell state |Φ⁺⟩ = (|00⟩ + |11⟩) / √2, the standard witness is:
    W = 1/2 * I - |Φ⁺⟩⟨Φ⁺|
Restricted to two complementary measurement settings (Z ⊗ Z and X ⊗ X):
    ⟨W⟩ = (1 - ⟨ZZ⟩ - ⟨XX⟩) / 2

Separability Bound:
-------------------
For all separable states ρ_sep:
    |⟨ZZ⟩ + ⟨XX⟩| ≤ 1  ==>  ⟨W⟩ ≥ 0

Entanglement Criterion:
-----------------------
A state is certified as genuinely entangled if and only if:
    ⟨W⟩ < 0

Statistical Rigor (Upper Confidence Bound):
--------------------------------------------
Because experimental QPU runs collect a finite number of shots (N_ZZ, N_XX),
the acceptance gate requires the Upper Confidence Bound (UCB) of the witness
to be strictly negative at confidence level (1 - α):
    UCB_α(W) = ⟨Ŵ⟩ + z_α * SE(Ŵ) < 0.0

where:
    SE(Ŵ) = 1/2 * sqrt( Var(⟨ẐẐ⟩)/N_ZZ + Var(⟨X̂X̂⟩)/N_XX )
"""

from __future__ import annotations
import hashlib
import json
import math
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from qiskit import QuantumCircuit


# Precomputed standard normal quantiles for one-sided upper confidence bounds
Z_QUANTILES = {
    0.90: 1.28155,
    0.95: 1.64485,
    0.975: 1.95996,
    0.99: 2.32635,
    0.999: 3.09023,
    0.9999: 3.71902,
}


def get_z_score(confidence_level: float) -> float:
    """Return the normal distribution critical value for a one-sided upper bound."""
    if confidence_level in Z_QUANTILES:
        return Z_QUANTILES[confidence_level]
    try:
        from scipy.stats import norm
        return float(norm.ppf(confidence_level))
    except ImportError:
        # Fallback to closest or 99%
        closest = min(Z_QUANTILES.keys(), key=lambda k: abs(k - confidence_level))
        return Z_QUANTILES[closest]


@dataclass
class PauliExpectation:
    basis: str
    expectation: float
    variance: float
    total_shots: int
    counts: Dict[str, int]


@dataclass
class WitnessEvaluationResult:
    exp_zz: float
    exp_xx: float
    shots_zz: int
    shots_xx: int
    witness_expectation: float
    witness_std_err: float
    confidence_level: float
    z_score: float
    witness_ucb: float
    is_entangled: bool
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_complementary_bell_circuits() -> Dict[str, QuantumCircuit]:
    """
    Constructs the two complementary circuits required for Bell state witness evaluation:
    1. 'zz': Standard computational basis measurement (measures Z ⊗ Z).
    2. 'xx': Hadamard rotation on both qubits before measurement (measures X ⊗ X).
    """
    # 1. Computational Basis (Z ⊗ Z)
    qc_zz = QuantumCircuit(2, 2, name="bell_basis_zz")
    qc_zz.h(0)
    qc_zz.cx(0, 1)
    qc_zz.measure([0, 1], [0, 1])

    # 2. Complementary Basis (X ⊗ X)
    qc_xx = QuantumCircuit(2, 2, name="bell_basis_xx")
    qc_xx.h(0)
    qc_xx.cx(0, 1)
    # Rotate eigenbasis of X to computational Z: H Z H = X
    qc_xx.h(0)
    qc_xx.h(1)
    qc_xx.measure([0, 1], [0, 1])

    return {"zz": qc_zz, "xx": qc_xx}


def calculate_pauli_expectation(counts: Dict[str, int], basis_name: str) -> PauliExpectation:
    """
    Calculate the Pauli correlation ⟨O⟩ = (N_00 - N_01 - N_10 + N_11) / N_total
    and its sample variance.
    """
    if not counts:
        raise ValueError(f"Empty counts provided for basis {basis_name}")

    n00 = counts.get("00", 0)
    n01 = counts.get("01", 0)
    n10 = counts.get("10", 0)
    n11 = counts.get("11", 0)
    total_shots = n00 + n01 + n10 + n11

    if total_shots <= 0:
        raise ValueError(f"Total shots must be > 0, got {total_shots} for {basis_name}")

    # Eigenvalues: (+1) for even parity (00, 11), (-1) for odd parity (01, 10)
    even_count = n00 + n11
    odd_count = n01 + n10
    exp_val = (even_count - odd_count) / total_shots

    # Unbiased sample variance: s^2 = (N / (N - 1)) * (1.0 - exp_val^2) for N > 1
    # To guard against zero-error collapse (when exp_val == ±1.0 on small sample sizes),
    # enforce a statistical variance floor: max(s^2, 1.0 / total_shots)
    if total_shots > 1:
        s_squared = (total_shots / (total_shots - 1)) * max(0.0, 1.0 - exp_val ** 2)
    else:
        s_squared = 1.0
    var_outcome = max(s_squared, 1.0 / total_shots)

    return PauliExpectation(
        basis=basis_name,
        expectation=exp_val,
        variance=var_outcome,
        total_shots=total_shots,
        counts=counts
    )


def evaluate_entanglement_witness(
    counts_zz: Dict[str, int],
    counts_xx: Dict[str, int],
    confidence_level: float = 0.99
) -> WitnessEvaluationResult:
    """
    Evaluate the entanglement witness operator:
        ⟨W⟩ = (1 - ⟨ZZ⟩ - ⟨XX⟩) / 2
    and its Upper Confidence Bound (UCB).
    
    Statistical Rigor Guarantees:
      1. Minimum shot threshold: requires at least 100 shots per basis.
      2. Independent variance tracking across Z⊗Z and X⊗X datasets.
      3. Hoeffding-consistent variance floor prevents zero-error collapse.
    """
    pauli_zz = calculate_pauli_expectation(counts_zz, "zz")
    pauli_xx = calculate_pauli_expectation(counts_xx, "xx")

    # Guard 1: Minimum sample size
    MINIMUM_SHOTS = 100
    if pauli_zz.total_shots < MINIMUM_SHOTS or pauli_xx.total_shots < MINIMUM_SHOTS:
        return WitnessEvaluationResult(
            exp_zz=pauli_zz.expectation,
            exp_xx=pauli_xx.expectation,
            shots_zz=pauli_zz.total_shots,
            shots_xx=pauli_xx.total_shots,
            witness_expectation=(1.0 - pauli_zz.expectation - pauli_xx.expectation) / 2.0,
            witness_std_err=1.0,
            confidence_level=confidence_level,
            z_score=get_z_score(confidence_level),
            witness_ucb=1.0,
            is_entangled=False,
            rejection_reason=f"Insufficient sample size: ZZ={pauli_zz.total_shots}, XX={pauli_xx.total_shots} (minimum {MINIMUM_SHOTS} required per basis)"
        )

    exp_zz = pauli_zz.expectation
    exp_xx = pauli_xx.expectation

    witness_mean = (1.0 - exp_zz - exp_xx) / 2.0

    # Variance of the estimator across independent measurement sets:
    # Var(Ŵ) = (1/4) * ( Var(⟨ZZ⟩)/N_zz + Var(⟨XX⟩)/N_xx )
    var_mean_zz = pauli_zz.variance / pauli_zz.total_shots
    var_mean_xx = pauli_xx.variance / pauli_xx.total_shots
    var_witness = 0.25 * (var_mean_zz + var_mean_xx)
    empirical_std_err = math.sqrt(max(0.0, var_witness))

    # Guard 2: Exact distribution-free Hoeffding bound for bounded sum of variables in [-1, +1]
    # W = 1/2 - 1/(2*N_zz)*sum(Z_i) - 1/(2*N_xx)*sum(X_j)
    # The range of each term T_i = -Z_i/(2*N_zz) is (1/2N - (-1/2N)) = 1/N_zz.
    # Sum of squared ranges: sum_{i=1}^{N_zz} (1/N_zz)^2 + sum_{j=1}^{N_xx} (1/N_xx)^2 = 1/N_zz + 1/N_xx.
    # By Hoeffding's inequality: P(Ŵ - ⟨W⟩ ≥ t) ≤ exp( -2 * t^2 / (1/N_zz + 1/N_xx) )
    # Setting tail probability to alpha = 1 - confidence_level (e.g. 0.01 for 99%):
    # t_hoeffding = sqrt( 0.5 * ln(1/alpha) * (1/N_zz + 1/N_xx) )
    alpha = max(1e-6, 1.0 - confidence_level)
    sum_sq_ranges = (1.0 / pauli_zz.total_shots) + (1.0 / pauli_xx.total_shots)
    hoeffding_delta = math.sqrt(0.5 * math.log(1.0 / alpha) * sum_sq_ranges)

    z_score = get_z_score(confidence_level)
    # The conservative standard error ensures that z_score * SE is at least hoeffding_delta
    conservative_std_err = max(empirical_std_err, hoeffding_delta / z_score)
    # The final UCB is guaranteed to satisfy both normal empirical confidence and distribution-free Hoeffding bound
    witness_ucb = witness_mean + max(z_score * conservative_std_err, hoeffding_delta)

    rejection = None
    if witness_mean >= 0.0:
        rejection = f"Sample witness expectation is non-negative: ⟨W⟩={witness_mean:.6f} ≥ 0.0 (classical/separable state)"
    elif witness_ucb >= 0.0:
        rejection = f"Upper confidence bound ({confidence_level*100:.1f}%) is non-negative: UCB={witness_ucb:.6f} ≥ 0.0 (insufficient statistical significance)"

    is_entangled = witness_ucb < 0.0

    return WitnessEvaluationResult(
        exp_zz=exp_zz,
        exp_xx=exp_xx,
        shots_zz=pauli_zz.total_shots,
        shots_xx=pauli_xx.total_shots,
        witness_expectation=witness_mean,
        witness_std_err=conservative_std_err,
        confidence_level=confidence_level,
        z_score=z_score,
        witness_ucb=witness_ucb,
        is_entangled=is_entangled,
        rejection_reason=rejection
    )


def run_local_reference_experiment(
    shots: int = 1024,
    confidence_level: float = 0.99
) -> Tuple[WitnessEvaluationResult, Dict[str, Any]]:
    """
    Executes the two complementary Bell circuits locally via Qiskit's StatevectorSampler
    and computes the certified witness proof package.
    """
    from qiskit.primitives import StatevectorSampler

    circuits = build_complementary_bell_circuits()
    qc_zz = circuits["zz"]
    qc_xx = circuits["xx"]

    sampler = StatevectorSampler()
    job = sampler.run([qc_zz, qc_xx], shots=shots)
    pub_results = job.result()

    def extract_counts(pub_result) -> Dict[str, int]:
        data_bin = pub_result.data
        reg_name = list(data_bin.keys())[0]
        return getattr(data_bin, reg_name).get_counts()

    counts_zz = extract_counts(pub_results[0])
    counts_xx = extract_counts(pub_results[1])

    witness_result = evaluate_entanglement_witness(
        counts_zz=counts_zz,
        counts_xx=counts_xx,
        confidence_level=confidence_level
    )

    proof_package = build_witness_proof_package(
        backend_name="qiskit_statevector_sampler",
        job_id=f"local-ref-witness-{int(shots)}",
        counts_zz=counts_zz,
        counts_xx=counts_xx,
        witness_result=witness_result
    )

    return witness_result, proof_package


def build_witness_proof_package(
    backend_name: str,
    job_id: str,
    counts_zz: Dict[str, int],
    counts_xx: Dict[str, int],
    witness_result: WitnessEvaluationResult
) -> Dict[str, Any]:
    """
    Packages the complementary-basis experiment into a canonical, tamper-evident proof.
    """
    rounded_exp_zz = round(witness_result.exp_zz, 6)
    rounded_exp_xx = round(witness_result.exp_xx, 6)
    rounded_witness_exp = round(witness_result.witness_expectation, 6)
    rounded_std_err = round(witness_result.witness_std_err, 6)
    rounded_ucb = round(witness_result.witness_ucb, 6)
    avg_correlation = round((witness_result.exp_zz + witness_result.exp_xx) / 2.0, 6)

    canonical_payload_dict = {
        "backend": backend_name,
        "confidence_level": witness_result.confidence_level,
        "correlation": avg_correlation,
        "counts_xx": counts_xx,
        "counts_zz": counts_zz,
        "entanglement_certified": witness_result.is_entangled,
        "exp_xx": rounded_exp_xx,
        "exp_zz": rounded_exp_zz,
        "job_id": job_id,
        "shots_xx": witness_result.shots_xx,
        "shots_zz": witness_result.shots_zz,
        "witness_expectation": rounded_witness_exp,
        "witness_std_err": rounded_std_err,
        "witness_ucb": rounded_ucb
    }

    canonical_payload = json.dumps(canonical_payload_dict, sort_keys=True, separators=(",", ":"))
    block_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

    return {
        "job_id": job_id,
        "canonical_payload": canonical_payload,
        "block_hash": block_hash,
        "correlation": avg_correlation,
        "witness_ucb": rounded_ucb,
        "witness_expectation": rounded_witness_exp,
        "zero_entropy": 0.0
    }
