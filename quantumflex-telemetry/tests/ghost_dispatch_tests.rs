use axum::{routing::post, Json, Router};
use quantumflex_telemetry::dispatch::ghost_dispatcher::{
    DispatchError, DispatchOutcome, GatekeeperDispatcher, GhostNodeManifest, GhostSinkConfig,
    OpaGatekeeperResult,
};
use serde_json::json;
use std::net::SocketAddr;
use std::sync::{
    atomic::{AtomicU32, Ordering},
    Arc,
};
use std::time::Duration;
use tokio::net::TcpListener;

async fn mock_sink_handler(
    Json(_payload): Json<GhostNodeManifest>,
) -> (axum::http::StatusCode, Json<serde_json::Value>) {
    (
        axum::http::StatusCode::CREATED,
        Json(json!({
            "status": "ABSORBED",
            "sequence_number": 42,
            "payload_sha256": "abcdef123456",
            "record_hash": "deadbeef9876"
        })),
    )
}

fn sample_ghost_manifest() -> GhostNodeManifest {
    GhostNodeManifest {
        node_uuid: "test-node-uuid".to_string(),
        timestamp_epoch_nonce: "test-nonce".to_string(),
        pcr_integrity_pass: false,
        nonce_freshness_pass: true,
        structural_anomaly: Some(json!({"reason": "pcr mismatch"})),
        execution_violations: vec![],
        raw_records_count: 1,
        entropy_action: "ABSORB_INTO_GHOST_SINK".to_string(),
        raw_telemetry_dump: None,
        h_attack: 0,
    }
}

async fn spawn_mock(app: Router) -> SocketAddr {
    let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move {
        axum::serve(listener, app).await.unwrap();
    });
    addr
}

fn dispatcher_for(addr: SocketAddr) -> GatekeeperDispatcher {
    let config = GhostSinkConfig {
        endpoint_url: format!("http://{addr}/v1/sink/anomaly"),
        request_timeout: Duration::from_millis(500),
        max_retries: 3,
        initial_retry_delay: Duration::from_millis(10),
    };
    GatekeeperDispatcher::new(config).unwrap()
}

#[tokio::test]
async fn test_anomaly_routed_to_ghost_sink() {
    let app = Router::new().route("/v1/sink/anomaly", post(mock_sink_handler));
    let addr = spawn_mock(app).await;
    let dispatcher = dispatcher_for(addr);

    let decision = OpaGatekeeperResult {
        allow: false,
        route_to_ghost: true,
        ledger_commit_manifest: None,
        ghost_node_manifest: Some(sample_ghost_manifest()),
    };

    let outcome = dispatcher.dispatch_verdict(decision, None).await.unwrap();
    match outcome {
        DispatchOutcome::AbsorbedByGhostNode(receipt) => {
            assert_eq!(receipt.status, "ABSORBED");
            assert_eq!(receipt.sequence_number, 42);
        }
        _ => panic!("Expected anomaly to be absorbed by Ghost Node"),
    }
}

#[tokio::test]
async fn test_allow_commits_ledger_and_never_posts() {
    let hits = Arc::new(AtomicU32::new(0));
    let hits_h = hits.clone();
    let app = Router::new().route(
        "/v1/sink/anomaly",
        post(move |Json(_p): Json<GhostNodeManifest>| {
            let hits_h = hits_h.clone();
            async move {
                hits_h.fetch_add(1, Ordering::SeqCst);
                (
                    axum::http::StatusCode::CREATED,
                    Json(json!({
                        "status": "ABSORBED",
                        "sequence_number": 1,
                        "payload_sha256": "00",
                        "record_hash": "00"
                    })),
                )
            }
        }),
    );
    let addr = spawn_mock(app).await;
    let dispatcher = dispatcher_for(addr);
    let decision = OpaGatekeeperResult {
        allow: true,
        route_to_ghost: false,
        ledger_commit_manifest: Some(json!({"status": "DETERMINISTIC_INVARIANT_PRESERVED"})),
        ghost_node_manifest: None,
    };
    match dispatcher.dispatch_verdict(decision, None).await.unwrap() {
        DispatchOutcome::CommittedToLedger(v) => {
            assert_eq!(v["status"], "DETERMINISTIC_INVARIANT_PRESERVED");
        }
        _ => panic!("expected ledger commit"),
    }
    assert_eq!(hits.load(Ordering::SeqCst), 0);
}

#[tokio::test]
async fn test_overlap_is_rejected() {
    let dispatcher = dispatcher_for("127.0.0.1:1".parse().unwrap());
    let decision = OpaGatekeeperResult {
        allow: true,
        route_to_ghost: true,
        ledger_commit_manifest: Some(json!({})),
        ghost_node_manifest: Some(sample_ghost_manifest()),
    };
    let err = dispatcher
        .dispatch_verdict(decision, None)
        .await
        .unwrap_err();
    assert!(matches!(err, DispatchError::Overlap));
}

#[tokio::test]
async fn test_retry_on_server_error_then_absorb() {
    let hits = Arc::new(AtomicU32::new(0));
    let hits_h = hits.clone();
    let app = Router::new().route(
        "/v1/sink/anomaly",
        post(move |Json(_p): Json<GhostNodeManifest>| {
            let hits_h = hits_h.clone();
            async move {
                let n = hits_h.fetch_add(1, Ordering::SeqCst) + 1;
                if n == 1 {
                    return (
                        axum::http::StatusCode::SERVICE_UNAVAILABLE,
                        Json(json!({"error": "backpressure"})),
                    );
                }
                (
                    axum::http::StatusCode::CREATED,
                    Json(json!({
                        "status": "ABSORBED",
                        "sequence_number": 7,
                        "payload_sha256": "aa",
                        "record_hash": "bb"
                    })),
                )
            }
        }),
    );
    let addr = spawn_mock(app).await;
    let dispatcher = dispatcher_for(addr);
    let decision = OpaGatekeeperResult {
        allow: false,
        route_to_ghost: true,
        ledger_commit_manifest: None,
        ghost_node_manifest: Some(sample_ghost_manifest()),
    };
    match dispatcher.dispatch_verdict(decision, None).await.unwrap() {
        DispatchOutcome::AbsorbedByGhostNode(r) => assert_eq!(r.sequence_number, 7),
        _ => panic!("expected absorb after retry"),
    }
    assert_eq!(hits.load(Ordering::SeqCst), 2);
}
