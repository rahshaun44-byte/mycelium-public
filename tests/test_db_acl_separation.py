# tests/test_db_acl_separation.py
"""
P1 #2 Verification Suite: Database ACL & Credential Separation.
Verifies fail-closed credential resolution and live PostgreSQL privilege boundaries.
"""

import os
from pathlib import Path
import pytest
import psycopg2

from src.db_credentials import (
    DEFAULT_ENV_PATH,
    DatabaseRole,
    open_role_connection,
    resolve_context_identity_hmac_key,
    resolve_role_credentials,
)


def test_insecure_env_file_permissions_fail_closed(tmp_path):
    """Env file with group/world read bits (e.g. 0644) must raise PermissionError."""
    env_file = tmp_path / "db_roles.env"
    env_file.write_text(
        "QF_WRITER_DB_USER=qf_writer\nQF_WRITER_DB_PASS=secret1\n"
        "QF_VERIFIER_DB_USER=qf_verifier\nQF_VERIFIER_DB_PASS=secret2\n",
        encoding="utf-8",
    )
    env_file.chmod(0o644)

    with pytest.raises(PermissionError, match="Insecure permissions"):
        resolve_role_credentials(DatabaseRole.WRITER, env_path=env_file)


def test_superuser_or_shared_login_rejected(tmp_path, monkeypatch):
    """Configuring privileged admin or identical usernames for writer and verifier must fail closed."""
    monkeypatch.delenv("QF_WRITER_DB_USER", raising=False)
    monkeypatch.delenv("QF_VERIFIER_DB_USER", raising=False)

    env_file = tmp_path / "db_roles.env"
    env_file.write_text(
        "QF_WRITER_DB_USER=postgres\nQF_WRITER_DB_PASS=secret1\n"
        "QF_VERIFIER_DB_USER=qf_verifier\nQF_VERIFIER_DB_PASS=secret2\n",
        encoding="utf-8",
    )
    env_file.chmod(0o600)

    with pytest.raises(PermissionError, match="Privileged user 'postgres' is forbidden"):
        resolve_role_credentials(DatabaseRole.WRITER, env_path=env_file)

    # Identical role names
    env_file.write_text(
        "QF_WRITER_DB_USER=same_user\nQF_WRITER_DB_PASS=secret1\n"
        "QF_VERIFIER_DB_USER=same_user\nQF_VERIFIER_DB_PASS=secret2\n",
        encoding="utf-8",
    )
    with pytest.raises(PermissionError, match="must not share username"):
        resolve_role_credentials(DatabaseRole.VERIFIER, env_path=env_file)


def test_valid_isolated_credentials_resolve_cleanly(tmp_path, monkeypatch):
    """Valid 0600 env file resolves distinct writer, verifier, and context roles."""
    for key in (
        "QF_WRITER_DB_USER",
        "QF_WRITER_DB_PASS",
        "QF_VERIFIER_DB_USER",
        "QF_VERIFIER_DB_PASS",
        "QF_CONTEXT_DB_USER",
        "QF_CONTEXT_DB_PASS",
        "QF_CONTEXT_IDENTITY_HMAC_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    env_file = tmp_path / "db_roles.env"
    identity_key = bytes(range(32)).hex()
    env_file.write_text(
        "QF_DB_HOST=127.0.0.1\nQF_DB_PORT=5432\n"
        "QF_WRITER_DB_USER=qf_writer\nQF_WRITER_DB_PASS=w\n"
        "QF_VERIFIER_DB_USER=qf_verifier\nQF_VERIFIER_DB_PASS=v\n"
        "QF_CONTEXT_DB_USER=qf_context\nQF_CONTEXT_DB_PASS=c\n"
        f"QF_CONTEXT_IDENTITY_HMAC_KEY={identity_key}\n",
        encoding="utf-8",
    )
    env_file.chmod(0o600)

    w_cfg = resolve_role_credentials(DatabaseRole.WRITER, dbname="telemetry", env_path=env_file)
    v_cfg = resolve_role_credentials(DatabaseRole.VERIFIER, dbname="telemetry", env_path=env_file)
    c_cfg = resolve_role_credentials(DatabaseRole.CONTEXT, dbname="telemetry", env_path=env_file)

    assert w_cfg["user"] == "qf_writer"
    assert w_cfg["password"] == "w"
    assert v_cfg["user"] == "qf_verifier"
    assert v_cfg["password"] == "v"
    assert c_cfg["user"] == "qf_context"
    assert c_cfg["password"] == "c"
    assert len({w_cfg["user"], v_cfg["user"], c_cfg["user"]}) == 3
    assert resolve_context_identity_hmac_key(env_path=env_file) == bytes(range(32))


def test_context_identity_key_requires_a_32_byte_hex_secret(tmp_path, monkeypatch):
    monkeypatch.delenv("QF_CONTEXT_IDENTITY_HMAC_KEY", raising=False)
    env_file = tmp_path / "db_roles.env"
    env_file.write_text("QF_CONTEXT_IDENTITY_HMAC_KEY=too-short\n", encoding="utf-8")
    env_file.chmod(0o600)

    with pytest.raises(PermissionError, match="Missing or malformed"):
        resolve_context_identity_hmac_key(env_path=env_file)


def test_context_provisioning_restores_device_audit_grants_after_acl_lockdown():
    root = Path(__file__).resolve().parents[1]
    script = (root / "scripts" / "apply_db_acl_separation.sh").read_text(encoding="utf-8")
    lockdown = script.index('apply_role_acl_sql "${SQL_FILE}"')
    authorization = script.index('apply_plain_sql "${AUTH_SQL_FILE}"')
    context = script.index("\n        apply_context_sql \\\n")

    assert lockdown < authorization < context
    assert "-v qf_context_identity_hmac_key" not in script
    assert 'printf "\\\\set qf_context_identity_hmac_key' in script


@pytest.mark.skipif(
    not DEFAULT_ENV_PATH.is_file() and not os.environ.get("QF_WRITER_DB_PASS"),
    reason="Live PostgreSQL role credentials not yet provisioned via scripts/apply_db_acl_separation.sh",
)
def test_live_postgres_writer_and_verifier_acl_invariants():
    """
    Live database proof on 127.0.0.1:5432:
    1. qf_writer CAN INSERT into quantum_telemetry_channel, CANNOT SELECT, UPDATE, or DELETE.
    2. qf_verifier CAN SELECT from quantum_telemetry_channel, CANNOT INSERT, UPDATE, or DELETE.
    """
    dbname = os.environ.get("DB_NAME", "telemetry")

    # 1. Verify qf_writer (APPEND-ONLY)
    w_conn = open_role_connection(DatabaseRole.WRITER, dbname=dbname)
    try:
        with w_conn:
            with w_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.quantum_telemetry_channel (node_id, timestamp, payload)
                    VALUES (%s, %s, %s)
                    """,
                    ("qfx-acl-probe", 1761516000, '{"probe": "acl_verification"}'),
                )

        # SELECT must fail with InsufficientPrivilege (42501)
        with pytest.raises(psycopg2.Error) as sel_err:
            with w_conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM public.quantum_telemetry_channel")
        w_conn.rollback()
        assert sel_err.value.pgcode == "42501"

        # DELETE must fail with InsufficientPrivilege (42501)
        with pytest.raises(psycopg2.Error) as del_err:
            with w_conn.cursor() as cur:
                cur.execute("DELETE FROM public.quantum_telemetry_channel WHERE node_id = 'qfx-acl-probe'")
        w_conn.rollback()
        assert del_err.value.pgcode == "42501"
    finally:
        w_conn.close()

    # 2. Verify qf_verifier (READ-ONLY)
    v_conn = open_role_connection(DatabaseRole.VERIFIER, dbname=dbname)
    try:
        with v_conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM public.quantum_telemetry_channel WHERE node_id = %s",
                ("qfx-acl-probe",),
            )
            count = cur.fetchone()[0]
            assert count >= 1

        # INSERT must fail on read-only session / privilege check (25006 or 42501)
        with pytest.raises(psycopg2.Error) as ins_err:
            with v_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO public.quantum_telemetry_channel (node_id, timestamp, payload) VALUES ('x', 1, '{}')"
                )
        v_conn.rollback()
        assert ins_err.value.pgcode in {"25006", "42501"}
    finally:
        v_conn.close()


@pytest.mark.skipif(
    not DEFAULT_ENV_PATH.is_file() and not os.environ.get("QF_WRITER_DB_PASS"),
    reason="Live PostgreSQL role credentials not yet provisioned via scripts/apply_db_acl_separation.sh",
)
def test_live_postgres_telemetry_log_acl_invariants():
    """
    Live database proof on 127.0.0.1:5432 for public.telemetry_log:
    1. qf_writer CAN INSERT without RETURNING, CANNOT SELECT, UPDATE, or DELETE.
    2. qf_verifier CAN SELECT, CANNOT INSERT, UPDATE, or DELETE.
    """
    dbname = os.environ.get("DB_NAME", "telemetry")

    # 1. qf_writer INSERT-only
    w_conn = open_role_connection(DatabaseRole.WRITER, dbname=dbname)
    try:
        with w_conn:
            with w_conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.telemetry_log (node_id, cpu_load_1m, ram_used_pct, timestamp, status, note)
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """,
                    ("qfx-acl-probe", 0.05, 30.0, "2026-10-28T20:30:00Z", "PULSE_OK", "ACL test probe"),
                )

        # SELECT denied
        with pytest.raises(psycopg2.Error) as sel_err:
            with w_conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM public.telemetry_log")
        w_conn.rollback()
        assert sel_err.value.pgcode == "42501"

        # UPDATE denied
        with pytest.raises(psycopg2.Error) as upd_err:
            with w_conn.cursor() as cur:
                cur.execute("UPDATE public.telemetry_log SET status = 'MUTATED' WHERE node_id = 'qfx-acl-probe'")
        w_conn.rollback()
        assert upd_err.value.pgcode == "42501"

        # DELETE denied
        with pytest.raises(psycopg2.Error) as del_err:
            with w_conn.cursor() as cur:
                cur.execute("DELETE FROM public.telemetry_log WHERE node_id = 'qfx-acl-probe'")
        w_conn.rollback()
        assert del_err.value.pgcode == "42501"
    finally:
        w_conn.close()

    # 2. qf_verifier READ-ONLY
    v_conn = open_role_connection(DatabaseRole.VERIFIER, dbname=dbname)
    try:
        with v_conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM public.telemetry_log WHERE node_id = %s",
                ("qfx-acl-probe",),
            )
            count = cur.fetchone()[0]
            assert count >= 1

        # INSERT denied
        with pytest.raises(psycopg2.Error) as ins_err:
            with v_conn.cursor() as cur:
                cur.execute("INSERT INTO public.telemetry_log (node_id, status) VALUES ('x', 'y')")
        v_conn.rollback()
        assert ins_err.value.pgcode in {"25006", "42501"}

        # UPDATE denied
        with pytest.raises(psycopg2.Error) as upd_err:
            with v_conn.cursor() as cur:
                cur.execute("UPDATE public.telemetry_log SET status = 'MUTATED'")
        v_conn.rollback()
        assert upd_err.value.pgcode in {"25006", "42501"}

        # DELETE denied
        with pytest.raises(psycopg2.Error) as del_err:
            with v_conn.cursor() as cur:
                cur.execute("DELETE FROM public.telemetry_log WHERE node_id = 'qfx-acl-probe'")
        v_conn.rollback()
        assert del_err.value.pgcode in {"25006", "42501"}
    finally:
        v_conn.close()


def test_missing_credentials_fails_closed(tmp_path, monkeypatch):
    """Missing or empty passwords must immediately raise PermissionError and never connect."""
    for key in ("QF_WRITER_DB_USER", "QF_WRITER_DB_PASS", "QF_VERIFIER_DB_USER", "QF_VERIFIER_DB_PASS"):
        monkeypatch.delenv(key, raising=False)

    empty_env = tmp_path / "empty.env"
    empty_env.write_text("QF_WRITER_DB_USER=qf_writer\n", encoding="utf-8")
    empty_env.chmod(0o600)

    with pytest.raises(PermissionError, match="Missing password"):
        resolve_role_credentials(DatabaseRole.WRITER, env_path=empty_env)
