-- QuantumFlex Context API persistence foundation.
-- Apply only through the approved database provisioning workflow.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS qf_private;
ALTER SCHEMA qf_private OWNER TO CURRENT_USER;
REVOKE ALL ON SCHEMA qf_private FROM PUBLIC;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'qf_context') THEN
        CREATE ROLE qf_context WITH
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT
            NOREPLICATION
            NOBYPASSRLS
            CONNECTION LIMIT 16;
    END IF;
END
$$;

ALTER ROLE qf_context WITH
    LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS
    CONNECTION LIMIT 16 PASSWORD :'qf_context_password';
ALTER ROLE qf_context SET statement_timeout = '10000ms';
ALTER ROLE qf_context SET idle_in_transaction_session_timeout = '15000ms';
REVOKE ALL ON SCHEMA qf_private FROM qf_context;

CREATE TABLE IF NOT EXISTS qf_private.context_signing_key (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (singleton),
    key_bytes BYTEA NOT NULL CHECK (octet_length(key_bytes) = 32)
);

INSERT INTO qf_private.context_signing_key (singleton, key_bytes)
VALUES (TRUE, decode(:'qf_context_identity_hmac_key', 'hex'))
ON CONFLICT (singleton) DO UPDATE SET key_bytes = EXCLUDED.key_bytes;

CREATE TABLE IF NOT EXISTS qf_private.context_identity_sessions (
    backend_pid INTEGER NOT NULL,
    transaction_id BIGINT NOT NULL,
    owner_id VARCHAR(128) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (backend_pid, transaction_id)
);

CREATE TABLE IF NOT EXISTS qf_private.context_identity_nonces (
    nonce VARCHAR(32) PRIMARY KEY,
    expires_at TIMESTAMPTZ NOT NULL
);

REVOKE ALL ON ALL TABLES IN SCHEMA qf_private FROM PUBLIC, qf_context;
ALTER TABLE qf_private.context_signing_key OWNER TO CURRENT_USER;
ALTER TABLE qf_private.context_identity_sessions OWNER TO CURRENT_USER;
ALTER TABLE qf_private.context_identity_nonces OWNER TO CURRENT_USER;

CREATE OR REPLACE FUNCTION qf_private.set_context_identity(
    p_owner_id TEXT,
    p_expires_at BIGINT,
    p_nonce TEXT,
    p_signature TEXT
) RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, qf_private
AS $$
DECLARE
    v_now BIGINT := floor(extract(epoch FROM clock_timestamp()))::BIGINT;
    v_key BYTEA;
    v_payload BYTEA;
    v_expected_signature TEXT;
BEGIN
    IF p_owner_id IS NULL OR length(p_owner_id) = 0 OR length(p_owner_id) > 128 THEN
        RAISE EXCEPTION 'invalid context owner identity' USING ERRCODE = '28000';
    END IF;
    IF p_expires_at < v_now OR p_expires_at > v_now + 60
       OR p_nonce !~ '^[0-9a-f]{32}$'
       OR p_signature !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'invalid or expired context identity claim' USING ERRCODE = '28000';
    END IF;

    SELECT key_bytes INTO STRICT v_key
    FROM qf_private.context_signing_key
    WHERE singleton;
    v_payload := convert_to(p_owner_id, 'UTF8')
        || decode('00', 'hex')
        || convert_to(p_expires_at::TEXT, 'UTF8')
        || decode('00', 'hex')
        || convert_to(p_nonce, 'UTF8');
    v_expected_signature := encode(public.hmac(v_payload, v_key, 'sha256'), 'hex');
    IF v_expected_signature <> p_signature THEN
        RAISE EXCEPTION 'invalid context identity signature' USING ERRCODE = '28000';
    END IF;

    DELETE FROM qf_private.context_identity_sessions
    WHERE expires_at <= clock_timestamp();
    DELETE FROM qf_private.context_identity_nonces
    WHERE expires_at <= clock_timestamp();

    INSERT INTO qf_private.context_identity_nonces (nonce, expires_at)
    VALUES (p_nonce, to_timestamp(p_expires_at))
    ON CONFLICT (nonce) DO NOTHING;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'context identity claim has already been used' USING ERRCODE = '28000';
    END IF;

    INSERT INTO qf_private.context_identity_sessions
        (backend_pid, transaction_id, owner_id, expires_at)
    VALUES (pg_backend_pid(), txid_current(), p_owner_id, to_timestamp(p_expires_at));
END
$$;
ALTER FUNCTION qf_private.set_context_identity(TEXT, BIGINT, TEXT, TEXT) OWNER TO CURRENT_USER;

CREATE OR REPLACE FUNCTION qf_private.current_context_owner()
RETURNS TEXT
LANGUAGE sql
SECURITY DEFINER
SET search_path = pg_catalog, qf_private
AS $$
    SELECT owner_id::TEXT
    FROM qf_private.context_identity_sessions
    WHERE backend_pid = pg_backend_pid()
      AND transaction_id = txid_current()
      AND expires_at > clock_timestamp()
$$;
ALTER FUNCTION qf_private.current_context_owner() OWNER TO CURRENT_USER;

REVOKE ALL ON FUNCTION qf_private.set_context_identity(TEXT, BIGINT, TEXT, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION qf_private.current_context_owner() FROM PUBLIC;
GRANT USAGE ON SCHEMA qf_private TO qf_context;
GRANT EXECUTE ON FUNCTION qf_private.set_context_identity(TEXT, BIGINT, TEXT, TEXT) TO qf_context;
GRANT EXECUTE ON FUNCTION qf_private.current_context_owner() TO qf_context;

CREATE TABLE IF NOT EXISTS public.qf_context_conversations (
    conversation_id UUID PRIMARY KEY,
    owner_id VARCHAR(128) NOT NULL,
    created_by_device VARCHAR(64) NOT NULL,
    project_id VARCHAR(256),
    data_classification VARCHAR(16) NOT NULL DEFAULT 'INTERNAL'
        CHECK (data_classification IN ('PUBLIC', 'INTERNAL', 'CONFIDENTIAL')),
    retention_policy VARCHAR(32) NOT NULL DEFAULT 'OWNER_CONTROLLED'
        CHECK (retention_policy IN ('OWNER_CONTROLLED')),
    legal_hold BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (conversation_id, owner_id)
);

CREATE TABLE IF NOT EXISTS public.qf_context_messages (
    message_id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL,
    owner_id VARCHAR(128) NOT NULL,
    sequence_no BIGINT NOT NULL CHECK (sequence_no > 0),
    sender_type VARCHAR(16) NOT NULL CHECK (sender_type IN ('USER', 'AGENT', 'SYSTEM')),
    sender_id VARCHAR(128) NOT NULL,
    ciphertext BYTEA NOT NULL,
    encryption_key_version VARCHAR(32) NOT NULL,
    data_classification VARCHAR(16) NOT NULL DEFAULT 'INTERNAL'
        CHECK (data_classification IN ('PUBLIC', 'INTERNAL', 'CONFIDENTIAL')),
    retention_policy VARCHAR(32) NOT NULL DEFAULT 'OWNER_CONTROLLED'
        CHECK (retention_policy IN ('OWNER_CONTROLLED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    UNIQUE (conversation_id, sequence_no),
    FOREIGN KEY (conversation_id, owner_id)
        REFERENCES public.qf_context_conversations (conversation_id, owner_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS public.qf_context_access (
    conversation_id UUID NOT NULL,
    owner_id VARCHAR(128) NOT NULL,
    principal_type VARCHAR(16) NOT NULL CHECK (principal_type IN ('DEVICE', 'AGENT')),
    principal_id VARCHAR(128) NOT NULL,
    permission VARCHAR(16) NOT NULL CHECK (permission IN ('READ', 'APPEND', 'DELETE', 'TASK')),
    granted_by VARCHAR(128) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    PRIMARY KEY (conversation_id, principal_type, principal_id, permission),
    FOREIGN KEY (conversation_id, owner_id)
        REFERENCES public.qf_context_conversations (conversation_id, owner_id)
        ON DELETE CASCADE
);

ALTER TABLE public.qf_context_access
    DROP CONSTRAINT IF EXISTS qf_context_access_permission_check;
ALTER TABLE public.qf_context_access
    ADD CONSTRAINT qf_context_access_permission_check
    CHECK (permission IN ('READ', 'APPEND', 'DELETE', 'TASK'));

CREATE TABLE IF NOT EXISTS public.qf_context_security_audit (
    audit_id BIGSERIAL PRIMARY KEY,
    owner_id VARCHAR(128),
    actor_id VARCHAR(128),
    resource_id UUID,
    operation VARCHAR(64) NOT NULL,
    decision VARCHAR(16) NOT NULL CHECK (decision IN ('ALLOW', 'DENY')),
    event_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '1 year'),
    metadata JSONB NOT NULL DEFAULT '{}'
);

ALTER TABLE public.qf_context_conversations OWNER TO CURRENT_USER;
ALTER TABLE public.qf_context_messages OWNER TO CURRENT_USER;
ALTER TABLE public.qf_context_access OWNER TO CURRENT_USER;
ALTER TABLE public.qf_context_security_audit OWNER TO CURRENT_USER;
ALTER SEQUENCE public.qf_context_security_audit_audit_id_seq OWNER TO CURRENT_USER;

CREATE INDEX IF NOT EXISTS idx_qf_context_conversations_owner_updated
    ON public.qf_context_conversations (owner_id, updated_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_qf_context_messages_owner_sequence
    ON public.qf_context_messages (owner_id, conversation_id, sequence_no)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_qf_context_access_owner
    ON public.qf_context_access (owner_id, conversation_id)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_qf_context_audit_expiry
    ON public.qf_context_security_audit (expires_at);

ALTER TABLE public.qf_context_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qf_context_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qf_context_access ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qf_context_security_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qf_context_conversations FORCE ROW LEVEL SECURITY;
ALTER TABLE public.qf_context_messages FORCE ROW LEVEL SECURITY;
ALTER TABLE public.qf_context_access FORCE ROW LEVEL SECURITY;
ALTER TABLE public.qf_context_security_audit FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS qf_context_owner_conversations ON public.qf_context_conversations;
CREATE POLICY qf_context_owner_conversations ON public.qf_context_conversations
    TO qf_context
    USING (
        owner_id = (SELECT qf_private.current_context_owner())
        AND deleted_at IS NULL
    )
    WITH CHECK (owner_id = (SELECT qf_private.current_context_owner()));

DROP POLICY IF EXISTS qf_context_owner_messages ON public.qf_context_messages;
CREATE POLICY qf_context_owner_messages ON public.qf_context_messages
    TO qf_context
    USING (
        owner_id = (SELECT qf_private.current_context_owner())
        AND deleted_at IS NULL
    )
    WITH CHECK (owner_id = (SELECT qf_private.current_context_owner()));

DROP POLICY IF EXISTS qf_context_owner_access ON public.qf_context_access;
CREATE POLICY qf_context_owner_access ON public.qf_context_access
    TO qf_context
    USING (
        owner_id = (SELECT qf_private.current_context_owner())
        AND deleted_at IS NULL
    )
    WITH CHECK (owner_id = (SELECT qf_private.current_context_owner()));

DROP POLICY IF EXISTS qf_context_owner_security_audit ON public.qf_context_security_audit;
CREATE POLICY qf_context_owner_security_audit ON public.qf_context_security_audit
    FOR INSERT TO qf_context
    WITH CHECK (owner_id = (SELECT qf_private.current_context_owner()));

REVOKE ALL ON public.qf_context_conversations, public.qf_context_messages,
    public.qf_context_access, public.qf_context_security_audit
    FROM PUBLIC, qf_writer, qf_verifier;
GRANT CONNECT ON DATABASE telemetry TO qf_context;
GRANT USAGE ON SCHEMA public TO qf_context;
REVOKE CREATE ON SCHEMA public FROM qf_context;
GRANT SELECT, INSERT, UPDATE, DELETE ON
    public.qf_context_conversations, public.qf_context_messages, public.qf_context_access
    TO qf_context;
GRANT INSERT ON public.qf_context_security_audit TO qf_context;
GRANT USAGE, SELECT ON SEQUENCE public.qf_context_security_audit_audit_id_seq TO qf_context;

COMMIT;
