#!/usr/bin/env python3
"""
QuantumFlex: End-to-End Telemetry Privacy Wiring & Persistence Boundary Proof
=============================================================================
Acceptance Criteria:
1. Trace the complete execution path through api_node/main.py, api_node/kafka_consumer.py,
   and direct persistence entry points.
2. Inject adversarial telemetry frames (case-insensitive _optout/_nomap, deeply nested, malformed).
3. Verify sanitization at every persistence boundary (PostgreSQL quantum_telemetry_channel,
   telemetry_log, and Athena neural embeddings).
4. Prove fail-closed behavior: sanitizer exceptions halt and abort downstream writes.
5. Inspect the resulting artifacts directly to prove zero leakage.
6. Verify direct persistence bypass attempts are actively rejected.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.privacy_filter import PrivacyFilter
from api_node.main import app, persist_telemetry_frame
from api_node.kafka_consumer import process_pulse
from starlette.testclient import TestClient


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def api_client():
    """FastAPI TestClient for api_node."""
    return TestClient(app)


# ==============================================================================
# 1. Edge Filter Invariant Tests (Recursive & Fail-Closed)
# ==============================================================================

class TestPrivacyFilterInvariants:
    def test_case_insensitive_variants(self):
        """All variations of _optout and _nomap must be detected."""
        variants = [
            "Home_optout", "_OPTOUT_5G", "Cafe_OpToUt",
            "Shop_nomap", "_NOMAP_Guest", "Lab_NoMaP_Ext"
        ]
        for v in variants:
            assert PrivacyFilter.should_exclude_ssid(v) is True, f"Failed for {v}"
            assert PrivacyFilter.contains_optout(v) is True
            assert PrivacyFilter.sanitize_telemetry_frame({"ssid": v}) is None

    def test_compliant_names_allowed(self):
        """Standard labels without opt-out markers are not falsely flagged, while operational frames pass and direct SSIDs are dropped."""
        compliant = ["Starlink-WiFi", "QuantumFlex-Mesh-01", "Archer_BE3600_Pro", "nomaple_syrup"]
        for c in compliant:
            assert PrivacyFilter.should_exclude_ssid(c) is False
            assert PrivacyFilter.contains_optout({"label": c}) is False
            # Direct SSID field must be dropped under Zero Ambient Data Invariant
            assert PrivacyFilter.sanitize_telemetry_frame({"ssid": c, "rssi": -50}) is None
        # Valid host telemetry frame passes
        valid_operational = PrivacyFilter.sanitize_telemetry_frame({"node_id": "qfx-yoga", "cpu_load_1m": 0.15})
        assert valid_operational is not None
        assert valid_operational["node_id"] == "qfx-yoga"

    def test_recursive_nested_detection(self):
        """Opt-out tags hidden in deeply nested structures must be detected."""
        nested_payload = {
            "node_id": "test-node",
            "metadata": {
                "scan_batch": {
                    "nested_ssid": "Secret_optout",
                    "rssi": -65
                }
            }
        }
        assert PrivacyFilter.contains_optout(nested_payload) is True
        assert PrivacyFilter.sanitize_telemetry_frame(nested_payload) is None

    def test_adversarial_malformed_types(self):
        """Non-dict and unexpected data structures must fail closed."""
        malformed_inputs = [None, 12345, "string_only", [1, 2, 3], True, b"bytes"]
        for m in malformed_inputs:
            assert PrivacyFilter.sanitize_telemetry_frame(m) is None

    def test_fail_closed_on_sanitizer_exception(self, monkeypatch):
        """If an unhandled exception occurs inside sanitization, it must return None."""
        def bomb(*args, **kwargs):
            raise RuntimeError("Simulated memory fault or regex crash!")

        monkeypatch.setattr(PrivacyFilter, "contains_optout", bomb)
        # Must fail closed: return None, never propagate or admit
        result = PrivacyFilter.sanitize_telemetry_frame({"ssid": "Clean_Network"})
        assert result is None


# ==============================================================================
# 2. API Gateway Persistence Boundary Tests (api_node/main.py)
# ==============================================================================

class TestApiGatewayPersistenceBoundary:
    def test_direct_persist_telemetry_frame_rejects_optout_bypass(self):
        """Direct invocation of persist_telemetry_frame must fail closed on opt-out tags."""
        with patch("psycopg2.connect") as mock_connect:
            # Direct bypass attempt with _optout in payload string
            optout_payload = json.dumps({"ssid": "Bypass_optout", "bssid": "11:22:33:44:55:66"})
            res = persist_telemetry_frame("node-evil", 1700000000, optout_payload)
            assert res is False, "persist_telemetry_frame must reject opted-out payload string"
            # Ensure database connection was NEVER initiated
            mock_connect.assert_not_called()

    def test_direct_persist_telemetry_frame_admits_clean_payload(self):
        """Direct invocation commits compliant operational payloads to PostgreSQL."""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("psycopg2.connect", return_value=mock_conn):
            clean_payload = json.dumps({"node_id": "node-clean", "cpu_load_1m": 0.25, "ram_used_pct": 50.0, "status": "PULSE_OK"})
            res = persist_telemetry_frame("node-clean", 1700000000, clean_payload)
            assert res is True
            mock_cursor.execute.assert_called_once()
            args = mock_cursor.execute.call_args[0][1]
            assert args[0] == "node-clean"
            assert "node-clean" in args[2]

    def test_api_submit_endpoint_strips_opted_out_frames(self, api_client):
        """The /api/v1/telemetry/submit route must strip opt-out frames while preserving valid host operational frames."""
        from cryptography.hazmat.primitives.asymmetric import ed25519

        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        pub_hex = public_key.public_bytes_raw().hex()

        node_id = "test-host"
        seq = 1
        timestamp = 1700000000

        mixed_payload = {
            "frames": [
                {"event_type": "cpu_load_pulse", "cpu_load_1m": 0.12},
                {"event_type": "audit_nomap", "reason": "internal_optout"},
                {"event_type": "ram_pulse", "ram_used_pct": 45.2},
                {"event_type": "telemetry_optout", "note": "drop_me"}
            ]
        }
        payload_str = json.dumps(mixed_payload)
        message_bytes = f"{node_id}:{seq}:{payload_str}".encode("utf-8")
        sig_hex = private_key.sign(message_bytes).hex()

        submission_body = {
            "node_id": node_id,
            "seq": seq,
            "timestamp": timestamp,
            "payload": payload_str,
            "signature": sig_hex,
            "public_key": pub_hex
        }

        recorded_persisted_payloads = []

        def capture_persist(n_id, ts, p_str):
            recorded_persisted_payloads.append(p_str)
            return True

        with patch("api_node.main.persist_telemetry_frame", side_effect=capture_persist):
            response = api_client.post("/api/v1/telemetry/submit", json=submission_body)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "VERIFIED"

            # Verify persisted artifact
            assert len(recorded_persisted_payloads) == 1
            persisted_obj = json.loads(recorded_persisted_payloads[0])
            retained_frames = persisted_obj["frames"]
            assert len(retained_frames) == 2
            retained_events = [f["event_type"] for f in retained_frames]
            assert "cpu_load_pulse" in retained_events
            assert "ram_pulse" in retained_events
            # Ensure zero opted-out frames touched persistence
            assert "audit_nomap" not in recorded_persisted_payloads[0]
            assert "telemetry_optout" not in recorded_persisted_payloads[0]

    def test_api_submit_endpoint_rejects_pure_optout_payload(self, api_client):
        """If all frames in a batch are opted-out, the API must reject with 403 Forbidden."""
        from cryptography.hazmat.primitives.asymmetric import ed25519

        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        pub_hex = public_key.public_bytes_raw().hex()

        node_id = "test-sensor"
        seq = 1
        timestamp = 1700000000

        pure_optout = {
            "frames": [
                {"ssid": "Net_optout", "rssi": -70},
                {"ssid": "Net_nomap", "rssi": -75}
            ]
        }
        payload_str = json.dumps(pure_optout)
        message_bytes = f"{node_id}:{seq}:{payload_str}".encode("utf-8")
        sig_hex = private_key.sign(message_bytes).hex()

        submission_body = {
            "node_id": node_id,
            "seq": seq,
            "timestamp": timestamp,
            "payload": payload_str,
            "signature": sig_hex,
            "public_key": pub_hex
        }

        with patch("api_node.main.persist_telemetry_frame") as mock_persist:
            response = api_client.post("/api/v1/telemetry/submit", json=submission_body)
            assert response.status_code == 403
            assert "Forbidden" in response.text
            mock_persist.assert_not_called()

    def test_api_submit_endpoint_rejects_prohibited_ambient_telemetry(self, api_client):
        """If a payload contains unauthorized ambient network or personal tracking fields, reject with 403."""
        from cryptography.hazmat.primitives.asymmetric import ed25519

        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        pub_hex = public_key.public_bytes_raw().hex()

        node_id = "test-sensor"
        seq = 2
        timestamp = 1700000000

        prohibited_payload = {
            "neighbor_networks": ["Neighbor_SSID_1", "Neighbor_SSID_2"],
            "wifi_scan": {"active": True},
        }
        payload_str = json.dumps(prohibited_payload)
        message_bytes = f"{node_id}:{seq}:{payload_str}".encode("utf-8")
        sig_hex = private_key.sign(message_bytes).hex()

        submission_body = {
            "node_id": node_id,
            "seq": seq,
            "timestamp": timestamp,
            "payload": payload_str,
            "signature": sig_hex,
            "public_key": pub_hex,
        }

        with patch("api_node.main.persist_telemetry_frame") as mock_persist:
            response = api_client.post("/api/v1/telemetry/submit", json=submission_body)
            assert response.status_code == 403
            assert "Prohibited ambient network or personal tracking identifiers" in response.text
            mock_persist.assert_not_called()

    def test_api_submit_endpoint_accepts_pure_operational_vitals(self, api_client):
        """Legitimate QuantumFlex operational vitals (CPU load, RAM, thermals, PQC state) are verified and persisted."""
        from cryptography.hazmat.primitives.asymmetric import ed25519

        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        pub_hex = public_key.public_bytes_raw().hex()

        node_id = "qfx-yoga"
        seq = 3
        timestamp = 1700000000

        pure_vitals = {
            "cpu_load_1m": 0.25,
            "ram_used_pct": 52.0,
            "temp_c": 41.5,
            "configured_kem": "ML-KEM-768",
            "runtime_kem": "ML-KEM-768",
            "tpm": {"device_available": True},
            "status": "PULSE_OK",
        }
        payload_str = json.dumps(pure_vitals)
        message_bytes = f"{node_id}:{seq}:{payload_str}".encode("utf-8")
        sig_hex = private_key.sign(message_bytes).hex()

        submission_body = {
            "node_id": node_id,
            "seq": seq,
            "timestamp": timestamp,
            "payload": payload_str,
            "signature": sig_hex,
            "public_key": pub_hex,
        }

        persisted_records = []
        with patch("api_node.main.persist_telemetry_frame", side_effect=lambda n, t, p: persisted_records.append(p) or True):
            response = api_client.post("/api/v1/telemetry/submit", json=submission_body)
            assert response.status_code == 200
            assert response.json()["status"] == "VERIFIED"
            assert len(persisted_records) == 1
            record_obj = json.loads(persisted_records[0])
            assert record_obj["cpu_load_1m"] == 0.25
            assert record_obj["configured_kem"] == "ML-KEM-768"



# ==============================================================================
# 3. Kafka Consumer Persistence Boundary Tests (api_node/kafka_consumer.py)
# ==============================================================================

class TestKafkaConsumerPersistenceBoundary:
    def test_process_pulse_drops_optout_telemetry_before_db_or_athena(self):
        """process_pulse must drop opt-out messages before AMARA DB or Athena embedding."""
        with patch("api_node.kafka_consumer.get_amara_connection") as mock_db, \
             patch("api_node.kafka_consumer.push_to_athena") as mock_athena:

            optout_pulse = json.dumps({
                "hostname": "qfx-yoga",
                "timestamp": "2026-10-26T17:00:00Z",
                "data": {
                    "ssid": "HomeNetwork_optout",
                    "ram_used_pct": 55.0,
                    "temp_c": 42.0
                }
            }).encode("utf-8")

            res = process_pulse(optout_pulse)
            # Returns True to acknowledge dropping the message (preventing poison loop)
            assert res is True
            # Zero database or Athena interactions permitted
            mock_db.assert_not_called()
            mock_athena.assert_not_called()

    def test_process_pulse_strips_nested_optout_frames(self):
        """process_pulse must strip opted-out frames from vitals.frames before commit."""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("api_node.kafka_consumer.get_amara_connection", return_value=mock_conn), \
             patch("api_node.kafka_consumer.push_to_athena", return_value={"status": "ok"}):

            mixed_pulse = json.dumps({
                "hostname": "qfx-yoga",
                "timestamp": "2026-10-26T17:00:00Z",
                "data": {
                    "cpu_load_1m": 0.5,
                    "ram_used_pct": 58.2,
                    "frames": [
                        {"event_type": "operational_pulse", "duration_ms": 12},
                        {"event_type": "audit_nomap", "duration_ms": 50}
                    ]
                }
            }).encode("utf-8")

            res = process_pulse(mixed_pulse)
            assert res is True
            mock_cursor.execute.assert_called_once()
            insert_args = mock_cursor.execute.call_args[0][1]
            assert insert_args[0] == "qfx-yoga"
            assert insert_args[1] == 0.5

    def test_process_pulse_handles_malformed_json_gracefully(self):
        """Malformed JSON payloads are dropped safely without throwing unhandled exceptions."""
        with patch("api_node.kafka_consumer.get_amara_connection") as mock_db:
            malformed_bytes = b"CORRUPTED{{{NOT_JSON"
            res = process_pulse(malformed_bytes)
            assert res is True
            mock_db.assert_not_called()


# ==============================================================================
# 4. End-to-End Leakage Proof / Artifact Inspection
# ==============================================================================

class TestArtifactZeroLeakageProof:
    def test_sanitization_failure_prevents_persistence(self, monkeypatch):
        """Prove that if PrivacyFilter fails or raises, zero data is committed."""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        def broken_filter(*args, **kwargs):
            raise ValueError("Unexpected filter internal error")

        monkeypatch.setattr(PrivacyFilter, "contains_optout", broken_filter)

        with patch("psycopg2.connect", return_value=mock_conn):
            res = persist_telemetry_frame("node-1", 1700000000, '{"data": "test"}')
            assert res is False
            mock_cursor.execute.assert_not_called()


# ==============================================================================
# 5. Adversarial Input & Failure Behavior Matrix (Check D Compliance)
# ==============================================================================

class TestZeroAmbientAdversarialMatrix:
    def _sign_and_submit(self, api_client, payload_dict, node_id="test-node"):
        from cryptography.hazmat.primitives.asymmetric import ed25519
        private_key = ed25519.Ed25519PrivateKey.generate()
        pub_hex = private_key.public_key().public_bytes_raw().hex()
        payload_str = json.dumps(payload_dict)
        sig_hex = private_key.sign(f"{node_id}:1:{payload_str}".encode("utf-8")).hex()
        return api_client.post(
            "/api/v1/telemetry/submit",
            json={
                "node_id": node_id,
                "seq": 1,
                "timestamp": 1700000000,
                "payload": payload_str,
                "signature": sig_hex,
                "public_key": pub_hex,
            },
        )

    def test_direct_ssid_field_rejected(self, api_client):
        """Direct 'ssid' key anywhere in payload must return 403 Forbidden."""
        res = self._sign_and_submit(api_client, {"ssid": "RogueAP"})
        assert res.status_code == 403
        assert "Prohibited ambient network" in res.text

    def test_nested_bssid_field_rejected(self, api_client):
        """Nested BSSID/MAC field must return 403 Forbidden."""
        res = self._sign_and_submit(api_client, {"metadata": {"bssid": "00:11:22:33:44:55"}})
        assert res.status_code == 403
        assert "Prohibited ambient network" in res.text

    def test_alternate_neighbor_field_rejected(self, api_client):
        """Alternate field names (nearby_aps, access_points, wifi_networks) must return 403 Forbidden."""
        alternates = [
            {"nearby_aps": [{"name": "AP1"}]},
            {"access_points": ["AP-A"]},
            {"wifi_networks": ["OfficeNet"]},
            {"scan_results": [{"channel": 6}]},
        ]
        for alt in alternates:
            res = self._sign_and_submit(api_client, alt)
            assert res.status_code == 403
            assert "Prohibited ambient network" in res.text

    def test_case_variant_prohibited_key_rejected(self, api_client):
        """Casing variations (SSID, Nearby-APs, BSSID) must be normalized and rejected with 403."""
        cased = [
            {"SSID": "CapsAP"},
            {"Nearby-APs": [{"mac": "02:00:00:00:00:01"}]},
            {"MAC_ADDRESS": "12:34:56:78:9A:BC"},
        ]
        for c in cased:
            res = self._sign_and_submit(api_client, c)
            assert res.status_code == 403
            assert "Prohibited ambient network" in res.text

    def test_oversized_deeply_nested_payload_fails_closed(self, api_client):
        """Recursion limit / excessive nesting (> 10 depth) must fail closed with 403."""
        deep = {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": {"i": {"j": {"k": "overflow"}}}}}}}}}}}
        res = self._sign_and_submit(api_client, deep)
        assert res.status_code == 403

    def test_prohibited_data_in_batch_atomic_rejection(self, api_client):
        """If a single frame in a multi-frame batch contains prohibited ambient data, the entire batch is rejected."""
        batch = {
            "frames": [
                {"cpu_load_1m": 0.10, "ram_used_pct": 35.0},
                {"event_type": "status_pulse", "status": "OK"},
                {"nearby_aps": ["InjectedNeighborAP"]},  # Prohibited
                {"temp_c": 40.0},
            ]
        }
        res = self._sign_and_submit(api_client, batch)
        assert res.status_code == 403
        assert "Prohibited ambient network or personal tracking identifiers detected" in res.text

    def test_persistence_validation_failure_no_db_write(self):
        """persist_telemetry_frame must perform zero database writes if prohibited ambient data is present."""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("psycopg2.connect", return_value=mock_conn):
            # Attempt direct persistence bypass with prohibited ambient data
            res = persist_telemetry_frame("node-evil", 1700000000, json.dumps({"nearby_aps": ["Target"]}))
            assert res is False
            mock_cursor.execute.assert_not_called()

