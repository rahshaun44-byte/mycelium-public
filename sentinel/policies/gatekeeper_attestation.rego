package quantumflex.telemetry.gatekeeper

import rego.v1

# PCR 10 / IMA Gatekeeper.
# Input is prepared by quantumflex-telemetry (PcrReplayEngine).
# allow → invariant Y. not allow → Ghost sink h.
# Ghost output has zero authority. It is not an admission candidate
# until a later A(Δx, k) pass. H_attack = 0.

default allow := false

# Complete assignment: a clean allow cannot still route to Ghost.
# A default of true plus `route_to_ghost { not allow }` would leave
# route_to_ghost true even when allow succeeded.
default route_to_ghost := false

route_to_ghost if {
	not allow
}

# ------------------------------------------------------------------------------
# 1. Hardware quote and cryptographic nonce validation
# ------------------------------------------------------------------------------

# Boolean rules are undefined when their body fails. Default them so
# ghost_node_manifest can always embed a real true/false.
default valid_pcr_replay := false
default valid_attestation_nonce := false

valid_pcr_replay if {
	input.pcr_matches == true
	input.replayed_pcr10 == input.expected_pcr10
	not input.anomaly
}

valid_attestation_nonce if {
	expected_nonce := data.active_epoch_nonces[input.node_uuid]
	input.epoch_nonce == expected_nonce
}

# ------------------------------------------------------------------------------
# 2. Linux IMA binary & library path verification
# ------------------------------------------------------------------------------

unauthorized_entries contains violation if {
	some record in input.ima_records
	expected_hash := data.golden_manifest[record.file_path]
	record.file_hash != expected_hash
	violation := {
		"file_path": record.file_path,
		"executed_hash": record.file_hash,
		"expected_hash": expected_hash,
		"reason": "Hash mismatch against golden manifest",
	}
}

unregistered_binaries contains violation if {
	some record in input.ima_records
	not data.golden_manifest[record.file_path]
	violation := {
		"file_path": record.file_path,
		"executed_hash": record.file_hash,
		"reason": "Binary path not present in golden manifest",
	}
}

runtime_execution_violations := array.concat(
	[v | some v in unauthorized_entries],
	[v | some v in unregistered_binaries],
)

# ------------------------------------------------------------------------------
# 3. Deterministic Gatekeeper verdict
# ------------------------------------------------------------------------------
# Philosophy: Y = f(x - h) + k
# Spec:       Y_t = F(A(x_t, k_t), k_t)
# h ≠ 0 → x_q. Recovery never grants authority.

allow if {
	valid_pcr_replay
	valid_attestation_nonce
	count(runtime_execution_violations) == 0
}

# Forensic payload for the Ghost entropy sink. Undefined when allow.
# Do not feed this object into f. Do not credit it as KEM entropy.
ghost_node_manifest := {
	"node_uuid": input.node_uuid,
	"timestamp_epoch_nonce": input.epoch_nonce,
	"pcr_integrity_pass": valid_pcr_replay,
	"nonce_freshness_pass": valid_attestation_nonce,
	"structural_anomaly": object.get(input, "anomaly", null),
	"execution_violations": runtime_execution_violations,
	"raw_records_count": count(input.ima_records),
	"entropy_action": "ABSORB_INTO_GHOST_SINK",
	"h_attack": 0,
} if not allow

# Ledger commit only on allow. Undefined when routed to Ghost.
ledger_commit_manifest := {
	"node_uuid": input.node_uuid,
	"verified_pcr10": input.replayed_pcr10,
	"records_committed": count(input.ima_records),
	"state_root": crypto.sha256(concat(":", [input.node_uuid, input.replayed_pcr10, input.epoch_nonce])),
	"status": "DETERMINISTIC_INVARIANT_PRESERVED",
} if allow
