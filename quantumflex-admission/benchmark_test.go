package main

import (
	"context"
	"crypto/ed25519"
	"crypto/mldsa"
	"encoding/json"
	"encoding/json/jsontext"
	"fmt"
	"math"
	"net/http"
	"net/http/httptest"
	"sort"
	"testing"
	"time"

	"golang.org/x/crypto/sha3"
)

// setupBenchmarkAttestation generates keys, payloads, and signatures for benchmarking.
func setupBenchmarkAttestation(b *testing.B) (ed25519.PublicKey, *mldsa.PublicKey, *Verifier, []byte, string, string, string) {
	pubEd, privEd, err := ed25519.GenerateKey(nil)
	if err != nil {
		b.Fatalf("ed25519 gen: %v", err)
	}

	privML, err := mldsa.GenerateKey(mldsa.MLDSA65())
	if err != nil {
		b.Fatalf("mldsa gen: %v", err)
	}
	pubML := privML.PublicKey()

	edID := "ed-bench-key"
	mlID := "ml-bench-key"

	verifier, err := NewVerifier(pubEd, edID, pubML, mlID)
	if err != nil {
		b.Fatalf("NewVerifier: %v", err)
	}

	payloadMap := map[string]interface{}{
		"schema_version":        "v1",
		"sequence":              2,
		"previous_state_digest": testPrevDigest,
		"policy_digest":         testPolicyDigest,
		"decision_id":           "decision-bench-001",
		"input_digest":          testInputDigest,
		"result":                "ALLOW",
	}

	payloadBytes, _ := json.Marshal(payloadMap)
	val := jsontext.Value(payloadBytes)
	val.Canonicalize()
	h := sha3.New256()
	h.Write([]byte(val))
	digest := h.Sum(nil)

	edSig := ed25519.Sign(privEd, digest)
	mlSig, err := privML.Sign(nil, digest, &mldsa.Options{Context: "QF-CRITICAL-STATE-V1"})
	if err != nil {
		b.Fatalf("ml sign: %v", err)
	}

	env := Envelope{}
	env.Attestation.KeyIDs.Ed25519KeyID = edID
	env.Attestation.KeyIDs.MLDSAKeyID = mlID
	env.Attestation.Signatures.Ed25519Signature = edSig
	env.Attestation.Signatures.MLDSASignature = mlSig
	env.Attestation.Payload = payloadBytes

	envBytes, err := json.Marshal(env)
	if err != nil {
		b.Fatalf("marshal env: %v", err)
	}

	return pubEd, pubML, verifier, envBytes, testPolicyDigest, testInputDigest, testPrevDigest
}

func Benchmark_JCSCanonicalization(b *testing.B) {
	rawPayload := []byte(`{"schema_version":"v1","sequence":2,"previous_state_digest":"sha3:STATE_K1","policy_digest":"sha3:POLICY_V1","decision_id":"dec-1001","input_digest":"sha3:INPUT_V1","result":"ALLOW"}`)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		val := jsontext.Value(rawPayload)
		if err := val.Canonicalize(); err != nil {
			b.Fatal(err)
		}
	}
}

func Benchmark_SHA3_256(b *testing.B) {
	data := []byte(`{"decision_id":"dec-1001","input_digest":"sha3:INPUT_V1","policy_digest":"sha3:POLICY_V1","previous_state_digest":"sha3:STATE_K1","result":"ALLOW","schema_version":"v1","sequence":2}`)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		h := sha3.New256()
		h.Write(data)
		_ = h.Sum(nil)
	}
}

func Benchmark_Ed25519_Verify(b *testing.B) {
	pub, priv, _ := ed25519.GenerateKey(nil)
	msg := []byte("sha3:digest-for-ed25519-benchmarking-32bytes")
	sig := ed25519.Sign(priv, msg)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		if !ed25519.Verify(pub, msg, sig) {
			b.Fatal("verify failed")
		}
	}
}

func Benchmark_MLDSA65_Verify(b *testing.B) {
	privML, _ := mldsa.GenerateKey(mldsa.MLDSA65())
	pubML := privML.PublicKey()
	msg := []byte("sha3:digest-for-mldsa65-benchmarking-32bytes")
	opts := &mldsa.Options{Context: "QF-CRITICAL-STATE-V1"}
	sig, _ := privML.Sign(nil, msg, opts)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		if err := mldsa.Verify(pubML, msg, sig, opts); err != nil {
			b.Fatal(err)
		}
	}
}

func Benchmark_OPA_WasmEval(b *testing.B) {
	ctx := context.Background()
	input, data := validPositiveInputAndData()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		allow, err := EvaluateWasm(ctx, testWasmPath, input, data)
		if err != nil || !allow {
			b.Fatalf("wasm eval failed: %v", err)
		}
	}
}

func Benchmark_SQLite_CommitTransition(b *testing.B) {
	store, err := NewStore(":memory:")
	if err != nil {
		b.Fatal(err)
	}
	defer store.Close()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		seq := uint64(i + 2)
		oldSeq := uint64(i + 1)
		decID := fmt.Sprintf("dec-bench-%d", i)
		err := store.CommitTransition(decID, seq, "sha3:DIGEST_NEXT", "ALLOW", oldSeq, "")
		if err != nil {
			b.Fatalf("commit transition: %v", err)
		}
	}
}

func Benchmark_Admit_Pipeline(b *testing.B) {
	mockServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusCreated)
	}))
	defer mockServer.Close()

	// Pre-generate private keys for per-iteration attestation creation
	pubEd, privEd, _ := ed25519.GenerateKey(nil)
	privML, _ := mldsa.GenerateKey(mldsa.MLDSA65())
	pubML := privML.PublicKey()

	edID := "bench-pipeline-ed"
	mlID := "bench-pipeline-ml"
	v, err := NewVerifier(pubEd, edID, pubML, mlID)
	if err != nil {
		b.Fatal(err)
	}

	store, err := NewStore(":memory:")
	if err != nil {
		b.Fatal(err)
	}
	defer store.Close()

	gk := NewGatekeeper(testWasmPath)
	gk.ghostNodeIP = mockServer.URL
	gk.SetActivePolicyDigest(testPolicyDigest)

	ctx := context.Background()
	currentSeq := uint64(1)
	currentDigest := testPrevDigest

	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		nextSeq := currentSeq + 1
		decID := fmt.Sprintf("dec-admit-%d", i)

		payloadMap := map[string]interface{}{
			"schema_version":        "v1",
			"sequence":              nextSeq,
			"previous_state_digest": currentDigest,
			"policy_digest":         testPolicyDigest,
			"decision_id":           decID,
			"input_digest":          testInputDigest,
			"result":                "ALLOW",
		}

		payloadBytes, _ := json.Marshal(payloadMap)
		val := jsontext.Value(payloadBytes)
		val.Canonicalize()
		h := sha3.New256()
		h.Write([]byte(val))
		stateDigestBytes := h.Sum(nil)
		actualStateDigest := fmt.Sprintf("sha3:%x", stateDigestBytes)

		edSig := ed25519.Sign(privEd, stateDigestBytes)
		mlSig, _ := privML.Sign(nil, stateDigestBytes, &mldsa.Options{Context: "QF-CRITICAL-STATE-V1"})

		env := Envelope{}
		env.Attestation.KeyIDs.Ed25519KeyID = edID
		env.Attestation.KeyIDs.MLDSAKeyID = mlID
		env.Attestation.Signatures.Ed25519Signature = edSig
		env.Attestation.Signatures.MLDSASignature = mlSig
		env.Attestation.Payload = payloadBytes

		envBytes, _ := json.Marshal(env)

		if err := gk.Admit(ctx, envBytes, v, store, testInputDigest); err != nil {
			b.Fatalf("Admit failed at iteration %d: %v", i, err)
		}

		currentSeq = nextSeq
		currentDigest = actualStateDigest
	}
}

func TestProfile_AdmissionLatencyPercentiles(t *testing.T) {
	mockServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusCreated)
	}))
	defer mockServer.Close()

	pubEd, privEd, _ := ed25519.GenerateKey(nil)
	privML, _ := mldsa.GenerateKey(mldsa.MLDSA65())
	pubML := privML.PublicKey()

	edID := "bench-profile-ed"
	mlID := "bench-profile-ml"
	v, err := NewVerifier(pubEd, edID, pubML, mlID)
	if err != nil {
		t.Fatal(err)
	}

	store, err := NewStore(":memory:")
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()

	gk := NewGatekeeper(testWasmPath)
	gk.ghostNodeIP = mockServer.URL
	gk.SetActivePolicyDigest(testPolicyDigest)

	ctx := context.Background()
	const iterations = 500
	latencies := make([]float64, iterations)

	currentSeq := uint64(1)
	currentDigest := testPrevDigest

	t.Logf("Running %d sequential end-to-end dual-signed admissions...", iterations)

	for i := 0; i < iterations; i++ {
		nextSeq := currentSeq + 1
		decID := fmt.Sprintf("profile-dec-%d", i)

		payloadMap := map[string]interface{}{
			"schema_version":        "v1",
			"sequence":              nextSeq,
			"previous_state_digest": currentDigest,
			"policy_digest":         testPolicyDigest,
			"decision_id":           decID,
			"input_digest":          testInputDigest,
			"result":                "ALLOW",
		}

		payloadBytes, _ := json.Marshal(payloadMap)
		val := jsontext.Value(payloadBytes)
		val.Canonicalize()
		h := sha3.New256()
		h.Write([]byte(val))
		stateDigestBytes := h.Sum(nil)
		actualStateDigest := fmt.Sprintf("sha3:%x", stateDigestBytes)

		edSig := ed25519.Sign(privEd, stateDigestBytes)
		mlSig, _ := privML.Sign(nil, stateDigestBytes, &mldsa.Options{Context: "QF-CRITICAL-STATE-V1"})

		env := Envelope{}
		env.Attestation.KeyIDs.Ed25519KeyID = edID
		env.Attestation.KeyIDs.MLDSAKeyID = mlID
		env.Attestation.Signatures.Ed25519Signature = edSig
		env.Attestation.Signatures.MLDSASignature = mlSig
		env.Attestation.Payload = payloadBytes

		envBytes, _ := json.Marshal(env)

		start := time.Now()
		if err := gk.Admit(ctx, envBytes, v, store, testInputDigest); err != nil {
			t.Fatalf("Admit failed at iteration %d: %v", i, err)
		}
		durationMicros := float64(time.Since(start).Nanoseconds()) / 1000.0
		latencies[i] = durationMicros

		currentSeq = nextSeq
		currentDigest = actualStateDigest
	}

	sort.Float64s(latencies)

	var sum float64
	for _, l := range latencies {
		sum += l
	}
	mean := sum / float64(iterations)

	p50 := latencies[int(math.Floor(0.50*float64(iterations)))]
	p90 := latencies[int(math.Floor(0.90*float64(iterations)))]
	p95 := latencies[int(math.Floor(0.95*float64(iterations)))]
	p99 := latencies[int(math.Floor(0.99*float64(iterations)))]
	min := latencies[0]
	max := latencies[iterations-1]

	t.Logf("=== QuantumFlex Admission Gate End-to-End Latency Profile ===")
	t.Logf("Total Samples: %d packets", iterations)
	t.Logf("Min Latency:   %.2f µs (%.3f ms)", min, min/1000.0)
	t.Logf("Mean Latency:  %.2f µs (%.3f ms)", mean, mean/1000.0)
	t.Logf("p50 (Median):  %.2f µs (%.3f ms)", p50, p50/1000.0)
	t.Logf("p90 Latency:   %.2f µs (%.3f ms)", p90, p90/1000.0)
	t.Logf("p95 Latency:   %.2f µs (%.3f ms)", p95, p95/1000.0)
	t.Logf("p99 Latency:   %.2f µs (%.3f ms)", p99, p99/1000.0)
	t.Logf("Max Latency:   %.2f µs (%.3f ms)", max, max/1000.0)

	// Invariant: p50 should comfortably be sub-10ms for pre-network gatekeeper admission
	if p50/1000.0 > 25.0 {
		t.Errorf("p50 latency exceeded 25ms SLA: %.3f ms", p50/1000.0)
	}
}
