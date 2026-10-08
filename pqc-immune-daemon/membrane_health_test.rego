package membrane.health_test

import data.membrane.health
import rego.v1

# Test: Healthy node with ML-KEM-768, agility profile, and verified clean threat feed
test_healthy_ml_kem if {
    result := health.verdict with input as {
        "requested_profile": "agility",
        "metadata": {"timestamp": "2026-07-15T19:00:00Z"},
        "components": [{
            "type": "crypto-asset",
            "cryptoProperties": {
                "algorithmProperties": {"algorithm": "ML-KEM-768"}
            }
        }]
    } with data.threat_flags as {
        "ML_KEM_COMPROMISED": false,
        "FRODOKEM_COMPROMISED": false
    }
    
    result.node_status == "COMPLIANT"
    result.verification_state == "VERIFIED"
    result.toxic_count == 0
}

# Test: ML-KEM-768 flagged as compromised with verified threat feed
test_compromised_ml_kem if {
    result := health.verdict with input as {
        "requested_profile": "agility",
        "metadata": {"timestamp": "2026-07-15T19:00:00Z"},
        "components": [{
            "type": "crypto-asset",
            "cryptoProperties": {
                "algorithmProperties": {"algorithm": "ML-KEM-768"}
            }
        }]
    } with data.threat_flags as {
        "ML_KEM_COMPROMISED": true,
        "FRODOKEM_COMPROMISED": false
    }
    
    result.node_status == "TOXIC"
    result.verification_state == "VERIFIED"
    result.recommended_fallback == "FrodoKEM-976-AES"
}

# Test: All PQC compromised — classical reversion with verified threat feed
test_full_reversion if {
    result := health.verdict with input as {
        "requested_profile": "agility",
        "metadata": {"timestamp": "2026-07-15T19:00:00Z"},
        "components": [{
            "type": "crypto-asset",
            "cryptoProperties": {
                "algorithmProperties": {"algorithm": "ML-KEM-768"}
            }
        }]
    } with data.threat_flags as {
        "ML_KEM_COMPROMISED": true,
        "FRODOKEM_COMPROMISED": true
    }
    
    result.node_status == "TOXIC"
    result.verification_state == "VERIFIED"
    result.recommended_fallback == "X25519"
}

# Test: Missing requested_profile must fail closed (Task 5)
test_missing_profile_fails_closed if {
    result := health.verdict with input as {
        "metadata": {"timestamp": "2026-07-15T19:00:00Z"},
        "components": [{
            "type": "crypto-asset",
            "cryptoProperties": {
                "algorithmProperties": {"algorithm": "ML-KEM-768"}
            }
        }]
    } with data.threat_flags as {
        "ML_KEM_COMPROMISED": false,
        "FRODOKEM_COMPROMISED": false
    }
    
    result.node_status == "TOXIC"
    result.verification_state == "INVALID"
    count(result.deny_reasons) > 0
}

# Test: Unknown requested_profile must fail closed (Task 5)
test_unknown_profile_fails_closed if {
    result := health.verdict with input as {
        "requested_profile": "quantum_cowboy",
        "metadata": {"timestamp": "2026-07-15T19:00:00Z"},
        "components": [{
            "type": "crypto-asset",
            "cryptoProperties": {
                "algorithmProperties": {"algorithm": "ML-KEM-768"}
            }
        }]
    } with data.threat_flags as {
        "ML_KEM_COMPROMISED": false,
        "FRODOKEM_COMPROMISED": false
    }
    
    result.node_status == "TOXIC"
    result.verification_state == "INVALID"
    count(result.deny_reasons) > 0
}

# Test: Missing threat feed must NOT be assumed safe (Task 7)
test_missing_threat_feed_unverified if {
    result := health.verdict with input as {
        "requested_profile": "agility",
        "metadata": {"timestamp": "2026-07-15T19:00:00Z"},
        "components": [{
            "type": "crypto-asset",
            "cryptoProperties": {
                "algorithmProperties": {"algorithm": "ML-KEM-768"}
            }
        }]
    } with data.threat_flags as {}
    
    result.node_status == "TOXIC"
    result.verification_state == "UNVERIFIED"
    result.node_status != "COMPLIANT"
}

# Test: Empty inventory must never become COMPLIANT (Task 6)
test_empty_components_denied if {
    result := health.verdict with input as {
        "requested_profile": "fips_strict",
        "metadata": {"timestamp": "2026-07-15T19:00:00Z"},
        "components": []
    } with data.threat_flags as {
        "ML_KEM_COMPROMISED": false,
        "FRODOKEM_COMPROMISED": false
    }
    
    result.node_status == "TOXIC"
    result.verification_state == "DENIED"
    result.node_status != "COMPLIANT"
}

# Test: Missing components must be marked MISSING (Task 6)
test_missing_components_marked_missing if {
    result := health.verdict with input as {
        "requested_profile": "fips_strict",
        "metadata": {"timestamp": "2026-07-15T19:00:00Z"}
    } with data.threat_flags as {
        "ML_KEM_COMPROMISED": false,
        "FRODOKEM_COMPROMISED": false
    }
    
    result.node_status == "TOXIC"
    result.verification_state == "MISSING"
}
