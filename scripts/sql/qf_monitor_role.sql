-- PREPARED MIGRATION: run manually as the existing database administrator.
-- One transaction. Existing records/columns remain; the new role cannot log in.
-- Password enrollment, service configuration and restart are separate steps.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';

DO $preflight$
BEGIN
    IF current_database() <> 'telemetry' THEN
        RAISE EXCEPTION 'Wrong database: this migration requires telemetry';
    END IF;
    IF current_setting('is_superuser') <> 'on' THEN
        RAISE EXCEPTION 'Existing administrator required';
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'qf_monitor_writer') THEN
        RAISE EXCEPTION 'qf_monitor_writer already exists: inspect it instead of reconfiguring';
    END IF;
END
$preflight$;

LOCK TABLE public.telemetry_log, public.throttle_events IN ACCESS EXCLUSIVE MODE;

DO $schema_check$
DECLARE
    columns_present text[];
BEGIN
    SELECT array_agg(attname::text ORDER BY attname) INTO columns_present
      FROM pg_attribute WHERE attrelid = 'public.telemetry_log'::regclass
        AND attnum > 0 AND NOT attisdropped;
    IF columns_present IS DISTINCT FROM ARRAY[
        'cpu_usage','disk_usage','id','node_id','ram_usage','swap_usage','timestamp'] THEN
        RAISE EXCEPTION 'Unexpected telemetry_log columns: inspect before migration';
    END IF;
    SELECT array_agg(attname::text ORDER BY attname) INTO columns_present
      FROM pg_attribute WHERE attrelid = 'public.throttle_events'::regclass
        AND attnum > 0 AND NOT attisdropped;
    IF columns_present IS DISTINCT FROM ARRAY['details','event_type','id','timestamp'] THEN
        RAISE EXCEPTION 'Unexpected throttle_events columns: inspect before migration';
    END IF;
    IF EXISTS (SELECT FROM pg_class WHERE oid IN
        ('public.telemetry_log'::regclass,'public.throttle_events'::regclass)
        AND (relkind <> 'r' OR relrowsecurity)) THEN
        RAISE EXCEPTION 'Unexpected table type or row security';
    END IF;
    IF EXISTS (SELECT FROM pg_trigger WHERE tgrelid IN
        ('public.telemetry_log'::regclass,'public.throttle_events'::regclass)
        AND NOT tgisinternal) OR EXISTS (SELECT FROM pg_rewrite WHERE ev_class IN
        ('public.telemetry_log'::regclass,'public.throttle_events'::regclass)) THEN
        RAISE EXCEPTION 'Unexpected trigger/rule: inspect side effects';
    END IF;
    IF pg_get_serial_sequence('public.telemetry_log','id') IS NULL OR
       pg_get_serial_sequence('public.throttle_events','id') IS NULL THEN
        RAISE EXCEPTION 'Expected serial sequence missing';
    END IF;
    IF EXISTS (
        SELECT FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl,acldefault('r',c.relowner))) a
        WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND c.relkind IN ('r','p','v','m','f') AND a.grantee = 0
    ) OR EXISTS (
        SELECT FROM pg_attribute p JOIN pg_class c ON c.oid=p.attrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        CROSS JOIN LATERAL aclexplode(p.attacl) a
        WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema' AND a.grantee=0
    ) THEN
        RAISE EXCEPTION 'PUBLIC application table/column grants require separate review';
    END IF;
    IF EXISTS (
        SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        CROSS JOIN LATERAL aclexplode(COALESCE(c.relacl,acldefault('S',c.relowner))) a
        WHERE c.relkind='S' AND n.nspname !~ '^pg_'
          AND n.nspname <> 'information_schema' AND a.grantee=0
    ) THEN
        RAISE EXCEPTION 'PUBLIC application sequence grants require separate review';
    END IF;
    IF EXISTS (
        SELECT FROM pg_database d
        CROSS JOIN LATERAL aclexplode(COALESCE(d.datacl,acldefault('d',d.datdba))) a
        WHERE d.datname=current_database() AND a.grantee=0 AND a.privilege_type='CREATE'
    ) THEN
        RAISE EXCEPTION 'PUBLIC database CREATE requires separate review';
    END IF;
    IF EXISTS (
        SELECT FROM pg_namespace n
        CROSS JOIN LATERAL aclexplode(COALESCE(n.nspacl,acldefault('n',n.nspowner))) a
        WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND a.grantee=0 AND a.privilege_type='CREATE'
    ) THEN
        RAISE EXCEPTION 'PUBLIC schema CREATE requires separate review';
    END IF;
    IF EXISTS (
        SELECT FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl,acldefault('f',p.proowner))) a
        WHERE p.prosecdef AND n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
          AND a.grantee=0 AND a.privilege_type='EXECUTE'
    ) THEN
        RAISE EXCEPTION 'PUBLIC security-definer routine requires separate review';
    END IF;
END
$schema_check$;

-- Nullable additions preserve the original columns and existing rows.
ALTER TABLE public.telemetry_log
    ADD COLUMN iowait_pct double precision,
    ADD COLUMN ram_used_pct double precision,
    ADD COLUMN swap_used_mb double precision,
    ADD COLUMN cpu_load_1m double precision,
    ADD COLUMN status text,
    ADD COLUMN note text;
ALTER TABLE public.throttle_events
    ADD COLUMN trigger_metric text,
    ADD COLUMN trigger_value double precision,
    ADD COLUMN threshold double precision,
    ADD COLUMN action text,
    ADD COLUMN result text;

CREATE ROLE qf_monitor_writer NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
    NOREPLICATION NOBYPASSRLS NOINHERIT CONNECTION LIMIT 2;

-- PUBLIC TEMP cannot be denied to just one role. Preserve the effective TEMP
-- privilege of every existing non-built-in role, then remove the blanket grant.
DO $preserve_temp$
DECLARE existing_role record;
BEGIN
    FOR existing_role IN SELECT rolname FROM pg_roles
        WHERE rolname !~ '^pg_' AND rolname <> 'qf_monitor_writer'
          AND has_database_privilege(oid,'telemetry','TEMP') LOOP
        EXECUTE format('GRANT TEMPORARY ON DATABASE telemetry TO %I',existing_role.rolname);
    END LOOP;
END
$preserve_temp$;
REVOKE TEMPORARY ON DATABASE telemetry FROM PUBLIC;
GRANT CONNECT ON DATABASE telemetry TO qf_monitor_writer;
GRANT USAGE ON SCHEMA public TO qf_monitor_writer;
GRANT INSERT (iowait_pct,ram_used_pct,swap_used_mb,cpu_load_1m,status,note)
    ON public.telemetry_log TO qf_monitor_writer;
GRANT INSERT (trigger_metric,trigger_value,threshold,action,result)
    ON public.throttle_events TO qf_monitor_writer;
DO $sequences$
BEGIN
    EXECUTE format('GRANT USAGE ON SEQUENCE %s TO qf_monitor_writer',
        pg_get_serial_sequence('public.telemetry_log','id')::regclass);
    EXECUTE format('GRANT USAGE ON SEQUENCE %s TO qf_monitor_writer',
        pg_get_serial_sequence('public.throttle_events','id')::regclass);
END
$sequences$;
ALTER ROLE qf_monitor_writer IN DATABASE telemetry SET search_path TO public;
ALTER ROLE qf_monitor_writer IN DATABASE telemetry SET statement_timeout TO '5s';
ALTER ROLE qf_monitor_writer IN DATABASE telemetry SET lock_timeout TO '2s';
COMMIT;
SELECT 'MONITOR_ROLE_PREPARED_NOLOGIN' AS result;
