import uuid
import hashlib
import hmac
import re
import time
from pathlib import Path

import pytest

from mcp_layer.qf_bot import context_store


class _Cursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        self.statements.append((query, params))

    def fetchone(self):
        return next(self.rows, None)

    def fetchall(self):
        return []


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.closed = False
        self.rolled_back = False
        self.committed = False

    def cursor(self):
        return self._cursor

    def close(self):
        self.closed = True

    def rollback(self):
        self.rolled_back = True

    def commit(self):
        self.committed = True


def test_unknown_or_unshared_conversation_is_not_reported_as_empty(monkeypatch):
    cursor = _Cursor([None])
    connection = _Connection(cursor)
    monkeypatch.setattr(context_store, "_connection", lambda _owner: connection)
    conversation_id = str(uuid.uuid4())

    with pytest.raises(context_store.ConversationNotFound):
        context_store.ContextStore().get_messages("owner-1", conversation_id, "qfx-pixel")

    query, params = cursor.statements[0]
    assert "qf_context_access" in query
    assert "a.principal_id = %s" in query
    assert params == (uuid.UUID(conversation_id), "qfx-pixel")
    assert len(cursor.statements) == 1
    assert connection.closed


def test_access_grant_requires_creator_device(monkeypatch):
    cursor = _Cursor([None])
    connection = _Connection(cursor)
    monkeypatch.setattr(context_store, "_connection", lambda _owner: connection)

    with pytest.raises(context_store.ConversationNotFound):
        context_store.ContextStore().grant_device_access(
            "owner-1", str(uuid.uuid4()), "pixel-device", "yoga-device", ["READ"]
        )

    assert "created_by_device = %s" in cursor.statements[0][0]
    assert cursor.statements[0][1][2] == "pixel-device"
    assert connection.rolled_back
    assert connection.closed


def test_access_grant_rejects_unknown_permissions_before_database_access(monkeypatch):
    monkeypatch.setattr(
        context_store,
        "_connection",
        lambda _owner: pytest.fail("invalid grants must not open a database connection"),
    )

    with pytest.raises(context_store.InvalidAccessGrant):
        context_store.ContextStore().grant_device_access(
            "owner-1", str(uuid.uuid4()), "yoga-device", "pixel-device", ["OWNER"]
        )


def test_context_provisioning_is_owner_bound_and_non_destructive():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "scripts" / "sql" / "005_qf_context_engine.sql").read_text(
        encoding="utf-8"
    )
    message_table = migration.split("CREATE TABLE IF NOT EXISTS public.qf_context_messages", 1)[1]
    message_table = message_table.split(");", 1)[0]

    assert "content_sha256" not in message_table
    assert "DROP COLUMN" not in migration
    assert "'DELETE'" in migration
    assert "qf_private.current_context_owner()" in migration
    assert "current_setting('qf.owner_id'" not in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
    assert "UPDATE public.qf_device_authorization" not in migration

    installer = (root / "scripts" / "apply_db_acl_separation.sh").read_text(
        encoding="utf-8"
    )
    assert "006_drop_context_content_digest.sql" not in installer
    digest_cleanup = (root / "scripts" / "sql" / "006_drop_context_content_digest.sql").read_text(
        encoding="utf-8"
    )
    assert "DROP COLUMN IF EXISTS content_sha256" in digest_cleanup


def test_context_connection_uses_signed_database_identity(monkeypatch):
    cursor = _Cursor([])
    connection = _Connection(cursor)
    key = bytes(range(32))
    monkeypatch.setattr(
        context_store, "open_role_connection", lambda *_args, **_kwargs: connection
    )
    monkeypatch.setattr(
        context_store, "resolve_context_identity_hmac_key", lambda: key
    )

    assert context_store._connection("owner-1") is connection
    query, params = cursor.statements[0]
    assert query == "SELECT qf_private.set_context_identity(%s, %s, %s, %s)"
    owner_id, expires_at, nonce, signature = params
    assert owner_id == "owner-1"
    assert expires_at >= time.time() + 59
    assert re.fullmatch(r"[0-9a-f]{32}", nonce)
    payload = f"{owner_id}\0{expires_at}\0{nonce}".encode("utf-8")
    assert hmac.compare_digest(
        signature, hmac.new(key, payload, hashlib.sha256).hexdigest()
    )


def test_context_connection_fails_closed_without_signing_key(monkeypatch):
    monkeypatch.setattr(
        context_store,
        "open_role_connection",
        lambda *_args, **_kwargs: pytest.fail("database must not connect without an HMAC key"),
    )
    monkeypatch.setattr(
        context_store,
        "resolve_context_identity_hmac_key",
        lambda: (_ for _ in ()).throw(PermissionError("missing key")),
    )

    with pytest.raises(
        context_store.ContextStoreError, match="context identity signing configuration"
    ):
        context_store._connection("owner-1")
