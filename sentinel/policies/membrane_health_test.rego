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

# Test: fips_strict profile with compliant ML-KEM-768 (Task 5)
test_fips_strict_compliant if {
    result := health.verdict with input as {
        "requested_profile": "fips_strict",
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
    count(result.deny_reasons) == 0
}

# Test: fips_strict profile rejects non-FIPS algorithm (Task 5)
test_fips_strict_rejects_non_fips if {
    result := health.verdict with input as {
        "requested_profile": "fips_strict",
        "metadata": {"timestamp": "2026-07-15T19:00:00Z"},
        "components": [{
            "type": "crypto-asset",
            "cryptoProperties": {
                "algorithmProperties": {"algorithm": "FrodoKEM-640-AES"}
            }
        }]
    } with data.threat_flags as {
        "ML_KEM_COMPROMISED": false,
        "FRODOKEM_COMPROMISED": false
    }
    
    result.node_status == "TOXIC"
    result.deny_reasons[_] == "FIPS compliance violation: Non-FIPS algorithm in fips_strict profile"
}

# Test: iso_strict profile with compliant ML-KEM-768 (Task 5)
test_iso_strict_compliant if {
    result := health.verdict with input as {
        "requested_profile": "iso_strict",
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
    count(result.deny_reasons) == 0
}

# Test: iso_strict profile rejects FrodoKEM-640-AES (Task 5)
test_iso_strict_rejects_frodokem640 if {
    result := health.verdict with input as {
        "requested_profile": "iso_strict",
        "metadata": {"timestamp": "2026-07-15T19:00:00Z"},
        "components": [{
            "type": "crypto-asset",
            "cryptoProperties": {
                "algorithmProperties": {"algorithm": "FrodoKEM-640-AES"}
            }
        }]
    } with data.threat_flags as {
        "ML_KEM_COMPROMISED": false,
        "FRODOKEM_COMPROMISED": false
    }
    
    result.node_status == "TOXIC"
    result.deny_reasons[_] == "ISO compliance violation: FrodoKEM-640 is not an ISO standard"
}

# Test: FrodoKEM flagged as compromised (Task 7)
test_compromised_frodokem if {
    result := health.verdict with input as {
        "requested_profile": "agility",
        "metadata": {"timestamp": "2026-07-15T19:00:00Z"},
        "components": [{
            "type": "crypto-asset",
            "cryptoProperties": {
                "algorithmProperties": {"algorithm": "FrodoKEM-640-AES"}
            }
        }]
    } with data.threat_flags as {
        "ML_KEM_COMPROMISED": false,
        "FRODOKEM_COMPROMISED": true
    }
    
    result.node_status == "TOXIC"
    result.verification_state == "VERIFIED"
    result.recommended_fallback == "X25519"
}

# Test: FrodoKEM with unverified threat feed fails (Task 7)
test_unverified_frodokem_threat_feed if {
    result := health.verdict with input as {
        "requested_profile": "agility",
        "metadata": {"timestamp": "2026-07-15T19:00:00Z"},
        "components": [{
            "type": "crypto-asset",
            "cryptoProperties": {
                "algorithmProperties": {"algorithm": "FrodoKEM-640-AES"}
            }
        }]
    } with data.threat_flags as {
        "ML_KEM_COMPROMISED": false
    }
    
    result.node_status == "TOXIC"
    result.verification_state == "UNVERIFIED"
    result.deny_reasons[_] == "Threat feed unverified: active algorithm has no threat attestation"
}

# Test: Non-crypto-asset components results in zero assessed crypto-assets (Task 6)
test_non_crypto_components_denied if {
    result := health.verdict with input as {
        "requested_profile": "fips_strict",
        "metadata": {"timestamp": "2026-07-15T19:00:00Z"},
        "components": [{
            "type": "framework",
            "name": "react"
        }]
    } with data.threat_flags as {
        "ML_KEM_COMPROMISED": false,
        "FRODOKEM_COMPROMISED": false
    }
    
    result.node_status == "TOXIC"
    result.deny_reasons[_] == "Missing crypto-assets: CBOM contains zero assessed crypto-asset components"
}
