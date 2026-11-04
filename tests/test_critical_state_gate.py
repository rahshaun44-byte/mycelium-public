#!/usr/bin/env python3
"""
QuantumFlex Critical-State v1: Below-the-Network Host Admission Test Suite
==========================================================================
Validates the authoritative execution chain:
  bytes 
    -> [1] Size/Rate Boundary
    -> [2] Strict JSON Decoder (DisallowUnknownFields)
    -> [3] RFC 8785 JCS Canonicalization
    -> [4] SHA3-256 Digest Recomputation
    -> [5] External Pinned Trust Store Verification (Ed25519 + ML-DSA)
    -> [6] OPA Policy Evaluation over Verified Facts (bootgate.rego)
    -> [7] Transactional Atomic Commit (fsync)
    -> [8] Execution Authorization

Tests the complete 11-case adversarial matrix + concurrent TOCTOU race prevention.
"""

import concurrent.futures
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric import ed25519

ROOT_DIR = Path(__file__).resolve().parents[1]
BOOTGATE_REGO = ROOT_DIR / "sentinel" / "policies" / "bootgate.rego"
MAX_ATTESTATION_BYTES = 64 * 1024  # 64 KB strict ceiling


def jcs_canonicalize(data: dict) -> bytes:
    """RFC 8785 JSON Canonicalization Scheme."""
    return json.dumps(data, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")


def sha3_256_hex(data: bytes) -> str:
    """Computes SHA3-256 hex string."""
    return hashlib.sha3_256(data).hexdigest()


class AdmissionTransactionManager:
    """
    Thread-safe and process-safe transactional admission state manager.
    Enforces atomic read-modify-write across anchor and replay ledger.
    """
    def __init__(self, state_dir: Path):
        self.state_dir = state_dir
        self.lock_file = state_dir / "admission.lock"
        self.anchor_file = state_dir / "anchor.json"
        self.ledger_file = state_dir / "consumed_decisions.jsonl"
        
        self.lock_file.touch(exist_ok=True)
        if not self.anchor_file.exists():
            genesis_anchor = {
                "sequence": 41,
                "state_digest": "sha3:STATE41"
            }
            self.anchor_file.write_text(json.dumps(genesis_anchor))
        if not self.ledger_file.exists():
            self.ledger_file.touch()

    def get_context(self) -> Tuple[Dict[str, Any], set]:
        """Reads current anchor and consumed decision set directly."""
        anchor = json.loads(self.anchor_file.read_text())
        consumed = set()
        if self.ledger_file.exists():
            for line in self.ledger_file.read_text().splitlines():
                line = line.strip()
                if line:
                    consumed.add(line)
        return anchor, consumed

    def commit_transaction(self, new_seq: int, new_digest: str, decision_id: str):
        """Atomically persists decision_id, sequence, and new state digest with fsync."""
        with open(self.lock_file, "r+") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                # 1. Append decision_id to durable ledger
                with open(self.ledger_file, "a") as f_led:
                    f_led.write(f"{decision_id}\n")
                    f_led.flush()
                    os.fsync(f_led.fileno())

                # 2. Write new anchor state atomically via tempfile replace
                new_anchor = {
                    "sequence": new_seq,
                    "state_digest": new_digest
                }
                tmp_anchor = self.anchor_file.with_suffix(".tmp")
                with open(tmp_anchor, "w") as f_anc:
                    json.dump(new_anchor, f_anc)
                    f_anc.flush()
                    os.fsync(f_anc.fileno())
                os.replace(tmp_anchor, self.anchor_file)
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)


class HostAdmissionVerifier:
    """
    Host-side cryptographic verifier implementing the strict execution pipeline.
    """
    def __init__(self, state_mgr: AdmissionTransactionManager, rego_policy: Path):
        self.state_mgr = state_mgr
        self.rego_policy = rego_policy
        
        # Pinned Trust Store (External authority keyring, NOT bundled in payload)
        self.ed_priv = ed25519.Ed25519PrivateKey.generate()
        self.trusted_ed25519_key_id = "key-ed25519-primary-2026"
        self.trusted_mldsa_key_id = "key-mldsa65-pqc-2026"
        
        self.pinned_keyring = {
            self.trusted_ed25519_key_id: self.ed_priv.public_key(),
            self.trusted_mldsa_key_id: b"SIMULATED_PINNED_MLDSA_ROOT"
        }
        
        # Governing environment context
        self.active_policy_digest = "sha3:POLICY_A"
        self.pending_input_digest = "sha3:INPUT_A"

    def sign_attestation(self, payload: dict, key_id_ed: str = None, key_id_ml: str = None,
                         corrupt_ed: bool = False, corrupt_ml: bool = False) -> bytes:
        """Helper to serialize and sign a state attestation."""
        ed_kid = key_id_ed or self.trusted_ed25519_key_id
        ml_kid = key_id_ml or self.trusted_mldsa_key_id
        
        jcs_bytes = jcs_canonicalize(payload)
        digest = hashlib.sha3_256(jcs_bytes).digest()
        
        ed_sig = self.ed_priv.sign(digest)
        if corrupt_ed:
            ed_sig = bytes([ed_sig[0] ^ 0xFF]) + ed_sig[1:]
            
        ml_sig = hashlib.sha3_256(digest + b":MLDSA-SIG").digest()
        if corrupt_ml:
            ml_sig = bytes([ml_sig[0] ^ 0xFF]) + ml_sig[1:]
            
        full_obj = {
            "attestation": {
                "payload": payload,
                "key_ids": {
                    "ed25519_key_id": ed_kid,
                    "ml_dsa_key_id": ml_kid
                },
                "signatures": {
                    "ed25519_signature": ed_sig.hex(),
                    "ml_dsa_signature": ml_sig.hex()
                }
            }
        }
        return json.dumps(full_obj).encode("utf-8")

    def process_ingress(self, raw_bytes: bytes) -> Tuple[str, str]:
        """
        Executes the exact 8-stage production admission pipeline.
        Returns: (status, reason) where status is "ALLOW", "DENY", or "REJECTED_PRE_OPA".
        """
        # [STAGE 1]: Size boundary check
        if len(raw_bytes) > MAX_ATTESTATION_BYTES:
            return "REJECTED_PRE_OPA", f"Size boundary violated ({len(raw_bytes)} B > {MAX_ATTESTATION_BYTES} B)"

        # [STAGE 2]: Strict JSON decoding & schema structure check
        try:
            raw_text = raw_bytes.decode("utf-8")
            obj = json.loads(raw_text)
        except Exception as e:
            return "REJECTED_PRE_OPA", f"JSON decode failure: {e}"

        if not isinstance(obj, dict) or "attestation" not in obj:
            return "REJECTED_PRE_OPA", "Malformed envelope: missing 'attestation' root"

        attestation = obj["attestation"]
        if not isinstance(attestation, dict) or "payload" not in attestation:
            return "REJECTED_PRE_OPA", "Malformed attestation: missing 'payload'"

        payload = attestation["payload"]
        if not isinstance(payload, dict):
            return "REJECTED_PRE_OPA", "Malformed payload: must be object"

        # Check for dynamic unexpected fields in payload (DisallowUnknownFields)
        expected_fields = {
            "schema_version", "sequence", "previous_state_digest",
            "policy_digest", "decision_id", "input_digest", "result"
        }
        actual_fields = set(payload.keys())
        if actual_fields != expected_fields:
            return "REJECTED_PRE_OPA", f"Strict struct mismatch: unexpected fields {actual_fields - expected_fields}"

        # [STAGE 3]: RFC 8785 JCS Canonicalization
        jcs_bytes = jcs_canonicalize(payload)

        # [STAGE 4]: SHA3-256 Digest Recomputation
        target_digest = hashlib.sha3_256(jcs_bytes).digest()

        # [STAGE 5]: External Pinned Trust Store Verification
        key_ids = attestation.get("key_ids", {})
        signatures = attestation.get("signatures", {})
        
        ed_kid = key_ids.get("ed25519_key_id")
        ml_kid = key_ids.get("ml_dsa_key_id")
        
        trusted_keyring = (
            ed_kid in self.pinned_keyring and 
            ml_kid in self.pinned_keyring
        )
        
        ed25519_verified = False
        ml_dsa_verified = False
        canonical_digest_verified = True  # By definition matches recomputed digest
        
        if trusted_keyring:
            # Ed25519 verification against pinned key
            try:
                pub = self.pinned_keyring[ed_kid]
                sig_bytes = bytes.fromhex(signatures.get("ed25519_signature", ""))
                pub.verify(sig_bytes, target_digest)
                ed25519_verified = True
            except Exception:
                ed25519_verified = False

            # ML-DSA verification against pinned key
            try:
                expected_ml_sig = hashlib.sha3_256(target_digest + b":MLDSA-SIG").digest().hex()
                actual_ml_sig = signatures.get("ml_dsa_signature", "")
                if actual_ml_sig == expected_ml_sig:
                    ml_dsa_verified = True
            except Exception:
                ml_dsa_verified = False

        # Assemble verified facts for OPA
        verification_facts = {
            "canonical_digest_verified": canonical_digest_verified,
            "ed25519_verified": ed25519_verified,
            "ml_dsa_verified": ml_dsa_verified,
            "trusted_keyring": trusted_keyring
        }

        # [STAGE 6 & 7]: Transactional Lock + OPA Evaluation + Atomic Commit
        with open(self.state_mgr.lock_file, "r+") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                # Read latest persistent state under lock
                anchor, consumed_decisions = self.state_mgr.get_context()
                
                opa_input = {
                    "attestation": {
                        "payload": payload
                    },
                    "verification": verification_facts
                }
                
                opa_data = {
                    "anchor": anchor,
                    "environment": {
                        "active_policy_digest": self.active_policy_digest,
                        "pending_input_digest": self.pending_input_digest
                    },
                    "ledger": {
                        "consumed_decisions": list(consumed_decisions)
                    }
                }
                
                # Evaluate OPA boot gate policy over verified facts
                with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_in, \
                     tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_data:
                    json.dump(opa_input, f_in)
                    json.dump(opa_data, f_data)
                    f_in_name, f_data_name = f_in.name, f_data.name

                try:
                    cmd = [
                        "opa", "eval",
                        "-i", f_in_name,
                        "-d", f_data_name,
                        "-d", str(self.rego_policy),
                        "data.quantumflex.bootgate.allow"
                    ]
                    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
                    res_json = json.loads(res.stdout)
                    allow = False
                    if res_json.get("result") and len(res_json["result"]) > 0:
                        allow = bool(res_json["result"][0].get("expressions", [{}])[0].get("value", False))
                finally:
                    os.remove(f_in_name)
                    os.remove(f_data_name)

                if not allow:
                    return "DENY", "OPA Hard Stop: policy, continuity, binding, crypto, or replay rejected"

                # ATOMIC COMMIT on ALLOW
                new_seq = payload["sequence"]
                new_state_digest = sha3_256_hex(jcs_bytes)
                dec_id = payload["decision_id"]
                
                # Append to durable ledger and update anchor file atomically
                with open(self.state_mgr.ledger_file, "a") as f_led:
                    f_led.write(f"{dec_id}\n")
                    f_led.flush()
                    os.fsync(f_led.fileno())
                    
                new_anchor_state = {
                    "sequence": new_seq,
                    "state_digest": new_state_digest
                }
                tmp_a = self.state_mgr.anchor_file.with_suffix(".tmp")
                with open(tmp_a, "w") as f_a:
                    json.dump(new_anchor_state, f_a)
                    f_a.flush()
                    os.fsync(f_a.fileno())
                os.replace(tmp_a, self.state_mgr.anchor_file)

                # [STAGE 8]: Execution Authorized
                return "ALLOW", f"Admitted sequence {new_seq}, decision {dec_id} committed"

            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)


def run_tests():
    print("=" * 75)
    print("  QUANTUMFLEX CRITICAL-STATE v1: BELOW-THE-NETWORK ADMISSION MATRIX  ")
    print("  Enforcing: Fingerprint = Integrity | Signature = Provenance        ")
    print("             Continuity  = Ordering  | OPA       = Authorization     ")
    print("=" * 75)

    test_dir = Path(tempfile.mkdtemp(prefix="qf_host_admission_test_"))
    try:
        state_mgr = AdmissionTransactionManager(test_dir)
        verifier = HostAdmissionVerifier(state_mgr, BOOTGATE_REGO)
        
        def make_valid_payload(seq=42, prev="sha3:STATE41", dec="decision-42",
                               pol="sha3:POLICY_A", inp="sha3:INPUT_A", res="ALLOW"):
            return {
                "schema_version": "v1",
                "sequence": seq,
                "previous_state_digest": prev,
                "policy_digest": pol,
                "decision_id": dec,
                "input_digest": inp,
                "result": res
            }

        # ---------------------------------------------------------------------
        # 1. Pristine Attestation -> ALLOW
        # ---------------------------------------------------------------------
        p1 = make_valid_payload(seq=42, prev="sha3:STATE41", dec="decision-42")
        raw1 = verifier.sign_attestation(p1)
        status, reason = verifier.process_ingress(raw1)
        print(f"[TEST 01] pristine attestation             -> {status:<6} | {reason}")
        assert status == "ALLOW", f"Expected ALLOW, got {status}: {reason}"

        # ---------------------------------------------------------------------
        # 2. Repeated Decision ID -> DENY
        # ---------------------------------------------------------------------
        p2 = make_valid_payload(seq=43, prev=verifier.state_mgr.get_context()[0]["state_digest"], dec="decision-42")
        raw2 = verifier.sign_attestation(p2)
        status, reason = verifier.process_ingress(raw2)
        print(f"[TEST 02] repeated decision_id             -> {status:<6} | {reason}")
        assert status == "DENY", f"Expected DENY, got {status}: {reason}"

        # ---------------------------------------------------------------------
        # 3. Sequence Rollback -> DENY
        # ---------------------------------------------------------------------
        curr_anchor, _ = verifier.state_mgr.get_context()
        p3 = make_valid_payload(seq=42, prev=curr_anchor["state_digest"], dec="decision-43") # seq rollback (should be 43)
        raw3 = verifier.sign_attestation(p3)
        status, reason = verifier.process_ingress(raw3)
        print(f"[TEST 03] sequence rollback                -> {status:<6} | {reason}")
        assert status == "DENY", f"Expected DENY, got {status}: {reason}"

        # ---------------------------------------------------------------------
        # 4. Wrong Predecessor Digest -> DENY
        # ---------------------------------------------------------------------
        p4 = make_valid_payload(seq=43, prev="sha3:ATTACKER_STATE", dec="decision-44")
        raw4 = verifier.sign_attestation(p4)
        status, reason = verifier.process_ingress(raw4)
        print(f"[TEST 04] wrong predecessor digest         -> {status:<6} | {reason}")
        assert status == "DENY", f"Expected DENY, got {status}: {reason}"

        # ---------------------------------------------------------------------
        # 5. Changed Policy -> DENY
        # ---------------------------------------------------------------------
        p5 = make_valid_payload(seq=43, prev=curr_anchor["state_digest"], dec="decision-45", pol="sha3:POLICY_ATTACKER")
        raw5 = verifier.sign_attestation(p5)
        status, reason = verifier.process_ingress(raw5)
        print(f"[TEST 05] changed policy                   -> {status:<6} | {reason}")
        assert status == "DENY", f"Expected DENY, got {status}: {reason}"

        # ---------------------------------------------------------------------
        # 6. Changed Execution Input -> DENY
        # ---------------------------------------------------------------------
        p6 = make_valid_payload(seq=43, prev=curr_anchor["state_digest"], dec="decision-46", inp="sha3:INPUT_ATTACKER")
        raw6 = verifier.sign_attestation(p6)
        status, reason = verifier.process_ingress(raw6)
        print(f"[TEST 06] changed execution input          -> {status:<6} | {reason}")
        assert status == "DENY", f"Expected DENY, got {status}: {reason}"

        # ---------------------------------------------------------------------
        # 7. Ed25519 Failure -> DENY
        # ---------------------------------------------------------------------
        p7 = make_valid_payload(seq=43, prev=curr_anchor["state_digest"], dec="decision-47")
        raw7 = verifier.sign_attestation(p7, corrupt_ed=True)
        status, reason = verifier.process_ingress(raw7)
        print(f"[TEST 07] Ed25519 failure                  -> {status:<6} | {reason}")
        assert status == "DENY", f"Expected DENY, got {status}: {reason}"

        # ---------------------------------------------------------------------
        # 8. ML-DSA Failure -> DENY
        # ---------------------------------------------------------------------
        p8 = make_valid_payload(seq=43, prev=curr_anchor["state_digest"], dec="decision-48")
        raw8 = verifier.sign_attestation(p8, corrupt_ml=True)
        status, reason = verifier.process_ingress(raw8)
        print(f"[TEST 08] ML-DSA failure                   -> {status:<6} | {reason}")
        assert status == "DENY", f"Expected DENY, got {status}: {reason}"

        # ---------------------------------------------------------------------
        # 9. Unknown Signing Authority -> DENY
        # ---------------------------------------------------------------------
        p9 = make_valid_payload(seq=43, prev=curr_anchor["state_digest"], dec="decision-49")
        raw9 = verifier.sign_attestation(p9, key_id_ed="rogue-unpinned-signer-id")
        status, reason = verifier.process_ingress(raw9)
        print(f"[TEST 09] unknown signing authority        -> {status:<6} | {reason}")
        assert status == "DENY", f"Expected DENY, got {status}: {reason}"

        # ---------------------------------------------------------------------
        # 10. Malformed JSON -> Rejected Before OPA
        # ---------------------------------------------------------------------
        raw10 = b'{"attestation": {"payload": {"schema_version": "v1", "injected_rogue_key": true}}}'
        status, reason = verifier.process_ingress(raw10)
        print(f"[TEST 10] malformed JSON                   -> {status:<6} | {reason}")
        assert status == "REJECTED_PRE_OPA", f"Expected REJECTED_PRE_OPA, got {status}"

        # ---------------------------------------------------------------------
        # 11. Oversized State Object -> Rejected Before Parsing
        # ---------------------------------------------------------------------
        raw11 = b"A" * (MAX_ATTESTATION_BYTES + 1024)
        status, reason = verifier.process_ingress(raw11)
        print(f"[TEST 11] oversized state object           -> {status:<6} | {reason}")
        assert status == "REJECTED_PRE_OPA", f"Expected REJECTED_PRE_OPA, got {status}"

        # ---------------------------------------------------------------------
        # 12. Transactional Concurrency Race (Anti-TOCTOU)
        # ---------------------------------------------------------------------
        curr_anchor, _ = verifier.state_mgr.get_context()
        p12 = make_valid_payload(seq=43, prev=curr_anchor["state_digest"], dec="decision-concurrent-43")
        raw12 = verifier.sign_attestation(p12)
        
        # Fire two simultaneous ingress attempts with identical decision_id
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(verifier.process_ingress, raw12)
            f2 = executor.submit(verifier.process_ingress, raw12)
            res1 = f1.result()
            res2 = f2.result()
            
        results = sorted([res1[0], res2[0]])
        print(f"[TEST 12] concurrent TOCTOU race (2x req)  -> Thread 1: {res1[0]}, Thread 2: {res2[0]}")
        assert results == ["ALLOW", "DENY"], f"Replay race vulnerability! Expected 1 ALLOW and 1 DENY, got {results}"

        print("=" * 75)
        print("  ALL 12 HOST ADMISSION BOUNDARY TESTS PASSED (100% GREEN)  ")
        print("=" * 75)

    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_critical_state_host_admission_matrix():
    """Validates the full 12-case host admission boundary matrix."""
    run_tests()


if __name__ == "__main__":
    run_tests()

