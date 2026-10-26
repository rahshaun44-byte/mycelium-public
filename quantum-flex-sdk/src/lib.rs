//! Edge-side Wi-Fi scan privacy filtering and persistence.
//!
//! Call [`prepare_telemetry`] or [`persist_telemetry`] on raw scan results
//! before anonymizing identifiers, signing packets, persisting records,
//! or sending data to a gateway.
//!
//! Complies with CCPA/CPRA, Google/Mozilla Wi-Fi opt-out conventions, and
//! global edge privacy standards by excluding any network whose SSID contains
//! `_optout` or `_nomap` (case-insensitive).

use std::io::Write;

/// A Wi-Fi observation before privacy processing.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ScanResult {
    pub ssid: String,
    pub bssid: String,
    pub rssi_dbm: i32,
}

/// A filtered observation ready for the next telemetry processing step.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TelemetryObservation {
    pub ssid: String,
    pub bssid: String,
    pub rssi_dbm: i32,
}

/// Exclude an SSID containing `_optout` or `_nomap`, regardless of ASCII letter case.
///
/// The marker may appear anywhere in the name. An empty or hidden SSID has no
/// marker and is retained. Both `_optout` and `_nomap` conventions are enforced
/// in strict compliance with CCPA/CPRA and global Wi-Fi mapping opt-out standards.
pub fn should_exclude_ssid(ssid: &str) -> bool {
    let bytes = ssid.as_bytes();
    bytes
        .windows(b"_optout".len())
        .any(|window| window.eq_ignore_ascii_case(b"_optout"))
        || bytes
            .windows(b"_nomap".len())
            .any(|window| window.eq_ignore_ascii_case(b"_nomap"))
}

/// Drop opted-out observations before they become telemetry records.
pub fn prepare_telemetry(scans: impl IntoIterator<Item = ScanResult>) -> Vec<TelemetryObservation> {
    scans
        .into_iter()
        .filter(|scan| !should_exclude_ssid(&scan.ssid))
        .map(|scan| TelemetryObservation {
            ssid: scan.ssid,
            bssid: scan.bssid,
            rssi_dbm: scan.rssi_dbm,
        })
        .collect()
}

/// A persistence sink for filtered telemetry observations.
pub trait TelemetryStore {
    type Error;

    /// Commit filtered observations to persistent storage.
    fn persist(&mut self, observations: &[TelemetryObservation]) -> Result<usize, Self::Error>;
}

/// Live persistence caller that filters raw Wi-Fi scan results through [`prepare_telemetry`]
/// and commits only compliant observations to the provided persistence store.
///
/// Any scans containing `_optout` or `_nomap` in their SSID are excluded at the edge
/// prior to persistence, ensuring zero leakage of opted-out identifiers into databases or ledgers.
pub fn persist_telemetry<S: TelemetryStore>(
    scans: impl IntoIterator<Item = ScanResult>,
    store: &mut S,
) -> Result<usize, S::Error> {
    let compliant = prepare_telemetry(scans);
    if compliant.is_empty() {
        return Ok(0);
    }
    store.persist(&compliant)
}

/// In-memory telemetry storage for buffering and testing.
#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct InMemoryStore {
    pub records: Vec<TelemetryObservation>,
}

impl InMemoryStore {
    pub fn new() -> Self {
        Self {
            records: Vec::new(),
        }
    }

    pub fn len(&self) -> usize {
        self.records.len()
    }

    pub fn is_empty(&self) -> bool {
        self.records.is_empty()
    }
}

impl TelemetryStore for InMemoryStore {
    type Error = std::io::Error;

    fn persist(&mut self, observations: &[TelemetryObservation]) -> Result<usize, Self::Error> {
        for obs in observations {
            if should_exclude_ssid(&obs.ssid) {
                return Err(std::io::Error::new(
                    std::io::ErrorKind::PermissionDenied,
                    "Privacy opt-out violation: observation contains opt-out/nomap SSID",
                ));
            }
        }
        let count = observations.len();
        self.records.extend_from_slice(observations);
        Ok(count)
    }
}

/// Live append-only JSON Lines stream persistence sink.
///
/// Writes compliant observations to any standard writer (file, socket, pipe)
/// without third-party runtime dependencies.
pub struct JsonLinesStore<W: Write> {
    writer: W,
}

impl<W: Write> JsonLinesStore<W> {
    pub fn new(writer: W) -> Self {
        Self { writer }
    }

    pub fn into_inner(self) -> W {
        self.writer
    }
}

impl<W: Write> TelemetryStore for JsonLinesStore<W> {
    type Error = std::io::Error;

    fn persist(&mut self, observations: &[TelemetryObservation]) -> Result<usize, Self::Error> {
        let mut count = 0;
        for obs in observations {
            if should_exclude_ssid(&obs.ssid) {
                return Err(std::io::Error::new(
                    std::io::ErrorKind::PermissionDenied,
                    "Privacy opt-out violation: observation contains opt-out/nomap SSID",
                ));
            }
            writeln!(
                self.writer,
                r#"{{"ssid":"{}","bssid":"{}","rssi_dbm":{}}}"#,
                escape_json_str(&obs.ssid),
                escape_json_str(&obs.bssid),
                obs.rssi_dbm
            )?;
            count += 1;
        }
        self.writer.flush()?;
        Ok(count)
    }
}

/// Helper function to escape JSON string characters without external dependencies.
fn escape_json_str(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            other => out.push(other),
        }
    }
    out
}

/// Live convenience persistence caller that opens (or creates) an append-only JSONL
/// file on disk, filters raw scans, and appends compliant records.
pub fn persist_to_jsonl_file<P: AsRef<std::path::Path>>(
    scans: impl IntoIterator<Item = ScanResult>,
    file_path: P,
) -> std::io::Result<usize> {
    let file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(file_path)?;
    let mut store = JsonLinesStore::new(file);
    persist_telemetry(scans, &mut store)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn scan(ssid: &str) -> ScanResult {
        ScanResult {
            ssid: ssid.into(),
            bssid: "aa:bb:cc:dd:ee:ff".into(),
            rssi_dbm: -48,
        }
    }

    #[test]
    fn detects_marker_anywhere_without_case_sensitivity() {
        for ssid in [
            "Home_optout",
            "_OPTOUT_Guest",
            "Cafe_OpToUt_5G",
            "CoffeeShop_nomap",
            "Guest_NOMAP",
            "_NoMaP_Lab",
        ] {
            assert!(should_exclude_ssid(ssid), "{ssid}");
        }
    }

    #[test]
    fn retains_names_without_the_exact_marker() {
        for ssid in ["", "Home", "optout", "nomap", "Home-optout", "Home-nomap", "Home_optou"] {
            assert!(!should_exclude_ssid(ssid), "{ssid}");
        }
    }

    #[test]
    fn removes_opted_out_scans_before_telemetry_construction() {
        let output = prepare_telemetry([
            scan("Private_OPTOUT"),
            scan("Public"),
            scan("Guest_optout"),
            scan("Office_nomap"),
            scan("CoffeeShop_NOMAP"),
        ]);
        assert_eq!(output.len(), 1);
        assert_eq!(output[0].ssid, "Public");
        assert_eq!(output[0].bssid, "aa:bb:cc:dd:ee:ff");
    }

    #[test]
    fn persist_telemetry_drops_optout_and_nomap_before_store() {
        let mut store = InMemoryStore::new();
        let scans = vec![
            scan("Valid_Mesh_1"),
            scan("Neighbor_optout"),
            scan("Valid_Mesh_2"),
            scan("Private_nomap"),
        ];

        let count = persist_telemetry(scans, &mut store).expect("persist failed");
        assert_eq!(count, 2);
        assert_eq!(store.len(), 2);
        assert_eq!(store.records[0].ssid, "Valid_Mesh_1");
        assert_eq!(store.records[1].ssid, "Valid_Mesh_2");
    }

    #[test]
    fn persist_telemetry_empty_when_all_opted_out() {
        let mut store = InMemoryStore::new();
        let scans = vec![scan("A_optout"), scan("B_nomap")];

        let count = persist_telemetry(scans, &mut store).expect("persist failed");
        assert_eq!(count, 0);
        assert!(store.is_empty());
    }

    #[test]
    fn json_lines_store_persists_formatted_records() {
        let mut buffer = Vec::new();
        let mut store = JsonLinesStore::new(&mut buffer);

        let scans = vec![
            scan("Valid_AP"),
            scan("Ignore_nomap"),
        ];

        let count = persist_telemetry(scans, &mut store).expect("persist failed");
        assert_eq!(count, 1);

        let output = String::from_utf8(buffer).expect("valid utf8");
        assert_eq!(
            output.trim(),
            r#"{"ssid":"Valid_AP","bssid":"aa:bb:cc:dd:ee:ff","rssi_dbm":-48}"#
        );
    }

    #[test]
    fn persist_to_jsonl_file_writes_and_appends() {
        let temp_dir = std::env::temp_dir();
        let test_file = temp_dir.join("qfx_sdk_test_telemetry.jsonl");
        let _ = std::fs::remove_file(&test_file);

        let scans = vec![
            scan("Network_Alpha"),
            scan("Network_optout"),
            scan("Network_nomap"),
            scan("Network_Beta"),
        ];

        let written = persist_to_jsonl_file(scans, &test_file).expect("write failed");
        assert_eq!(written, 2);

        let content = std::fs::read_to_string(&test_file).expect("read failed");
        let lines: Vec<&str> = content.lines().collect();
        assert_eq!(lines.len(), 2);
        assert!(lines[0].contains("Network_Alpha"));
        assert!(lines[1].contains("Network_Beta"));

        let _ = std::fs::remove_file(&test_file);
    }

    #[test]
    fn direct_store_persist_rejects_unvetted_observations() {
        let unvetted = TelemetryObservation {
            ssid: "Secret_optout".into(),
            bssid: "11:22:33:44:55:66".into(),
            rssi_dbm: -50,
        };

        let mut in_mem = InMemoryStore::new();
        let res_mem = in_mem.persist(&[unvetted.clone()]);
        assert!(res_mem.is_err(), "InMemoryStore must reject opted-out observation");
        assert!(in_mem.is_empty(), "InMemoryStore must not retain opted-out observation");

        let mut buf = Vec::new();
        let mut jl = JsonLinesStore::new(&mut buf);
        let res_jl = jl.persist(&[unvetted]);
        assert!(res_jl.is_err(), "JsonLinesStore must reject opted-out observation");
        assert!(buf.is_empty(), "JsonLinesStore must not write opted-out observation");
    }
}

