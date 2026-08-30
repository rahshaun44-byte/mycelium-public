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

GRANT ALL PRIVILEGES ON TABLE quantum_telemetry_channel TO quantum_sentinel;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO quantum_sentinel;
GRANT ALL PRIVILEGES ON TABLE quantum_telemetry_channel TO rahshaunchambers;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rahshaunchambers;
