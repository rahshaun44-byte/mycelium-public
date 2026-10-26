-- scripts/sql/002_enforce_writer_verifier_acl.sql
-- QuantumFlex P1 #2: Append-Only Writer (qf_writer) & Read-Only Verifier (qf_verifier) ACL Isolation

BEGIN;

-- 1. Ensure target ledger tables exist in schema public before locking down privileges
CREATE TABLE IF NOT EXISTS public.quantum_telemetry_channel (
    id BIGSERIAL PRIMARY KEY,
    node_id TEXT NOT NULL,
    timestamp BIGINT NOT NULL,
    payload TEXT NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS public.telemetry_log (
    id BIGSERIAL PRIMARY KEY,
    node_id TEXT NOT NULL,
    cpu_load_1m DOUBLE PRECISION,
    ram_used_pct DOUBLE PRECISION,
    timestamp BIGINT NOT NULL,
    status TEXT NOT NULL,
    note TEXT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- 2. Provision or update isolated login roles
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'qf_writer') THEN
        CREATE ROLE qf_writer WITH
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT
            NOREPLICATION
            NOBYPASSRLS
            CONNECTION LIMIT 32;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'qf_verifier') THEN
        CREATE ROLE qf_verifier WITH
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT
            NOREPLICATION
            NOBYPASSRLS
            CONNECTION LIMIT 32;
    END IF;
END
$$;

-- Apply passwords injected via psql -v variables
ALTER ROLE qf_writer WITH PASSWORD :qf_writer_password;
ALTER ROLE qf_verifier WITH PASSWORD :qf_verifier_password;

-- Force read-only transactions at the PostgreSQL session engine level for qf_verifier
ALTER ROLE qf_verifier SET default_transaction_read_only = on;
ALTER ROLE qf_writer SET statement_timeout = '5000ms';
ALTER ROLE qf_verifier SET statement_timeout = '10000ms';

-- 3. Strip all default and residual privileges from PUBLIC, qf_writer, and qf_verifier
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM PUBLIC, qf_writer, qf_verifier;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC, qf_writer, qf_verifier;
REVOKE CREATE ON SCHEMA public FROM PUBLIC, qf_writer, qf_verifier;

-- 4. Grant database CONNECT and schema USAGE
GRANT CONNECT ON DATABASE telemetry TO qf_writer, qf_verifier;
GRANT USAGE ON SCHEMA public TO qf_writer, qf_verifier;

-- 5. Grant STRICT APPEND-ONLY (INSERT only) to qf_writer
GRANT INSERT ON TABLE
    public.quantum_telemetry_channel,
    public.telemetry_log
TO qf_writer;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO qf_writer;

-- 6. Grant STRICT READ-ONLY (SELECT only) to qf_verifier
GRANT SELECT ON TABLE
    public.quantum_telemetry_channel,
    public.telemetry_log
TO qf_verifier;

-- 7. Defense-in-Depth: Immutable Ledger Trigger (blocks UPDATE/DELETE/TRUNCATE even by table owners)
CREATE OR REPLACE FUNCTION public.qf_reject_ledger_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '[QF-IMMUTABLE-LEDGER] Forbidden % operation on append-only table %.%',
        TG_OP, TG_TABLE_SCHEMA, TG_TABLE_NAME
        USING ERRCODE = '42501'; -- insufficient_privilege
END;
$$;

DROP TRIGGER IF EXISTS trg_immutable_quantum_telemetry_channel ON public.quantum_telemetry_channel;
CREATE TRIGGER trg_immutable_quantum_telemetry_channel
    BEFORE UPDATE OR DELETE OR TRUNCATE ON public.quantum_telemetry_channel
    FOR EACH STATEMENT
    EXECUTE FUNCTION public.qf_reject_ledger_mutation();

DROP TRIGGER IF EXISTS trg_immutable_telemetry_log ON public.telemetry_log;
CREATE TRIGGER trg_immutable_telemetry_log
    BEFORE UPDATE OR DELETE OR TRUNCATE ON public.telemetry_log
    FOR EACH STATEMENT
    EXECUTE FUNCTION public.qf_reject_ledger_mutation();

COMMIT;
