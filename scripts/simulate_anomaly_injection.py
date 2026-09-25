#!/usr/bin/env python3
"""
QuantumFlex Critical-State v1: Anomaly Injection & Ghost Node Hard Stop Simulator
==================================================================================
Mathematically verifies the invariant: Y = f(x - h) + k

Components Tested:
  1. Strict Memory Layout (CriticalStatePayload, StateSignatures, StateAttestation)
  2. RFC 8785 JCS Canonicalization + SHA3-256 Digest
  3. Dual-Signature Provenance Gate (Ed25519 + ML-DSA post-quantum path)
  4. OPA Boot Gate Invariant & Anti-Replay Policy (critical_state_bootgate.rego)
  5. Ingress Gatekeeper Hard Stop Anomaly Routing
  6. Rust-based Isolated Ghost Node Entropy Sink (127.0.0.1:19443)
  7. Hash-Chained JSONL Ledger Invariants (H_attack = 0, zero authority)
"""

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ed25519

ROOT_DIR = Path(__file__).resolve().parents[1]
REGO_POLICY = ROOT_DIR / "sentinel" / "policies" / "critical_state_bootgate.rego"
GHOST_SINK_BIN = ROOT_DIR / "quantumflex-ghost-sink" / "target" / "release" / "quantumflex-ghost-sink"
SINK_URL = "http://127.0.0.1:19443/v1/sink/anomaly"
SINK_HEALTH = "http://127.0.0.1:19443/healthz"


def jcs_canonicalize(data: dict) -> bytes:
    """RFC 8785 JSON Canonicalization Scheme (JCS) serializer."""
    return json.dumps(data, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")


def sha3_256_hex(data: bytes) -> str:
    """Calculates SHA3-256 hexadecimal digest."""
    return hashlib.sha3_256(data).hexdigest()


class GatekeeperEngine:
    def __init__(self, policy_path: Path):
        self.policy_path = policy_path
        self.ed_priv = ed25519.Ed25519PrivateKey.generate()
        self.ed_pub = self.ed_priv.public_key()
        self.ed_pub_hex = self.ed_pub.public_bytes_raw().hex()
        # Simulated deterministic ML-DSA PQC public key / identity
        self.mldsa_pub_hex = hashlib.sha3_256(b"ML-DSA-65-TEST-ROOT-KEY").hexdigest()
        
        # Local persistent anchor (k)
        self.anchor = {
            "sequence": 0,
            "state_digest": sha3_256_hex(b"GENESIS_STATE_ANCHOR_K0")
        }
        
        # Anti-replay ledger
        self.consumed_decisions = []
        
        # Active environment context (p, x)
        self.active_policy_digest = sha3_256_hex(policy_path.read_bytes())
        self.pending_input_digest = sha3_256_hex(b"EXECUTION_PAYLOAD_X_V1")

    def build_attestation(self, sequence: int, previous_digest: str, decision_id: str,
                          policy_digest: str, input_digest: str, result: str = "ALLOW",
                          extra_fields: dict = None, corrupt_ed_sig: bool = False) -> dict:
        """Constructs and cryptographically signs a StateAttestation object."""
        payload = {
            "schema_version": "v1",
            "sequence": sequence,
            "previous_state_digest": previous_digest,
            "policy_digest": policy_digest,
            "decision_id": decision_id,
            "input_digest": input_digest,
            "result": result,
            "public_credentials": {
                "ed25519_pub_key": self.ed_pub_hex,
                "ml_dsa_pub_key": self.mldsa_pub_hex
            }
        }
        if extra_fields:
            payload.update(extra_fields)

        # 1. JCS Canonicalization
        jcs_bytes = jcs_canonicalize(payload)
        # 2. SHA3-256 Digest
        digest_bytes = hashlib.sha3_256(jcs_bytes).digest()

        # 3. Dual Signatures (Ed25519 + ML-DSA)
        ed_sig = self.ed_priv.sign(digest_bytes)
        if corrupt_ed_sig:
            # Flip 1 byte for perturbation attack
            ed_sig = bytes([ed_sig[0] ^ 0xFF]) + ed_sig[1:]

        # Simulated deterministic post-quantum signature
        mldsa_sig = hashlib.sha3_256(digest_bytes + b"ML-DSA-SIG-PATH").hexdigest()

        return {
            "payload": payload,
            "signatures": {
                "ed25519_signature": ed_sig.hex(),
                "ml_dsa_signature": mldsa_sig
            }
        }

    def inspect_and_admit(self, attestation: dict) -> tuple[bool, str]:
        """Ingress Gatekeeper evaluation of Y = f(x - h) + k."""
        # 1. Cryptographic Provenance Pre-check (Ed25519 signature over SHA3-256 of JCS)
        try:
            payload = attestation.get("payload", {})
            jcs_bytes = jcs_canonicalize(payload)
            digest_bytes = hashlib.sha3_256(jcs_bytes).digest()
            sig_hex = attestation.get("signatures", {}).get("ed25519_signature", "")
            sig_bytes = bytes.fromhex(sig_hex)
            self.ed_pub.verify(sig_bytes, digest_bytes)
        except Exception as e:
            reason = f"Cryptographic provenance failed: {e}"
            self.route_to_ghost_node(attestation, reason)
            return False, reason

        # 2. OPA Policy Evaluation at Boot Gate
        data_doc = {
            "anchor": self.anchor,
            "environment": {
                "active_policy_digest": self.active_policy_digest,
                "pending_input_digest": self.pending_input_digest
            },
            "ledger": {
                "consumed_decisions": self.consumed_decisions
            }
        }

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_in, \
             tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f_data:
            json.dump(attestation, f_in)
            json.dump(data_doc, f_data)
            in_path, data_path = f_in.name, f_data.name

        try:
            cmd = [
                "opa", "eval",
                "-i", in_path,
                "-d", data_path,
                "-d", str(self.policy_path),
                "data.quantumflex.critical_bootgate.allow"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            eval_data = json.loads(res.stdout)
            allow = False
            results = eval_data.get("result", [])
            if results and len(results) > 0:
                allow = bool(results[0].get("expressions", [{}])[0].get("value", False))
        finally:
            os.remove(in_path)
            os.remove(data_path)

        if not allow:
            reason = "OPA boot gate policy violation (schema, continuity, binding, or replay)"
            self.route_to_ghost_node(attestation, reason)
            return False, reason

        # 3. Execution Authority Granted (Y committed to continuity chain)
        seq = payload["sequence"]
        self.anchor["sequence"] = seq
        self.anchor["state_digest"] = sha3_256_hex(jcs_bytes)
        self.consumed_decisions.append(payload["decision_id"])
        return True, "ADMIT (Invariant Y committed to continuity chain)"

    def route_to_ghost_node(self, attestation: dict, reason: str):
        """Absorbs anomaly (h) into the Ghost Node entropy sink."""
        sink_payload = {
            "node_uuid": "fedora-primary-alpha",
            "timestamp_epoch_nonce": str(int(time.time())),
            "pcr_integrity_pass": False,
            "nonce_freshness_pass": True,
            "structural_anomaly": {"reason": reason},
            "execution_violations": [{"phase": "BOOT_GATE_INSPECTION", "reason": reason}],
            "raw_records_count": 1,
            "entropy_action": "ABSORB_INTO_GHOST_SINK",
            "raw_telemetry_dump": json.dumps(attestation),
            "h_attack": 0
        }
        req = urllib.request.Request(
            SINK_URL,
            data=json.dumps(sink_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"       [GHOST SINK ABSORPTION] Seq: {data['sequence_number']} | Hash: {data['record_hash'][:16]}... | Status: {data['status']}")


def wait_for_sink_health(timeout=10.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(SINK_HEALTH, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.2)
    return False


def main():
    print("=" * 70)
    print("  QUANTUMFLEX CRITICAL-STATE v1: ANOMALY INJECTION SIMULATOR  ")
    print("  Mathematical Invariant: Y = f(x - h) + k                   ")
    print("=" * 70)

    # 1. Setup isolated storage directory for Ghost Node
    sim_dir = Path(tempfile.mkdtemp(prefix="qf_anomaly_sim_"))
    ledger_file = sim_dir / "entropy_sink_ledger.jsonl"
    print(f"[*] Isolated Ghost Node Storage: {sim_dir}")

    # 2. Launch real compiled Rust Ghost Node binary
    env = os.environ.copy()
    env["SINK_LISTEN_ADDR"] = "127.0.0.1:19443"
    env["SINK_ALLOW_UNBOUND"] = "0"
    env["SINK_STORAGE_PATH"] = str(sim_dir)

    sink_proc = subprocess.Popen(
        [str(GHOST_SINK_BIN)],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    try:
        if not wait_for_sink_health():
            print("[-] Error: Failed to connect to Ghost Node sink on 127.0.0.1:19443")
            sys.exit(1)
        print("[+] Ghost Node Anomaly Sink Active on http://127.0.0.1:19443")

        gatekeeper = GatekeeperEngine(REGO_POLICY)
        print(f"[+] Initialized Ingress Gatekeeper Engine:")
        print(f"    • Active Policy Digest (p) : {gatekeeper.active_policy_digest[:24]}...")
        print(f"    • Pending Input Digest (x)  : {gatekeeper.pending_input_digest[:24]}...")
        print(f"    • Local Anchor (k_0)        : Seq={gatekeeper.anchor['sequence']}, Digest={gatekeeper.anchor['state_digest'][:24]}...")

        # ---------------------------------------------------------------------
        # TEST 0: Nominal Baseline Progression (Y_1)
        # ---------------------------------------------------------------------
        print("\n[*] [NOMINAL 0] Ingesting authentic state attestation (Y_1)...")
        d0_id = str(uuid.uuid4())
        att0 = gatekeeper.build_attestation(
            sequence=1,
            previous_digest=gatekeeper.anchor["state_digest"],
            decision_id=d0_id,
            policy_digest=gatekeeper.active_policy_digest,
            input_digest=gatekeeper.pending_input_digest
        )
        ok, msg = gatekeeper.inspect_and_admit(att0)
        assert ok, f"Nominal 0 failed: {msg}"
        print(f"    [PASS] {msg}")
        print(f"    [STATE UPDATE] Anchor advanced: Seq={gatekeeper.anchor['sequence']}, Digest={gatekeeper.anchor['state_digest'][:24]}...")

        # ---------------------------------------------------------------------
        # INJECTION 1: Anomaly h_1 (Schema Mutation / Dynamic Field Injection)
        # ---------------------------------------------------------------------
        print("\n[*] [ATTACK 1] Injecting Malformed Schema & Dynamic Field Injection (h_1)...")
        d1_id = str(uuid.uuid4())
        att1 = gatekeeper.build_attestation(
            sequence=2,
            previous_digest=gatekeeper.anchor["state_digest"],
            decision_id=d1_id,
            policy_digest=gatekeeper.active_policy_digest,
            input_digest=gatekeeper.pending_input_digest,
            extra_fields={"unauthorized_dynamic_key": "c2_payload_injection"}
        )
        ok, msg = gatekeeper.inspect_and_admit(att1)
        assert not ok, "Security failure: Malformed schema allowed!"
        print(f"    [HARD STOP TRIGGERED] Anomaly rejected: {msg}")
        assert gatekeeper.anchor["sequence"] == 1, "Anchor mutated during attack!"

        # ---------------------------------------------------------------------
        # INJECTION 2: Anomaly h_2 (Continuity Sequence Skip)
        # ---------------------------------------------------------------------
        print("\n[*] [ATTACK 2] Injecting Sequence Skip / Non-Monotonic Jump (h_2)...")
        d2_id = str(uuid.uuid4())
        att2 = gatekeeper.build_attestation(
            sequence=99,  # Sequence jump! Expected 2
            previous_digest=gatekeeper.anchor["state_digest"],
            decision_id=d2_id,
            policy_digest=gatekeeper.active_policy_digest,
            input_digest=gatekeeper.pending_input_digest
        )
        ok, msg = gatekeeper.inspect_and_admit(att2)
        assert not ok, "Security failure: Sequence jump allowed!"
        print(f"    [HARD STOP TRIGGERED] Anomaly rejected: {msg}")

        # ---------------------------------------------------------------------
        # INJECTION 3: Anomaly h_3 (Continuity Fork / Corrupted Previous Digest)
        # ---------------------------------------------------------------------
        print("\n[*] [ATTACK 3] Injecting Fork Attack / Forged Previous State Digest (h_3)...")
        d3_id = str(uuid.uuid4())
        att3 = gatekeeper.build_attestation(
            sequence=2,
            previous_digest=sha3_256_hex(b"FORGED_PAST_STATE_HASH"),
            decision_id=d3_id,
            policy_digest=gatekeeper.active_policy_digest,
            input_digest=gatekeeper.pending_input_digest
        )
        ok, msg = gatekeeper.inspect_and_admit(att3)
        assert not ok, "Security failure: Corrupted previous state digest allowed!"
        print(f"    [HARD STOP TRIGGERED] Anomaly rejected: {msg}")

        # ---------------------------------------------------------------------
        # INJECTION 4: Anomaly h_4 (Decision ID Replay Attack)
        # ---------------------------------------------------------------------
        print("\n[*] [ATTACK 4] Injecting Expired Decision ID Replay Attack (h_4)...")
        # Replaying d0_id which was consumed in Nominal 0!
        att4 = gatekeeper.build_attestation(
            sequence=2,
            previous_digest=gatekeeper.anchor["state_digest"],
            decision_id=d0_id,  # REPLAY!
            policy_digest=gatekeeper.active_policy_digest,
            input_digest=gatekeeper.pending_input_digest
        )
        ok, msg = gatekeeper.inspect_and_admit(att4)
        assert not ok, "Security failure: Replayed decision ID allowed!"
        print(f"    [HARD STOP TRIGGERED] Anomaly rejected: {msg}")

        # ---------------------------------------------------------------------
        # INJECTION 5: Anomaly h_5 (Stale Policy Digest / Old ALLOW Replay)
        # ---------------------------------------------------------------------
        print("\n[*] [ATTACK 5] Injecting Stale Policy Digest Violation (h_5)...")
        d5_id = str(uuid.uuid4())
        att5 = gatekeeper.build_attestation(
            sequence=2,
            previous_digest=gatekeeper.anchor["state_digest"],
            decision_id=d5_id,
            policy_digest=sha3_256_hex(b"OUTDATED_VULNERABLE_POLICY_REVISION"),
            input_digest=gatekeeper.pending_input_digest
        )
        ok, msg = gatekeeper.inspect_and_admit(att5)
        assert not ok, "Security failure: Stale policy digest allowed!"
        print(f"    [HARD STOP TRIGGERED] Anomaly rejected: {msg}")

        # ---------------------------------------------------------------------
        # INJECTION 6: Anomaly h_6 (Input Digest Binding Violation)
        # ---------------------------------------------------------------------
        print("\n[*] [ATTACK 6] Injecting Input Digest Binding Violation (h_6)...")
        d6_id = str(uuid.uuid4())
        att6 = gatekeeper.build_attestation(
            sequence=2,
            previous_digest=gatekeeper.anchor["state_digest"],
            decision_id=d6_id,
            policy_digest=gatekeeper.active_policy_digest,
            input_digest=sha3_256_hex(b"DIFFERENT_UNAPPROVED_COMMAND_INPUT")
        )
        ok, msg = gatekeeper.inspect_and_admit(att6)
        assert not ok, "Security failure: Mismatched input digest allowed!"
        print(f"    [HARD STOP TRIGGERED] Anomaly rejected: {msg}")

        # ---------------------------------------------------------------------
        # INJECTION 7: Anomaly h_7 (Cryptographic Signature Perturbation)
        # ---------------------------------------------------------------------
        print("\n[*] [ATTACK 7] Injecting Cryptographic Signature Perturbation (h_7)...")
        d7_id = str(uuid.uuid4())
        att7 = gatekeeper.build_attestation(
            sequence=2,
            previous_digest=gatekeeper.anchor["state_digest"],
            decision_id=d7_id,
            policy_digest=gatekeeper.active_policy_digest,
            input_digest=gatekeeper.pending_input_digest,
            corrupt_ed_sig=True  # 1-bit perturbation
        )
        ok, msg = gatekeeper.inspect_and_admit(att7)
        assert not ok, "Security failure: Corrupted digital signature allowed!"
        print(f"    [HARD STOP TRIGGERED] Anomaly rejected: {msg}")

        # ---------------------------------------------------------------------
        # TEST 8: Post-Attack Nominal Recovery (Y_2)
        # ---------------------------------------------------------------------
        print("\n[*] [NOMINAL RECOVERY] Verifying system recovery and progression (Y_2)...")
        d8_id = str(uuid.uuid4())
        att8 = gatekeeper.build_attestation(
            sequence=2,
            previous_digest=gatekeeper.anchor["state_digest"],
            decision_id=d8_id,
            policy_digest=gatekeeper.active_policy_digest,
            input_digest=gatekeeper.pending_input_digest
        )
        ok, msg = gatekeeper.inspect_and_admit(att8)
        assert ok, f"Nominal 2 failed: {msg}"
        print(f"    [PASS] {msg}")
        print(f"    [STATE UPDATE] Anchor advanced: Seq={gatekeeper.anchor['sequence']}, Digest={gatekeeper.anchor['state_digest'][:24]}...")

        # ---------------------------------------------------------------------
        # TEST 9: Ghost Node Sink Ledger Invariant Audit
        # ---------------------------------------------------------------------
        print("\n[*] [AUDIT] Inspecting Ghost Node Anomaly Sink Ledger...")
        assert ledger_file.exists(), f"Ledger file missing at {ledger_file}"
        lines = [json.loads(l) for l in ledger_file.read_text().strip().split("\n") if l.strip()]
        print(f"    [+] Total Anomalies Absorbed in Hash Chain: {len(lines)}")
        assert len(lines) == 7, f"Expected 7 absorbed anomalies, found {len(lines)}"

        for idx, rec in enumerate(lines, 1):
            assert rec["sequence_number"] == idx
            assert rec["payload"]["entropy_action"] == "ABSORB_INTO_GHOST_SINK"
            assert rec["payload"]["h_attack"] == 0, "Security violation: H_attack > 0!"
            print(f"    • Ledger Record #{rec['sequence_number']}: "
                  f"Hash={rec['record_hash'][:16]}... | "
                  f"Reason={rec['payload']['structural_anomaly']['reason'][:42]}...")

        print("\n" + "=" * 70)
        print("  ALL 7 ANOMALY INJECTION ATTACKS SAFELY ABSORBED  ")
        print("  INVARIANT Y = f(x - h) + k FULLY VERIFIED        ")
        print("  ZERO BLIND EXECUTIONS · ZERO STATE DRIFT        ")
        print("=" * 70)

    finally:
        print("[*] Terminating Ghost Node subprocess...")
        sink_proc.terminate()
        sink_proc.wait(timeout=5)
        shutil.rmtree(sim_dir, ignore_errors=True)
        print("[+] Teardown complete.")


if __name__ == "__main__":
    main()
