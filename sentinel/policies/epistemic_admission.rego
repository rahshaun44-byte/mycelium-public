package quantumflex.epistemic

import rego.v1

# ==============================================================================
# QUANTUMFLEX EPISTEMIC ADMISSION POLICY (QF-ATHENA-FOUNDATION-02)
# Enforces:
#   1. Machine Verification != Empirical Truth Invariant
#   2. Mathematical Tier M4/M5 must have certified proof record
#   3. Empirical Tier E4/E5 must have physical measurement provenance and Merkle proofs
#   4. Theoretical Tier E1-E3 admitted only with bounded semantic entropy & falsification
#   5. Fail-closed on contaminated literature (quarantine_status != "CLEAN")
# ==============================================================================

default allow_vault_admission := false
default mathematical_proof_valid := false
default empirical_provenance_valid := false
default theoretical_uncertainty_valid := false
default literature_decontaminated := false

# Check decontamination: Must be explicitly CLEAN
literature_decontaminated if {
    input.decontamination.quarantine_status == "CLEAN"
}

# Rule 1: Mathematical results claimed as M4 or M5 must possess verified machine proof
mathematical_proof_valid if {
    input.epistemic_tier in ["M4", "M5"]
    input.verification.verified == true
    input.verification.kernel in ["Lean4", "Coq", "SymPy"]
    input.verification.execution_time_ms > 0
}

# Rule 2: Empirical claims E4 or E5 must possess independent physical measurement provenance
empirical_provenance_valid if {
    input.epistemic_tier in ["E4", "E5"]
    input.provenance.source_type == "physical_measurement"
    input.provenance.replications_count >= 2
    count(input.provenance.merkle_proof) > 0
}

# Rule 3: Theoretical models E1-E3 admitted only with explicit uncertainty bounds
theoretical_uncertainty_valid if {
    input.epistemic_tier in ["E1", "E2", "E3"]
    input.uncertainty.falsification_criteria_defined == true
    input.uncertainty.semantic_entropy_score < 0.40
}

# Primary Admission Gate:
# Requires literature to be clean AND matching tier condition satisfied
allow_vault_admission if {
    literature_decontaminated
    mathematical_proof_valid
}

allow_vault_admission if {
    literature_decontaminated
    empirical_provenance_valid
}

allow_vault_admission if {
    literature_decontaminated
    theoretical_uncertainty_valid
}
