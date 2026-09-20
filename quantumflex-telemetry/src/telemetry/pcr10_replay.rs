//! Strict PCR 10 replay over Linux IMA `ima-ng` / `ima-sig` ASCII logs.
//!
//! Recalculates the rolling SHA-256 extend chain
//! `PCR_i = SHA256(PCR_{i-1} || TemplateHash_i)`, compares the terminal
//! state to the SHA-256 PCR 10 value, and structures mismatches as the
//! friction term \(h\) for the Ghost sink.
//!
//! `expected_pcr` is the PCR 10 bank value. `TPMS_ATTEST.pcrDigest` for a
//! quote that selects only PCR 10 is `SHA256(PCR10)` — see
//! [`PcrReplayEngine::quote_pcr_digest`]. Do not compare a composite quote
//! digest to the raw PCR.
//!
//! SHA-1 template hashes (40 hex chars) cannot replay a SHA-256 PCR bank.
//! Those lines fail closed.

use serde::Serialize;
use sha2::{Digest, Sha256};
use std::fmt;

pub const PCR10_INDEX: u32 = 10;
pub const SHA256_DIGEST_LEN: usize = 32;

const ALLOWED_TEMPLATES: &[&str] = &["ima-ng", "ima-sig"];

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ReplayError {
    InvalidPcrIndex(u32),
    MalformedTemplateHash(String),
    MalformedRecord(String),
    DigestMismatch {
        calculated: [u8; SHA256_DIGEST_LEN],
        expected: [u8; SHA256_DIGEST_LEN],
    },
}

impl fmt::Display for ReplayError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::InvalidPcrIndex(idx) => write!(f, "Invalid PCR index: {idx}, expected 10"),
            Self::MalformedTemplateHash(err) => write!(f, "Malformed template hash: {err}"),
            Self::MalformedRecord(err) => write!(f, "Malformed IMA record: {err}"),
            Self::DigestMismatch {
                calculated,
                expected,
            } => write!(
                f,
                "PCR 10 desynchronization: calculated {}, expected {}",
                hex::encode(calculated),
                hex::encode(expected)
            ),
        }
    }
}

impl std::error::Error for ReplayError {}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ImaEntry {
    pub pcr: u32,
    pub template_hash: [u8; SHA256_DIGEST_LEN],
    pub template_name: String,
    pub file_hash_algorithm: String,
    pub file_hash: [u8; SHA256_DIGEST_LEN],
    pub file_path: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct AnomalyPayload {
    pub reason: String,
    pub calculated_pcr: String,
    pub expected_pcr: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub offending_entry: Option<String>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct GatekeeperTelemetryInput {
    pub node_uuid: String,
    pub epoch_nonce: String,
    pub replayed_pcr10: String,
    pub expected_pcr10: String,
    pub pcr_matches: bool,
    pub ima_records: Vec<ImaRecordEvaluation>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub anomaly: Option<AnomalyPayload>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct ImaRecordEvaluation {
    pub file_path: String,
    pub file_hash: String,
    pub algorithm: String,
}

pub struct PcrReplayEngine;

impl PcrReplayEngine {
    /// Parse an ASCII IMA log entry (e.g. from `/sys/kernel/security/ima/ascii_runtime_measurements`).
    ///
    /// Format: `<pcr> <template-hash> <template-name> <file-hash-algo>:<file-hash> <file-path> [sig]`
    pub fn parse_ascii_line(line: &str) -> Result<ImaEntry, ReplayError> {
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.len() < 5 {
            return Err(ReplayError::MalformedRecord(format!(
                "Insufficient columns in line: '{line}'"
            )));
        }

        let pcr: u32 = parts[0].parse().map_err(|_| {
            ReplayError::MalformedRecord(format!("Invalid PCR index: {}", parts[0]))
        })?;

        if pcr != PCR10_INDEX {
            return Err(ReplayError::InvalidPcrIndex(pcr));
        }

        let template_name = parts[2].to_string();
        if !ALLOWED_TEMPLATES.contains(&template_name.as_str()) {
            return Err(ReplayError::MalformedRecord(format!(
                "Unsupported IMA template {template_name:?}; expected ima-ng or ima-sig"
            )));
        }

        let template_hash_bytes =
            hex::decode(parts[1]).map_err(|e| ReplayError::MalformedTemplateHash(e.to_string()))?;
        if template_hash_bytes.len() != SHA256_DIGEST_LEN {
            return Err(ReplayError::MalformedTemplateHash(format!(
                "SHA-256 PCR 10 requires a 32-byte template digest, got {} bytes (SHA-1 ascii logs cannot replay this bank)",
                template_hash_bytes.len()
            )));
        }
        let mut template_hash = [0u8; SHA256_DIGEST_LEN];
        template_hash.copy_from_slice(&template_hash_bytes);

        let hash_parts: Vec<&str> = parts[3].split(':').collect();
        if hash_parts.len() != 2 {
            return Err(ReplayError::MalformedRecord(format!(
                "Invalid file hash format: {}",
                parts[3]
            )));
        }

        let file_hash_algorithm = hash_parts[0].to_ascii_lowercase();
        if file_hash_algorithm != "sha256" {
            return Err(ReplayError::MalformedRecord(format!(
                "Unsupported file hash algorithm {file_hash_algorithm:?}; expected sha256"
            )));
        }

        let file_hash_bytes = hex::decode(hash_parts[1])
            .map_err(|e| ReplayError::MalformedRecord(format!("Invalid file hash hex: {e}")))?;
        if file_hash_bytes.len() != SHA256_DIGEST_LEN {
            return Err(ReplayError::MalformedRecord(format!(
                "File hash length mismatch: expected 32 bytes, got {}",
                file_hash_bytes.len()
            )));
        }
        let mut file_hash = [0u8; SHA256_DIGEST_LEN];
        file_hash.copy_from_slice(&file_hash_bytes);

        let file_path = path_without_ima_sig(template_name.as_str(), &parts[4..]);
        if file_path.is_empty() {
            return Err(ReplayError::MalformedRecord(
                "IMA record missing file path".to_string(),
            ));
        }

        Ok(ImaEntry {
            pcr,
            template_hash,
            template_name,
            file_hash_algorithm,
            file_hash,
            file_path,
        })
    }

    /// Replay PCR 10: `PCR_i = SHA256(PCR_{i-1} || TemplateHash_i)`.
    pub fn replay_pcr10(
        initial_pcr: [u8; SHA256_DIGEST_LEN],
        entries: &[ImaEntry],
    ) -> [u8; SHA256_DIGEST_LEN] {
        let mut current_pcr = initial_pcr;
        for entry in entries {
            let mut hasher = Sha256::new();
            hasher.update(current_pcr);
            hasher.update(entry.template_hash);
            current_pcr = hasher.finalize().into();
        }
        current_pcr
    }

    /// TPM 2.0 quote `pcrDigest` over a SHA-256 bank selection:
    /// `H(PCR[n1] || PCR[n2] || ...)`.
    ///
    /// A quote that selects only PCR 10 is `SHA256(PCR10)`, not PCR 10 itself.
    pub fn quote_pcr_digest(selected_pcrs: &[[u8; SHA256_DIGEST_LEN]]) -> [u8; SHA256_DIGEST_LEN] {
        let mut hasher = Sha256::new();
        for pcr in selected_pcrs {
            hasher.update(pcr);
        }
        hasher.finalize().into()
    }

    /// Verify PCR against the expected SHA-256 PCR 10 value and build OPA input.
    ///
    /// Parse failures and digest mismatches become `anomaly` (\(h\)). This
    /// function never admits; OPA decides `allow` vs Ghost.
    pub fn verify_and_prepare_opa_input(
        node_uuid: &str,
        epoch_nonce: &[u8],
        raw_ima_log: &str,
        expected_pcr: [u8; SHA256_DIGEST_LEN],
    ) -> GatekeeperTelemetryInput {
        let initial_pcr = [0u8; SHA256_DIGEST_LEN];
        let mut entries = Vec::new();
        let mut parsing_anomaly: Option<AnomalyPayload> = None;

        for line in raw_ima_log.lines() {
            let trimmed = line.trim();
            if trimmed.is_empty() {
                continue;
            }
            match Self::parse_ascii_line(trimmed) {
                Ok(entry) => entries.push(entry),
                Err(err) => {
                    parsing_anomaly = Some(AnomalyPayload {
                        reason: format!("Log parsing failure: {err}"),
                        calculated_pcr: hex::encode(initial_pcr),
                        expected_pcr: hex::encode(expected_pcr),
                        offending_entry: Some(trimmed.to_string()),
                    });
                    break;
                }
            }
        }

        let calculated_pcr = Self::replay_pcr10(initial_pcr, &entries);
        let pcr_matches = calculated_pcr == expected_pcr;

        let anomaly = if let Some(anomaly) = parsing_anomaly {
            Some(anomaly)
        } else if entries.is_empty() {
            Some(AnomalyPayload {
                reason: "No IMA records to replay".to_string(),
                calculated_pcr: hex::encode(calculated_pcr),
                expected_pcr: hex::encode(expected_pcr),
                offending_entry: None,
            })
        } else if !pcr_matches {
            Some(AnomalyPayload {
                reason: "PCR 10 hardware digest mismatch - hash chain broken".to_string(),
                calculated_pcr: hex::encode(calculated_pcr),
                expected_pcr: hex::encode(expected_pcr),
                offending_entry: None,
            })
        } else {
            None
        };

        let ima_records = entries
            .into_iter()
            .map(|e| ImaRecordEvaluation {
                file_path: e.file_path,
                file_hash: hex::encode(e.file_hash),
                algorithm: e.file_hash_algorithm,
            })
            .collect();

        GatekeeperTelemetryInput {
            node_uuid: node_uuid.to_string(),
            epoch_nonce: hex::encode(epoch_nonce),
            replayed_pcr10: hex::encode(calculated_pcr),
            expected_pcr10: hex::encode(expected_pcr),
            pcr_matches,
            ima_records,
            anomaly,
        }
    }
}

impl GatekeeperTelemetryInput {
    pub fn to_opa_json(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string(self)
    }
}

fn path_without_ima_sig(template_name: &str, tail: &[&str]) -> String {
    if tail.is_empty() {
        return String::new();
    }
    if template_name == "ima-sig" && tail.len() >= 2 {
        let last = tail[tail.len() - 1];
        if is_even_hex(last) && last.len() >= 16 {
            return tail[..tail.len() - 1].join(" ");
        }
    }
    tail.join(" ")
}

fn is_even_hex(token: &str) -> bool {
    token.len() % 2 == 0 && !token.is_empty() && token.bytes().all(|b| b.is_ascii_hexdigit())
}
