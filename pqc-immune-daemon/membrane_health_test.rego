package membrane.health_test

import rego.v1
import data.membrane.health

# ── Helper CBOM Builder ──────────────────────────────────────────
make_cbom(kem_algo, sig_algo) := {
    "bomFormat": "CycloneDX",
    "specVersion": "1.6",
    "metadata": {
        "timestamp": "2026-08-18T12:00:00Z"
    },
    "components": [
        {
            "type": "crypto-asset",
            "name": kem_algo,
            "cryptoProperties": {
                "assetType": "algorithm",
                "algorithmProperties": {"algorithm": kem_algo}
            }
        },
        {
            "type": "crypto-asset",
            "name": sig_algo,
            "cryptoProperties": {
                "assetType": "algorithm",
                "algorithmProperties": {"algorithm": sig_algo}
            }
        }
    ]
}

# ── Test 1: Compliant Verdict under Normal Conditions ────────────
test_compliant_verdict if {
    cbom := make_cbom("ML-KEM-768", "ML-DSA-65")
    v := health.verdict with input as cbom with data.threat_flags as {}
    v.node_status == "COMPLIANT"
    v.toxic_count == 0
    v.recommended_fallback == "NONE"
}

# ── Test 2: ML-KEM-512 maps to FrodoKEM-640-AES ──────────────────
test_mlkem_512_fallback if {
    cbom := make_cbom("ML-KEM-512", "ML-DSA-44")
    v := health.verdict with input as cbom with data.threat_flags as {"ML_KEM_COMPROMISED": true}
    v.node_status == "TOXIC"
    v.toxic_count == 1
    v.recommended_fallback == "FrodoKEM-640-AES"
}

# ── Test 3: ML-KEM-768 maps to FrodoKEM-976-AES ──────────────────
test_mlkem_768_fallback if {
    cbom := make_cbom("ML-KEM-768", "ML-DSA-65")
    v := health.verdict with input as cbom with data.threat_flags as {"ML_KEM_COMPROMISED": true}
    v.node_status == "TOXIC"
    v.toxic_count == 1
    v.recommended_fallback == "FrodoKEM-976-AES"
}

# ── Test 4: ML-KEM-1024 maps to FrodoKEM-1344-AES ────────────────
test_mlkem_1024_fallback if {
    cbom := make_cbom("ML-KEM-1024", "ML-DSA-87")
    v := health.verdict with input as cbom with data.threat_flags as {"ML_KEM_COMPROMISED": true}
    v.node_status == "TOXIC"
    v.toxic_count == 1
    v.recommended_fallback == "FrodoKEM-1344-AES"
}

# ── Test 5: Full Lattice Collapse steps down to X25519 ───────────
test_dual_collapse_to_classical if {
    cbom := make_cbom("ML-KEM-768", "ML-DSA-65")
    v := health.verdict with input as cbom with data.threat_flags as {
        "ML_KEM_COMPROMISED": true,
        "FRODOKEM_COMPROMISED": true
    }
    v.node_status == "TOXIC"
    v.recommended_fallback == "X25519"
}

# ── Test 6: Unknown/Deprecated algorithm is rejected ─────────────
test_unapproved_algorithm_rejected if {
    cbom := make_cbom("RSA-1024", "SHA-1")
    v := health.verdict with input as cbom with data.threat_flags as {}
    v.node_status == "TOXIC"
    v.toxic_count == 2
}

# ── Test 7: ISO Strict Profile Rejects FrodoKEM-640 ──────────────
test_iso_strict_denies_frodokem_640 if {
    input_data := {
        "requested_profile": "iso_strict",
        "cipher": "FrodoKEM-640-AES"
    }
    denials := health.deny with input as input_data
    denials["ISO compliance violation: FrodoKEM-640 is not an ISO standard"]
}

# ── Test 8: ISO Strict Profile Omits FrodoKEM-640 from Fallback ─
test_iso_strict_fallback_omits_frodokem_640 if {
    cbom := object.union(make_cbom("ML-KEM-512", "ML-DSA-44"), {"requested_profile": "iso_strict"})
    v := health.verdict with input as cbom with data.threat_flags as {"ML_KEM_COMPROMISED": true}
    v.node_status == "TOXIC"
    v.recommended_fallback == "NONE"
}

# ── Test 9: FIPS Strict Profile (NIST FIPS 203) Disallows Non-FIPS Fallback ──
test_fips_strict_disallows_non_fips_fallback if {
    cbom := object.union(make_cbom("ML-KEM-512", "ML-DSA-44"), {"requested_profile": "fips_strict"})
    v := health.verdict with input as cbom with data.threat_flags as {"ML_KEM_COMPROMISED": true}
    v.node_status == "TOXIC"
    v.recommended_fallback == "NONE"
}

# Strict-profile denial must affect the actual endpoint, not just a deny set.
test_incomplete_inventory_denied if {
    every inventory in [{}, {"components": []}, {"components": [{"type": "library"}]}, {"components": [{"type": "crypto-asset"}]}] {
        cbom := object.union(inventory, {"requested_profile": "fips_strict", "metadata": {"timestamp": "2026-09-16T00:00:00Z"}})
        v := health.verdict with input as cbom
        v.node_status == "TOXIC"
        v.total_components == 0
        v.recommended_fallback == "NONE"
    }
}

test_strict_frodo_verdict if {
    cbom := object.union(make_cbom("FrodoKEM-976-AES", "ML-DSA-65"), {"requested_profile": "fips_strict"})
    v := health.verdict with input as cbom
    v.node_status == "TOXIC"
    v.recommended_fallback == "NONE"
}

test_strict_all_mlkem_variants_stop if {
    every kem in ["ML-KEM-512", "ML-KEM-768", "ML-KEM-1024"] {
        cbom := object.union(make_cbom(kem, "ML-DSA-65"), {"requested_profile": "fips_strict"})
        v := health.verdict with input as cbom with data.threat_flags as {"ML_KEM_COMPROMISED": true, "FRODOKEM_COMPROMISED": true}
        v.node_status == "TOXIC"
        v.recommended_fallback == "NONE"
    }
}
