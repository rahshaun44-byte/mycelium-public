use axum::{
    extract::{DefaultBodyLimit, State},
    http::StatusCode,
    response::Json,
    routing::{get, post},
    Router,
};
use quantumflex_ghost_sink::{
    default_storage_dir, refuse_unbound_listen, AnomalyIngressPayload, IngestResponse, Ledger,
    SinkError,
};
use std::{
    env,
    net::SocketAddr,
    path::PathBuf,
    sync::Arc,
    time::{SystemTime, UNIX_EPOCH},
};
use tokio::sync::Mutex;
use tower_http::trace::TraceLayer;
use tracing::{error, info};

#[derive(Clone)]
struct AppState {
    ledger: Arc<Mutex<Ledger>>,
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info,quantumflex_ghost_sink=debug".into()),
        )
        .init();

    let listen_addr_str =
        env::var("SINK_LISTEN_ADDR").unwrap_or_else(|_| "127.0.0.1:19443".to_string());
    let allow_unbound = env::var("SINK_ALLOW_UNBOUND")
        .map(|v| v == "1" || v.eq_ignore_ascii_case("true"))
        .unwrap_or(false);
    if let Err(e) = refuse_unbound_listen(&listen_addr_str, allow_unbound) {
        panic!("{e}");
    }

    let max_bytes: usize = env::var("SINK_MAX_PAYLOAD_BYTES")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(10 * 1024 * 1024);

    let storage_dir = default_storage_dir();
    std::fs::create_dir_all(&storage_dir)
        .unwrap_or_else(|e| panic!("Failed to initialize storage path {:?}: {e}", storage_dir));

    let log_file_path: PathBuf = storage_dir.join("entropy_sink_ledger.jsonl");
    let ledger = Ledger::recover(&log_file_path).unwrap_or_else(|e| {
        panic!("Ghost sink ledger recovery failed (fail-closed): {e}");
    });

    info!(
        target: "quantumflex::sink",
        "Initialized Ghost Node sink. Storage file: {:?}. Starting Sequence: {}, Prior Hash: {}",
        log_file_path,
        ledger.last_sequence(),
        hex::encode(ledger.last_record_hash())
    );

    let state = AppState {
        ledger: Arc::new(Mutex::new(ledger)),
    };

    let app = router(state, max_bytes);

    let addr: SocketAddr = listen_addr_str
        .parse()
        .unwrap_or_else(|e| panic!("Invalid listen address '{listen_addr_str}': {e}"));

    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .unwrap_or_else(|e| panic!("Binding TCP listener on {addr} failed: {e}"));

    info!(
        target: "quantumflex::sink",
        "Ghost Node absorption receiver listening on http://{addr} (not engine mTLS :9443)"
    );

    if let Err(e) = axum::serve(listener, app).await {
        error!(target: "quantumflex::sink", "Server fatal runtime failure: {e}");
    }
}

fn router(state: AppState, max_bytes: usize) -> Router {
    Router::new()
        .route("/healthz", get(healthcheck))
        .route("/v1/sink/anomaly", post(ingest_anomaly))
        .layer(TraceLayer::new_for_http())
        .layer(DefaultBodyLimit::max(max_bytes))
        .with_state(state)
}

async fn healthcheck() -> &'static str {
    "OK"
}

async fn ingest_anomaly(
    State(state): State<AppState>,
    Json(payload): Json<AnomalyIngressPayload>,
) -> Result<(StatusCode, Json<IngestResponse>), (StatusCode, String)> {
    let now_ns = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("Clock error: {e}"),
            )
        })?
        .as_nanos() as u64;

    let mut ledger = state.ledger.lock().await;
    match ledger.ingest(payload, now_ns) {
        Ok(response) => {
            info!(
                target: "quantumflex::sink",
                "Absorbed friction term (h). Seq: {}, Hash: {}",
                response.sequence_number,
                response.record_hash
            );
            Ok((StatusCode::CREATED, Json(response)))
        }
        Err(SinkError::BadEntropyAction(a)) => Err((
            StatusCode::BAD_REQUEST,
            format!("entropy_action rejected: {a}"),
        )),
        Err(e) => {
            error!(target: "quantumflex::sink", "Persistence failure: {e}");
            Err((
                StatusCode::INTERNAL_SERVER_ERROR,
                "Failed to write anomaly to append-only disk sink".to_string(),
            ))
        }
    }
}
