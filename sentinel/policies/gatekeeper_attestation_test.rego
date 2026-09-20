package quantumflex.telemetry.gatekeeper_test

import data.quantumflex.telemetry.gatekeeper as gk
import rego.v1

golden := {
	"/usr/lib/systemd/systemd": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
	"/usr/bin/quantumflex-relay": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
}

nonces := {"node-a": "6e6f6e63652d31"}

clean_input := {
	"node_uuid": "node-a",
	"epoch_nonce": "6e6f6e63652d31",
	"replayed_pcr10": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
	"expected_pcr10": "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
	"pcr_matches": true,
	"ima_records": [
		{
			"file_path": "/usr/lib/systemd/systemd",
			"file_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
			"algorithm": "sha256",
		},
		{
			"file_path": "/usr/bin/quantumflex-relay",
			"file_hash": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
			"algorithm": "sha256",
		},
	],
}

test_allow_clean_invariant if {
	gk.allow with input as clean_input with data.golden_manifest as golden with data.active_epoch_nonces as nonces
	not gk.route_to_ghost with input as clean_input with data.golden_manifest as golden with data.active_epoch_nonces as nonces
	gk.ledger_commit_manifest.status == "DETERMINISTIC_INVARIANT_PRESERVED" with input as clean_input with data.golden_manifest as golden with data.active_epoch_nonces as nonces
	not gk.ghost_node_manifest with input as clean_input with data.golden_manifest as golden with data.active_epoch_nonces as nonces
}

test_pcr_mismatch_routes_to_ghost if {
	inp := object.union(clean_input, {"pcr_matches": false, "expected_pcr10": "ff"})
	not gk.allow with input as inp with data.golden_manifest as golden with data.active_epoch_nonces as nonces
	gk.route_to_ghost with input as inp with data.golden_manifest as golden with data.active_epoch_nonces as nonces
	gk.ghost_node_manifest.entropy_action == "ABSORB_INTO_GHOST_SINK" with input as inp with data.golden_manifest as golden with data.active_epoch_nonces as nonces
	gk.ghost_node_manifest.h_attack == 0 with input as inp with data.golden_manifest as golden with data.active_epoch_nonces as nonces
	not gk.ledger_commit_manifest with input as inp with data.golden_manifest as golden with data.active_epoch_nonces as nonces
}

test_anomaly_blocks_allow if {
	inp := object.union(clean_input, {"anomaly": {"reason": "hash chain broken"}})
	not gk.allow with input as inp with data.golden_manifest as golden with data.active_epoch_nonces as nonces
	gk.route_to_ghost with input as inp with data.golden_manifest as golden with data.active_epoch_nonces as nonces
}

test_stale_nonce_is_ghost if {
	inp := object.union(clean_input, {"epoch_nonce": "deadbeef"})
	not gk.allow with input as inp with data.golden_manifest as golden with data.active_epoch_nonces as nonces
}

test_hash_mismatch_against_golden if {
	inp := json.patch(clean_input, [{
		"op": "replace",
		"path": "/ima_records/1/file_hash",
		"value": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
	}])
	not gk.allow with input as inp with data.golden_manifest as golden with data.active_epoch_nonces as nonces
	count(gk.runtime_execution_violations) == 1 with input as inp with data.golden_manifest as golden with data.active_epoch_nonces as nonces
}

test_unregistered_binary if {
	inp := json.patch(clean_input, [{
		"op": "add",
		"path": "/ima_records/-",
		"value": {
			"file_path": "/tmp/evil",
			"file_hash": "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
			"algorithm": "sha256",
		},
	}])
	not gk.allow with input as inp with data.golden_manifest as golden with data.active_epoch_nonces as nonces
	gk.route_to_ghost with input as inp with data.golden_manifest as golden with data.active_epoch_nonces as nonces
}

test_missing_nonce_table_fail_closed if {
	not gk.allow with input as clean_input with data.golden_manifest as golden with data.active_epoch_nonces as {}
}
