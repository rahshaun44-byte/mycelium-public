package main

import (
	"crypto/ed25519"
	"crypto/mldsa"
	"encoding/json"
	"encoding/json/jsontext"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"testing"

	"golang.org/x/crypto/sha3"
)

func setupTestEnvironment(t *testing.T) (*Store, *Verifier, string) {
	tempDir, err := os.MkdirTemp("", "qf-admission-test")
	if err != nil {
		t.Fatalf("failed to create temp dir: %v", err)
	}

	dbPath := filepath.Join(tempDir, "qf_state.db")
	store, err := NewStore(dbPath)
	if err != nil {
		t.Fatalf("failed to init store: %v", err)
	}

	pub, _, err := ed25519.GenerateKey(nil)
	if err != nil {
		t.Fatalf("failed to generate ed25519: %v", err)
	}

	privML, err := mldsa.GenerateKey(mldsa.MLDSA65())
	if err != nil {
		t.Fatalf("failed to generate mldsa: %v", err)
	}
	pubML := privML.PublicKey()

	verifier, err := NewVerifier(pub, "key-ed25519-pinned-alpha", pubML, "key-mldsa-pinned-alpha")
	if err != nil {
		t.Fatalf("NewVerifier failed: %v", err)
	}

	return store, verifier, tempDir
}

func TestConcurrentDuplicateAdmission(t *testing.T) {
	store, _, tempDir := setupTestEnvironment(t)
	defer os.RemoveAll(tempDir)
	defer store.Close()

	// Simulate concurrent identical attestations reaching the store
	decisionID := "decision-concurrent-100"
	var wg sync.WaitGroup
	var successCount int
	var mu sync.Mutex

	for i := 0; i < 5; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			err := store.CommitTransition(decisionID, 2, "sha3:STATE_K2", "ALLOW", 1, "sha3:STATE_K1")
			
			mu.Lock()
			if err == nil {
				successCount++
			}
			mu.Unlock()
		}()
	}
	wg.Wait()

	if successCount != 1 {
		t.Errorf("expected exactly 1 successful commit, got %d", successCount)
	}
}

func TestCrashBeforeCommit(t *testing.T) {
	store, _, tempDir := setupTestEnvironment(t)
	defer os.RemoveAll(tempDir)
	defer store.Close()
	
	// 1. Test rollback (expecting seq 1, passing new seq 3 instead of 2)
	err := store.CommitTransition("decision-fail-seq", 3, "sha3:STATE_K3", "ALLOW", 1, "sha3:STATE_K1")
	if err == nil {
		t.Fatalf("expected error due to monotonicity violation (skipped sequence)")
	}

	// 2. Test rollback (expecting seq 1, passing seq 0)
	err = store.CommitTransition("decision-fail-rollback", 0, "sha3:STATE_K0", "ALLOW", 1, "sha3:STATE_K1")
	if err == nil {
		t.Fatalf("expected error due to monotonicity violation (rollback sequence)")
	}

	// 3. Test non-ALLOW result
	err = store.CommitTransition("decision-fail-deny", 2, "sha3:STATE_K2", "DENY", 1, "sha3:STATE_K1")
	if err == nil {
		t.Fatalf("expected error due to non-ALLOW result")
	}

	// 4. Test concurrency violation (expectedOldSequence mismatch)
	err = store.CommitTransition("decision-fail-concurrency", 2, "sha3:STATE_K2", "ALLOW", 999, "sha3:STATE_K1")
	if err == nil {
		t.Fatalf("expected error due to concurrency violation")
	}

	// 5. Test continuity violation (expectedPreviousDigest mismatch)
	err = store.CommitTransition("decision-fail-digest", 2, "sha3:STATE_K2", "ALLOW", 1, "sha3:WRONG_PREV")
	if err == nil {
		t.Fatalf("expected error due to previous state digest mismatch")
	}

	// 6. Test sequence upper bound violation (> MaxSequence)
	err = store.CommitTransition("decision-fail-max", MaxSequence+1, "sha3:STATE_K_MAX", "ALLOW", 1, "sha3:STATE_K1")
	if err == nil {
		t.Fatalf("expected error due to sequence exceeding MaxSequence")
	}

	// Read anchor, ensure it's still Sequence 1 and sha3:STATE_K1
	anchor, err := store.GetAnchor()
	if err != nil {
		t.Fatalf("failed to get anchor: %v", err)
	}
	if anchor.Sequence != 1 || anchor.StateDigest != "sha3:STATE_K1" {
		t.Errorf("anchor unexpectedly mutated: seq=%d, digest=%s", anchor.Sequence, anchor.StateDigest)
	}
}

func TestStore_DSNConflictHandling(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "qf-dsn-test")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tempDir)

	dbPath := filepath.Join(tempDir, "conflict.db")
	conflictingDSN := fmt.Sprintf("%s?_txlock=deferred&cache=shared", dbPath)

	store, err := NewStore(conflictingDSN)
	if err != nil {
		t.Fatalf("failed to create store with conflicting DSN: %v", err)
	}
	defer store.Close()

	// Verify we can commit transition atomically
	err = store.CommitTransition("dec-dsn-01", 2, "sha3:STATE_K2", "ALLOW", 1, "sha3:STATE_K1")
	if err != nil {
		t.Fatalf("commit failed: %v", err)
	}
}

func TestStore_PostWriteRollbackRecovery(t *testing.T) {
	tempDir, err := os.MkdirTemp("", "qf-rollback-test")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(tempDir)

	dbPath := filepath.Join(tempDir, "rollback.db")
	store, err := NewStore(dbPath)
	if err != nil {
		t.Fatal(err)
	}

	// Begin manual transaction, insert into ledger, then rollback to simulate crash after insert
	tx, err := store.db.Begin()
	if err != nil {
		t.Fatal(err)
	}
	_, err = tx.Exec("INSERT INTO ledger (decision_id, sequence, result) VALUES (?, ?, ?)", "decision-crash", 2, "ALLOW")
	if err != nil {
		t.Fatal(err)
	}
	// Simulate crash: explicitly rollback without committing
	tx.Rollback()
	store.Close()

	// Reopen database from disk and assert both tables remain unchanged
	reopenedStore, err := NewStore(dbPath)
	if err != nil {
		t.Fatal(err)
	}
	defer reopenedStore.Close()

	anchor, err := reopenedStore.GetAnchor()
	if err != nil {
		t.Fatal(err)
	}
	if anchor.Sequence != 1 || anchor.StateDigest != "sha3:STATE_K1" {
		t.Fatalf("reopened anchor state corrupted: sequence=%d", anchor.Sequence)
	}

	decisions, err := reopenedStore.GetConsumedDecisions()
	if err != nil {
		t.Fatal(err)
	}
	if len(decisions) != 0 {
		t.Fatalf("reopened ledger contains uncommitted record: %v", decisions)
	}
}

func TestVerifier_ParameterValidation(t *testing.T) {
	pubEd, _, _ := ed25519.GenerateKey(nil)
	privML, _ := mldsa.GenerateKey(mldsa.MLDSA65())
	pubML := privML.PublicKey()

	// 1. Invalid Ed25519 key length
	_, err := NewVerifier([]byte("too-short"), "ed-id", pubML, "ml-id")
	if err == nil {
		t.Errorf("expected error for short Ed25519 key")
	}

	// 2. Empty Ed25519 Key ID
	_, err = NewVerifier(pubEd, "", pubML, "ml-id")
	if err == nil {
		t.Errorf("expected error for empty Ed25519 key ID")
	}

	// 3. Nil ML-DSA key
	_, err = NewVerifier(pubEd, "ed-id", nil, "ml-id")
	if err == nil {
		t.Errorf("expected error for nil ML-DSA key")
	}

	// 4. Empty ML-DSA Key ID
	_, err = NewVerifier(pubEd, "ed-id", pubML, "")
	if err == nil {
		t.Errorf("expected error for empty ML-DSA key ID")
	}

	// 5. Wrong ML-DSA parameter set (ML-DSA-44 or ML-DSA-87 instead of ML-DSA-65)
	privML44, err := mldsa.GenerateKey(mldsa.MLDSA44())
	if err == nil {
		_, err = NewVerifier(pubEd, "ed-id", privML44.PublicKey(), "ml-id")
		if err == nil {
			t.Errorf("expected error for non-ML-DSA-65 key (ML-DSA-44)")
		}
	}

	privML87, err := mldsa.GenerateKey(mldsa.MLDSA87())
	if err == nil {
		_, err = NewVerifier(pubEd, "ed-id", privML87.PublicKey(), "ml-id")
		if err == nil {
			t.Errorf("expected error for non-ML-DSA-65 key (ML-DSA-87)")
		}
	}
}

func TestJCSStrictParsing(t *testing.T) {
	_, verifier, tempDir := setupTestEnvironment(t)
	defer os.RemoveAll(tempDir)

	// Valid template
	validPayload := map[string]interface{}{
		"schema_version":        "v1",
		"sequence":              2,
		"previous_state_digest": "sha3:STATE_K1",
		"policy_digest":         "sha3:POLICY_V1",
		"decision_id":           "dec-001",
		"input_digest":          "sha3:INPUT_V1",
		"result":                "ALLOW",
	}

	makeEnvelope := func(p map[string]interface{}) []byte {
		pb, _ := json.Marshal(p)
		env := map[string]interface{}{
			"attestation": map[string]interface{}{
				"key_ids": map[string]interface{}{
					"ed25519_key_id": "key-ed25519-pinned-alpha",
					"ml_dsa_key_id":   "key-mldsa-pinned-alpha",
				},
				"signatures": map[string]interface{}{
					"ed25519_signature": make([]byte, 64),
					"ml_dsa_signature":   make([]byte, 100),
				},
				"payload": json.RawMessage(pb),
			},
		}
		b, _ := json.Marshal(env)
		return b
	}

	// 1. Sequence > MaxSequence
	p := copyMap(validPayload)
	p["sequence"] = 9007199254740992
	_, _, _, err := verifier.ProcessAttestation(makeEnvelope(p))
	if err == nil {
		t.Errorf("expected rejection for sequence exceeding integer precision")
	}

	// 2. Sequence < 1 (e.g. 0)
	p = copyMap(validPayload)
	p["sequence"] = 0
	_, _, _, err = verifier.ProcessAttestation(makeEnvelope(p))
	if err == nil {
		t.Errorf("expected rejection for sequence < 1")
	}

	// 3. SchemaVersion != "v1"
	p = copyMap(validPayload)
	p["schema_version"] = "v2"
	_, _, _, err = verifier.ProcessAttestation(makeEnvelope(p))
	if err == nil {
		t.Errorf("expected rejection for unsupported schema version")
	}

	// 4. Missing required field (policy_digest)
	p = copyMap(validPayload)
	p["policy_digest"] = ""
	_, _, _, err = verifier.ProcessAttestation(makeEnvelope(p))
	if err == nil {
		t.Errorf("expected rejection for missing policy_digest")
	}

	// 5. Invalid Result enum (not ALLOW or DENY)
	p = copyMap(validPayload)
	p["result"] = "PENDING"
	_, _, _, err = verifier.ProcessAttestation(makeEnvelope(p))
	if err == nil {
		t.Errorf("expected rejection for invalid result enum")
	}

	// 6. Duplicate key (JSON v2 whole-slice rejection)
	dupBytes := []byte(`{"attestation":{"key_ids":{"ed25519_key_id":"k1","ml_dsa_key_id":"k2"},"signatures":{"ed25519_signature":"","ml_dsa_signature":""},"payload":{"schema_version":"v1","sequence":2,"sequence":3}}}`)
	_, _, _, err = verifier.ProcessAttestation(dupBytes)
	if err == nil {
		t.Errorf("expected rejection for duplicate keys (JSON v2 semantics)")
	}

	// 7. Trailing JSON garbage
	trailingBytes := append(makeEnvelope(validPayload), []byte(`{"trailing":"garbage"}`)...)
	_, _, _, err = verifier.ProcessAttestation(trailingBytes)
	if err == nil {
		t.Errorf("expected rejection for trailing JSON garbage")
	}

	// 8. Oversized payload
	oversizedPayload := make([]byte, MaxAttestationBytes+10)
	_, _, _, err = verifier.ProcessAttestation(oversizedPayload)
	if err == nil {
		t.Errorf("expected rejection for oversized payload")
	}
}

func copyMap(m map[string]interface{}) map[string]interface{} {
	cp := make(map[string]interface{})
	for k, v := range m {
		cp[k] = v
	}
	return cp
}

func TestMLDSAVerification(t *testing.T) {
	_, verifier, tempDir := setupTestEnvironment(t)
	defer os.RemoveAll(tempDir)

	privML, err := mldsa.GenerateKey(mldsa.MLDSA65())
	if err != nil {
		t.Fatalf("failed to generate key: %v", err)
	}
	
	verifier.PinnedMLDSAPublicKey = privML.PublicKey()

	payloadObj := map[string]interface{}{
		"schema_version":        "v1",
		"sequence":              2,
		"previous_state_digest": "sha3:STATE_K1",
		"policy_digest":         "sha3:POLICY_V1",
		"decision_id":           "dec-mldsa-01",
		"input_digest":          "sha3:INPUT_V1",
		"result":                "ALLOW",
	}
	payloadBytes, _ := json.Marshal(payloadObj)
	
	val := jsontext.Value(payloadBytes)
	val.Canonicalize()
	
	h := sha3.New256()
	h.Write([]byte(val))
	digest := h.Sum(nil)

	// 0. Positive Case
	sigValid, _ := privML.Sign(nil, digest, &mldsa.Options{Context: "QF-CRITICAL-STATE-V1"})
	
	env := Envelope{}
	env.Attestation.KeyIDs.Ed25519KeyID = verifier.TrustedEd25519KeyID
	env.Attestation.KeyIDs.MLDSAKeyID = verifier.TrustedMLDSAKeyID
	env.Attestation.Signatures.MLDSASignature = sigValid
	env.Attestation.Signatures.Ed25519Signature = make([]byte, 64)
	env.Attestation.Payload = payloadBytes
	
	validEnvBytes, _ := json.Marshal(env)
	opaInput, _, _, err := verifier.ProcessAttestation(validEnvBytes)
	if err != nil || !opaInput.Verification.MLDSAVerified {
		t.Fatalf("expected valid signature to pass: %v", err)
	}

	// 1. Wrong signature
	env.Attestation.Signatures.MLDSASignature = []byte("bad-sig")
	badSigBytes, _ := json.Marshal(env)
	opaInput, _, _, _ = verifier.ProcessAttestation(badSigBytes)
	if opaInput.Verification.MLDSAVerified {
		t.Errorf("expected wrong signature -> DENY")
	}

	// 2. Wrong payload with valid signature
	wrongPayloadObj := copyMap(payloadObj)
	wrongPayloadObj["sequence"] = 3
	wrongPayloadBytes, _ := json.Marshal(wrongPayloadObj)
	env.Attestation.Signatures.MLDSASignature = sigValid
	env.Attestation.Payload = wrongPayloadBytes
	wrongEnvBytes, _ := json.Marshal(env)
	opaInput, _, _, _ = verifier.ProcessAttestation(wrongEnvBytes)
	if opaInput.Verification.MLDSAVerified {
		t.Errorf("expected wrong payload with valid signature -> DENY")
	}
	env.Attestation.Payload = payloadBytes // reset

	// 3. Right signature + wrong context
	sigWrongContext, _ := privML.Sign(nil, digest, &mldsa.Options{Context: "WRONG-CONTEXT"})
	env.Attestation.Signatures.MLDSASignature = sigWrongContext
	wrongCtxBytes, _ := json.Marshal(env)
	opaInput, _, _, _ = verifier.ProcessAttestation(wrongCtxBytes)
	if opaInput.Verification.MLDSAVerified {
		t.Errorf("expected right signature + wrong context -> DENY")
	}

	// 4. Right signature + unpinned public key
	unpinnedPrivML, _ := mldsa.GenerateKey(mldsa.MLDSA65())
	sigUnpinned, _ := unpinnedPrivML.Sign(nil, digest, &mldsa.Options{Context: "QF-CRITICAL-STATE-V1"})
	env.Attestation.Signatures.MLDSASignature = sigUnpinned
	unpinnedBytes, _ := json.Marshal(env)
	opaInput, _, _, _ = verifier.ProcessAttestation(unpinnedBytes)
	if opaInput.Verification.MLDSAVerified {
		t.Errorf("expected right signature + unpinned public key -> DENY")
	}
}
