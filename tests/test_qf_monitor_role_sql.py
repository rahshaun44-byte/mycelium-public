"""Exercise the monitor migration in an isolated PostgreSQL 15 container.

No host mounts, published ports, production credentials or live database access.
Set QF_MONITOR_TEST_BASELINE=1 to reproduce the existing column mismatch.
"""
from pathlib import Path
from contextlib import contextmanager
import os
import subprocess
import time
import uuid

import pytest

MIGRATION = Path(__file__).resolve().parents[1] / "scripts/sql/qf_monitor_role.sql"
ROLE = "qf_monitor_writer"
TABLES = ("telemetry_log", "throttle_events", "sentinel_ledger", "invariant_audit_ledger",
          "task_queue", "memory_logs", "integrity_registry", "quantum_telemetry_channel")


@contextmanager
def isolated_database():
    name = "qf-monitor-role-test-" + uuid.uuid4().hex[:12]
    subprocess.run([
        "podman", "run", "--detach", "--rm", "--network=none", "--name", name,
        "--tmpfs", "/var/lib/postgresql/data:rw", "-e", "POSTGRES_HOST_AUTH_METHOD=trust",
        "-e", "POSTGRES_DB=telemetry", "docker.io/library/postgres:15-alpine",
    ], check=True, capture_output=True, text=True)

    def sql(statement, *, check=True):
        result = subprocess.run([
            "podman", "exec", "-i", name, "psql", "-X", "-A", "-t",
            "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "telemetry",
        ], input=statement, capture_output=True, text=True)
        if check and result.returncode:
            raise AssertionError(result.stderr)
        return result

    try:
        for _ in range(40):
            if sql("SELECT 1", check=False).returncode == 0:
                break
            time.sleep(0.25)
        else:
            pytest.fail("Isolated PostgreSQL did not become ready")
        sql("""
            CREATE ROLE existing_service LOGIN;
            CREATE TABLE telemetry_log (
              id serial PRIMARY KEY, timestamp timestamptz DEFAULT now(), node_id varchar,
              cpu_usage numeric, ram_usage numeric, swap_usage numeric, disk_usage numeric);
            CREATE TABLE throttle_events (
              id serial PRIMARY KEY, timestamp timestamptz DEFAULT now(), event_type varchar, details text);
            INSERT INTO telemetry_log(node_id) VALUES ('existing-row');
            INSERT INTO throttle_events(event_type) VALUES ('existing-row');
        """)
        for table in TABLES[2:]:
            sql(f"CREATE TABLE {table}(id serial PRIMARY KEY, payload text)")
        sql("GRANT SELECT ON telemetry_log TO existing_service")
        yield sql
    finally:
        subprocess.run(["podman", "rm", "--force", name], capture_output=True, text=True, check=True)


@pytest.fixture(scope="module")
def database():
    with isolated_database() as sql:
        if os.environ.get("QF_MONITOR_TEST_BASELINE") != "1":
            sql(MIGRATION.read_text())
        yield sql


def test_actual_monitor_insert_shapes_succeed(database):
    prefix = "" if os.environ.get("QF_MONITOR_TEST_BASELINE") == "1" else f"SET SESSION AUTHORIZATION {ROLE};"
    database(f"""BEGIN; {prefix}
        INSERT INTO public.telemetry_log
          (iowait_pct,ram_used_pct,swap_used_mb,cpu_load_1m,status,note)
          VALUES (1,40,0,0.3,'OPTIMAL','synthetic test');
        INSERT INTO public.throttle_events
          (trigger_metric,trigger_value,threshold,action,result)
          VALUES ('ram',90,85,'pause','synthetic test');
        ROLLBACK;
    """)


def test_existing_data_and_other_role_privileges_are_preserved(database):
    assert database("SELECT count(*) FROM telemetry_log").stdout.strip() == "1"
    assert database("SELECT count(*) FROM throttle_events").stdout.strip() == "1"
    assert database("SELECT has_table_privilege('existing_service','telemetry_log','SELECT')").stdout.strip() == "t"
    assert database("SELECT has_database_privilege('existing_service','telemetry','TEMP')").stdout.strip() == "t"


def test_role_is_dormant_unprivileged_and_has_no_memberships(database):
    assert database(f"""SELECT NOT(rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
       OR rolreplication OR rolbypassrls OR rolinherit) FROM pg_roles WHERE rolname='{ROLE}'""").stdout.strip() == "t"
    assert database(f"SELECT count(*) FROM pg_auth_members WHERE member='{ROLE}'::regrole OR roleid='{ROLE}'::regrole").stdout.strip() == "0"
    result = database(f"SET SESSION AUTHORIZATION {ROLE}; SELECT session_user=current_user AND current_user='{ROLE}'")
    assert result.stdout.strip().endswith("t")


@pytest.mark.parametrize("statement", [
    "SELECT * FROM public.telemetry_log LIMIT 0",
    "EXPLAIN UPDATE public.telemetry_log SET status='bad'",
    "EXPLAIN DELETE FROM public.telemetry_log",
    "TRUNCATE public.telemetry_log",
    "INSERT INTO public.telemetry_log(id) VALUES(123)",
    "INSERT INTO public.throttle_events(timestamp) VALUES(now())",
    "CREATE TABLE public.unwanted(id integer)",
    "CREATE TEMP TABLE unwanted(id integer)",
    "CREATE ROLE unwanted LOGIN",
    "SET ROLE existing_service",
    "SELECT setval('public.telemetry_log_id_seq',1)",
])
def test_forbidden_operations_are_denied(database, statement):
    result = database(f"SET SESSION AUTHORIZATION {ROLE}; BEGIN; {statement}; ROLLBACK;", check=False)
    assert result.returncode != 0
    assert "permission denied" in result.stderr


@pytest.mark.parametrize("table", TABLES[2:])
def test_unrelated_application_tables_are_denied(database, table):
    for statement in (f"SELECT * FROM public.{table} LIMIT 0",
                      f"EXPLAIN INSERT INTO public.{table}(payload) VALUES('test')"):
        result = database(f"SET SESSION AUTHORIZATION {ROLE}; BEGIN; {statement}; ROLLBACK;", check=False)
        assert result.returncode != 0
        assert "permission denied" in result.stderr


def test_reapplying_refuses_to_reconfigure_existing_role(database):
    result = database(MIGRATION.read_text(), check=False)
    assert result.returncode != 0
    assert "already exists" in result.stderr
    assert database(f"SELECT rolcanlogin FROM pg_roles WHERE rolname='{ROLE}'").stdout.strip() == "f"


@pytest.mark.parametrize("unexpected_grant", [
    "CREATE SEQUENCE public.unrelated_public_seq; GRANT USAGE ON SEQUENCE public.unrelated_public_seq TO PUBLIC",
    "CREATE TABLE public.unrelated_partitioned(part integer) PARTITION BY RANGE(part); GRANT SELECT ON public.unrelated_partitioned TO PUBLIC",
    "GRANT CREATE ON DATABASE telemetry TO PUBLIC",
])
def test_unexpected_public_privileges_abort_without_partial_changes(unexpected_grant):
    with isolated_database() as sql:
        sql(unexpected_grant)
        result = sql(MIGRATION.read_text(), check=False)
        assert result.returncode != 0
        assert "PUBLIC" in result.stderr
        assert sql(f"SELECT count(*) FROM pg_roles WHERE rolname='{ROLE}'").stdout.strip() == "0"
        assert sql("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='telemetry_log' AND column_name='iowait_pct'").stdout.strip() == "0"
