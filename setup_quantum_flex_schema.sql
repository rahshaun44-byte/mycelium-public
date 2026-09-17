-- ============================================================================
-- QUANTUM FLEX: Telemetry Schema Initialization
-- ============================================================================

CREATE TABLE IF NOT EXISTS quantum_telemetry_channel (
    id SERIAL PRIMARY KEY,
    node_id VARCHAR(64) NOT NULL,
    timestamp BIGINT NOT NULL,
    payload TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_telemetry_timestamp ON quantum_telemetry_channel(timestamp);

GRANT USAGE ON SCHEMA public TO quantum_sentinel;
GRANT INSERT, SELECT ON TABLE public.quantum_telemetry_channel TO quantum_sentinel;
GRANT USAGE, SELECT ON SEQUENCE public.quantum_telemetry_channel_id_seq TO quantum_sentinel;

GRANT USAGE ON SCHEMA public TO rahshaunchambers;
GRANT INSERT, SELECT ON TABLE public.quantum_telemetry_channel TO rahshaunchambers;
GRANT USAGE, SELECT ON SEQUENCE public.quantum_telemetry_channel_id_seq TO rahshaunchambers;
