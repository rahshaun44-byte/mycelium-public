package quantumflex.epistemic_test

import rego.v1
import data.quantumflex.epistemic

# TC-OPA-01: Valid M4 machine proof with clean decontamination passes
test_mathematical_m4_verified_allowed if {
    test_input := {
        "epistemic_tier": "M4",
        "verification": {
            "verified": true,
            "kernel": "SymPy",
            "execution_time_ms": 12.5
        },
        "decontamination": {
            "quarantine_status": "CLEAN"
        }
    }
    epistemic.allow_vault_admission with input as test_input
}

# TC-OPA-02: Unverified M4 theorem is rejected fail-closed
test_mathematical_m4_unverified_rejected if {
    test_input := {
        "epistemic_tier": "M4",
        "verification": {
            "verified": false,
            "kernel": "SymPy",
            "execution_time_ms": 12.5
        },
        "decontamination": {
            "quarantine_status": "CLEAN"
        }
    }
    not epistemic.allow_vault_admission with input as test_input
}

# TC-OPA-03: Unsupported kernel is rejected
test_mathematical_unsupported_kernel_rejected if {
    test_input := {
        "epistemic_tier": "M4",
        "verification": {
            "verified": true,
            "kernel": "UncertifiedCalculator",
            "execution_time_ms": 5.0
        },
        "decontamination": {
            "quarantine_status": "CLEAN"
        }
    }
    not epistemic.allow_vault_admission with input as test_input
}

# TC-OPA-04: Replicated physical measurement with Merkle proof passes
test_empirical_e5_replicated_allowed if {
    test_input := {
        "epistemic_tier": "E5",
        "provenance": {
            "source_type": "physical_measurement",
            "replications_count": 3,
            "merkle_proof": [{"position": "left", "hash": "0123456789abcdef"}]
        },
        "decontamination": {
            "quarantine_status": "CLEAN"
        }
    }
    epistemic.allow_vault_admission with input as test_input
}

# TC-OPA-05: Empirical claim missing Merkle proof is rejected
test_empirical_missing_merkle_rejected if {
    test_input := {
        "epistemic_tier": "E5",
        "provenance": {
            "source_type": "physical_measurement",
            "replications_count": 3,
            "merkle_proof": []
        },
        "decontamination": {
            "quarantine_status": "CLEAN"
        }
    }
    not epistemic.allow_vault_admission with input as test_input
}

# TC-OPA-06: Quarantined benchmark leak fails closed even if verified
test_quarantined_document_rejected if {
    test_input := {
        "epistemic_tier": "M4",
        "verification": {
            "verified": true,
            "kernel": "Lean4",
            "execution_time_ms": 45.0
        },
        "decontamination": {
            "quarantine_status": "QUARANTINED"
        }
    }
    not epistemic.allow_vault_admission with input as test_input
}

# TC-OPA-07: Theoretical model with bounded entropy and falsification criteria passes
test_theoretical_e2_bounded_entropy_allowed if {
    test_input := {
        "epistemic_tier": "E2",
        "uncertainty": {
            "falsification_criteria_defined": true,
            "semantic_entropy_score": 0.22
        },
        "decontamination": {
            "quarantine_status": "CLEAN"
        }
    }
    epistemic.allow_vault_admission with input as test_input
}

# TC-OPA-08: High semantic entropy (>0.40) is rejected
test_theoretical_high_entropy_rejected if {
    test_input := {
        "epistemic_tier": "E2",
        "uncertainty": {
            "falsification_criteria_defined": true,
            "semantic_entropy_score": 0.58
        },
        "decontamination": {
            "quarantine_status": "CLEAN"
        }
    }
    not epistemic.allow_vault_admission with input as test_input
}
