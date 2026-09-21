package quantumflex.bootgate_test

import rego.v1

import data.quantumflex.bootgate

good_input := {
	"attestation": {"payload": {
		"schema_version": "v1",
		"sequence": 42,
		"previous_state_digest": "sha3:STATE41",
		"policy_digest": "sha3:POLICY_A",
		"decision_id": "decision-42",
		"input_digest": "sha3:INPUT_A",
		"result": "ALLOW",
	}},
	"verification": {
		"canonical_digest_verified": true,
		"ed25519_verified": true,
		"ml_dsa_verified": true,
		"trusted_keyring": true,
	},
}

test_valid_state_allowed if {
	bootgate.allow with input as good_input
		with data.anchor as {"sequence": 41, "state_digest": "sha3:STATE41"}
		with data.environment as {"active_policy_digest": "sha3:POLICY_A", "pending_input_digest": "sha3:INPUT_A"}
		with data.ledger as {"consumed_decisions": []}
}

test_replayed_decision_denied if {
	not bootgate.allow with input as good_input
		with data.anchor as {"sequence": 41, "state_digest": "sha3:STATE41"}
		with data.environment as {"active_policy_digest": "sha3:POLICY_A", "pending_input_digest": "sha3:INPUT_A"}
		with data.ledger as {"consumed_decisions": ["decision-42"]}
}

test_wrong_previous_digest_denied if {
	not bootgate.allow with input as good_input
		with data.anchor as {"sequence": 41, "state_digest": "sha3:ATTACKER_STATE"}
		with data.environment as {"active_policy_digest": "sha3:POLICY_A", "pending_input_digest": "sha3:INPUT_A"}
		with data.ledger as {"consumed_decisions": []}
}

test_policy_swap_denied if {
	not bootgate.allow with input as good_input
		with data.anchor as {"sequence": 41, "state_digest": "sha3:STATE41"}
		with data.environment as {"active_policy_digest": "sha3:POLICY_ATTACKER", "pending_input_digest": "sha3:INPUT_A"}
		with data.ledger as {"consumed_decisions": []}
}

test_bad_ed25519_denied if {
	bad := object.union(
		good_input,
		{"verification": {
			"canonical_digest_verified": true,
			"ed25519_verified": false,
			"ml_dsa_verified": true,
			"trusted_keyring": true,
		}},
	)
	not bootgate.allow with input as bad
		with data.anchor as {"sequence": 41, "state_digest": "sha3:STATE41"}
		with data.environment as {"active_policy_digest": "sha3:POLICY_A", "pending_input_digest": "sha3:INPUT_A"}
		with data.ledger as {"consumed_decisions": []}
}

test_bad_ml_dsa_denied if {
	bad := object.union(
		good_input,
		{"verification": {
			"canonical_digest_verified": true,
			"ed25519_verified": true,
			"ml_dsa_verified": false,
			"trusted_keyring": true,
		}},
	)
	not bootgate.allow with input as bad
		with data.anchor as {"sequence": 41, "state_digest": "sha3:STATE41"}
		with data.environment as {"active_policy_digest": "sha3:POLICY_A", "pending_input_digest": "sha3:INPUT_A"}
		with data.ledger as {"consumed_decisions": []}
}

test_untrusted_keyring_denied if {
	bad := object.union(
		good_input,
		{"verification": {
			"canonical_digest_verified": true,
			"ed25519_verified": true,
			"ml_dsa_verified": true,
			"trusted_keyring": false,
		}},
	)
	not bootgate.allow with input as bad
		with data.anchor as {"sequence": 41, "state_digest": "sha3:STATE41"}
		with data.environment as {"active_policy_digest": "sha3:POLICY_A", "pending_input_digest": "sha3:INPUT_A"}
		with data.ledger as {"consumed_decisions": []}
}

test_bad_canonical_digest_denied if {
	bad := object.union(
		good_input,
		{"verification": {
			"canonical_digest_verified": false,
			"ed25519_verified": true,
			"ml_dsa_verified": true,
			"trusted_keyring": true,
		}},
	)
	not bootgate.allow with input as bad
		with data.anchor as {"sequence": 41, "state_digest": "sha3:STATE41"}
		with data.environment as {"active_policy_digest": "sha3:POLICY_A", "pending_input_digest": "sha3:INPUT_A"}
		with data.ledger as {"consumed_decisions": []}
}

test_sequence_rollback_denied if {
	not bootgate.allow with input as good_input
		with data.anchor as {"sequence": 42, "state_digest": "sha3:STATE41"}
		with data.environment as {"active_policy_digest": "sha3:POLICY_A", "pending_input_digest": "sha3:INPUT_A"}
		with data.ledger as {"consumed_decisions": []}
}

test_input_mismatch_denied if {
	not bootgate.allow with input as good_input
		with data.anchor as {"sequence": 41, "state_digest": "sha3:STATE41"}
		with data.environment as {"active_policy_digest": "sha3:POLICY_A", "pending_input_digest": "sha3:INPUT_ATTACKER"}
		with data.ledger as {"consumed_decisions": []}
}

test_sequence_exceeds_ieee754_precision_denied if {
	# 9007199254740992 exceeds 2^53 - 1
	overflow_input := {
		"attestation": {"payload": {
			"schema_version": "v1",
			"sequence": 9007199254740992,
			"previous_state_digest": "sha3:STATE41",
			"policy_digest": "sha3:POLICY_A",
			"decision_id": "decision-overflow",
			"input_digest": "sha3:INPUT_A",
			"result": "ALLOW",
		}},
		"verification": {
			"canonical_digest_verified": true,
			"ed25519_verified": true,
			"ml_dsa_verified": true,
			"trusted_keyring": true,
		},
	}
	not bootgate.allow with input as overflow_input
		with data.anchor as {"sequence": 9007199254740991, "state_digest": "sha3:STATE41"}
		with data.environment as {"active_policy_digest": "sha3:POLICY_A", "pending_input_digest": "sha3:INPUT_A"}
		with data.ledger as {"consumed_decisions": []}
}
