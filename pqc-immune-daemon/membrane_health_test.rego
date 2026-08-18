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
