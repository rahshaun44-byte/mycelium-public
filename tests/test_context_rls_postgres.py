"""PostgreSQL integration tests for signed owner identity and context RLS."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
import uuid

import psycopg2
import pytest


def _owner_claim(key: bytes, owner_id: str) -> tuple[str, int, str, str]:
    expires_at = int(time.time()) + 60
    nonce = secrets.token_hex(16)
    payload = f"{owner_id}\0{expires_at}\0{nonce}".encode("utf-8")
    signature = hmac.new(key, payload, hashlib.sha256).hexdigest()
    return owner_id, expires_at, nonce, signature


def _bind_owner(cursor, key: bytes, owner_id: str) -> tuple[str, int, str, str]:
    claim = _owner_claim(key, owner_id)
    cursor.execute(
        "SELECT qf_private.set_context_identity(%s, %s, %s, %s)",
        claim,
    )
    return claim


@pytest.mark.integration
def test_context_rls_rejects_forged_guc_and_isolates_owners():
    dsn = os.environ.get("QF_CONTEXT_RLS_TEST_DSN")
    key_hex = os.environ.get("QF_CONTEXT_IDENTITY_HMAC_KEY", "")
    if not dsn:
        pytest.skip("set QF_CONTEXT_RLS_TEST_DSN to an isolated qf_context database")
    if len(key_hex) != 64:
        pytest.fail("QF_CONTEXT_IDENTITY_HMAC_KEY must contain a 32-byte hex key")

    key = bytes.fromhex(key_hex)
    owner_a = f"rls-test-a-{uuid.uuid4().hex}"
    owner_b = f"rls-test-b-{uuid.uuid4().hex}"
    conversation_id = uuid.uuid4()
    conn = psycopg2.connect(dsn)
    with conn.cursor() as cursor:
        cursor.execute("SELECT session_user")
        role = cursor.fetchone()[0]
    if role != "qf_context":
        conn.close()
        pytest.fail("QF_CONTEXT_RLS_TEST_DSN must connect as the qf_context role")
    try:
        with conn.cursor() as cursor:
            owner_a_claim = _bind_owner(cursor, key, owner_a)
            cursor.execute(
                """INSERT INTO public.qf_context_conversations
                     (conversation_id, owner_id, created_by_device)
                   VALUES (%s, %s, 'rls-integration-test')""",
                (str(conversation_id), owner_a),
            )
        conn.commit()

        with conn.cursor() as cursor:
            with pytest.raises(psycopg2.Error) as replayed_claim:
                cursor.execute(
                    "SELECT qf_private.set_context_identity(%s, %s, %s, %s)",
                    owner_a_claim,
                )
            assert replayed_claim.value.pgcode == "28000"
        conn.rollback()

        with conn.cursor() as cursor:
            forged_claim = list(_owner_claim(key, owner_a))
            forged_claim[3] = "00" * 32
            with pytest.raises(psycopg2.Error) as forged_signature:
                cursor.execute(
                    "SELECT qf_private.set_context_identity(%s, %s, %s, %s)",
                    forged_claim,
                )
            assert forged_signature.value.pgcode == "28000"
        conn.rollback()

        with conn.cursor() as cursor:
            _bind_owner(cursor, key, owner_b)
            cursor.execute(
                "SELECT count(*) FROM public.qf_context_conversations WHERE conversation_id = %s",
                (str(conversation_id),),
            )
            assert cursor.fetchone()[0] == 0
        conn.commit()

        with conn.cursor() as cursor:
            _bind_owner(cursor, key, owner_b)
            with pytest.raises(psycopg2.Error) as denied_insert:
                cursor.execute(
                    """INSERT INTO public.qf_context_conversations
                         (conversation_id, owner_id, created_by_device)
                       VALUES (%s, %s, 'rls-integration-test')""",
                    (str(uuid.uuid4()), owner_a),
                )
            assert denied_insert.value.pgcode == "42501"
        conn.rollback()

        with conn.cursor() as cursor:
            cursor.execute("SELECT set_config('qf.owner_id', %s, true)", (owner_a,))
            cursor.execute(
                "SELECT count(*) FROM public.qf_context_conversations WHERE conversation_id = %s",
                (str(conversation_id),),
            )
            assert cursor.fetchone()[0] == 0
        conn.commit()
    finally:
        try:
            conn.rollback()
            with conn.cursor() as cursor:
                _bind_owner(cursor, key, owner_a)
                cursor.execute(
                    "DELETE FROM public.qf_context_conversations WHERE conversation_id = %s",
                    (str(conversation_id),),
                )
            conn.commit()
        finally:
            conn.close()
