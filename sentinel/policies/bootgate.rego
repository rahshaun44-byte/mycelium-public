package quantumflex.bootgate

import rego.v1

default allow := false

allow if {
	valid_schema
	valid_crypto
	valid_continuity
	valid_binding
	not decision_replayed
}

valid_schema if {
	input.attestation.payload.schema_version == "v1"
	is_number(input.attestation.payload.sequence)
	input.attestation.payload.sequence >= 1
	input.attestation.payload.sequence <= 9007199254740991
	is_string(input.attestation.payload.previous_state_digest)
	is_string(input.attestation.payload.policy_digest)
	is_string(input.attestation.payload.decision_id)
	is_string(input.attestation.payload.input_digest)
	input.attestation.payload.result in {"ALLOW", "DENY"}
}

# These are facts established by the host-side verifier,
# not conclusions OPA reaches by inspecting signature strings.
valid_crypto if {
	input.verification.canonical_digest_verified == true
	input.verification.ed25519_verified == true
	input.verification.ml_dsa_verified == true
	input.verification.trusted_keyring == true
}

valid_continuity if {
	input.attestation.payload.sequence == data.anchor.sequence + 1
	input.attestation.payload.previous_state_digest == data.anchor.state_digest
}

valid_binding if {
	input.attestation.payload.result == "ALLOW"
	input.attestation.payload.policy_digest == data.environment.active_policy_digest
	input.attestation.payload.input_digest == data.environment.pending_input_digest
}

decision_replayed if {
	input.attestation.payload.decision_id in data.ledger.consumed_decisions
}
