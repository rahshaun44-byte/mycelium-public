"""Authentication and owner-scope checks for QF-Bot conversation routes."""

from __future__ import annotations

import base64
import secrets
import time
from pathlib import Path

from fastapi.testclient import TestClient
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from mcp_layer.qf_bot import bot_server, device_auth


def _authorized_policy(owner_id: str, operations: set[str]):
    def authorize(device_id, operation, **_kwargs):
        if operation not in operations:
            return False, "DENY: Unauthorized operation", {}
        return True, "ALLOW", {"owner_id": owner_id}

    return authorize


def test_history_rejects_unsigned_request(monkeypatch):
    monkeypatch.setattr(bot_server.device_auth, "verify", lambda *_args: None)
    response = TestClient(bot_server.app).get("/api/history")
    assert response.status_code == 401
    assert "signed device request" in response.json()["detail"]


def test_history_requires_chat_read_permission(monkeypatch):
    monkeypatch.setattr(bot_server.device_auth, "verify", lambda *_args: "qfx-pixel")
    monkeypatch.setattr(
        bot_server,
        "evaluate_operation_authorization",
        _authorized_policy("owner-1", {"chat:write"}),
    )
    response = TestClient(bot_server.app).get("/api/history")
    assert response.status_code == 403
    assert "chat:read" in response.json()["detail"]


def test_history_is_limited_to_authorized_owner(monkeypatch):
    requested = []

    class Store:
        def get_messages(self, owner_id, conversation_id, device_id):
            requested.append((owner_id, conversation_id, device_id))
            return [{"content": "owner one"}]

    monkeypatch.setattr(bot_server.device_auth, "verify", lambda *_args: "qfx-pixel")
    monkeypatch.setattr(
        bot_server,
        "evaluate_operation_authorization",
        _authorized_policy("owner-1", {"chat:read"}),
    )
    monkeypatch.setattr(bot_server, "record_governance_audit", lambda **_kwargs: True)
    monkeypatch.setattr(bot_server, "ContextStore", Store)

    response = TestClient(bot_server.app).get("/api/history?conversation_id=conversation-1")

    assert response.status_code == 200
    assert response.json()["messages"] == [{"content": "owner one"}]
    assert requested == [("owner-1", "conversation-1", "qfx-pixel")]


def test_conversation_access_grant_canonicalizes_device_id(monkeypatch):
    grants = []

    class Store:
        def grant_device_access(self, owner_id, conversation_id, actor_id, device_id, permissions):
            grants.append((owner_id, conversation_id, actor_id, device_id, permissions))

    monkeypatch.setattr(bot_server.device_auth, "verify", lambda *_args: "yoga-1")
    monkeypatch.setattr(
        bot_server,
        "evaluate_operation_authorization",
        _authorized_policy("owner-1", {"chat:write"}),
    )
    monkeypatch.setattr(bot_server, "record_governance_audit", lambda **_kwargs: True)
    monkeypatch.setattr(bot_server, "ContextStore", Store)

    response = TestClient(bot_server.app).post(
        "/api/conversations/conversation-1/access",
        json={"device_id": "pixel-11-pro", "permissions": ["READ", "APPEND"]},
    )

    assert response.status_code == 200
    assert grants == [
        ("owner-1", "conversation-1", "yoga-1", "qfx-pixel", ["READ", "APPEND"])
    ]


def test_chat_requires_chat_write_before_processing(monkeypatch):
    processed = []
    monkeypatch.setattr(bot_server.device_auth, "verify", lambda *_args: "qfx-pixel")
    monkeypatch.setattr(
        bot_server,
        "evaluate_operation_authorization",
        _authorized_policy("owner-1", {"chat:read"}),
    )
    monkeypatch.setattr(
        bot_server.orchestrator,
        "handle_message",
        lambda *args, **kwargs: processed.append((args, kwargs)),
    )

    response = TestClient(bot_server.app).post("/api/chat", json={"message": "continue"})

    assert response.status_code == 403
    assert processed == []


def test_chat_passes_owner_identity_after_chat_write_authorization(monkeypatch):
    observed = []
    saved = []

    class Store:
        def latest_conversation_id(self, owner_id, device_id):
            return None

        def start_conversation(self, owner_id, device_id, content, classification, project_id):
            saved.append(("start", owner_id, device_id, content))
            return "conversation-1", "message-1"

        def append_message(
            self, owner_id, conversation_id, sender_type, sender_id, content, classification,
            principal_id,
        ):
            saved.append((sender_type, owner_id, conversation_id, content))

    monkeypatch.setattr(bot_server.device_auth, "verify", lambda *_args: "pixel-11-pro")
    monkeypatch.setattr(
        bot_server,
        "evaluate_operation_authorization",
        _authorized_policy("owner-1", {"chat:write"}),
    )
    monkeypatch.setattr(bot_server, "record_governance_audit", lambda **_kwargs: True)

    async def handle_message(message, target_bot=None, conversation_context=""):
        observed.append((message, target_bot, conversation_context))
        return {"response": "continued"}

    monkeypatch.setattr(bot_server, "ContextStore", Store)
    monkeypatch.setattr(bot_server.orchestrator, "handle_message", handle_message)
    response = TestClient(bot_server.app).post(
        "/api/chat",
        json={"message": "continue", "target_bot": "athena"},
    )

    assert response.status_code == 200
    assert response.json()["response"] == "continued"
    assert response.json()["conversation_id"] == "conversation-1"
    assert observed == [("continue", "athena", "")]
    assert saved == [
        ("start", "owner-1", "qfx-pixel", "continue"),
        ("AGENT", "owner-1", "conversation-1", "continued"),
    ]


def test_chat_resumes_owner_latest_conversation(monkeypatch):
    observed = []
    saved = []

    class Store:
        def latest_conversation_id(self, owner_id, device_id):
            assert owner_id == "owner-1"
            assert device_id == "qfx-pixel"
            return "conversation-existing"

        def get_messages(self, owner_id, conversation_id, device_id):
            assert (owner_id, conversation_id) == ("owner-1", "conversation-existing")
            assert device_id == "qfx-pixel"
            return [{"sender_type": "USER", "content": "remember the migration plan"}]

        def append_message(
            self, owner_id, conversation_id, sender_type, sender_id, content, classification,
            principal_id,
        ):
            saved.append((sender_type, conversation_id, content))

    monkeypatch.setattr(bot_server.device_auth, "verify", lambda *_args: "qfx-pixel")
    monkeypatch.setattr(
        bot_server,
        "evaluate_operation_authorization",
        _authorized_policy("owner-1", {"chat:write"}),
    )
    monkeypatch.setattr(bot_server, "record_governance_audit", lambda **_kwargs: True)
    monkeypatch.setattr(bot_server, "ContextStore", Store)

    async def handle_message(message, target_bot=None, conversation_context=""):
        observed.append(conversation_context)
        return {"response": "resumed"}

    monkeypatch.setattr(bot_server.orchestrator, "handle_message", handle_message)
    response = TestClient(bot_server.app).post("/api/chat", json={"message": "continue"})

    assert response.status_code == 200
    assert response.json()["conversation_id"] == "conversation-existing"
    assert "remember the migration plan" in observed[0]
    assert saved == [
        ("USER", "conversation-existing", "continue"),
        ("AGENT", "conversation-existing", "resumed"),
    ]


def test_chat_hardstop_requires_separate_operation_scope(monkeypatch):
    operations = []

    def authorize(_device, operation, **_kwargs):
        operations.append(operation)
        if operation == "chat:write":
            return True, "ALLOW", {"owner_id": "owner-1"}
        return False, "DENY: Unauthorized operation", {}

    monkeypatch.setattr(bot_server.device_auth, "verify", lambda *_args: "qfx-pixel")
    monkeypatch.setattr(bot_server, "evaluate_operation_authorization", authorize)
    monkeypatch.setattr(
        bot_server.orchestrator,
        "handle_message",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("must not dispatch")),
    )

    response = TestClient(bot_server.app).post("/api/chat", json={"message": "/hardstop"})

    assert response.status_code == 403
    assert operations == ["system:hardstop"]


def test_chat_fails_closed_when_authorization_audit_is_unavailable(monkeypatch):
    monkeypatch.setattr(bot_server.device_auth, "verify", lambda *_args: "qfx-pixel")
    monkeypatch.setattr(
        bot_server,
        "evaluate_operation_authorization",
        _authorized_policy("owner-1", {"chat:write"}),
    )
    monkeypatch.setattr(bot_server, "record_governance_audit", lambda **_kwargs: False)

    response = TestClient(bot_server.app).post("/api/chat", json={"message": "continue"})

    assert response.status_code == 503
    assert "audit service is unavailable" in response.json()["detail"]


def test_bootstrap_reports_authenticated_and_authorized_separately(monkeypatch):
    monkeypatch.setattr(bot_server.device_auth, "verify", lambda *_args: "pixel-11-pro")
    monkeypatch.setattr(
        bot_server,
        "get_device_authorization",
        lambda device_id: {
            "authorization_status": "AUTHORIZED",
            "revoked_at": None,
            "expires_at": "2099-01-01T00:00:00+00:00",
        } if device_id == "qfx-pixel" else None,
    )

    response = TestClient(bot_server.app).get("/mobile/bootstrap")

    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert data["authorized"] is True
    assert data["authentication_method"] == "signed-device-request"
    assert data["device_id"] == "qfx-pixel"


def test_qfx_pixel_alias_verifies_against_pixel_11_pro_key(tmp_path, monkeypatch):
    keys_dir = tmp_path / "devices"
    keys_dir.mkdir(mode=0o700)
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    (keys_dir / "pixel-11-pro.pem").write_bytes(public_key)
    (keys_dir / "pixel-11-pro.pem").chmod(0o600)
    monkeypatch.setenv("QF_DEVICE_KEYS_DIR", str(keys_dir))

    method = "GET"
    path = "/api/history"
    timestamp = str(int(time.time()))
    nonce = secrets.token_urlsafe(24)
    signature = private_key.sign(
        device_auth.canonical_message(method, path, timestamp, nonce, b""),
        ec.ECDSA(hashes.SHA256()),
    )
    headers = {
        "x-qf-device": "qfx-pixel",
        "x-qf-timestamp": timestamp,
        "x-qf-nonce": nonce,
        "x-qf-signature": base64.b64encode(signature).decode("ascii"),
    }

    assert device_auth.verify(method, path, headers, b"") == "qfx-pixel"
