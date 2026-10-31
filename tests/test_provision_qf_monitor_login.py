"""Synthetic provisioning checks; no production credentials or service changes."""
from contextlib import contextmanager
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

import pytest


TOOL = Path(__file__).resolve().parents[1] / "tools/provision_qf_monitor_login.py"


def load_tool():
    assert TOOL.is_file(), "manual monitor login tool is not implemented"
    spec = importlib.util.spec_from_file_location("provision_qf_monitor_login", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tool():
    return load_tool()


class SyntheticBackend:
    """Only external systemd/SQL/TCP boundaries are replaced."""
    def __init__(self, failure=None):
        self.failure = failure
        self.login = False
        self.active = False
        self.sql = []
        self.reloads = 0
        self.stops = 0
        self.password = None

    def require_inactive(self):
        if self.active:
            raise RuntimeError("synthetic active unit")

    def admin(self, statement):
        self.sql.append(statement)
        if "NOLOGIN;" in statement:
            self.login = False
            return "MONITOR_LOGIN_DISABLED"
        if "LOGIN PASSWORD" in statement:
            self.login = True
            return "MONITOR_LOGIN_ENABLED"
        if self.failure == "preflight":
            raise RuntimeError("do not print synthetic-secret")
        return "MONITOR_ROLE_DORMANT"

    def verify_tcp(self, password):
        self.password = password
        assert self.login
        if self.failure == "tcp":
            raise RuntimeError("do not print " + password)
        return ("qf_monitor_writer", "qf_monitor_writer", "telemetry")

    def reload(self, paths):
        self.reloads += 1
        if self.failure == "reload":
            raise RuntimeError("do not print " + self.password)

    def stop(self):
        self.stops += 1
        self.active = False


def test_default_plan_never_probes_or_creates_credentials(tool, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(tool, "default_home", lambda: tmp_path)
    monkeypatch.setattr(tool, "Backend", lambda: pytest.fail("plan touched an external system"))
    monkeypatch.setattr(tool.secrets, "token_urlsafe", lambda *_: pytest.fail("plan generated a password"))
    assert tool.main([]) == 0
    assert list(tmp_path.iterdir()) == []
    assert "--apply" in capsys.readouterr().out


def test_success_uses_exclusive_private_files_and_same_restricted_identity(tool, tmp_path):
    parent = tmp_path / ".config/quantumflex"
    parent.mkdir(parents=True, mode=0o775)
    parent.chmod(0o775)
    untouched = parent / "other-service.env"
    untouched.write_text("SYNTHETIC=untouched\n")
    backend = SyntheticBackend()
    paths = tool.Paths.for_home(tmp_path)
    tool.provision(paths, backend, inherited_names=("PGPASSWORD", "SENTINEL_DB_PASSWORD"))
    assert parent.stat().st_mode & 0o777 == 0o700
    assert paths.profile.stat().st_mode & 0o777 == 0o600
    assert paths.dropin.stat().st_mode & 0o777 == 0o600
    assert untouched.read_text() == "SYNTHETIC=untouched\n"
    values = dict(line.split("=", 1) for line in paths.profile.read_text().splitlines() if "=" in line)
    assert values["DB_USER"] == values["GHOSTNODE_DB_USER"] == "qf_monitor_writer"
    assert values["DB_PASSWORD"] == values["GHOSTNODE_DB_PASSWORD"] == backend.password
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", backend.password)
    assert values["DB_HOST"] == "127.0.0.1"
    assert values["DB_PORT"] == "5432"
    assert values["DB_NAME"] == "telemetry"
    assert values["PYTHON_DOTENV_DISABLED"] == "1"
    assert backend.password not in "\n".join(backend.sql)
    assert "SCRAM-SHA-256$" in "\n".join(backend.sql)
    assert backend.login and not backend.active
    assert backend.reloads == 1 and backend.stops == 0


@pytest.mark.parametrize("target", ["profile", "dropin"])
def test_existing_artifact_refuses_without_rotation_or_overwrite(tool, tmp_path, target):
    paths = tool.Paths.for_home(tmp_path)
    existing = getattr(paths, target)
    existing.parent.mkdir(parents=True)
    existing.write_text("original synthetic value")
    backend = SyntheticBackend()
    with pytest.raises(tool.ExistingArtifactError):
        tool.provision(paths, backend)
    assert existing.read_text() == "original synthetic value"
    assert not backend.login and backend.sql == []
    assert not getattr(paths, "dropin" if target == "profile" else "profile").exists()


def test_active_unit_refuses_before_any_file_or_sql_change(tool, tmp_path):
    backend = SyntheticBackend()
    backend.active = True
    with pytest.raises(Exception):
        tool.provision(tool.Paths.for_home(tmp_path), backend)
    assert list(tmp_path.iterdir()) == []
    assert backend.sql == [] and backend.stops == 0


@pytest.mark.parametrize("failure", ["tcp", "reload"])
def test_failure_after_enrollment_disables_login_and_preserves_artifacts(tool, tmp_path, failure):
    paths = tool.Paths.for_home(tmp_path)
    backend = SyntheticBackend(failure)
    with pytest.raises(tool.EnrollmentFailed) as error:
        tool.provision(paths, backend)
    assert not backend.login and not backend.active
    assert backend.stops == 1
    assert paths.profile.is_file() and paths.dropin.is_file()
    assert error.value.login_disabled and error.value.service_stopped
    assert backend.password not in str(error.value)


def test_preflight_failure_creates_no_secret_or_partial_profile(tool, tmp_path):
    backend = SyntheticBackend("preflight")
    with pytest.raises(Exception):
        tool.provision(tool.Paths.for_home(tmp_path), backend)
    assert list(tmp_path.iterdir()) == []
    assert not backend.login


@pytest.mark.parametrize("unsafe", ["symlink", "git"])
def test_profile_cannot_escape_or_enter_a_git_checkout(tool, tmp_path, unsafe):
    home = tmp_path / "home"
    home.mkdir()
    if unsafe == "symlink":
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        (home / ".config").symlink_to(elsewhere, target_is_directory=True)
    else:
        (home / ".git").mkdir()
        (home / ".git/HEAD").write_text("ref: refs/heads/synthetic\n")
    with pytest.raises(tool.UnsafePathError):
        tool.provision(tool.Paths.for_home(home), SyntheticBackend())
    assert not (tmp_path / "elsewhere/quantumflex/qf-monitor.env").exists()


def test_dropin_resets_shared_files_and_removes_other_database_credentials(tool, tmp_path):
    dropin = tool.render_dropin(tool.Paths.for_home(tmp_path).profile,
                               ("CUSTOM_DB_PASSWORD", "PGPASSWORD", "GHOSTNODE_DB_PASSWORD"))
    # Interpret the environment directives as systemd does, including resets.
    files = ["/synthetic/shared.env"]
    explicit = {"PGUSER": "administrator"}
    removed = set()
    for line in dropin.splitlines():
        if line.startswith("EnvironmentFile="):
            value = line.split("=", 1)[1]
            files = files + [value.strip('"')] if value else []
        elif line.startswith("Environment="):
            value = line.split("=", 1)[1]
            if value:
                key, val = value.split("=", 1)
                explicit[key] = val
            else:
                explicit = {}
        elif line.startswith("UnsetEnvironment="):
            removed.update(line.split("=", 1)[1].split())
    assert files == [str(tool.Paths.for_home(tmp_path).profile)]
    assert explicit == {"PYTHONUNBUFFERED": "1"}
    assert {"PGPASSWORD", "PGSERVICE", "PGSERVICEFILE", "PGPASSFILE", "PGUSER",
            "DATABASE_URL", "SENTINEL_DB_PASSWORD", "CUSTOM_DB_PASSWORD"} <= removed
    assert not {"DB_USER", "DB_PASSWORD", "GHOSTNODE_DB_USER", "GHOSTNODE_DB_PASSWORD"} & removed


def test_actual_monitor_import_and_helper_cannot_load_dotenv_or_use_admin_identity(tool):
    password = "A" * 43
    values = dict(line.split("=", 1) for line in tool.render_profile(password).splitlines() if "=" in line)
    child = """
import dotenv.main
def forbidden(*args, **kwargs):
    raise AssertionError('dotenv opened a credential file')
dotenv.main.DotEnv = forbidden
import psycopg2
connections = []
psycopg2.connect = lambda **kwargs: connections.append(kwargs) or object()
import amara.qf_monitor as monitor
assert monitor.PG_CONFIG['user'] == 'qf_monitor_writer'
assert monitor.PG_CONFIG['password'] == 'A' * 43
from sentinel import invariant_gate
assert invariant_gate.get_db_connection(raise_on_error=True) is not None
assert connections[0]['user'] == 'qf_monitor_writer'
assert connections[0]['password'] == 'A' * 43
print('synthetic monitor credentials verified')
"""
    result = subprocess.run([sys.executable, "-c", child], env={"PATH": os.environ["PATH"], **values},
                            cwd=TOOL.parent.parent, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "synthetic monitor credentials verified"


def test_admin_transport_has_no_plaintext_password_or_verifier_in_argv(tool, monkeypatch):
    calls = []
    def capture(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, "MONITOR_LOGIN_ENABLED\n", "")
    monkeypatch.setattr(tool.subprocess, "run", capture)
    password = "A" * 43
    verifier = tool.scram_verifier(password)
    tool.Backend().admin(tool.enable_sql(verifier))
    argv, kwargs = calls[0]
    assert "amara-matrix" in argv and "rocky" in argv and "telemetry" in argv
    assert password not in " ".join(argv) and verifier not in " ".join(argv)
    assert password not in kwargs["input"] and verifier in kwargs["input"]
    assert "SET LOCAL log_statement = 'none'" in kwargs["input"]
    assert "SET LOCAL log_min_error_statement = 'panic'" in kwargs["input"]


def test_tcp_verification_refuses_trust_authentication(tool, monkeypatch):
    import psycopg2
    class Connection:
        def close(self):
            pass
    monkeypatch.setattr(psycopg2, "connect", lambda **kwargs: Connection())
    with pytest.raises(tool.PasswordAuthenticationError):
        tool.Backend().verify_tcp("A" * 43)


def test_tcp_verification_requires_wrong_password_denial_then_exact_identity(tool, monkeypatch):
    import psycopg2
    passwords = []
    class Connection:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def close(self):
            pass
        def cursor(self):
            return self
        def execute(self, statement):
            assert statement == "SELECT current_user, session_user, current_database()"
        def fetchone(self):
            return ("qf_monitor_writer", "qf_monitor_writer", "telemetry")
    def connect(**kwargs):
        passwords.append(kwargs["password"])
        if len(passwords) == 1:
            raise psycopg2.OperationalError('password authentication failed for user "qf_monitor_writer"')
        return Connection()
    monkeypatch.setattr(psycopg2, "connect", connect)
    assert tool.Backend().verify_tcp("A" * 43) == ("qf_monitor_writer", "qf_monitor_writer", "telemetry")
    assert len(passwords) == 2 and passwords[0] != passwords[1] == "A" * 43


def test_tcp_verification_does_not_treat_other_connect_failures_as_authentication_denial(tool, monkeypatch):
    import psycopg2
    def offline(**kwargs):
        raise psycopg2.OperationalError("connection refused")
    monkeypatch.setattr(psycopg2, "connect", offline)
    with pytest.raises(tool.PasswordAuthenticationError):
        tool.Backend().verify_tcp("A" * 43)


@contextmanager
def isolated_database():
    name = "qf-monitor-login-test-" + uuid.uuid4().hex[:12]
    subprocess.run(["podman", "run", "--pull=never", "--detach", "--rm", "--network=none",
                    "--name", name, "--tmpfs", "/var/lib/postgresql/data:rw",
                    "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "-e", "POSTGRES_DB=telemetry",
                    "docker.io/library/postgres:15-alpine"], capture_output=True, text=True, check=True)
    def sql(statement, check=True):
        result = subprocess.run(["podman", "exec", "-i", name, "psql", "-X", "-A", "-t",
                                 "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "telemetry"],
                                input=statement, capture_output=True, text=True)
        if check:
            assert result.returncode == 0, result.stderr
        return result
    try:
        for _ in range(60):
            if sql("SELECT 1", False).returncode == 0:
                break
            time.sleep(0.2)
        else:
            pytest.fail("isolated PostgreSQL did not become ready")
        sql("CREATE TABLE telemetry_log (id serial PRIMARY KEY, timestamp timestamptz DEFAULT now(), "
            "node_id varchar,cpu_usage numeric,ram_usage numeric,swap_usage numeric,disk_usage numeric); "
            "CREATE TABLE throttle_events (id serial PRIMARY KEY,timestamp timestamptz DEFAULT now(),event_type varchar,details text)")
        sql((TOOL.parent.parent / "scripts/sql/qf_monitor_role.sql").read_text())
        yield name, sql
    finally:
        subprocess.run(["podman", "rm", "--force", name], capture_output=True, text=True, check=True)


def _isolated_postgres_ready() -> bool:
    flag = os.environ.get("QF_MONITOR_LOGIN_ISOLATED_TESTS")
    if flag == "0":
        return False
    if flag == "1":
        return True
    try:
        res = subprocess.run(
            ["podman", "image", "exists", "docker.io/library/postgres:15-alpine"],
            capture_output=True,
            timeout=5,
        )
        return res.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


ISOLATED_POSTGRES_AVAILABLE = _isolated_postgres_ready()


@pytest.mark.skipif(not ISOLATED_POSTGRES_AVAILABLE, reason="cached docker.io/library/postgres:15-alpine podman image unavailable")
def test_scram_verifier_authenticates_over_isolated_container_tcp(tool):
    with isolated_database() as (name, sql):
        password = "A" * 43
        sql(tool.enable_sql(tool.scram_verifier(password)))
        hba = "local all all trust\nhost all all 127.0.0.1/32 scram-sha-256\n"
        subprocess.run(["podman", "exec", "-i", name, "sh", "-c", "cat > /var/lib/postgresql/data/pg_hba.conf"],
                       input=hba, text=True, capture_output=True, check=True)
        sql("SELECT pg_reload_conf()")
        # Synthetic password enters this isolated container through stdin only.
        script = "export PGPASSWORD='" + password + "'\nexec psql -X -A -t -h 127.0.0.1 " \
                 "-U qf_monitor_writer -d telemetry -c 'SELECT current_user,session_user,current_database()'\n"
        result = subprocess.run(["podman", "exec", "-i", name, "sh"], input=script,
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "qf_monitor_writer|qf_monitor_writer|telemetry"
        sql(tool.disable_sql())
        assert sql("SELECT rolcanlogin FROM pg_roles WHERE rolname='qf_monitor_writer'").stdout.strip() == "f"


@pytest.mark.skipif(not ISOLATED_POSTGRES_AVAILABLE, reason="cached docker.io/library/postgres:15-alpine podman image unavailable")
@pytest.mark.parametrize("unexpected", [
    "ALTER ROLE qf_monitor_writer LOGIN",
    "ALTER ROLE qf_monitor_writer SUPERUSER",
    "ALTER ROLE qf_monitor_writer INHERIT",
    "CREATE ROLE other_role; GRANT other_role TO qf_monitor_writer",
    "CREATE ROLE other_role; GRANT qf_monitor_writer TO other_role",
    "ALTER ROLE qf_monitor_writer PASSWORD 'synthetic-prior-enrollment'",
    "GRANT SELECT ON telemetry_log TO qf_monitor_writer",
])
def test_sql_guard_refuses_login_privilege_or_membership_drift(tool, unexpected):
    with isolated_database() as (_, sql):
        sql(unexpected)
        summary = "SELECT rolcanlogin,rolsuper,rolinherit,rolpassword IS NULL FROM pg_authid WHERE rolname='qf_monitor_writer'"
        before = sql(summary).stdout
        result = sql(tool.enable_sql(tool.scram_verifier("A" * 43)), False)
        assert result.returncode != 0
        assert sql(summary).stdout == before
