//! Isolated Ghost Node entropy sink.
//!
//! Absorbs Gatekeeper `ghost_node_manifest` payloads into an append-only
//! hash-chained JSONL ledger. This crate grants **no** admission authority.
//! Residues are not credited as KEM entropy (`H_attack = 0`).
//!
//! Default listen address is loopback on 19443. Port 9443 is the engine
//! mTLS listener and must not be reused for unauthenticated HTTP.

use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

pub const REQUIRED_ENTROPY_ACTION: &str = "ABSORB_INTO_GHOST_SINK";
pub const GENESIS_HASH: [u8; 32] = [0u8; 32];

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct AnomalyIngressPayload {
    pub node_uuid: String,
    pub timestamp_epoch_nonce: String,
    pub pcr_integrity_pass: bool,
    pub nonce_freshness_pass: bool,
    pub structural_anomaly: Option<serde_json::Value>,
    pub execution_violations: Vec<serde_json::Value>,
    pub raw_records_count: usize,
    pub entropy_action: String,
    #[serde(default)]
    pub raw_telemetry_dump: Option<String>,
    /// Policy may emit this. Non-zero is recorded, never credited.
    #[serde(default)]
    pub h_attack: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct LedgerRecord {
    pub sequence_number: u64,
    pub ingested_at_ns: u64,
    pub previous_record_hash: String,
    pub payload_sha256: String,
    pub record_hash: String,
    pub payload: AnomalyIngressPayload,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct IngestResponse {
    pub status: String,
    pub sequence_number: u64,
    pub payload_sha256: String,
    pub record_hash: String,
}

#[derive(Debug)]
pub enum SinkError {
    BadEntropyAction(String),
    Serialize(serde_json::Error),
    Io(std::io::Error),
    BrokenChain {
        sequence: u64,
        expected: String,
        computed: String,
    },
    UnboundListen(String),
}

impl From<serde_json::Error> for SinkError {
    fn from(value: serde_json::Error) -> Self {
        Self::Serialize(value)
    }
}

impl From<std::io::Error> for SinkError {
    fn from(value: std::io::Error) -> Self {
        Self::Io(value)
    }
}

pub fn payload_sha256(payload: &AnomalyIngressPayload) -> Result<[u8; 32], serde_json::Error> {
    let bytes = serde_json::to_vec(payload)?;
    Ok(Sha256::digest(bytes).into())
}

pub fn record_hash(
    sequence: u64,
    ingested_at_ns: u64,
    previous: &[u8; 32],
    payload_hash: &[u8; 32],
) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(sequence.to_be_bytes());
    hasher.update(ingested_at_ns.to_be_bytes());
    hasher.update(previous);
    hasher.update(payload_hash);
    hasher.finalize().into()
}

pub fn validate_payload(payload: &AnomalyIngressPayload) -> Result<(), SinkError> {
    if payload.entropy_action != REQUIRED_ENTROPY_ACTION {
        return Err(SinkError::BadEntropyAction(payload.entropy_action.clone()));
    }
    Ok(())
}

#[derive(Debug)]
pub struct Ledger {
    last_sequence: u64,
    last_record_hash: [u8; 32],
    log_file_path: PathBuf,
}

impl Ledger {
    pub fn recover(path: &Path) -> Result<Self, SinkError> {
        if !path.exists() {
            return Ok(Self {
                last_sequence: 0,
                last_record_hash: GENESIS_HASH,
                log_file_path: path.to_path_buf(),
            });
        }

        let contents = std::fs::read_to_string(path)?;
        let mut last_seq = 0u64;
        let mut last_hash = GENESIS_HASH;

        for line in contents.lines() {
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }
            let record: LedgerRecord = serde_json::from_str(trimmed)?;
            let p_hash = payload_sha256(&record.payload)?;
            let computed = record_hash(
                record.sequence_number,
                record.ingested_at_ns,
                &last_hash,
                &p_hash,
            );
            let computed_hex = hex::encode(computed);
            if computed_hex != record.record_hash {
                return Err(SinkError::BrokenChain {
                    sequence: record.sequence_number,
                    expected: record.record_hash,
                    computed: computed_hex,
                });
            }
            last_seq = record.sequence_number;
            last_hash = computed;
        }

        Ok(Self {
            last_sequence: last_seq,
            last_record_hash: last_hash,
            log_file_path: path.to_path_buf(),
        })
    }

    pub fn last_sequence(&self) -> u64 {
        self.last_sequence
    }

    pub fn last_record_hash(&self) -> [u8; 32] {
        self.last_record_hash
    }

    pub fn ingest(
        &mut self,
        payload: AnomalyIngressPayload,
        ingested_at_ns: u64,
    ) -> Result<IngestResponse, SinkError> {
        validate_payload(&payload)?;
        let payload_hash = payload_sha256(&payload)?;
        let payload_sha256_hex = hex::encode(payload_hash);
        let sequence_number = self.last_sequence + 1;
        let prev_hash_hex = hex::encode(self.last_record_hash);
        let current = record_hash(
            sequence_number,
            ingested_at_ns,
            &self.last_record_hash,
            &payload_hash,
        );
        let current_hex = hex::encode(current);

        let record = LedgerRecord {
            sequence_number,
            ingested_at_ns,
            previous_record_hash: prev_hash_hex,
            payload_sha256: payload_sha256_hex.clone(),
            record_hash: current_hex.clone(),
            payload,
        };
        let serialized = serde_json::to_string(&record)?;
        append_to_disk(&self.log_file_path, &serialized)?;

        self.last_sequence = sequence_number;
        self.last_record_hash = current;

        Ok(IngestResponse {
            status: "ABSORBED".to_string(),
            sequence_number,
            payload_sha256: payload_sha256_hex,
            record_hash: current_hex,
        })
    }
}

pub fn append_to_disk(path: &Path, line: &str) -> std::io::Result<()> {
    use std::fs::OpenOptions;
    use std::io::Write;

    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let mut file = OpenOptions::new().create(true).append(true).open(path)?;
    file.write_all(line.as_bytes())?;
    file.write_all(b"\n")?;
    file.sync_data()?;
    Ok(())
}

pub fn refuse_unbound_listen(addr: &str, allow_unbound: bool) -> Result<(), SinkError> {
    let lower = addr.to_ascii_lowercase();
    let unbound = lower.starts_with("0.0.0.0:")
        || lower.starts_with("[::]:")
        || lower.starts_with("[::0]:")
        || lower == "0.0.0.0"
        || lower == "[::]";
    if unbound && !allow_unbound {
        return Err(SinkError::UnboundListen(addr.to_string()));
    }
    Ok(())
}

pub fn default_storage_dir() -> PathBuf {
    if let Ok(p) = std::env::var("SINK_STORAGE_PATH") {
        return PathBuf::from(p);
    }
    if let Ok(xdg) = std::env::var("XDG_DATA_HOME") {
        return PathBuf::from(xdg).join("quantumflex/ghost_sink");
    }
    if let Ok(home) = std::env::var("HOME") {
        return PathBuf::from(home).join(".local/share/quantumflex/ghost_sink");
    }
    PathBuf::from("/var/log/quantumflex/sink")
}

impl std::fmt::Display for SinkError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::BadEntropyAction(a) => write!(
                f,
                "payload entropy_action must be {REQUIRED_ENTROPY_ACTION}, got {a:?}"
            ),
            Self::Serialize(e) => write!(f, "serialization failure: {e}"),
            Self::Io(e) => write!(f, "ledger I/O: {e}"),
            Self::BrokenChain {
                sequence,
                expected,
                computed,
            } => write!(
                f,
                "broken hash chain at sequence {sequence}: expected {expected}, computed {computed}"
            ),
            Self::UnboundListen(a) => write!(
                f,
                "listen address {a} is unbound (0.0.0.0/::); set SINK_ALLOW_UNBOUND=1 only inside an isolated netns"
            ),
        }
    }
}

impl std::error::Error for SinkError {}
