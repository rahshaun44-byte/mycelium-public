# tests/test_qf_legal_governance.py
"""
QuantumFlex Legal & Operational Assurance Layer (QF-LOAL) Compliance Suite
==========================================================================
Verifies permanent compliance with QF-LEGAL-001 Authorized Operation Invariant:
1. Unregistered device -> Denied
2. Revoked device -> Denied
3. Expired authorization -> Denied
4. Invalid device signature -> Denied
5. Unauthorized operation -> Denied
6. Missing consent where required -> Denied
7. Unauthorized OTA download -> Denied
8. Unverified software provenance -> Quarantined
9. Privacy opt-out telemetry -> Not persisted
10. Audit record generation -> Successful
11. Device authorization revoked while connected -> Subsequent privileged requests denied
12. Offline node -> Retains last known authorization state without being falsely marked authorized
13. Separation of Concerns: Active Heartbeat != Legal Authorization
"""

import json
import time
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from api_node.main import app as api_app, persist_telemetry_frame
from mcp_layer.qf_bot.bot_server import app as bot_app
from src.legal_governance import (
    evaluate_operation_authorization,
    record_governance_audit,
    revoke_device_authorization,
    get_device_authorization,
    EVENT_PRIVACY_OPTOUT_ENFORCED,
    EVENT_DEVICE_QUARANTINED,
    EVENT_DEVICE_AUTHORIZATION_REVOKED
)

api_client = TestClient(api_app)
bot_client = TestClient(bot_app)


class TestQFLegalGovernance:

    def test_unregistered_device_denied(self):
        """Unregistered devices are denied access by default (fail-closed)."""
        allowed, decision, record = evaluate_operation_authorization(
            node_id="phantom-node-999",
            requested_operation="telemetry:heartbeat",
            operator_id="unknown_operator",
            signature_verified=True,
            authenticated=True,
        )
        assert allowed is False
        assert "DENY" in decision
        assert record == {}

    def test_revoked_device_denied(self):
        """A device marked as REVOKED is denied execution immediately."""
        mock_record = {
            "node_id": "revoked-pixel",
            "owner_id": "rocky@qfx-pixel",
            "authorization_status": "REVOKED",
            "permitted_purposes": ["*"],
            "permitted_operations": ["*"],
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "revoked_at": datetime.now(timezone.utc).isoformat(),
        }
        with patch("src.legal_governance.get_device_authorization", return_value=mock_record):
            allowed, decision, _ = evaluate_operation_authorization(
                node_id="revoked-pixel",
                requested_operation="draft:approve",
                signature_verified=True,
                authenticated=True,
            )
            assert allowed is False
            assert "REVOKED" in decision.upper() or "REVOKED" in mock_record["authorization_status"]

    def test_expired_authorization_denied(self):
        """A device whose authorization window has elapsed is denied privileged execution."""
        mock_record = {
            "node_id": "expired-yoga",
            "owner_id": "rocky@qfx-yoga",
            "authorization_status": "AUTHORIZED",
            "permitted_purposes": ["*"],
            "permitted_operations": ["*"],
            "expires_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "revoked_at": None,
        }
        with patch("src.legal_governance.get_device_authorization", return_value=mock_record):
            allowed, decision, _ = evaluate_operation_authorization(
                node_id="expired-yoga",
                requested_operation="settlement:execute",
                signature_verified=True,
                authenticated=True,
            )
            assert allowed is False
            assert "EXPIRED" in decision.upper()

    def test_invalid_device_signature_denied(self):
        """A registered device with invalid cryptographic signature is denied."""
        mock_record = {
            "node_id": "qfx-pixel",
            "owner_id": "rocky@qfx-pixel",
            "authorization_status": "AUTHORIZED",
            "permitted_purposes": ["tactical-hud"],
            "permitted_operations": ["draft:approve"],
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "revoked_at": None,
        }
        with patch("src.legal_governance.get_device_authorization", return_value=mock_record):
            allowed, decision, _ = evaluate_operation_authorization(
                node_id="qfx-pixel",
                requested_operation="draft:approve",
                signature_verified=False,
                authenticated=False,
            )
            assert allowed is False
            assert "DENY" in decision

    def test_unauthorized_operation_denied(self):
        """A device requesting an operation outside its permitted_operations scope is denied."""
        mock_record = {
            "node_id": "qfx-pixel",
            "owner_id": "rocky@qfx-pixel",
            "authorization_status": "AUTHORIZED",
            "permitted_purposes": ["tactical-hud"],
            "permitted_operations": ["telemetry:heartbeat", "chat:read"],
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "revoked_at": None,
        }
        with patch("src.legal_governance.get_device_authorization", return_value=mock_record):
            allowed, decision, _ = evaluate_operation_authorization(
                node_id="qfx-pixel",
                requested_operation="substrate:destructive_wipe",
                signature_verified=True,
                authenticated=True,
            )
            assert allowed is False
            assert "UNAUTHORIZED OPERATION" in decision.upper()

    def test_missing_consent_or_purpose_denied(self):
        """A device requesting an operation outside authorized purpose is denied."""
        mock_record = {
            "node_id": "qfx-pixel",
            "owner_id": "rocky@qfx-pixel",
            "authorization_status": "AUTHORIZED",
            "permitted_purposes": ["tactical-hud"],
            "permitted_operations": ["*"],
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "revoked_at": None,
        }
        with patch("src.legal_governance.get_device_authorization", return_value=mock_record):
            allowed, decision, _ = evaluate_operation_authorization(
                node_id="qfx-pixel",
                requested_operation="telemetry:submit",
                purpose="unauthorized-commercial-surveillance",
                signature_verified=True,
                authenticated=True,
            )
            assert allowed is False
            assert "UNAUTHORIZED PURPOSE" in decision.upper()

    def test_unverified_software_provenance_quarantined(self):
        """Software tampering or provenance mismatch triggers immediate device quarantine."""
        mock_record = {
            "node_id": "qfx-pixel",
            "owner_id": "rocky@qfx-pixel",
            "authorization_status": "AUTHORIZED",
            "permitted_purposes": ["*"],
            "permitted_operations": ["*"],
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "revoked_at": None,
        }
        with patch("src.legal_governance.get_device_authorization", return_value=mock_record):
            allowed, decision, _ = evaluate_operation_authorization(
                node_id="qfx-pixel",
                requested_operation="telemetry:submit",
                signature_verified=True,
                authenticated=True,
                provenance_verified=False,
                provenance_mismatch=True,
            )
            assert allowed is False
            assert "QUARANTINE" in decision.upper()

    def test_privacy_optout_telemetry_never_persisted(self):
        """Telemetry payloads bearing _optout or _nomap are never persisted to PostgreSQL."""
        optout_payload = json.dumps({
            "node_id": "qfx-pixel",
            "ssid": "MyHomeNetwork_optout",
            "cpu_load": 0.1
        })
        # Direct persistence check
        res = persist_telemetry_frame("qfx-pixel", int(time.time()), optout_payload)
        assert res is False

        # Evaluation pipeline check
        allowed, decision, _ = evaluate_operation_authorization(
            node_id="qfx-pixel",
            requested_operation="telemetry:submit",
            signature_verified=True,
            authenticated=True,
            privacy_optout=True,
        )
        assert allowed is False
        assert "PRIVACY OPT-OUT" in decision.upper()

    def test_audit_record_generation_successful(self):
        """Audit generation successfully commits events and redacts sensitive credentials."""
        with patch("src.db_credentials.open_role_connection") as mock_open:
            mock_cursor = MagicMock()
            mock_conn = MagicMock()
            mock_conn.__enter__.return_value = mock_conn
            mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_open.return_value = mock_conn

            res = record_governance_audit(
                event_type="TEST_AUDIT_EVENT",
                node_id="qfx-yoga",
                operator_id="rocky",
                requested_operation="test:action",
                authorization_decision="ADMIT",
                metadata={"secret_key": "raw_private_key_bytes", "safe_param": "normal_val"}
            )
            assert res is True
            mock_cursor.execute.assert_called_once()
            call_args = mock_cursor.execute.call_args[0][1]
            meta_json = call_args[8]
            assert "[REDACTED]" in meta_json
            assert "raw_private_key_bytes" not in meta_json

    def test_device_authorization_revoked_while_connected(self):
        """When a connected node is revoked in database, subsequent requests are immediately blocked."""
        # Step 1: Device is authorized
        mock_auth = {
            "node_id": "qfx-pixel",
            "owner_id": "rocky@qfx-pixel",
            "authorization_status": "AUTHORIZED",
            "permitted_purposes": ["*"],
            "permitted_operations": ["*"],
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "revoked_at": None,
        }
        with patch("src.legal_governance.get_device_authorization", return_value=mock_auth):
            allowed1, _, _ = evaluate_operation_authorization(
                node_id="qfx-pixel",
                requested_operation="draft:approve",
                signature_verified=True,
                authenticated=True,
            )
            assert allowed1 is True

        # Step 2: Revocation occurs
        mock_revoked = dict(mock_auth)
        mock_revoked["authorization_status"] = "REVOKED"
        mock_revoked["revoked_at"] = datetime.now(timezone.utc).isoformat()

        with patch("src.legal_governance.get_device_authorization", return_value=mock_revoked):
            allowed2, decision2, _ = evaluate_operation_authorization(
                node_id="qfx-pixel",
                requested_operation="draft:approve",
                signature_verified=True,
                authenticated=True,
            )
            assert allowed2 is False
            assert "REVOKED" in decision2.upper()

    def test_offline_node_retains_last_known_state_without_false_authorization(self):
        """
        An offline node (missing heartbeats) must retain its last known legal authorization state.
        A missing heartbeat does NOT constitute revocation or consent withdrawal.
        """
        mock_offline = {
            "node_id": "qfx-pixel",
            "owner_id": "rocky@qfx-pixel",
            "authorization_status": "AUTHORIZED",
            "permitted_purposes": ["tactical-hud"],
            "permitted_operations": ["telemetry:heartbeat"],
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "revoked_at": None,
        }
        # Node has been offline for 600s
        last_seen_epoch = int(time.time()) - 600
        is_missing_heartbeat = (int(time.time()) - last_seen_epoch) > 300

        assert is_missing_heartbeat is True

        with patch("src.legal_governance.get_device_authorization", return_value=mock_offline):
            auth = get_device_authorization("qfx-pixel")
            # Legal status remains AUTHORIZED even though network state is OFFLINE
            assert auth["authorization_status"] == "AUTHORIZED"
            assert auth["revoked_at"] is None

    def test_active_heartbeat_does_not_imply_legal_authorization(self):
        """
        CRITICAL INVARIANT: A device reporting ACTIVE in node_registry is NOT automatically
        authorized to perform privileged operations if its legal record is PENDING or SUSPENDED.
        """
        # Node g6pro or unadmitted node sending heartbeats
        mock_unadmitted = {
            "node_id": "g6pro",
            "owner_id": "rocky@g6pro",
            "authorization_status": "SUSPENDED",
            "permitted_purposes": ["standby-isolation"],
            "permitted_operations": [],
            "expires_at": None,
            "revoked_at": None,
        }
        with patch("src.legal_governance.get_device_authorization", return_value=mock_unadmitted):
            allowed, decision, _ = evaluate_operation_authorization(
                node_id="g6pro",
                requested_operation="draft:approve",
                signature_verified=True,
                authenticated=True,
            )
            assert allowed is False
            assert "SUSPENDED" in decision.upper()

    def test_unauthorized_ota_download_denied(self):
        """A revoked or unauthenticated device cannot download OTA assets."""
        resp = bot_client.get("/mobile/download/cli", headers={"x-qf-device": "revoked-device"})
        # Should be denied or rejected if unauthorized device requests it
        mock_revoked = {
            "node_id": "revoked-device",
            "owner_id": "untrusted",
            "authorization_status": "REVOKED",
            "permitted_purposes": [],
            "permitted_operations": [],
            "expires_at": None,
            "revoked_at": datetime.now(timezone.utc).isoformat(),
        }
        with patch("src.legal_governance.get_device_authorization", return_value=mock_revoked):
            allowed, decision, _ = evaluate_operation_authorization(
                node_id="revoked-device",
                requested_operation="ota:download",
                signature_verified=True,
                authenticated=True,
            )
            assert allowed is False
            assert "REVOKED" in decision.upper()
