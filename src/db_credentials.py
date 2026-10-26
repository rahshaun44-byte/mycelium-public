# src/db_credentials.py
"""
QuantumFlex Role-Scoped PostgreSQL Connection Factory.
Separates append-only ingestion (qf_writer) from read-only verification (qf_verifier).
"""

from __future__ import annotations

import enum
import os
from pathlib import Path
from typing import Dict

import psycopg2
from psycopg2.extensions import connection as PgConnection


class DatabaseRole(str, enum.Enum):
    WRITER = "WRITER"      # Strictly INSERT-only (qf_writer)
    VERIFIER = "VERIFIER"  # Strictly SELECT-only (qf_verifier)


DEFAULT_ENV_PATH = Path.home() / ".config" / "quantumflex" / "db_roles.env"


def _load_env_file(path: Path = DEFAULT_ENV_PATH) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.is_file():
        return values
    # Fail closed if file permissions are world/group readable (anything wider than 0600)
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        raise PermissionError(
            f"[QF-DB-ACL] Insecure permissions ({oct(mode)}) on {path}; expected 0o600"
        )
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip()
    return values


def resolve_role_credentials(
    role: DatabaseRole,
    dbname: str = "telemetry",
    env_path: Path = DEFAULT_ENV_PATH,
) -> Dict[str, object]:
    """
    Resolves strictly separated credentials for WRITER or VERIFIER.
    Refuses to fall back to superuser or allow writer/verifier cross-assignment.
    """
    if not isinstance(role, DatabaseRole):
        raise ValueError(f"Invalid DatabaseRole: {role!r}")

    file_env = _load_env_file(env_path)

    def _get(key: str, default: str = "") -> str:
        return os.environ.get(key) or file_env.get(key, default)

    host = _get("QF_DB_HOST", os.environ.get("DB_HOST", "127.0.0.1"))
    port = int(_get("QF_DB_PORT", os.environ.get("DB_PORT", "5432")))

    if role == DatabaseRole.WRITER:
        user = _get("QF_WRITER_DB_USER", "qf_writer")
        password = _get("QF_WRITER_DB_PASS", "")
    else:
        user = _get("QF_VERIFIER_DB_USER", "qf_verifier")
        password = _get("QF_VERIFIER_DB_PASS", "")

    # Fail closed if someone configures superuser or admin logins
    forbidden_admins = {"postgres", "root", "admin", "rocky", "amara_admin", "amara_matrix_admin"}
    if user.lower() in forbidden_admins:
        raise PermissionError(
            f"[QF-DB-ACL] Privileged user '{user}' is forbidden for role {role.value}"
        )

    writer_user = _get("QF_WRITER_DB_USER", "qf_writer")
    verifier_user = _get("QF_VERIFIER_DB_USER", "qf_verifier")
    if writer_user == verifier_user:
        raise PermissionError(
            f"[QF-DB-ACL] Writer and Verifier roles must not share username '{writer_user}'"
        )

    if not password:
        raise PermissionError(
            f"[QF-DB-ACL] Missing password for {role.value} ({user}). "
            "Run scripts/apply_db_acl_separation.sh or set QF_WRITER_DB_PASS / QF_VERIFIER_DB_PASS."
        )

    return {
        "host": host,
        "port": port,
        "dbname": dbname,
        "user": user,
        "password": password,
        "connect_timeout": 3,
    }


def open_role_connection(
    role: DatabaseRole,
    dbname: str = "telemetry",
    env_path: Path = DEFAULT_ENV_PATH,
) -> PgConnection:
    """Opens a PostgreSQL connection bound to the specified least-privilege role."""
    conn_kwargs = resolve_role_credentials(role=role, dbname=dbname, env_path=env_path)
    conn = psycopg2.connect(**conn_kwargs)
    if role == DatabaseRole.VERIFIER:
        conn.set_session(readonly=True)
    return conn
