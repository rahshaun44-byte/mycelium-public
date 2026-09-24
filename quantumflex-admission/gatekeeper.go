package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"time"

	"golang.org/x/crypto/sha3"
)

const ghostNodeBridgeURL = "http://10.88.0.50:19443/v1/sink/anomaly"

// Fixed enumerated reason codes (opaque metadata; no attacker payload content or parser strings)
const (
	ReasonVerificationFailed = "ERR_VERIFICATION_FAILED"
	ReasonStrictDecodeFailed = "ERR_STRICT_DECODE_FAILED"
	ReasonOversizedPayload   = "ERR_OVERSIZED_PAYLOAD"
	ReasonInvalidSchema      = "ERR_INVALID_SCHEMA"
	ReasonPolicyViolation    = "ERR_POLICY_VIOLATION"
	ReasonMissingBindings    = "ERR_MISSING_BINDINGS"
	ReasonTransactionFailed  = "ERR_TRANSACTION_FAILED"
)

// AnomalyIngressPayload matches the Rust Ghost sink AnomalyIngressPayload exactly.
type AnomalyIngressPayload struct {
	NodeUUID            string                 `json:"node_uuid"`
	TimestampEpochNonce string                 `json:"timestamp_epoch_nonce"`
	PCRIntegrityPass    bool                   `json:"pcr_integrity_pass"`
	NonceFreshnessPass  bool                   `json:"nonce_freshness_pass"`
	StructuralAnomaly   map[string]interface{} `json:"structural_anomaly,omitempty"`
	ExecutionViolations []interface{}          `json:"execution_violations"`
	RawRecordsCount     int                    `json:"raw_records_count"`
	EntropyAction       string                 `json:"entropy_action"`
	RawTelemetryDump    *string                `json:"raw_telemetry_dump,omitempty"`
	HAttack             uint32                 `json:"h_attack,omitempty"`
}

type IngressGatekeeper struct {
	wasmPolicyPath     string
	ghostNodeIP        string
	activePolicyDigest string
	httpClient         *http.Client
	executeCallback    func(ctx context.Context, payload *PayloadStruct) error
}

func NewGatekeeper(wasmPath string) *IngressGatekeeper {
	return &IngressGatekeeper{
		wasmPolicyPath: wasmPath,
		ghostNodeIP:    ghostNodeBridgeURL,
		httpClient: &http.Client{
			Timeout: 500 * time.Millisecond,
			CheckRedirect: func(req *http.Request, via []*http.Request) error {
				return http.ErrUseLastResponse
			},
		},
	}
}

func (gk *IngressGatekeeper) SetActivePolicyDigest(digest string) {
	gk.activePolicyDigest = digest
}

func (gk *IngressGatekeeper) SetExecutionCallback(cb func(ctx context.Context, payload *PayloadStruct) error) {
	gk.executeCallback = cb
}

// Admit strictly orders verification, policy evaluation, atomic state mutation, and execution.
func (gk *IngressGatekeeper) Admit(ctx context.Context, payloadBytes []byte, verifier *Verifier, store *Store, pendingInputDigest string) error {
	if verifier == nil || store == nil {
		return fmt.Errorf("Gatekeeper rejected: uninitialized verifier or store")
	}

	// 1. Host Verification Boundary
	opaInput, parsedPayload, stateDigest, err := verifier.ProcessAttestation(payloadBytes)
	if err != nil {
		gk.routeToGhostNode(ctx, payloadBytes, ReasonVerificationFailed)
		return err
	}

	// 2. Validate Trusted Bindings
	if gk.activePolicyDigest == "" || pendingInputDigest == "" {
		gk.routeToGhostNode(ctx, payloadBytes, ReasonMissingBindings)
		return fmt.Errorf("Gatekeeper rejected: missing trusted bindings")
	}

	// 3. Fetch Authoritative State
	anchor, err := store.GetAnchor()
	if err != nil {
		return fmt.Errorf("failed to fetch authoritative state: %w", err)
	}

	decisions, err := store.GetConsumedDecisions()
	if err != nil {
		return fmt.Errorf("failed to fetch ledger: %w", err)
	}

	data := &OPAData{
		Anchor: anchor,
		Environment: OPAEnvironment{
			ActivePolicyDigest: gk.activePolicyDigest,
			PendingInputDigest: pendingInputDigest,
		},
	}
	data.Ledger.ConsumedDecisions = decisions

	// 4. WASM Policy Execution
	allow, err := EvaluateWasm(ctx, gk.wasmPolicyPath, opaInput, data)
	if err != nil || !allow {
		gk.routeToGhostNode(ctx, payloadBytes, ReasonPolicyViolation)
		return fmt.Errorf("Gatekeeper rejected: policy denied")
	}

	// 5. Authoritative State Mutation (under serial transaction)
	err = store.CommitTransition(parsedPayload.DecisionID, parsedPayload.Sequence, stateDigest, "ALLOW", anchor.Sequence, anchor.StateDigest)
	if err != nil {
		gk.routeToGhostNode(ctx, payloadBytes, ReasonTransactionFailed)
		return fmt.Errorf("transaction rejected: %w", err)
	}

	// 6. Verified Execution Integration (proceeds ONLY after commit)
	if gk.executeCallback != nil {
		if err := gk.executeCallback(ctx, parsedPayload); err != nil {
			return fmt.Errorf("execution callback failed: %w", err)
		}
	}

	log.Printf("[GATEKEEPER] State mutation committed (seq=%d). Execution proceeding.", parsedPayload.Sequence)
	return nil
}

// routeToGhostNode shunts opaque anomaly metadata to the Ghost Node entropy sink.
// It NEVER exports raw inbound payload bytes or dynamic error strings.
func (gk *IngressGatekeeper) routeToGhostNode(ctx context.Context, h []byte, reasonCode string) error {
	hsh := sha3.Sum256(h)
	digest := fmt.Sprintf("sha3:%x", hsh)

	payload := AnomalyIngressPayload{
		NodeUUID:            "qf-node-local",
		TimestampEpochNonce: fmt.Sprintf("%d", time.Now().UnixNano()),
		PCRIntegrityPass:    false,
		NonceFreshnessPass:  false,
		StructuralAnomaly: map[string]interface{}{
			"reason_code":        reasonCode,
			"byte_length":        len(h),
			"correlation_digest": digest,
		},
		ExecutionViolations: make([]interface{}, 0),
		RawRecordsCount:     1,
		EntropyAction:       "ABSORB_INTO_GHOST_SINK",
	}

	metaBytes, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal anomaly payload: %w", err)
	}

	reqCtx, cancel := context.WithTimeout(ctx, 500*time.Millisecond)
	defer cancel()

	req, err := http.NewRequestWithContext(reqCtx, "POST", gk.ghostNodeIP, bytes.NewBuffer(metaBytes))
	if err != nil {
		return fmt.Errorf("Gatekeeper rejected: %s", reasonCode)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := gk.httpClient.Do(req)
	if err != nil {
		log.Printf("[GHOST NODE] Delivery failed (failsafe drop maintained): %v", err)
		return fmt.Errorf("Gatekeeper rejected: %s", reasonCode)
	}
	defer resp.Body.Close()

	// Bound response body reading
	_, _ = io.CopyN(io.Discard, resp.Body, 1024)

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		log.Printf("[GHOST NODE] Sink returned non-success HTTP status: %d", resp.StatusCode)
		return fmt.Errorf("Gatekeeper rejected: %s (sink status %d)", reasonCode, resp.StatusCode)
	}

	log.Printf("[GHOST NODE] Anomaly metadata successfully routed to HTTP entropy sink.")
	return fmt.Errorf("Gatekeeper rejected: %s", reasonCode)
}
