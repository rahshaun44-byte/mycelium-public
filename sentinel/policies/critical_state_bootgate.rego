package quantumflex.bootgate

import rego.v1

# -------------------------------------------------------------------------
# Default Hard Stop
# Any failure results in an absolute deny. Unverified vectors (h) are 
# routed to the Ghost Node rather than executing blindly.
# -------------------------------------------------------------------------
default allow := false

# Main Admission Gate
allow if {
	valid_schema
	valid_continuity
	valid_decision_binding
	not is_replayed
}

# -------------------------------------------------------------------------
# 1. Schema & Memory Layout Integrity (Closed-Set Struct Enforcement)
# Enforces that the JSON strictly matches the Go/Rust struct layout with
# zero dynamic field injections or loose typing.
# -------------------------------------------------------------------------
allowed_payload_keys := {
	"schema_version",
	"sequence",
	"previous_state_digest",
	"policy_digest",
	"decision_id",
	"input_digest",
	"result",
	"public_credentials",
}

allowed_cred_keys := {
	"ed25519_pub_key",
	"ml_dsa_pub_key",
}

allowed_sig_keys := {
	"ed25519_signature",
	"ml_dsa_signature",
}

valid_schema if {
	# Exact closed-set key validation: rejects any injected / rogue fields
	payload_keys := {k | _ = input.payload[k]}
	payload_keys == allowed_payload_keys

	cred_keys := {k | _ = input.payload.public_credentials[k]}
	cred_keys == allowed_cred_keys

	sig_keys := {k | _ = input.signatures[k]}
	sig_keys == allowed_sig_keys

	# Strict Type and Value Checks
	input.payload.schema_version == "v1"
	is_number(input.payload.sequence)
	is_string(input.payload.previous_state_digest)
	is_string(input.payload.policy_digest)
	is_string(input.payload.decision_id)
	is_string(input.payload.input_digest)
	is_string(input.payload.result)

	# Credentials
	is_string(input.payload.public_credentials.ed25519_pub_key)
	is_string(input.payload.public_credentials.ml_dsa_pub_key)

	# Signatures
	is_string(input.signatures.ed25519_signature)
	is_string(input.signatures.ml_dsa_signature)
}

# -------------------------------------------------------------------------
# 2. Continuity Chain Validation (k)
# data.anchor is provided at runtime, representing the node's last valid state.
# -------------------------------------------------------------------------
valid_continuity if {
	# Sequence must strictly increment by exactly 1.
	input.payload.sequence == data.anchor.sequence + 1

	# Cryptographically links to the local persistent anchor.
	input.payload.previous_state_digest == data.anchor.state_digest
}

# -------------------------------------------------------------------------
# 3. Decision-Specific Binding (x, p)
# Prevents an old ALLOW from being replayed against a new configuration.
# -------------------------------------------------------------------------
valid_decision_binding if {
	input.payload.result == "ALLOW"

	# The policy digest (p) must match the currently enforced baseline policy.
	input.payload.policy_digest == data.environment.active_policy_digest

	# The input digest (x) must match the payload currently attempting execution.
	input.payload.input_digest == data.environment.pending_input_digest
}

# -------------------------------------------------------------------------
# 4. Anti-Replay Enforcement
# -------------------------------------------------------------------------
is_replayed if {
	# decision_id must not exist in the node's ledger of previously consumed IDs.
	input.payload.decision_id in data.ledger.consumed_decisions
}
