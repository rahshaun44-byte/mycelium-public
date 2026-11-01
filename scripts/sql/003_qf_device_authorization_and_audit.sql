-- scripts/sql/003_qf_device_authorization_and_audit.sql
-- QuantumFlex Legal & Operational Assurance Layer (QF-LOAL)
-- Schema migration for device authorization registry and immutable governance audit trail.

CREATE TABLE IF NOT EXISTS qf_device_authorization (
    node_id VARCHAR(64) PRIMARY KEY,
    owner_id VARCHAR(128) NOT NULL,
    authorization_status VARCHAR(24) NOT NULL DEFAULT 'PENDING',
    permitted_purposes JSONB NOT NULL DEFAULT '[]',
    permitted_operations JSONB NOT NULL DEFAULT '[]',
    consent_record_id VARCHAR(128),
    authorization_basis TEXT NOT NULL,
    hardware_identity TEXT,
    hardware_verified BOOLEAN NOT NULL DEFAULT FALSE,
    software_provenance_sha256 CHAR(64),
    authorized_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    last_reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        authorization_status IN (
            'PENDING',
            'AUTHORIZED',
            'SUSPENDED',
            'REVOKED',
            'EXPIRED'
        )
    )
);

CREATE TABLE IF NOT EXISTS qf_governance_audit (
    audit_id BIGSERIAL PRIMARY KEY,
    event_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(64) NOT NULL,
    node_id VARCHAR(64),
    operator_id VARCHAR(128),
    requested_operation VARCHAR(128),
    authorization_decision VARCHAR(32) NOT NULL,
    policy_version VARCHAR(32) NOT NULL DEFAULT 'QF-LEGAL-001/v1',
    evidence_hash CHAR(64),
    denial_reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_device_auth_status ON qf_device_authorization(authorization_status);
CREATE INDEX IF NOT EXISTS idx_gov_audit_node ON qf_governance_audit(node_id);
CREATE INDEX IF NOT EXISTS idx_gov_audit_type ON qf_governance_audit(event_type);

GRANT SELECT, INSERT, UPDATE ON qf_device_authorization TO qf_writer;
GRANT SELECT ON qf_device_authorization TO qf_verifier;
GRANT SELECT, INSERT ON qf_governance_audit TO qf_writer;
GRANT USAGE, SELECT ON SEQUENCE qf_governance_audit_audit_id_seq TO qf_writer;
GRANT SELECT ON qf_governance_audit TO qf_verifier;
