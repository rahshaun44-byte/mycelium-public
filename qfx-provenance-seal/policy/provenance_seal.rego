package quantumflex.provenance_seal

import rego.v1

default allow := false

# Reject immediately if KEM suite has exhausted to NONE (node halted)
valid_kem_suite if {
    input.kem_suite in ["ML-KEM-768", "ML-KEM-1024", "FrodoKEM-976-AES", "FrodoKEM-1344-AES", "X25519"]
}

valid_structure if {
    input.seal_version == "1.0.0"
    is_string(input.node_id)
    count(input.node_id) > 0
    is_string(input.content_sha256)
    count(input.content_sha256) == 64
    is_string(input.policy_epoch)
    is_number(input.ts_unix)
    is_string(input.nonce)
    is_string(input.alg)
    is_string(input.sig)
}

# Skew tolerance: 300 seconds
clock_valid if {
    now := time.now_ns() / 1000000000
    skew := abs(now - input.ts_unix)
    skew <= 300
}

abs(x) := x if x >= 0
abs(x) := 0 - x if x < 0

allow if {
    valid_structure
    valid_kem_suite
    clock_valid
}
