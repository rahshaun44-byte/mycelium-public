use quantumflex_telemetry::{
    GatekeeperTelemetryInput, ImaEntry, PcrReplayEngine, ReplayError, PCR10_INDEX,
};
use sha2::{Digest, Sha256};

fn compute_sha256(data: &[u8]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(data);
    hasher.finalize().into()
}

fn ascii_line(template_name: &str, template: [u8; 32], file_hash: [u8; 32], path: &str) -> String {
    format!(
        "10 {} {template_name} sha256:{} {path}",
        hex::encode(template),
        hex::encode(file_hash)
    )
}

#[test]
fn test_clean_pcr_replay_success() {
    let initial_pcr = [0u8; 32];
    let template_1 = compute_sha256(b"init_template");
    let template_2 = compute_sha256(b"systemd_exec");

    let entry1 = ImaEntry {
        pcr: 10,
        template_hash: template_1,
        template_name: "ima-ng".to_string(),
        file_hash_algorithm: "sha256".to_string(),
        file_hash: compute_sha256(b"/usr/lib/systemd/systemd"),
        file_path: "/usr/lib/systemd/systemd".to_string(),
    };

    let entry2 = ImaEntry {
        pcr: 10,
        template_hash: template_2,
        template_name: "ima-ng".to_string(),
        file_hash_algorithm: "sha256".to_string(),
        file_hash: compute_sha256(b"/usr/bin/quantumflex-relay"),
        file_path: "/usr/bin/quantumflex-relay".to_string(),
    };

    let entries = vec![entry1, entry2];
    let computed = PcrReplayEngine::replay_pcr10(initial_pcr, &entries);

    let mut h1 = Sha256::new();
    h1.update(initial_pcr);
    h1.update(template_1);
    let step1: [u8; 32] = h1.finalize().into();

    let mut h2 = Sha256::new();
    h2.update(step1);
    h2.update(template_2);
    let expected: [u8; 32] = h2.finalize().into();

    assert_eq!(computed, expected);
}

#[test]
fn test_anomaly_detection_on_tampered_quote() {
    let initial_pcr = [0u8; 32];
    let template_1 = compute_sha256(b"legitimate_entry");

    let entry = ImaEntry {
        pcr: 10,
        template_hash: template_1,
        template_name: "ima-ng".to_string(),
        file_hash_algorithm: "sha256".to_string(),
        file_hash: compute_sha256(b"/usr/bin/python3"),
        file_path: "/usr/bin/python3".to_string(),
    };

    let entries = vec![entry];
    let computed = PcrReplayEngine::replay_pcr10(initial_pcr, &entries);
    let fabricated_tpm_quote_digest = [0xFFu8; 32];

    assert_ne!(computed, fabricated_tpm_quote_digest);
}

#[test]
fn parse_ima_ng_and_ima_sig_paths() {
    let template = compute_sha256(b"tmpl");
    let file_hash = compute_sha256(b"/usr/bin/true");
    let ng = ascii_line("ima-ng", template, file_hash, "/usr/bin/true");
    let entry = PcrReplayEngine::parse_ascii_line(&ng).expect("ima-ng");
    assert_eq!(entry.pcr, PCR10_INDEX);
    assert_eq!(entry.template_name, "ima-ng");
    assert_eq!(entry.file_path, "/usr/bin/true");
    assert_eq!(entry.template_hash, template);
    assert_eq!(entry.file_hash, file_hash);

    let sig_line = format!(
        "10 {} ima-sig sha256:{} /usr/bin/true {}",
        hex::encode(template),
        hex::encode(file_hash),
        "aa".repeat(32)
    );
    let sig = PcrReplayEngine::parse_ascii_line(&sig_line).expect("ima-sig");
    assert_eq!(sig.file_path, "/usr/bin/true");
    assert_eq!(sig.template_name, "ima-sig");
}

#[test]
fn reject_non_pcr10_and_sha1_template_hash() {
    let file_hash = hex::encode(compute_sha256(b"f"));
    let sha256_th = hex::encode(compute_sha256(b"t"));
    let bad_pcr = format!("11 {sha256_th} ima-ng sha256:{file_hash} /bin/true");
    match PcrReplayEngine::parse_ascii_line(&bad_pcr) {
        Err(ReplayError::InvalidPcrIndex(11)) => {}
        other => panic!("expected InvalidPcrIndex, got {other:?}"),
    }

    let sha1_th = "aa".repeat(20);
    let sha1_line = format!("10 {sha1_th} ima-ng sha256:{file_hash} /bin/true");
    match PcrReplayEngine::parse_ascii_line(&sha1_line) {
        Err(ReplayError::MalformedTemplateHash(msg)) => {
            assert!(msg.contains("32-byte"), "{msg}");
        }
        other => panic!("expected MalformedTemplateHash, got {other:?}"),
    }
}

#[test]
fn verify_prepares_h_on_mismatch_and_omits_anomaly_on_clean() {
    let template = compute_sha256(b"init_template");
    let file_hash = compute_sha256(b"/usr/lib/systemd/systemd");
    let line = ascii_line("ima-ng", template, file_hash, "/usr/lib/systemd/systemd");
    let expected = PcrReplayEngine::replay_pcr10(
        [0u8; 32],
        &[ImaEntry {
            pcr: 10,
            template_hash: template,
            template_name: "ima-ng".into(),
            file_hash_algorithm: "sha256".into(),
            file_hash,
            file_path: "/usr/lib/systemd/systemd".into(),
        }],
    );

    let clean =
        PcrReplayEngine::verify_and_prepare_opa_input("node-a", b"nonce-1", &line, expected);
    assert!(clean.pcr_matches);
    assert!(clean.anomaly.is_none());
    assert_eq!(clean.ima_records.len(), 1);
    let json = clean.to_opa_json().expect("json");
    assert!(!json.contains("\"anomaly\""), "{json}");

    let dirty =
        PcrReplayEngine::verify_and_prepare_opa_input("node-a", b"nonce-1", &line, [0xFFu8; 32]);
    assert!(!dirty.pcr_matches);
    let anomaly = dirty.anomaly.expect("h");
    assert!(anomaly.reason.contains("hash chain broken"));
}

#[test]
fn empty_log_and_parse_failure_are_friction() {
    let empty: GatekeeperTelemetryInput =
        PcrReplayEngine::verify_and_prepare_opa_input("n", b"e", "\n", [0u8; 32]);
    assert!(empty
        .anomaly
        .expect("empty")
        .reason
        .contains("No IMA records"));

    let bad =
        PcrReplayEngine::verify_and_prepare_opa_input("n", b"e", "not-an-ima-line", [0u8; 32]);
    let reason = bad.anomaly.expect("parse").reason;
    assert!(reason.contains("Log parsing failure"), "{reason}");
}

#[test]
fn quote_pcr_digest_is_hash_of_selected_pcrs_not_the_pcr_itself() {
    let pcr10 = compute_sha256(b"pcr10-value");
    let digest = PcrReplayEngine::quote_pcr_digest(&[pcr10]);
    assert_ne!(digest, pcr10);
    assert_eq!(digest, compute_sha256(&pcr10));
}
