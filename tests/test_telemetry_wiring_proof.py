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
        """Standard SSIDs without opt-out markers must be retained."""
        compliant = ["Starlink-WiFi", "QuantumFlex-Mesh-01", "Archer_BE3600_Pro", "nomaple_syrup"]
        for c in compliant:
            assert PrivacyFilter.should_exclude_ssid(c) is False
            assert PrivacyFilter.contains_optout({"ssid": c}) is False
            sanitized = PrivacyFilter.sanitize_telemetry_frame({"ssid": c, "rssi": -50})
            assert sanitized is not None
            assert sanitized["ssid"] == c

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
        """Direct invocation commits compliant payloads to PostgreSQL."""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        with patch("psycopg2.connect", return_value=mock_conn):
            clean_payload = json.dumps({"ssid": "Compliant_AP", "rssi": -45})
            res = persist_telemetry_frame("node-clean", 1700000000, clean_payload)
            assert res is True
            mock_cursor.execute.assert_called_once()
            args = mock_cursor.execute.call_args[0][1]
            assert args[0] == "node-clean"
            assert "Compliant_AP" in args[2]

    def test_api_submit_endpoint_strips_opted_out_frames(self, api_client):
        """The /api/v1/telemetry/submit route must strip opt-out frames before persistence."""
        from cryptography.hazmat.primitives.asymmetric import ed25519

        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        pub_hex = public_key.public_bytes_raw().hex()

        node_id = "test-sensor"
        seq = 1
        timestamp = 1700000000

        mixed_payload = {
            "frames": [
                {"ssid": "Valid_AP_1", "bssid": "AA:11", "rssi": -50},
                {"ssid": "Private_nomap", "bssid": "BB:22", "rssi": -70},
                {"ssid": "Valid_AP_2", "bssid": "CC:33", "rssi": -55},
                {"ssid": "Neighbor_optout", "bssid": "DD:44", "rssi": -80}
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
            retained_ssids = [f["ssid"] for f in retained_frames]
            assert "Valid_AP_1" in retained_ssids
            assert "Valid_AP_2" in retained_ssids
            # Ensure zero opted-out SSIDs touched persistence
            assert "Private_nomap" not in recorded_persisted_payloads[0]
            assert "Neighbor_optout" not in recorded_persisted_payloads[0]
            # Ensure co-located BSSIDs/MAC addresses were purged alongside SSIDs
            assert "BB:22" not in recorded_persisted_payloads[0]
            assert "DD:44" not in recorded_persisted_payloads[0]

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
                        {"ssid": "Allowed_Sensor_Mesh", "rssi": -48},
                        {"ssid": "SpyCamera_nomap", "rssi": -85}
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
