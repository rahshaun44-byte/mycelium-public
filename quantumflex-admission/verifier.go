package main

import (
	"crypto/ed25519"
	"crypto/mldsa"
	jsonv2 "encoding/json/v2"
	"encoding/json/jsontext"
	"fmt"
	"golang.org/x/crypto/sha3"
)

const MaxAttestationBytes = 64 * 1024
const MaxSequence = 9007199254740991

type Envelope struct {
	Attestation struct {
		Payload    jsontext.Value `json:"payload"`
		KeyIDs     KeyIDs          `json:"key_ids"`
		Signatures Signatures      `json:"signatures"`
	} `json:"attestation"`
}

type PayloadStruct struct {
	SchemaVersion       string `json:"schema_version"`
	Sequence            uint64 `json:"sequence"`
	PreviousStateDigest string `json:"previous_state_digest"`
	PolicyDigest        string `json:"policy_digest"`
	DecisionID          string `json:"decision_id"`
	InputDigest         string `json:"input_digest"`
	Result              string `json:"result"`
}

type KeyIDs struct {
	Ed25519KeyID string `json:"ed25519_key_id"`
	MLDSAKeyID   string `json:"ml_dsa_key_id"`
}

type Signatures struct {
	Ed25519Signature []byte `json:"ed25519_signature"`
	MLDSASignature   []byte `json:"ml_dsa_signature"`
}

type VerificationFacts struct {
	CanonicalDigestVerified bool `json:"canonical_digest_verified"`
	Ed25519Verified         bool `json:"ed25519_verified"`
	MLDSAVerified           bool `json:"ml_dsa_verified"`
	TrustedKeyring          bool `json:"trusted_keyring"`
}

type OPAInput struct {
	Attestation struct {
		Payload jsontext.Value `json:"payload"`
	} `json:"attestation"`
	Verification VerificationFacts `json:"verification"`
}

type OPAEnvironment struct {
	ActivePolicyDigest string `json:"active_policy_digest"`
	PendingInputDigest string `json:"pending_input_digest"`
}

type OPAData struct {
	Anchor      Anchor         `json:"anchor"`
	Environment OPAEnvironment `json:"environment"`
	Ledger      struct {
		ConsumedDecisions []string `json:"consumed_decisions"`
	} `json:"ledger"`
}

type Verifier struct {
	PinnedEd25519PublicKey ed25519.PublicKey
	PinnedMLDSAPublicKey   *mldsa.PublicKey
	TrustedEd25519KeyID    string
	TrustedMLDSAKeyID      string
}

// NewVerifier constructs and validates a trusted keyring verifier fail-closed.
func NewVerifier(edPub ed25519.PublicKey, edID string, mlPub *mldsa.PublicKey, mlID string) (*Verifier, error) {
	if len(edPub) != ed25519.PublicKeySize {
		return nil, fmt.Errorf("invalid Ed25519 public key length: got %d, expected %d", len(edPub), ed25519.PublicKeySize)
	}
	if edID == "" {
		return nil, fmt.Errorf("empty Ed25519 key ID")
	}
	if mlPub == nil {
		return nil, fmt.Errorf("nil ML-DSA public key")
	}
	if mlPub.Parameters() != mldsa.MLDSA65() {
		return nil, fmt.Errorf("invalid ML-DSA parameters: expected ML-DSA-65, got %v", mlPub.Parameters())
	}
	if mlID == "" {
		return nil, fmt.Errorf("empty ML-DSA key ID")
	}

	return &Verifier{
		PinnedEd25519PublicKey: edPub,
		PinnedMLDSAPublicKey:   mlPub,
		TrustedEd25519KeyID:    edID,
		TrustedMLDSAKeyID:      mlID,
	}, nil
}

func (v *Verifier) ProcessAttestation(rawBytes []byte) (*OPAInput, *PayloadStruct, string, error) {
	if v == nil || len(v.PinnedEd25519PublicKey) != ed25519.PublicKeySize || v.PinnedMLDSAPublicKey == nil || v.TrustedEd25519KeyID == "" || v.TrustedMLDSAKeyID == "" {
		return nil, nil, "", fmt.Errorf("REJECTED_PRE_OPA: verifier is uninitialized or invalid configuration")
	}

	if v.PinnedMLDSAPublicKey.Parameters() != mldsa.MLDSA65() {
		return nil, nil, "", fmt.Errorf("REJECTED_PRE_OPA: Pinned ML-DSA key is not ML-DSA-65")
	}

	if len(rawBytes) > MaxAttestationBytes {
		return nil, nil, "", fmt.Errorf("REJECTED_PRE_OPA: oversized attestation")
	}

	// 1. Strict decode (JSON v2 semantics in Go 1.27)
	var env Envelope
	if err := jsonv2.Unmarshal(rawBytes, &env, jsonv2.RejectUnknownMembers(true)); err != nil {
		return nil, nil, "", fmt.Errorf("REJECTED_PRE_OPA: strict decoding failed or trailing bytes detected: %w", err)
	}

	if env.Attestation.KeyIDs.Ed25519KeyID == "" || env.Attestation.KeyIDs.MLDSAKeyID == "" {
		return nil, nil, "", fmt.Errorf("REJECTED_PRE_OPA: missing required key IDs")
	}

	var payloadStruct PayloadStruct
	if err := jsonv2.Unmarshal(env.Attestation.Payload, &payloadStruct, jsonv2.RejectUnknownMembers(true)); err != nil {
		return nil, nil, "", fmt.Errorf("REJECTED_PRE_OPA: struct mismatch: %w", err)
	}

	if payloadStruct.SchemaVersion != "v1" {
		return nil, nil, "", fmt.Errorf("REJECTED_PRE_OPA: unsupported schema version: %q", payloadStruct.SchemaVersion)
	}

	if payloadStruct.Sequence < 1 {
		return nil, nil, "", fmt.Errorf("REJECTED_PRE_OPA: sequence must be >= 1, got %d", payloadStruct.Sequence)
	}

	if payloadStruct.Sequence > MaxSequence {
		return nil, nil, "", fmt.Errorf("REJECTED_PRE_OPA: sequence exceeds integer precision limit")
	}

	if payloadStruct.PreviousStateDigest == "" {
		return nil, nil, "", fmt.Errorf("REJECTED_PRE_OPA: missing previous_state_digest")
	}
	if payloadStruct.PolicyDigest == "" {
		return nil, nil, "", fmt.Errorf("REJECTED_PRE_OPA: missing policy_digest")
	}
	if payloadStruct.DecisionID == "" {
		return nil, nil, "", fmt.Errorf("REJECTED_PRE_OPA: missing decision_id")
	}
	if payloadStruct.InputDigest == "" {
		return nil, nil, "", fmt.Errorf("REJECTED_PRE_OPA: missing input_digest")
	}
	if payloadStruct.Result != "ALLOW" && payloadStruct.Result != "DENY" {
		return nil, nil, "", fmt.Errorf("REJECTED_PRE_OPA: invalid result %q, must be ALLOW or DENY", payloadStruct.Result)
	}

	// 2. RFC 8785 Canonicalization
	val := jsontext.Value(env.Attestation.Payload)
	if err := val.Canonicalize(); err != nil {
		return nil, nil, "", fmt.Errorf("REJECTED_PRE_OPA: canonicalization failed: %w", err)
	}
	jcsBytes := []byte(val)
	
	// 3. Hash with SHA3-256
	h := sha3.New256()
	h.Write(jcsBytes)
	digest := h.Sum(nil)
	digestHex := fmt.Sprintf("sha3:%x", digest)

	// 4. Crypto Verification
	facts := VerificationFacts{
		CanonicalDigestVerified: true,
	}

	if env.Attestation.KeyIDs.Ed25519KeyID == v.TrustedEd25519KeyID && len(env.Attestation.Signatures.Ed25519Signature) == ed25519.SignatureSize {
		if ed25519.Verify(v.PinnedEd25519PublicKey, digest, env.Attestation.Signatures.Ed25519Signature) {
			facts.Ed25519Verified = true
		}
	}

	if env.Attestation.KeyIDs.MLDSAKeyID == v.TrustedMLDSAKeyID && len(env.Attestation.Signatures.MLDSASignature) > 0 {
		err := mldsa.Verify(v.PinnedMLDSAPublicKey, digest, env.Attestation.Signatures.MLDSASignature, &mldsa.Options{
			Context: "QF-CRITICAL-STATE-V1",
		})
		if err == nil {
			facts.MLDSAVerified = true
		}
	}

	// Facts Generation: Ensure TrustedKeyring is only set if both IDs match
	if env.Attestation.KeyIDs.Ed25519KeyID == v.TrustedEd25519KeyID && env.Attestation.KeyIDs.MLDSAKeyID == v.TrustedMLDSAKeyID {
		facts.TrustedKeyring = true
	}

	opaInput := &OPAInput{
		Verification: facts,
	}
	opaInput.Attestation.Payload = val // canonicalized payload

	return opaInput, &payloadStruct, digestHex, nil
}
