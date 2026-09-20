//! Consumes an OPA Gatekeeper verdict and enforces `Y ∩ h = ∅`.
//!
//! `allow && !route_to_ghost` → ledger commit payload (caller writes Y).
//! `!allow && route_to_ghost` → POST to the Ghost sink over HTTP/1.1.
//! `allow && route_to_ghost` is an invariant violation and is never ingested.
//! Ghost receipts are not admission. `H_attack = 0`.
//!
//! The isolated sink is HTTP on loopback / a private netns, not engine mTLS
//! `:9443`. A rustls stack is not pulled in: current rustc 1.83 cannot
//! resolve reqwest/rustls graphs that require edition 2024.

use bytes::Bytes;
use http_body_util::{BodyExt, Full};
use hyper::Request;
use hyper_util::client::legacy::connect::HttpConnector;
use hyper_util::client::legacy::Client;
use hyper_util::rt::TokioExecutor;
use serde::{Deserialize, Serialize};
use std::time::Duration;
use thiserror::Error;
use tracing::{error, info, warn};

#[derive(Debug, Error)]
pub enum DispatchError {
    #[error("HTTP client error: {0}")]
    HttpClient(String),

    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    #[error("Ghost sink rejected anomaly with status {status}: {body}")]
    SinkRejection {
        status: http::StatusCode,
        body: String,
    },

    #[error("Invalid state: routing to ghost requested, but ghost_node_manifest is missing")]
    MissingGhostManifest,

    #[error("Invalid state: allow=true without ledger_commit_manifest")]
    MissingLedgerManifest,

    #[error("Invariant violation: allow and route_to_ghost are both true (Y ∩ h ≠ ∅)")]
    Overlap,

    #[error("Indeterminate policy evaluation: allow=false and route_to_ghost=false")]
    Indeterminate,
}

/// Output shape expected from OPA Gatekeeper evaluation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OpaGatekeeperResult {
    pub allow: bool,
    pub route_to_ghost: bool,
    pub ledger_commit_manifest: Option<serde_json::Value>,
    pub ghost_node_manifest: Option<GhostNodeManifest>,
}

/// Structured friction term (h) matching the sink `AnomalyIngressPayload`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GhostNodeManifest {
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
    #[serde(default)]
    pub h_attack: u32,
}

#[derive(Debug, Clone, Deserialize, Serialize, PartialEq, Eq)]
pub struct SinkReceipt {
    pub status: String,
    pub sequence_number: u64,
    pub payload_sha256: String,
    pub record_hash: String,
}

#[derive(Debug, Clone)]
pub struct GhostSinkConfig {
    pub endpoint_url: String,
    pub request_timeout: Duration,
    pub max_retries: usize,
    pub initial_retry_delay: Duration,
}

impl Default for GhostSinkConfig {
    fn default() -> Self {
        Self {
            endpoint_url: std::env::var("GHOST_SINK_URL")
                .unwrap_or_else(|_| "http://127.0.0.1:19443/v1/sink/anomaly".to_string()),
            request_timeout: Duration::from_millis(1500),
            max_retries: 3,
            initial_retry_delay: Duration::from_millis(50),
        }
    }
}

pub struct GatekeeperDispatcher {
    client: Client<HttpConnector, Full<Bytes>>,
    config: GhostSinkConfig,
}

impl GatekeeperDispatcher {
    pub fn new(config: GhostSinkConfig) -> Result<Self, DispatchError> {
        let mut connector = HttpConnector::new();
        connector.set_nodelay(true);
        let client = Client::builder(TokioExecutor::new()).build(connector);
        Ok(Self { client, config })
    }

    /// Bifurcate OPA output into ledger commit (Y) or Ghost absorption (h).
    pub async fn dispatch_verdict(
        &self,
        decision: OpaGatekeeperResult,
        raw_telemetry_dump: Option<String>,
    ) -> Result<DispatchOutcome, DispatchError> {
        match (decision.allow, decision.route_to_ghost) {
            (true, true) => {
                error!(
                    target: "quantumflex::gatekeeper",
                    "Invariant violation: allow and route_to_ghost both true"
                );
                Err(DispatchError::Overlap)
            }
            (true, false) => {
                let commit_payload = decision
                    .ledger_commit_manifest
                    .ok_or(DispatchError::MissingLedgerManifest)?;
                info!(
                    target: "quantumflex::gatekeeper",
                    "Node integrity verified (h = 0). Ledger commit is the caller's duty."
                );
                Ok(DispatchOutcome::CommittedToLedger(commit_payload))
            }
            (false, true) => {
                let mut manifest = decision
                    .ghost_node_manifest
                    .ok_or(DispatchError::MissingGhostManifest)?;
                if manifest.raw_telemetry_dump.is_none() {
                    manifest.raw_telemetry_dump = raw_telemetry_dump;
                }
                warn!(
                    target: "quantumflex::gatekeeper",
                    node_uuid = %manifest.node_uuid,
                    records = manifest.raw_records_count,
                    violations = manifest.execution_violations.len(),
                    "Integrity mismatch. Routing friction (h) to Ghost Node."
                );
                let receipt = self.send_to_ghost_sink_with_retry(&manifest).await?;
                info!(
                    target: "quantumflex::gatekeeper",
                    receipt_seq = receipt.sequence_number,
                    record_hash = %receipt.record_hash,
                    "Anomaly absorbed into Ghost Node ledger. No admission granted."
                );
                Ok(DispatchOutcome::AbsorbedByGhostNode(receipt))
            }
            (false, false) => {
                error!(target: "quantumflex::gatekeeper", "Indeterminate policy evaluation state");
                Err(DispatchError::Indeterminate)
            }
        }
    }

    async fn send_to_ghost_sink_with_retry(
        &self,
        payload: &GhostNodeManifest,
    ) -> Result<SinkReceipt, DispatchError> {
        let mut attempt = 0;
        let mut delay = self.config.initial_retry_delay;
        let body_bytes = serde_json::to_vec(payload)?;

        loop {
            attempt += 1;
            let request = Request::post(&self.config.endpoint_url)
                .header("content-type", "application/json")
                .body(Full::new(Bytes::from(body_bytes.clone())))
                .map_err(|e| DispatchError::HttpClient(e.to_string()))?;

            let response =
                tokio::time::timeout(self.config.request_timeout, self.client.request(request))
                    .await;

            match response {
                Ok(Ok(resp)) if resp.status().is_success() => {
                    let status = resp.status();
                    let collected = resp
                        .into_body()
                        .collect()
                        .await
                        .map_err(|e| DispatchError::HttpClient(e.to_string()))?;
                    let receipt = serde_json::from_slice::<SinkReceipt>(&collected.to_bytes())
                        .map_err(|e| {
                            DispatchError::HttpClient(format!(
                                "sink {status} body is not a receipt: {e}"
                            ))
                        })?;
                    return Ok(receipt);
                }
                Ok(Ok(resp)) => {
                    let status = resp.status();
                    let collected = resp
                        .into_body()
                        .collect()
                        .await
                        .map_err(|e| DispatchError::HttpClient(e.to_string()))?;
                    let body = String::from_utf8_lossy(&collected.to_bytes()).into_owned();
                    if !status.is_server_error() || attempt >= self.config.max_retries {
                        return Err(DispatchError::SinkRejection { status, body });
                    }
                    warn!(
                        target: "quantumflex::gatekeeper",
                        attempt,
                        status = %status,
                        "Ghost Node returned server error, retrying absorption..."
                    );
                }
                Ok(Err(err)) => {
                    if attempt >= self.config.max_retries {
                        return Err(DispatchError::HttpClient(err.to_string()));
                    }
                    warn!(
                        target: "quantumflex::gatekeeper",
                        attempt,
                        error = %err,
                        "Ghost Node sink unreachable, retrying..."
                    );
                }
                Err(_) => {
                    if attempt >= self.config.max_retries {
                        return Err(DispatchError::HttpClient(
                            "ghost sink request timed out".to_string(),
                        ));
                    }
                    warn!(
                        target: "quantumflex::gatekeeper",
                        attempt,
                        "Ghost Node sink timed out, retrying..."
                    );
                }
            }

            tokio::time::sleep(delay).await;
            delay *= 2;
        }
    }
}

/// Downstream of OPA. Does not write the post-quantum ledger and does not
/// mint authority from a Ghost receipt.
pub async fn handle_boundary_ingress(
    dispatcher: &GatekeeperDispatcher,
    opa_result: OpaGatekeeperResult,
    raw_ima_log: &str,
) -> Result<DispatchOutcome, DispatchError> {
    dispatcher
        .dispatch_verdict(opa_result, Some(raw_ima_log.to_string()))
        .await
}

#[derive(Debug)]
pub enum DispatchOutcome {
    CommittedToLedger(serde_json::Value),
    AbsorbedByGhostNode(SinkReceipt),
}
