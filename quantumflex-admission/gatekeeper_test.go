package main

import (
	"context"
	"crypto/ed25519"
	"crypto/mldsa"
	"encoding/json"
	"encoding/json/jsontext"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"golang.org/x/crypto/sha3"
)

func createDualSignedAttestation(t *testing.T, payloadMap map[string]interface{}, edPriv ed25519.PrivateKey, edID string, mlPriv *mldsa.PrivateKey, mlID string) []byte {
	payloadBytes, err := json.Marshal(payloadMap)
	if err != nil {
		t.Fatalf("marshal payload: %v", err)
	}

	val := jsontext.Value(payloadBytes)
	if err := val.Canonicalize(); err != nil {
		t.Fatalf("canonicalize: %v", err)
	}
	h := sha3.New256()
	h.Write([]byte(val))
	digest := h.Sum(nil)

	edSig := ed25519.Sign(edPriv, digest)
	mlSig, err := mlPriv.Sign(nil, digest, &mldsa.Options{Context: "QF-CRITICAL-STATE-V1"})
	if err != nil {
		t.Fatalf("ml sign: %v", err)
	}

	env := Envelope{}
	env.Attestation.KeyIDs.Ed25519KeyID = edID
	env.Attestation.KeyIDs.MLDSAKeyID = mlID
	env.Attestation.Signatures.Ed25519Signature = edSig
	env.Attestation.Signatures.MLDSASignature = mlSig
	env.Attestation.Payload = payloadBytes

	envBytes, err := json.Marshal(env)
	if err != nil {
		t.Fatalf("marshal envelope: %v", err)
	}
	return envBytes
}

func TestGatekeeper_DualSignedAdmit_Success(t *testing.T) {
	edPub, edPriv, _ := ed25519.GenerateKey(nil)
	mlPriv, _ := mldsa.GenerateKey(mldsa.MLDSA65())
	mlPub := mlPriv.PublicKey()

	edID := "ed25519-gatekeeper-test"
	mlID := "mldsa-gatekeeper-test"

	verifier, err := NewVerifier(edPub, edID, mlPub, mlID)
	if err != nil {
		t.Fatalf("NewVerifier failed: %v", err)
	}

	store, err := NewStore(":memory:")
	if err != nil {
		t.Fatalf("NewStore failed: %v", err)
	}
	defer store.Close()

	gk := NewGatekeeper(testWasmPath)
	gk.SetActivePolicyDigest(testPolicyDigest)

	var executionExecuted atomic.Bool
	gk.SetExecutionCallback(func(ctx context.Context, payload *PayloadStruct) error {
		executionExecuted.Store(true)
		return nil
	})

	payloadMap := map[string]interface{}{
		"schema_version":        "v1",
		"sequence":              2,
		"previous_state_digest": testPrevDigest,
		"policy_digest":         testPolicyDigest,
		"decision_id":           "decision-admit-success-001",
		"input_digest":          testInputDigest,
		"result":                "ALLOW",
	}

	attestationBytes := createDualSignedAttestation(t, payloadMap, edPriv, edID, mlPriv, mlID)

	ctx := context.Background()
	err = gk.Admit(ctx, attestationBytes, verifier, store, testInputDigest)
	if err != nil {
		t.Fatalf("Admit failed on valid dual-signed attestation: %v", err)
	}

	if !executionExecuted.Load() {
		t.Errorf("expected execution callback to run after successful admission")
	}

	// Verify authoritative state in store
	anchor, err := store.GetAnchor()
	if err != nil {
		t.Fatalf("GetAnchor failed: %v", err)
	}
	if anchor.Sequence != 2 {
		t.Errorf("expected anchor sequence to advance to 2, got %d", anchor.Sequence)
	}

	decisions, err := store.GetConsumedDecisions()
	if err != nil {
		t.Fatalf("GetConsumedDecisions failed: %v", err)
	}
	if len(decisions) != 1 || decisions[0] != "decision-admit-success-001" {
		t.Errorf("expected ledger to contain decision, got %v", decisions)
	}
}

func TestGatekeeper_NegativeCases_StateRemainsUnchanged(t *testing.T) {
	edPub, edPriv, _ := ed25519.GenerateKey(nil)
	mlPriv, _ := mldsa.GenerateKey(mldsa.MLDSA65())
	mlPub := mlPriv.PublicKey()

	edID := "ed25519-gatekeeper-test"
	mlID := "mldsa-gatekeeper-test"

	verifier, _ := NewVerifier(edPub, edID, mlPub, mlID)

	cases := []struct {
		name               string
		activePolicyDigest string
		pendingInputDigest string
		mutatePayload      func(m map[string]interface{})
		tamperBytes        func(b []byte) []byte
	}{
		{
			name:               "Missing Active Policy Digest Binding",
			activePolicyDigest: "", // empty
			pendingInputDigest: testInputDigest,
		},
		{
			name:               "Missing Pending Input Digest Binding",
			activePolicyDigest: testPolicyDigest,
			pendingInputDigest: "", // empty
		},
		{
			name:               "Mismatched Active Policy Binding",
			activePolicyDigest: "sha3:DIFFERENT_POLICY",
			pendingInputDigest: testInputDigest,
		},
		{
			name:               "Mismatched Pending Input Binding",
			activePolicyDigest: testPolicyDigest,
			pendingInputDigest: "sha3:DIFFERENT_INPUT",
		},
		{
			name:               "Sequence Rollback (Sequence 1 instead of 2)",
			activePolicyDigest: testPolicyDigest,
			pendingInputDigest: testInputDigest,
			mutatePayload: func(m map[string]interface{}) {
				m["sequence"] = 1
			},
		},
		{
			name:               "Result is DENY",
			activePolicyDigest: testPolicyDigest,
			pendingInputDigest: testInputDigest,
			mutatePayload: func(m map[string]interface{}) {
				m["result"] = "DENY"
			},
		},
		{
			name:               "Previous State Digest Mismatch",
			activePolicyDigest: testPolicyDigest,
			pendingInputDigest: testInputDigest,
			mutatePayload: func(m map[string]interface{}) {
				m["previous_state_digest"] = "sha3:WRONG_PREV"
			},
		},
		{
			name:               "Tampered Signature",
			activePolicyDigest: testPolicyDigest,
			pendingInputDigest: testInputDigest,
			tamperBytes: func(b []byte) []byte {
				return []byte(strings.Replace(string(b), "ed25519_signature\":\"", "ed25519_signature\":\"bad-sig", 1))
			},
		},
		{
			name:               "Malformed Strict JSON (extra field)",
			activePolicyDigest: testPolicyDigest,
			pendingInputDigest: testInputDigest,
			tamperBytes: func(b []byte) []byte {
				return []byte(strings.Replace(string(b), "}}", `,"PRIVATE_SECRET_123":"leaked"}}`, 1))
			},
		},
	}

	mockServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusCreated)
	}))
	defer mockServer.Close()

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			store, err := NewStore(":memory:")
			if err != nil {
				t.Fatalf("NewStore: %v", err)
			}
			defer store.Close()

			gk := NewGatekeeper(testWasmPath)
			gk.ghostNodeIP = mockServer.URL
			gk.SetActivePolicyDigest(tc.activePolicyDigest)

			var executionExecuted atomic.Bool
			gk.SetExecutionCallback(func(ctx context.Context, payload *PayloadStruct) error {
				executionExecuted.Store(true)
				return nil
			})

			payloadMap := map[string]interface{}{
				"schema_version":        "v1",
				"sequence":              2,
				"previous_state_digest": testPrevDigest,
				"policy_digest":         testPolicyDigest,
				"decision_id":           fmt.Sprintf("dec-neg-%s", tc.name),
				"input_digest":          testInputDigest,
				"result":                "ALLOW",
			}
			if tc.mutatePayload != nil {
				tc.mutatePayload(payloadMap)
			}

			attestationBytes := createDualSignedAttestation(t, payloadMap, edPriv, edID, mlPriv, mlID)
			if tc.tamperBytes != nil {
				attestationBytes = tc.tamperBytes(attestationBytes)
			}

			ctx := context.Background()
			err = gk.Admit(ctx, attestationBytes, verifier, store, tc.pendingInputDigest)
			if err == nil {
				t.Fatalf("expected Admit to REJECT on negative case %q, but succeeded", tc.name)
			}

			// Execution callback MUST NOT have run
			if executionExecuted.Load() {
				t.Errorf("execution callback ran on rejected input %q", tc.name)
			}

			// Verify authoritative state remains UNCHANGED
			anchor, err := store.GetAnchor()
			if err != nil {
				t.Fatalf("GetAnchor failed: %v", err)
			}
			if anchor.Sequence != 1 || anchor.StateDigest != testPrevDigest {
				t.Errorf("anchor mutated! expected sequence=1 digest=%s, got seq=%d digest=%s",
					testPrevDigest, anchor.Sequence, anchor.StateDigest)
			}

			decisions, err := store.GetConsumedDecisions()
			if err != nil {
				t.Fatalf("GetConsumedDecisions failed: %v", err)
			}
			if len(decisions) != 0 {
				t.Errorf("ledger mutated! expected 0 decisions, got %v", decisions)
			}
		})
	}
}

func TestGatekeeper_GhostNodeTransport_NoSecretsAndSchemaConformant(t *testing.T) {
	recvChan := make(chan []byte, 1)

	// Mock Ghost Node HTTP Server conforming to Rust sink
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		buf := make([]byte, 8192)
		n, _ := r.Body.Read(buf)
		recvChan <- buf[:n]
		w.WriteHeader(http.StatusCreated) // 201 Created as returned by Rust axum sink
	}))
	defer server.Close()

	gk := NewGatekeeper(testWasmPath)
	gk.ghostNodeIP = server.URL
	gk.SetActivePolicyDigest(testPolicyDigest)

	store, _ := NewStore(":memory:")
	defer store.Close()

	edPub, _, _ := ed25519.GenerateKey(nil)
	mlPriv, _ := mldsa.GenerateKey(mldsa.MLDSA65())
	v, _ := NewVerifier(edPub, "ed-1", mlPriv.PublicKey(), "ml-1")

	// Inject secret into malformed JSON
	secretPayload := []byte(`{"attestation":{"payload":{"PRIVATE_SECRET_123":"super_sensitive_token"}}}`)

	ctx := context.Background()
	err := gk.Admit(ctx, secretPayload, v, store, testInputDigest)
	if err == nil {
		t.Fatal("expected Admit to reject malformed payload")
	}

	select {
	case receivedBytes := <-recvChan:
		// 1. Verify NO secret leakage
		receivedStr := string(receivedBytes)
		if strings.Contains(receivedStr, "PRIVATE_SECRET_123") || strings.Contains(receivedStr, "super_sensitive_token") {
			t.Fatalf("SECURITY VIOLATION: Secret leaked in ghost node payload: %s", receivedStr)
		}

		// 2. Deserialize as Rust sink's AnomalyIngressPayload
		var anomalyPayload AnomalyIngressPayload
		if err := json.Unmarshal(receivedBytes, &anomalyPayload); err != nil {
			t.Fatalf("payload does not match Rust sink AnomalyIngressPayload schema: %v\nReceived: %s", err, receivedStr)
		}

		if anomalyPayload.EntropyAction != "ABSORB_INTO_GHOST_SINK" {
			t.Errorf("expected entropy_action 'ABSORB_INTO_GHOST_SINK', got %q", anomalyPayload.EntropyAction)
		}
		if anomalyPayload.NodeUUID == "" {
			t.Errorf("expected non-empty node_uuid")
		}
		if anomalyPayload.TimestampEpochNonce == "" {
			t.Errorf("expected non-empty timestamp_epoch_nonce")
		}

		reasonCode, ok := anomalyPayload.StructuralAnomaly["reason_code"].(string)
		if !ok || !strings.HasPrefix(reasonCode, "ERR_") {
			t.Errorf("expected enumerated reason code prefix ERR_, got %v", anomalyPayload.StructuralAnomaly["reason_code"])
		}

	case <-time.After(1 * time.Second):
		t.Fatal("timeout waiting for Ghost Node notification")
	}
}

func TestGatekeeper_GhostNodeTransport_SinkErrorsDoNotBypassDenial(t *testing.T) {
	// Test that 422, 500, or a stalled sink still results in unconditional denial
	statusCodes := []int{http.StatusUnprocessableEntity, http.StatusInternalServerError, http.StatusBadRequest}

	for _, statusCode := range statusCodes {
		t.Run(fmt.Sprintf("HTTP_%d", statusCode), func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				w.WriteHeader(statusCode)
			}))
			defer server.Close()

			gk := NewGatekeeper(testWasmPath)
			gk.ghostNodeIP = server.URL
			gk.SetActivePolicyDigest(testPolicyDigest)

			store, _ := NewStore(":memory:")
			defer store.Close()

			edPub, _, _ := ed25519.GenerateKey(nil)
			mlPriv, _ := mldsa.GenerateKey(mldsa.MLDSA65())
			v, _ := NewVerifier(edPub, "ed-1", mlPriv.PublicKey(), "ml-1")

			err := gk.Admit(context.Background(), []byte(`{"bad":"json"}`), v, store, testInputDigest)
			if err == nil {
				t.Fatalf("expected Admit to deny despite sink error %d", statusCode)
			}
		})
	}

	// Test canceled context
	t.Run("Canceled_Context", func(t *testing.T) {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			time.Sleep(100 * time.Millisecond)
			w.WriteHeader(http.StatusOK)
		}))
		defer server.Close()

		gk := NewGatekeeper(testWasmPath)
		gk.ghostNodeIP = server.URL
		gk.SetActivePolicyDigest(testPolicyDigest)

		store, _ := NewStore(":memory:")
		defer store.Close()

		edPub, _, _ := ed25519.GenerateKey(nil)
		mlPriv, _ := mldsa.GenerateKey(mldsa.MLDSA65())
		v, _ := NewVerifier(edPub, "ed-1", mlPriv.PublicKey(), "ml-1")

		ctx, cancel := context.WithCancel(context.Background())
		cancel() // immediately canceled

		err := gk.Admit(ctx, []byte(`{"bad":"json"}`), v, store, testInputDigest)
		if err == nil {
			t.Fatalf("expected Admit to deny on canceled context")
		}
	})
}
