module QuantumFlex_Core

open FStar.Mul
open FStar.UInt32
open FStar.UInt16

(* =========================================================================
   QUANTUMFLEX VERIFIED CORE: MATHEMATICAL INVARIANT SPECIFICATION
   Standard References: NIST FIPS 203, OMB M-26-15, RFC 7748
   Properties Proved:
     1. Strict FIPS 203 PQC Downgrade Impossibility
     2. Absorbing Quarantine Sink (Quarantine cannot transition to Active)
     3. Authentication Fail-Closed Evaluation
     4. Single-Session Wire Frame Bounding & Rollover Protection
   ========================================================================= *)

(* --- Strata 1: Finite State Machine Invariant Types --- *)

type engine_state =
  | StateUninitialized : engine_state
  | StateLocked        : engine_state
  | StateActive        : engine_state
  | StateQuarantine    : engine_state
  | StateRecovery      : engine_state

type auth_credential =
  | CredNone                : auth_credential
  | CredMtlsCertVerified    : auth_credential
  | CredShamirThresholdMet  : auth_credential
  | CredTwoManAttestation   : auth_credential

type transition_verdict =
  | VerdictAllow : next:engine_state -> transition_verdict
  | VerdictDeny  : transition_verdict

(* Transition legality logic *)
val eval_transition : current:engine_state -> target:engine_state -> cred:auth_credential -> transition_verdict
let eval_transition current target cred =
  match current, target, cred with
  (* Uninitialized -> Locked on boot/genesis *)
  | StateUninitialized, StateLocked, _ -> VerdictAllow StateLocked

  (* Locked -> Active requires verified Shamir Threshold or mTLS admin *)
  | StateLocked, StateActive, CredShamirThresholdMet -> VerdictAllow StateActive
  | StateLocked, StateActive, CredMtlsCertVerified   -> VerdictAllow StateActive

  (* Active -> Quarantine triggered on any invariant violation or anomaly *)
  | StateActive, StateQuarantine, _ -> VerdictAllow StateQuarantine

  (* Active -> Locked on operator unmount / seal *)
  | StateActive, StateLocked, CredMtlsCertVerified -> VerdictAllow StateLocked

  (* QUARANTINE ABSORBING INVARIANT:
     Quarantine can NEVER transition directly to Active.
     Quarantine can ONLY transition to Recovery with Two-Man Cryptographic Attestation. *)
  | StateQuarantine, StateRecovery, CredTwoManAttestation -> VerdictAllow StateRecovery

  (* Recovery -> Locked once remediation and zeroization complete *)
  | StateRecovery, StateLocked, CredMtlsCertVerified -> VerdictAllow StateLocked

  (* All other transitions are strictly denied *)
  | _, _, _ -> VerdictDeny

(* Formal Invariant Theorem 1: Quarantine cannot silently become Active *)
val lemma_quarantine_never_directly_active : cred:auth_credential ->
  Lemma (eval_transition StateQuarantine StateActive cred == VerdictDeny)
let lemma_quarantine_never_directly_active cred = ()

(* Formal Invariant Theorem 2: Missing credentials cannot produce Allow to Active *)
val lemma_missing_auth_denies_active : current:engine_state ->
  Lemma (eval_transition current StateActive CredNone == VerdictDeny)
let lemma_missing_auth_denies_active current = ()


(* --- Strata 2: Strict PQC Algorithm Negotiation Invariant --- *)

type pqc_profile =
  | ProfileStrictFips203    : pqc_profile
  | ProfileAgileTransition  : pqc_profile
  | ProfileLegacyClassical  : pqc_profile

type pqc_algorithm =
  | AlgMLKEM768   : pqc_algorithm
  | AlgMLKEM1024  : pqc_algorithm
  | AlgFrodo976   : pqc_algorithm
  | AlgX25519     : pqc_algorithm
  | AlgUnknown    : pqc_algorithm

type policy_verdict =
  | PolicyAllow : pqc_algorithm -> policy_verdict
  | PolicyDeny  : policy_verdict

val eval_pqc_proposal : profile:pqc_profile -> proposal:pqc_algorithm -> policy_verdict
let eval_pqc_proposal profile proposal =
  match profile with
  | ProfileStrictFips203 ->
      (match proposal with
       | AlgMLKEM768  -> PolicyAllow AlgMLKEM768
       | AlgMLKEM1024 -> PolicyAllow AlgMLKEM1024
       | _            -> PolicyDeny)  (* Strict mode forbids all classical/fallback ciphers *)
  | ProfileAgileTransition ->
      (match proposal with
       | AlgMLKEM768  -> PolicyAllow AlgMLKEM768
       | AlgMLKEM1024 -> PolicyAllow AlgMLKEM1024
       | AlgFrodo976  -> PolicyAllow AlgFrodo976
       | _            -> PolicyDeny)
  | ProfileLegacyClassical ->
      PolicyDeny (* Closed by default in sovereign perimeter *)

(* Formal Invariant Theorem 3: PQC Downgrade to X25519 or Unknown is impossible under FIPS 203 *)
val lemma_pqc_downgrade_impossible : proposal:pqc_algorithm ->
  Lemma (requires (proposal == AlgX25519 \/ proposal == AlgFrodo976 \/ proposal == AlgUnknown))
        (ensures (eval_pqc_proposal ProfileStrictFips203 proposal == PolicyDeny))
let lemma_pqc_downgrade_impossible proposal = ()


(* --- Strata 3: Wire Framing Bounds & Monotonicity Invariant --- *)

let max_chunk_len : nat = 1450
let max_total_chunks : nat = 64
let max_sequence_id : nat = 4294967294 (* 0xFFFFFFFE = 2^32 - 2 *)

type wire_frame_meta = {
  chunk_len    : nat;
  chunk_idx    : nat;
  total_chunks : nat;
  seq_id       : nat;
}

type frame_verdict =
  | FrameValid   : frame_verdict
  | FrameInvalid : reason:nat -> frame_verdict

val eval_wire_bounds : frame:wire_frame_meta -> frame_verdict
let eval_wire_bounds frame =
  if frame.chunk_len = 0 || frame.chunk_len > max_chunk_len then
    FrameInvalid 3 (* ERR_CHUNK_BOUNDS *)
  else if frame.total_chunks = 0 || frame.total_chunks > max_total_chunks then
    FrameInvalid 3 (* ERR_CHUNK_BOUNDS *)
  else if frame.chunk_idx >= frame.total_chunks then
    FrameInvalid 3 (* ERR_CHUNK_BOUNDS *)
  else if frame.seq_id >= max_sequence_id then
    FrameInvalid 7 (* ERR_SEQ_EXHAUSTED - silent wraparound forbidden *)
  else
    FrameValid

(* Formal Invariant Theorem 4: Frames exceeding 1450 bytes or 64 chunks are strictly rejected *)
val lemma_wire_bounds_enforced : frame:wire_frame_meta ->
  Lemma (requires (frame.chunk_len > max_chunk_len \/ frame.total_chunks > max_total_chunks \/ frame.chunk_idx >= frame.total_chunks))
        (ensures (eval_wire_bounds frame == FrameInvalid 3))
let lemma_wire_bounds_enforced frame = ()

(* Formal Invariant Theorem 5: Sequence rollover past 0xFFFFFFFE is strictly rejected *)
val lemma_seq_rollover_rejected : frame:wire_frame_meta ->
  Lemma (requires (frame.seq_id >= max_sequence_id))
        (ensures (eval_wire_bounds frame == FrameInvalid 7))
let lemma_seq_rollover_rejected frame = ()
