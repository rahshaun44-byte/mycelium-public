package main

import (
	"context"
	"encoding/json"
	"os"
	"testing"
)

const (
	testRegoPath = "/home/quant/.config/quantumflex/policies/bootgate.rego"
	testWasmPath = "/home/quant/.config/quantumflex/policies/quantumflex_bootgate.wasm"
	testPolicyDigest = "sha3:POLICY_BOOTGATE_V1"
	testInputDigest  = "sha3:INPUT_PENDING_V1"
	testPrevDigest   = "sha3:STATE_K1"
)

func validPositiveInputAndData() (*OPAInput, *OPAData) {
	payloadMap := map[string]interface{}{
		"schema_version":        "v1",
		"sequence":              2,
		"previous_state_digest": testPrevDigest,
		"policy_digest":         testPolicyDigest,
		"decision_id":           "decision-parity-pos-001",
		"input_digest":          testInputDigest,
		"result":                "ALLOW",
	}
	payloadBytes, _ := json.Marshal(payloadMap)

	input := &OPAInput{}
	input.Attestation.Payload = payloadBytes
	input.Verification.CanonicalDigestVerified = true
	input.Verification.Ed25519Verified = true
	input.Verification.MLDSAVerified = true
	input.Verification.TrustedKeyring = true

	data := &OPAData{
		Anchor: Anchor{
			Sequence:    1,
			StateDigest: testPrevDigest,
		},
		Environment: OPAEnvironment{
			ActivePolicyDigest: testPolicyDigest,
			PendingInputDigest: testInputDigest,
		},
	}
	data.Ledger.ConsumedDecisions = []string{}

	return input, data
}

func TestOPAParity_PositiveExecution(t *testing.T) {
	ctx := context.Background()
	input, data := validPositiveInputAndData()

	nativeAllow, err := EvaluateNative(ctx, testRegoPath, input, data)
	if err != nil {
		t.Fatalf("EvaluateNative failed on valid fixture: %v", err)
	}

	wasmAllow, err := EvaluateWasm(ctx, testWasmPath, input, data)
	if err != nil {
		t.Fatalf("EvaluateWasm failed on valid fixture: %v", err)
	}

	// Parity requires BOTH paths to explicitly evaluate to true
	if !nativeAllow {
		t.Errorf("Native evaluation expected true, got false")
	}
	if !wasmAllow {
		t.Errorf("WASM evaluation expected true, got false")
	}
	if nativeAllow != wasmAllow {
		t.Errorf("Parity mismatch! Native: %v, WASM: %v", nativeAllow, wasmAllow)
	}
}

func TestOPAParity_NegativeCases(t *testing.T) {
	ctx := context.Background()

	cases := []struct {
		name    string
		mutate  func(input *OPAInput, data *OPAData)
	}{
		{
			name: "Sequence Rollback (seq 0)",
			mutate: func(input *OPAInput, data *OPAData) {
				var p map[string]interface{}
				json.Unmarshal(input.Attestation.Payload, &p)
				p["sequence"] = 0
				b, _ := json.Marshal(p)
				input.Attestation.Payload = b
			},
		},
		{
			name: "Sequence Skip (seq 4 when anchor is 1)",
			mutate: func(input *OPAInput, data *OPAData) {
				var p map[string]interface{}
				json.Unmarshal(input.Attestation.Payload, &p)
				p["sequence"] = 4
				b, _ := json.Marshal(p)
				input.Attestation.Payload = b
			},
		},
		{
			name: "Previous State Digest Mismatch",
			mutate: func(input *OPAInput, data *OPAData) {
				var p map[string]interface{}
				json.Unmarshal(input.Attestation.Payload, &p)
				p["previous_state_digest"] = "sha3:TAMPERED_PREV"
				b, _ := json.Marshal(p)
				input.Attestation.Payload = b
			},
		},
		{
			name: "Policy Digest Binding Mismatch",
			mutate: func(input *OPAInput, data *OPAData) {
				var p map[string]interface{}
				json.Unmarshal(input.Attestation.Payload, &p)
				p["policy_digest"] = "sha3:UNKNOWN_POLICY"
				b, _ := json.Marshal(p)
				input.Attestation.Payload = b
			},
		},
		{
			name: "Input Digest Binding Mismatch",
			mutate: func(input *OPAInput, data *OPAData) {
				var p map[string]interface{}
				json.Unmarshal(input.Attestation.Payload, &p)
				p["input_digest"] = "sha3:UNEXPECTED_INPUT"
				b, _ := json.Marshal(p)
				input.Attestation.Payload = b
			},
		},
		{
			name: "Replayed Decision ID",
			mutate: func(input *OPAInput, data *OPAData) {
				data.Ledger.ConsumedDecisions = []string{"decision-parity-pos-001"}
			},
		},
		{
			name: "DENY Result",
			mutate: func(input *OPAInput, data *OPAData) {
				var p map[string]interface{}
				json.Unmarshal(input.Attestation.Payload, &p)
				p["result"] = "DENY"
				b, _ := json.Marshal(p)
				input.Attestation.Payload = b
			},
		},
		{
			name: "Untrusted Keyring Fact False",
			mutate: func(input *OPAInput, data *OPAData) {
				input.Verification.TrustedKeyring = false
			},
		},
		{
			name: "Ed25519 Verified Fact False",
			mutate: func(input *OPAInput, data *OPAData) {
				input.Verification.Ed25519Verified = false
			},
		},
		{
			name: "ML-DSA Verified Fact False",
			mutate: func(input *OPAInput, data *OPAData) {
				input.Verification.MLDSAVerified = false
			},
		},
		{
			name: "Canonical Digest Verified Fact False",
			mutate: func(input *OPAInput, data *OPAData) {
				input.Verification.CanonicalDigestVerified = false
			},
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			input, data := validPositiveInputAndData()
			tc.mutate(input, data)

			nativeAllow, err := EvaluateNative(ctx, testRegoPath, input, data)
			if err != nil {
				t.Fatalf("EvaluateNative unexpected error: %v", err)
			}

			wasmAllow, err := EvaluateWasm(ctx, testWasmPath, input, data)
			if err != nil {
				t.Fatalf("EvaluateWasm unexpected error: %v", err)
			}

			if nativeAllow != wasmAllow {
				t.Errorf("Parity mismatch on %s: Native=%v, WASM=%v", tc.name, nativeAllow, wasmAllow)
			}
			if nativeAllow != false {
				t.Errorf("Expected DENY (false) on %s, got Native=%v, WASM=%v", tc.name, nativeAllow, wasmAllow)
			}
		})
	}
}

func TestOPAParity_ArtifactErrors(t *testing.T) {
	ctx := context.Background()
	input, data := validPositiveInputAndData()

	// 1. Literal invalid wasm file ("not a wasm module")
	tmpInvalidWasm, err := os.CreateTemp("", "invalid-*.wasm")
	if err != nil {
		t.Fatal(err)
	}
	defer os.Remove(tmpInvalidWasm.Name())
	tmpInvalidWasm.WriteString("not a wasm module")
	tmpInvalidWasm.Close()

	_, err = EvaluateWasm(ctx, tmpInvalidWasm.Name(), input, data)
	if err == nil {
		t.Errorf("expected error when evaluating non-wasm file, got nil")
	}

	// 2. Missing wasm file
	_, err = EvaluateWasm(ctx, "/path/does/not/exist/policy.wasm", input, data)
	if err == nil {
		t.Errorf("expected error when wasm file is missing, got nil")
	}
}
