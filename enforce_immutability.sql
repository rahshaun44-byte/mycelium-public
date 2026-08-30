-- ============================================================================
-- QUANTUM FLEX: Zero-Trust Immutability Enforcement
-- ============================================================================

-- Strip all destructive permissions from public and the ingestion engine role
REVOKE ALL PRIVILEGES ON TABLE quantum_telemetry_channel FROM PUBLIC;
REVOKE ALL PRIVILEGES ON TABLE quantum_telemetry_channel FROM quantum_sentinel;

-- Strictly grant append-only (INSERT) and read (SELECT) permissions
GRANT INSERT, SELECT ON TABLE quantum_telemetry_channel TO quantum_sentinel;
GRANT USAGE, SELECT ON SEQUENCE quantum_telemetry_channel_id_seq TO quantum_sentinel;

-- Lock schema modifications: only superuser/owner can alter
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO quantum_sentinel;
