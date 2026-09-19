//! Edge-side Wi-Fi scan privacy filtering.
//!
//! Call [`prepare_telemetry`] on raw scan results before anonymizing identifiers,
//! signing packets, persisting records, or sending data to a gateway.

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

/// Exclude an SSID containing `_optout`, regardless of ASCII letter case.
///
/// The marker may appear anywhere in the name. An empty or hidden SSID has no
/// marker and is retained. This function does not apply the separate `_nomap`
/// convention.
pub fn should_exclude_ssid(ssid: &str) -> bool {
    ssid.as_bytes()
        .windows(b"_optout".len())
        .any(|window| window.eq_ignore_ascii_case(b"_optout"))
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
        for ssid in ["Home_optout", "_OPTOUT_Guest", "Cafe_OpToUt_5G"] {
            assert!(should_exclude_ssid(ssid), "{ssid}");
        }
    }

    #[test]
    fn retains_names_without_the_exact_marker() {
        for ssid in ["", "Home", "optout", "Home-optout", "Home_optou"] {
            assert!(!should_exclude_ssid(ssid), "{ssid}");
        }
    }

    #[test]
    fn removes_opted_out_scans_before_telemetry_construction() {
        let output = prepare_telemetry([scan("Private_OPTOUT"), scan("Public"), scan("Guest_optout")]);
        assert_eq!(output.len(), 1);
        assert_eq!(output[0].ssid, "Public");
        assert_eq!(output[0].bssid, "aa:bb:cc:dd:ee:ff");
    }
}
