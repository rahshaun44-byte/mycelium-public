module QuantumFlex_Core

open FStar.UInt32
open FStar.UInt16

(* =========================================================================
   QUANTUMFLEX VERIFIED CORE: MATHEMATICAL INVARIANT SPECIFICATION
   Standard References: NIST FIPS 203/204/205, OMB M-26-15, RFC 7748
   
   Milestone 1 Formal Foundation:
     1. Decoupled Abstract Cryptographic Policy Gate (zero hardcoded legacy ciphers)
     2. Absorbing Terminal Collapse Sink (Collapsed cannot be re-activated)
     3. Quarantine Non-Bypassability (Quarantine error cannot become Active)
     4. Enforced Recovery Stage (Quarantine recovery must transit via Recovery with Operator Auth)
     5. Fail-Closed Authentication on State Escalation
     6. Wire Framing Bounds & Monotonicity Invariants
   ========================================================================= *)

noextract
type krml_attribute =
  | CIntEnum : string -> krml_attribute
  | CExport  : string -> krml_attribute

(* --- Strata 1: Finite State Machine Invariant Types --- *)

[@ (CIntEnum "qf_engine_state_t") ]
type engine_state =
  | StateUninitialized : engine_state
  | StateActive        : engine_state
  | StateQuarantine    : engine_state
  | StateRecovery      : engine_state
  | StateCollapsed     : engine_state

[@ (CIntEnum "qf_policy_verdict_t") ]
type policy_verdict =
  | VerdictCompliant           : policy_verdict
  | VerdictDegraded            : policy_verdict
  | VerdictToxic               : policy_verdict
  | VerdictSupervisorUnreachable : policy_verdict

[@ (CIntEnum "qf_auth_cred_t") ]
type auth_credential =
  | CredNone                : auth_credential
  | CredOperatorAttestation : auth_credential
  | CredTwoManAttestation   : auth_credential

type transition_result = {
  next_state  : engine_state;
  retries_out : FStar.UInt16.t;
  permitted   : bool;
}

let max_quarantine_retries : FStar.UInt16.t = 5us

(* Deterministic FSM Transition Function *)
[@ (CExport "qf_core_step_fsm") ]
val step_fsm :
  current:engine_state ->
  verdict:policy_verdict ->
  cred:auth_credential ->
  retries:FStar.UInt16.t ->
  transition_result

let step_fsm current verdict cred retries =
  match current with
  (* ABSORBING TERMINAL SINK: Collapsed stays Collapsed under all inputs *)
  | StateCollapsed ->
      { next_state = StateCollapsed; retries_out = retries; permitted = false }

  (* UNINITIALIZED: Enters Active only on verified policy compliance *)
  | StateUninitialized ->
      (match verdict with
       | VerdictCompliant ->
           { next_state = StateActive; retries_out = 0us; permitted = true }
       | _ ->
           { next_state = StateQuarantine; retries_out = 0us; permitted = false })

  (* ACTIVE: Normal operation. Any violation triggers immediate Quarantine or Collapse *)
  | StateActive ->
      (match verdict with
       | VerdictCompliant ->
           { next_state = StateActive; retries_out = 0us; permitted = true }
       | VerdictDegraded ->
           { next_state = StateQuarantine; retries_out = 0us; permitted = false }
       | VerdictSupervisorUnreachable ->
           { next_state = StateQuarantine; retries_out = 0us; permitted = false }
       | VerdictToxic ->
           { next_state = StateCollapsed; retries_out = 0us; permitted = false })

  (* QUARANTINE: Errors increment retry budget. Recovery mandates StateRecovery, NOT Active *)
  | StateQuarantine ->
      (match verdict with
       | VerdictCompliant ->
           (* Structural requirement: Quarantine MUST pass through Recovery *)
           { next_state = StateRecovery; retries_out = 0us; permitted = false }
       | VerdictToxic ->
           (* Structural requirement: Toxic in quarantine collapses immediately *)
           { next_state = StateCollapsed; retries_out = retries; permitted = false }
       | VerdictDegraded | VerdictSupervisorUnreachable ->
           if retries >= max_quarantine_retries then
             { next_state = StateCollapsed; retries_out = retries; permitted = false }
           else
             { next_state = StateQuarantine; retries_out = FStar.UInt16.add retries 1us; permitted = false })

  (* RECOVERY: Post-quarantine clearance. Active requires operator cryptographic attestation *)
  | StateRecovery ->
      (match verdict, cred with
       | VerdictCompliant, CredOperatorAttestation ->
           { next_state = StateActive; retries_out = 0us; permitted = true }
       | VerdictCompliant, CredTwoManAttestation ->
           { next_state = StateActive; retries_out = 0us; permitted = true }
       | VerdictToxic, _ ->
           { next_state = StateCollapsed; retries_out = 0us; permitted = false }
       | _, _ ->
           (* Without explicit operator authorization, remains in Recovery and denied *)
           { next_state = StateRecovery; retries_out = 0us; permitted = false })


(* --- Mathematical Invariant Proofs (Discharged via Z3 SMT) --- *)

(* Theorem 1: Terminal Collapse is an Absorbing Sink *)
val theorem_collapse_is_absorbing :
  verdict:policy_verdict -> cred:auth_credential -> retries:FStar.UInt16.t ->
  Lemma (let r = step_fsm StateCollapsed verdict cred retries in
         r.next_state == StateCollapsed /\ r.permitted == false)
let theorem_collapse_is_absorbing verdict cred retries = ()

(* Theorem 2: Quarantine Errors Can Never Jump Directly to Active *)
val theorem_quarantine_error_never_active :
  verdict:policy_verdict -> cred:auth_credential -> retries:FStar.UInt16.t ->
  Lemma (requires (verdict =!= VerdictCompliant))
        (ensures (let r = step_fsm StateQuarantine verdict cred retries in
                  r.next_state =!= StateActive /\ r.permitted == false))
let theorem_quarantine_error_never_active verdict cred retries = ()

(* Theorem 3: Quarantine Recovery Must Route via StateRecovery, Never Directly to Active *)
val theorem_quarantine_recovery_routes_to_recovery :
  cred:auth_credential -> retries:FStar.UInt16.t ->
  Lemma (let r = step_fsm StateQuarantine VerdictCompliant cred retries in
         r.next_state == StateRecovery /\ r.permitted == false)
let theorem_quarantine_recovery_routes_to_recovery cred retries = ()

(* Theorem 4: Recovery to Active Strictly Requires Authorized Operator Credentials *)
val theorem_recovery_to_active_requires_authorization :
  verdict:policy_verdict -> cred:auth_credential ->
  Lemma (requires (cred == CredNone))
        (ensures (let r = step_fsm StateRecovery verdict cred 0us in
                  r.next_state =!= StateActive /\ r.permitted == false))
let theorem_recovery_to_active_requires_authorization verdict cred = ()

(* Theorem 5: Toxic Verdict from Any State Always Triggers Terminal Collapse *)
val theorem_toxic_verdict_always_collapses :
  current:engine_state -> cred:auth_credential -> retries:FStar.UInt16.t ->
  Lemma (requires (current =!= StateUninitialized))
        (ensures (let r = step_fsm current VerdictToxic cred retries in
                  r.next_state == StateCollapsed /\ r.permitted == false))
let theorem_toxic_verdict_always_collapses current cred retries = ()


(* --- Strata 2: Decoupled Cryptographic Policy Evaluation --- *)

[@ (CIntEnum "qf_crypto_level_t") ]
type crypto_security_level =
  | LevelLegacyDeprecated : crypto_security_level
  | LevelStandardClassical : crypto_security_level
  | LevelPostQuantumFips   : crypto_security_level

type crypto_asset_descriptor = {
  asset_id       : FStar.UInt16.t;
  security_level : crypto_security_level;
  is_revoked     : bool;
}

type policy_criteria = {
  min_required_level : crypto_security_level;
  allow_revoked      : bool;
}

[@ (CExport "qf_core_eval_crypto_asset") ]
val eval_crypto_asset : policy:policy_criteria -> asset:crypto_asset_descriptor -> policy_verdict
let eval_crypto_asset policy asset =
  if asset.is_revoked && not policy.allow_revoked then
    VerdictToxic
  else
    match policy.min_required_level, asset.security_level with
    | LevelPostQuantumFips, LevelPostQuantumFips -> VerdictCompliant
    | LevelPostQuantumFips, _                   -> VerdictDegraded
    | LevelStandardClassical, LevelLegacyDeprecated -> VerdictDegraded
    | _, _ -> VerdictCompliant

(* Theorem 6: Revoked Cryptographic Primitives Always Yield VerdictToxic When Revocation Disallowed *)
val theorem_revoked_primitive_is_toxic :
  policy:policy_criteria -> asset:crypto_asset_descriptor ->
  Lemma (requires (asset.is_revoked == true /\ policy.allow_revoked == false))
        (ensures (eval_crypto_asset policy asset == VerdictToxic))
let theorem_revoked_primitive_is_toxic policy asset = ()

(* Theorem 7: Strict PQC Mode Strictly Rejects Deprecated Primitives *)
val theorem_strict_pqc_rejects_deprecated :
  policy:policy_criteria -> asset:crypto_asset_descriptor ->
  Lemma (requires (policy.min_required_level == LevelPostQuantumFips /\
                   asset.security_level == LevelLegacyDeprecated))
        (ensures (eval_crypto_asset policy asset == VerdictDegraded \/
                  eval_crypto_asset policy asset == VerdictToxic))
let theorem_strict_pqc_rejects_deprecated policy asset = ()


(* --- Strata 3: Wire Framing Bounds & Monotonicity Invariants --- *)

let max_chunk_len    : FStar.UInt16.t = 1450us
let max_total_chunks : FStar.UInt16.t = 64us
let max_sequence_id  : FStar.UInt32.t = 4294967294ul

type wire_frame_meta = {
  chunk_len    : FStar.UInt16.t;
  chunk_idx    : FStar.UInt16.t;
  total_chunks : FStar.UInt16.t;
  seq_id       : FStar.UInt32.t;
}

[@ (CIntEnum "qf_wire_error_t") ]
type frame_verdict =
  | FrameValid   : frame_verdict
  | FrameInvalid : reason:FStar.UInt16.t -> frame_verdict

[@ (CExport "qf_core_eval_wire_bounds") ]
val eval_wire_bounds : frame:wire_frame_meta -> frame_verdict
let eval_wire_bounds frame =
  if frame.chunk_len = 0us || frame.chunk_len > max_chunk_len then
    FrameInvalid 3us (* ERR_CHUNK_BOUNDS *)
  else if frame.total_chunks = 0us || frame.total_chunks > max_total_chunks then
    FrameInvalid 3us (* ERR_CHUNK_BOUNDS *)
  else if frame.chunk_idx >= frame.total_chunks then
    FrameInvalid 3us (* ERR_CHUNK_BOUNDS *)
  else if frame.seq_id >= max_sequence_id then
    FrameInvalid 7us (* ERR_SEQ_EXHAUSTED - silent wraparound forbidden *)
  else
    FrameValid

(* Theorem 8: Out-of-bounds chunks are strictly rejected *)
val theorem_wire_bounds_enforced : frame:wire_frame_meta ->
  Lemma (requires (frame.chunk_len = 0us \/ frame.chunk_len > max_chunk_len \/
                   frame.total_chunks = 0us \/ frame.total_chunks > max_total_chunks \/
                   frame.chunk_idx >= frame.total_chunks))
        (ensures (eval_wire_bounds frame == FrameInvalid 3us))
let theorem_wire_bounds_enforced frame = ()

(* Theorem 9: Sequence rollover past 0xFFFFFFFE is strictly rejected *)
val theorem_seq_rollover_rejected : frame:wire_frame_meta ->
  Lemma (requires (frame.chunk_len > 0us /\ frame.chunk_len <= max_chunk_len /\
                   frame.total_chunks > 0us /\ frame.total_chunks <= max_total_chunks /\
                   frame.chunk_idx < frame.total_chunks /\
                   frame.seq_id >= max_sequence_id))
        (ensures (eval_wire_bounds frame == FrameInvalid 7us))
let theorem_seq_rollover_rejected frame = ()
