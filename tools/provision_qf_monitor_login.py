#!/usr/bin/env python3
"""Manually enroll the dormant monitor role and bind its stopped user unit.

Default: print a plan, without probing systemd/PostgreSQL or generating secrets.
Run --apply yourself with the repository venv. No start/restart, grants, data
writes, password rotation, .env reads, or overwrite of existing artifacts.
The generated credential is stored only in the private profile outside Git.
"""
from dataclasses import dataclass
import argparse
import base64
import hashlib
import hmac
import io
import os
from pathlib import Path
import pwd
import re
import secrets
import stat
import subprocess
import sys


ROLE = "qf_monitor_writer"
UNIT = "qf-monitor.service"
DEDICATED_KEYS = {"DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD",
                  "GHOSTNODE_DB_USER", "GHOSTNODE_DB_PASSWORD"}
OTHER_DATABASE_KEYS = {
    "DATABASE_URL", "DATABASE_URI", "DB_URL", "DB_URI", "DB_DSN", "DB_PASS",
    "DB_USERNAME", "DBPASS", "DBUSER", "DATABASE_PASSWORD", "DATABASE_USER",
    "PGUSER", "PGPASSWORD", "PGPASSFILE", "PGSERVICE", "PGSERVICEFILE",
    "PGSYSCONFDIR", "PGHOST", "PGHOSTADDR", "PGPORT", "PGDATABASE", "PGOPTIONS",
    "PGAPPNAME", "PGSSLMODE", "PGREQUIRESSL", "PGSSLCERT", "PGSSLKEY",
    "PGSSLROOTCERT", "PGSSLCRL", "PGSSLCRLDIR", "PGGSSENCMODE", "PGKRBSRVNAME",
    "PGCHANNELBINDING", "PGTARGETSESSIONATTRS", "PGCONNECT_TIMEOUT", "PGLOADBALANCEHOSTS",
    "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "POSTGRES_HOST",
    "POSTGRES_PORT", "SENTINEL_DB_USER", "SENTINEL_DB_PASSWORD", "PQC_DB_USER",
    "PQC_DB_PASSWORD", "PQC_DB_HOST", "PQC_DB_NAME", "QF_DB_USER", "QF_DB_PASSWORD",
}


class ProvisionError(RuntimeError):
    """Failures deliberately carry no external exception text or credential."""


class ExistingArtifactError(ProvisionError):
    pass


class UnsafePathError(ProvisionError):
    pass


class InactiveUnitError(ProvisionError):
    pass


class RolePreflightError(ProvisionError):
    pass


class PasswordAuthenticationError(ProvisionError):
    pass


class UnitConfigurationError(ProvisionError):
    pass


class DotenvGuardError(ProvisionError):
    pass


class EnrollmentFailed(ProvisionError):
    def __init__(self, error_type, login_disabled, service_stopped):
        super().__init__()
        self.error_type = error_type
        self.login_disabled = login_disabled
        self.service_stopped = service_stopped


@dataclass(frozen=True)
class Paths:
    profile: Path
    dropin: Path

    @classmethod
    def for_home(cls, home):
        home = Path(home)
        return cls(home / ".config/quantumflex/qf-monitor.env",
                   home / ".config/systemd/user/qf-monitor.service.d/90-dedicated-database.conf")


def default_home():
    # Ignore HOME/XDG_CONFIG_HOME overrides for the real provisioning destination.
    return Path(pwd.getpwuid(os.getuid()).pw_dir)


def database_variable(name):
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)) and (
        name in OTHER_DATABASE_KEYS or name in DEDICATED_KEYS or name.startswith("PG")
        or re.search(r"(?:^|_)(?:DB|DATABASE|POSTGRES|POSTGRESQL)(?:_|$)", name) is not None)


def scrub_process_environment():
    # Inspect names only: do not preserve, print or copy credential values.
    names = tuple(name for name in os.environ if database_variable(name))
    for name in names:
        os.environ.pop(name, None)
    return names


def render_profile(password):
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", password):
        raise ProvisionError()
    return ("# Dedicated qf-monitor credential. Keep this file private.\n"
            "PYTHON_DOTENV_DISABLED=1\nDB_HOST=127.0.0.1\nDB_PORT=5432\nDB_NAME=telemetry\n"
            f"DB_USER={ROLE}\nDB_PASSWORD={password}\n"
            f"GHOSTNODE_DB_USER={ROLE}\nGHOSTNODE_DB_PASSWORD={password}\n")


def render_dropin(profile, inherited_names=()):
    path = str(profile)
    if not profile.is_absolute() or any(ord(char) < 32 for char in path):
        raise UnsafePathError()
    path = path.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
    removed = OTHER_DATABASE_KEYS | {name for name in inherited_names if database_variable(name)}
    removed -= DEDICATED_KEYS
    return ("# Prepared by the manual monitor enrollment tool. No service start.\n[Service]\n"
            "Environment=\nPassEnvironment=\nEnvironmentFile=\nUnsetEnvironment=\n"
            "Environment=PYTHONUNBUFFERED=1\n"
            f'EnvironmentFile="{path}"\n'
            "UnsetEnvironment=" + " ".join(sorted(removed)) + "\n")


def validate_paths(paths):
    home = paths.profile.parent.parent.parent
    if any(os.path.lexists(target) for target in (paths.profile, paths.dropin)):
        raise ExistingArtifactError()
    for target in (paths.profile, paths.dropin):
        if not target.is_absolute():
            raise UnsafePathError()
        for ancestor in target.parents:
            marker = ancestor / ".git"
            # An empty sandbox protection directory is not a Git checkout.
            if marker.is_file() or os.path.lexists(marker / "HEAD"):
                raise UnsafePathError()
            if os.path.lexists(ancestor):
                metadata = ancestor.lstat()
                owner_safe = not ancestor.is_relative_to(home) or metadata.st_uid == os.getuid()
                if not stat.S_ISDIR(metadata.st_mode) or not owner_safe:
                    raise UnsafePathError()


def exclusive_write(path, content, *, private_parent=False):
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        metadata = os.fstat(directory)
        if metadata.st_uid != os.getuid():
            raise UnsafePathError()
        if private_parent:
            os.fchmod(directory, 0o700)
        descriptor = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directory)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(directory)
    finally:
        os.close(directory)


def require_dotenv_guard():
    from dotenv import load_dotenv
    name = "QF_MONITOR_DOTENV_PROBE_" + secrets.token_hex(8).upper()
    previous = os.environ.get("PYTHON_DOTENV_DISABLED")
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"
    try:
        if load_dotenv(stream=io.StringIO(name + "=blocked\n"), override=True) or name in os.environ:
            raise DotenvGuardError()
    finally:
        os.environ.pop(name, None)
        if previous is None:
            os.environ.pop("PYTHON_DOTENV_DISABLED", None)
        else:
            os.environ["PYTHON_DOTENV_DISABLED"] = previous


def scram_verifier(password):
    # psycopg2's encrypt_password requires a connection for SCRAM even with an
    # explicit algorithm. RFC5802/7677 derivation here is verified against PG15.
    # Generated passwords are ASCII only, so SASLprep cannot change them.
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", password):
        raise ProvisionError()
    salt = secrets.token_bytes(16)
    salted = hashlib.pbkdf2_hmac("sha256", password.encode("ascii"), salt, 4096)
    client = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
    stored = hashlib.sha256(client).digest()
    server = hmac.new(salted, b"Server Key", hashlib.sha256).digest()
    encoded = [base64.b64encode(value).decode("ascii") for value in (salt, stored, server)]
    return "SCRAM-SHA-256$4096:" + encoded[0] + "$" + encoded[1] + ":" + encoded[2]


ROLE_GUARD = """
DO $guard$
BEGIN
  IF current_database() <> 'telemetry' OR current_setting('is_superuser') <> 'on' THEN
    RAISE EXCEPTION 'Wrong enrollment administrator or database';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'qf_monitor_writer'
      AND NOT (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
               OR rolbypassrls OR rolinherit) AND rolconnlimit = 2)
     OR NOT EXISTS (SELECT FROM pg_authid WHERE rolname = 'qf_monitor_writer' AND rolpassword IS NULL)
     OR EXISTS (SELECT FROM pg_auth_members WHERE
         member = (SELECT oid FROM pg_roles WHERE rolname = 'qf_monitor_writer') OR
         roleid = (SELECT oid FROM pg_roles WHERE rolname = 'qf_monitor_writer')) THEN
    RAISE EXCEPTION 'Monitor role is not dormant and unprivileged';
  END IF;
  IF NOT has_database_privilege('qf_monitor_writer','telemetry','CONNECT')
      OR has_database_privilege('qf_monitor_writer','telemetry','CREATE,TEMP')
      OR NOT has_schema_privilege('qf_monitor_writer','public','USAGE')
      OR EXISTS (SELECT FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname <> 'information_schema'
          AND has_schema_privilege('qf_monitor_writer',oid,'CREATE')) THEN
    RAISE EXCEPTION 'Monitor database or schema privileges changed';
  END IF;
  IF EXISTS (SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
      WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND c.relkind IN ('r','p','v','m','f') AND
          has_table_privilege('qf_monitor_writer',c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'))
      OR (SELECT count(*) FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
          JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'
          AND a.attnum>0 AND NOT a.attisdropped AND
          ((c.relname='telemetry_log' AND a.attname IN
              ('iowait_pct','ram_used_pct','swap_used_mb','cpu_load_1m','status','note')) OR
           (c.relname='throttle_events' AND a.attname IN
              ('trigger_metric','trigger_value','threshold','action','result')))
          AND has_column_privilege('qf_monitor_writer',c.oid,a.attnum,'INSERT')) <> 11
      OR EXISTS (SELECT FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
          JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND c.relkind IN ('r','p','v','m','f') AND a.attnum>0 AND NOT a.attisdropped
          AND (has_column_privilege('qf_monitor_writer',c.oid,a.attnum,'SELECT,UPDATE,REFERENCES,INSERT WITH GRANT OPTION')
            OR (has_column_privilege('qf_monitor_writer',c.oid,a.attnum,'INSERT') AND NOT
              (n.nspname='public' AND
                ((c.relname='telemetry_log' AND a.attname IN
                    ('iowait_pct','ram_used_pct','swap_used_mb','cpu_load_1m','status','note')) OR
                 (c.relname='throttle_events' AND a.attname IN
                    ('trigger_metric','trigger_value','threshold','action','result'))))))) THEN
    RAISE EXCEPTION 'Monitor table or column privileges changed';
  END IF;
  IF (SELECT count(DISTINCT value) FROM unnest(ARRAY[
      pg_get_serial_sequence('public.telemetry_log','id'),
      pg_get_serial_sequence('public.throttle_events','id')]) value) <> 2
      OR EXISTS (SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
          WHERE c.relkind='S' AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND CASE WHEN c.oid IN (pg_get_serial_sequence('public.telemetry_log','id')::regclass,
                                 pg_get_serial_sequence('public.throttle_events','id')::regclass)
              THEN NOT has_sequence_privilege('qf_monitor_writer',c.oid,'USAGE') OR
                   has_sequence_privilege('qf_monitor_writer',c.oid,'SELECT,UPDATE,USAGE WITH GRANT OPTION')
              ELSE has_sequence_privilege('qf_monitor_writer',c.oid,'USAGE,SELECT,UPDATE') END)
      OR EXISTS (SELECT FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
          WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' AND p.prosecdef
          AND has_function_privilege('qf_monitor_writer',p.oid,'EXECUTE')) THEN
    RAISE EXCEPTION 'Monitor sequence or security definer privileges changed';
  END IF;
  IF EXISTS (SELECT FROM pg_settings WHERE name IN ('pgaudit.log','pgaudit.log_catalog')
             AND setting NOT IN ('none','off')) THEN
    RAISE EXCEPTION 'Independent statement auditing requires separate enrollment review';
  END IF;
END
$guard$;
"""


def preflight_sql():
    return ROLE_GUARD + "SELECT 'MONITOR_ROLE_DORMANT';\n"


def enable_sql(verifier):
    # Only a validated SCRAM verifier reaches SQL; no plaintext password is sent.
    if not re.fullmatch(r"SCRAM-SHA-256\$[0-9]+:[A-Za-z0-9+/=]+\$[A-Za-z0-9+/=]+:[A-Za-z0-9+/=]+", verifier):
        raise ProvisionError()
    return ("SET log_transaction_sample_rate = 0;\nBEGIN;\nSET LOCAL log_statement = 'none';\n"
            "SET LOCAL log_min_error_statement = 'panic';\n"
            "SET LOCAL log_min_duration_statement = -1;\n"
            "SET LOCAL log_min_duration_sample = -1;\n"
            "SET LOCAL log_statement_sample_rate = 0;\n"
            "SET LOCAL debug_print_parse = off;\nSET LOCAL debug_print_rewritten = off;\n"
            "SET LOCAL debug_print_plan = off;\n"
            "SET LOCAL statement_timeout = '10s';\n" + ROLE_GUARD +
            f"ALTER ROLE {ROLE} LOGIN PASSWORD '{verifier}';\n"
            "COMMIT;\nSELECT 'MONITOR_LOGIN_ENABLED';\n")


def disable_sql():
    return f"ALTER ROLE {ROLE} NOLOGIN;\nSELECT 'MONITOR_LOGIN_DISABLED';\n"


class Backend:
    def command(self, argv, *, input=None):
        result = subprocess.run(argv, input=input, capture_output=True, text=True, timeout=30)
        if result.returncode:
            # Do not propagate stderr/CalledProcessError: SQL can contain a verifier.
            raise ProvisionError()
        return result.stdout.strip()

    def properties(self, names):
        output = self.command(["systemctl", "--user", "show", UNIT, "--no-pager",
                               *["--property=" + name for name in names]])
        return dict(line.split("=", 1) for line in output.splitlines() if "=" in line)

    def require_inactive(self):
        values = self.properties(("ActiveState", "SubState", "LoadState"))
        if values != {"LoadState": "loaded", "ActiveState": "inactive", "SubState": "dead"}:
            raise InactiveUnitError()

    def manager_credential_names(self):
        # Secret values flow directly into a key-only filter, never into captured
        # output or this process. No .env file or systemd Environment is read.
        filter_code = ("import re,sys\nfor line in sys.stdin:\n"
                       " m=re.match(r'([A-Za-z_][A-Za-z0-9_]*)=',line)\n"
                       " if m: print(m.group(1))\n")
        with subprocess.Popen(["systemctl", "--user", "show-environment"],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as process:
            try:
                result = subprocess.run([sys.executable, "-c", filter_code], stdin=process.stdout,
                                        capture_output=True, text=True, timeout=15)
                process.stdout.close()
                status = process.wait(timeout=15)
            except BaseException:
                process.kill()
                raise
        if status or result.returncode:
            raise UnitConfigurationError()
        return tuple(name for name in result.stdout.splitlines() if database_variable(name))

    def admin(self, statement):
        return self.command(["podman", "exec", "-i", "amara-matrix", "env", "-i",
                             "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                             "psql", "-X", "--no-password", "-q", "-A", "-t",
                             "-v", "ON_ERROR_STOP=1", "-U", "rocky", "-d", "telemetry"], input=statement)

    def verify_tcp(self, password):
        import psycopg2
        options = dict(host="127.0.0.1", port=5432, dbname="telemetry", user=ROLE,
                       connect_timeout=5, application_name="qf-monitor-enrollment-check",
                       sslmode="disable", gssencmode="disable", passfile="/dev/null",
                       options="-c default_transaction_read_only=on -c statement_timeout=5000")
        wrong = secrets.token_urlsafe(32)
        while wrong == password:
            wrong = secrets.token_urlsafe(32)
        try:
            connection = psycopg2.connect(password=wrong, **options)
        except psycopg2.Error as error:
            # libpq connection errors often omit pgcode; use its specific auth
            # diagnostic as fallback, without displaying the exception text.
            if getattr(error, "pgcode", None) != "28P01" and not re.search(
                    r'password authentication failed for user ["\']qf_monitor_writer["\']', str(error)):
                raise PasswordAuthenticationError() from None
        else:
            connection.close()
            raise PasswordAuthenticationError()
        connection = psycopg2.connect(password=password, **options)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_user, session_user, current_database()")
                identity = cursor.fetchone()
            if identity != (ROLE, ROLE, "telemetry"):
                raise PasswordAuthenticationError()
            return identity
        finally:
            connection.close()

    def reload(self, paths):
        self.command(["systemctl", "--user", "daemon-reload"])
        values = self.properties(("EnvironmentFiles", "DropInPaths"))
        if values.get("EnvironmentFiles") != str(paths.profile) + " (ignore_errors=no)":
            raise UnitConfigurationError()
        if values.get("DropInPaths") != str(paths.dropin):
            raise UnitConfigurationError()
        self.require_inactive()

    def stop(self):
        self.command(["systemctl", "--user", "stop", UNIT])
        self.require_inactive()


def provision(paths, backend, inherited_names=()):
    validate_paths(paths)
    backend.require_inactive()
    if backend.admin(preflight_sql()) != "MONITOR_ROLE_DORMANT":
        raise RolePreflightError()
    require_dotenv_guard()
    password = secrets.token_urlsafe(32)
    verifier = scram_verifier(password)
    # Exclusive writes retain even partially prepared artifacts on every error.
    # Never retry/overwrite them or silently rotate an enrollment credential.
    exclusive_write(paths.profile, render_profile(password), private_parent=True)
    exclusive_write(paths.dropin, render_dropin(paths.profile, inherited_names))
    backend.require_inactive()
    try:
        # Treat an interrupted/ambiguous SQL completion as possibly enrolled.
        if backend.admin(enable_sql(verifier)) != "MONITOR_LOGIN_ENABLED":
            raise RolePreflightError()
        identity = backend.verify_tcp(password)
        if identity != (ROLE, ROLE, "telemetry"):
            raise PasswordAuthenticationError()
        backend.reload(paths)
        backend.require_inactive()
        return identity
    except BaseException as error:
        stopped = disabled = False
        try:
            backend.stop()
            stopped = True
        except BaseException:
            pass
        try:
            disabled = backend.admin(disable_sql()) == "MONITOR_LOGIN_DISABLED"
        except BaseException:
            pass
        raise EnrollmentFailed(type(error).__name__, disabled, stopped) from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="enroll and bind the stopped monitor; never start it")
    args = parser.parse_args(argv)
    paths = Paths.for_home(default_home())
    if not args.apply:
        print("Plan only. Run with --apply to enroll the dormant qf_monitor_writer role.")
        print("Require inactive qf-monitor.service and dormant unprivileged role with no memberships.")
        print("Create exclusive private profile: " + str(paths.profile))
        print("Create exclusive unit drop-in: " + str(paths.dropin))
        print("Verify password authentication and TCP identity, reload systemd, leave service inactive.")
        print("Any enrollment failure attempts NOLOGIN rollback and keeps partial artifacts for inspection.")
        return 0
    try:
        if os.getuid() == 0:
            raise ProvisionError()
        inherited = scrub_process_environment()
        backend = Backend()
        inherited += backend.manager_credential_names()
        identity = provision(paths, backend, inherited)
        print("TCP password authentication verified: " + identity[0] + "@" + identity[2])
        print("Private profile: " + str(paths.profile))
        print("Unit drop-in: " + str(paths.dropin))
        print("qf-monitor.service remains inactive. No start/restart was issued.")
        return 0
    except EnrollmentFailed as error:
        print("Enrollment failed: " + error.error_type, file=sys.stderr)
        print("NOLOGIN rollback confirmed: " + str(error.login_disabled).lower(), file=sys.stderr)
        print("Service stopped confirmed: " + str(error.service_stopped).lower(), file=sys.stderr)
        print("Prepared artifacts retained; do not rerun or overwrite them.", file=sys.stderr)
        return 1
    except BaseException as error:
        print("Provisioning refused/failed: " + type(error).__name__, file=sys.stderr)
        print("Any partial artifacts are retained; no rotation or overwrite is attempted.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
