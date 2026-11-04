-- Schema Migration: Athena Vector Store v1 -> v2 (Epistemic Foundation)
PRAGMA foreign_keys = ON;

-- 0. Documents Table: Stores parent source documents
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT UNIQUE,
    content TEXT,
    metadata JSON,
    created_at TEXT
);

-- 1. Claims Table: Stores fine-grained assertions extracted from ingested text
CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    document_id INTEGER NOT NULL,
    claim_text TEXT NOT NULL,
    byte_offset_start INTEGER NOT NULL,
    byte_offset_end INTEGER NOT NULL,
    source_sha256 TEXT NOT NULL,
    claim_sha256 TEXT NOT NULL,
    epistemic_tier TEXT NOT NULL CHECK(epistemic_tier IN ('E1','E2','E3','E4','E5','M1','M2','M3','M4','M5')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_claims_source ON claims(source_sha256);
CREATE INDEX IF NOT EXISTS idx_claims_tier ON claims(epistemic_tier);

-- 2. Evidence Spans Table: Merkle-verified citation paths
CREATE TABLE IF NOT EXISTS evidence_spans (
    span_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    doc_uri TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK(source_type IN ('peer_reviewed_literature', 'formal_proof', 'physical_measurement', 'operational_telemetry')),
    merkle_root TEXT NOT NULL,
    leaf_index INTEGER NOT NULL,
    leaf_hash TEXT NOT NULL,
    inclusion_proof_json TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_evidence_claim ON evidence_spans(claim_id);
CREATE INDEX IF NOT EXISTS idx_evidence_root ON evidence_spans(merkle_root);

-- 3. Verification Records Table: Mechanical proof checker results
CREATE TABLE IF NOT EXISTS verification_records (
    record_id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    verifier_kernel TEXT NOT NULL CHECK(verifier_kernel IN ('SymPy', 'Lean4', 'Coq', 'Z3', 'NumericalSolver')),
    kernel_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('VERIFIED', 'REFUTED', 'TIMEOUT', 'CONJECTURE_ONLY')),
    assumptions_json TEXT NOT NULL,
    proof_script TEXT NOT NULL,
    execution_time_ms REAL NOT NULL,
    verified_at TEXT NOT NULL,
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_verif_claim ON verification_records(claim_id);
CREATE INDEX IF NOT EXISTS idx_verif_status ON verification_records(status);

-- 4. Literature Decontamination Table: Leakage screening and deduplication
CREATE TABLE IF NOT EXISTS decontamination_records (
    paper_id TEXT PRIMARY KEY,
    source_uri TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    minhash_signature TEXT NOT NULL,
    benchmark_leakage_score REAL NOT NULL,
    quarantine_status TEXT NOT NULL CHECK(quarantine_status IN ('CLEAN', 'QUARANTINED', 'DUPLICATE')),
    audited_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decontam_sha ON decontamination_records(content_sha256);
CREATE INDEX IF NOT EXISTS idx_decontam_status ON decontamination_records(quarantine_status);
