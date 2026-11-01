-- scripts/sql/004_node_registry_schema.sql
-- QuantumFlex Decoupled Asynchronous Telemetry Mesh (QF-M1)
-- Schema definition for edge node registry and dynamic state hydration view.

CREATE TABLE IF NOT EXISTS node_registry (
    node_id VARCHAR(64) PRIMARY KEY,
    tailscale_ip INET NOT NULL,
    transport_peer_ip INET,
    reported_ip INET,
    hardware_claim VARCHAR(64),
    hardware_verified BOOLEAN NOT NULL DEFAULT FALSE,
    attestation_evidence_hash TEXT,
    hardware_root_trust VARCHAR(64),
    pqc_algorithm VARCHAR(32) DEFAULT 'ML-KEM-768',
    last_seen_epoch BIGINT NOT NULL,
    status VARCHAR(20) DEFAULT 'INITIALIZING',
    entropy_delta_h DOUBLE PRECISION DEFAULT 0.0,
    firmware_attestation_hash TEXT
);

CREATE INDEX IF NOT EXISTS idx_node_last_seen ON node_registry(last_seen_epoch);
CREATE INDEX IF NOT EXISTS idx_node_status ON node_registry(status);

-- Decoupled state projection view:
-- Converts asynchronous heartbeat intervals to operational states without synchronous network polling.
CREATE OR REPLACE VIEW node_health_status AS
SELECT
    node_id,
    tailscale_ip,
    transport_peer_ip,
    hardware_claim,
    hardware_verified,
    attestation_evidence_hash,
    hardware_root_trust,
    pqc_algorithm,
    CASE
        WHEN status = 'RETIRED_MAINTENANCE' THEN 'RETIRED_MAINTENANCE'
        WHEN status = 'QUARANTINED' THEN 'QUARANTINED'
        WHEN (EXTRACT(EPOCH FROM NOW())::BIGINT - last_seen_epoch) < 90 THEN 'ACTIVE'
        WHEN (EXTRACT(EPOCH FROM NOW())::BIGINT - last_seen_epoch) < 300 THEN 'HOLD_ACTIVE'
        ELSE 'OFFLINE'
    END AS node_state,
    last_seen_epoch,
    entropy_delta_h,
    reported_ip
FROM node_registry;

GRANT SELECT, INSERT, UPDATE ON node_registry TO qf_writer;
GRANT SELECT ON node_registry TO qf_verifier;
GRANT SELECT ON node_health_status TO qf_verifier;
GRANT SELECT ON node_health_status TO qf_writer;
