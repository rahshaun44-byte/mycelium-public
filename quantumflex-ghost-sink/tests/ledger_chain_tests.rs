use quantumflex_ghost_sink::{
    default_storage_dir, refuse_unbound_listen, AnomalyIngressPayload, Ledger,
    REQUIRED_ENTROPY_ACTION,
};
use serde_json::json;

fn sample_payload() -> AnomalyIngressPayload {
    AnomalyIngressPayload {
        node_uuid: "3a0627e7-b6f7-4a73-9ef6-ec572cf93b21".into(),
        timestamp_epoch_nonce: "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
            .into(),
        pcr_integrity_pass: false,
        nonce_freshness_pass: true,
        structural_anomaly: Some(json!({
            "reason": "PCR 10 hardware digest mismatch - hash chain broken"
        })),
        execution_violations: vec![json!({
            "file_path": "/tmp/unauthorized_agent",
            "reason": "Binary path not present in golden manifest"
        })],
        raw_records_count: 1,
        entropy_action: REQUIRED_ENTROPY_ACTION.into(),
        raw_telemetry_dump: None,
        h_attack: 0,
    }
}

#[test]
fn hash_chain_survives_restart() {
    let dir = std::env::temp_dir().join(format!("qf-sink-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("entropy_sink_ledger.jsonl");

    let mut ledger = Ledger::recover(&path).unwrap();
    let r1 = ledger.ingest(sample_payload(), 1).unwrap();
    let r2 = ledger.ingest(sample_payload(), 2).unwrap();
    assert_eq!(r1.sequence_number, 1);
    assert_eq!(r2.sequence_number, 2);
    assert_ne!(r1.record_hash, r2.record_hash);
    assert_eq!(r1.status, "ABSORBED");

    let recovered = Ledger::recover(&path).unwrap();
    assert_eq!(recovered.last_sequence(), 2);
    assert_eq!(recovered.last_record_hash(), ledger.last_record_hash());
    let _ = std::fs::remove_dir_all(&dir);
}

#[test]
fn broken_chain_fail_closes() {
    let dir = std::env::temp_dir().join(format!("qf-sink-break-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("entropy_sink_ledger.jsonl");
    let mut ledger = Ledger::recover(&path).unwrap();
    ledger.ingest(sample_payload(), 1).unwrap();
    std::fs::write(&path, "{not json}\n").unwrap();
    let err = Ledger::recover(&path).unwrap_err();
    assert!(err.to_string().contains("serialization") || err.to_string().contains("broken"));
    let _ = std::fs::remove_dir_all(&dir);
}

#[test]
fn reject_wrong_entropy_action() {
    let dir = std::env::temp_dir().join(format!("qf-sink-act-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&dir);
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join("entropy_sink_ledger.jsonl");
    let mut ledger = Ledger::recover(&path).unwrap();
    let mut payload = sample_payload();
    payload.entropy_action = "CREDIT_AS_KEM_ENTROPY".into();
    let err = ledger.ingest(payload, 1).unwrap_err();
    assert!(err.to_string().contains("entropy_action"));
    let _ = std::fs::remove_dir_all(&dir);
}

#[test]
fn refuse_unbound_listen_without_opt_in() {
    assert!(refuse_unbound_listen("0.0.0.0:9443", false).is_err());
    assert!(refuse_unbound_listen("0.0.0.0:19443", true).is_ok());
    assert!(refuse_unbound_listen("127.0.0.1:19443", false).is_ok());
}

#[test]
fn default_storage_is_not_engine_log_dir() {
    std::env::remove_var("SINK_STORAGE_PATH");
    let path = default_storage_dir();
    let rendered = path.to_string_lossy();
    assert!(
        rendered.contains("ghost_sink") || rendered.contains("quantumflex/sink"),
        "{rendered}"
    );
}
