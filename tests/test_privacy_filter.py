#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.privacy_filter import PrivacyFilter


class TestPrivacyFilter(unittest.TestCase):
    def test_optout_detection_standard(self):
        self.assertTrue(PrivacyFilter.should_exclude_ssid("HomeNetwork_optout"))
        self.assertTrue(PrivacyFilter.should_exclude_ssid("CoffeeShop_nomap"))
        self.assertTrue(PrivacyFilter.should_exclude_ssid("Office_OPTOUT_5G"))
        self.assertTrue(PrivacyFilter.should_exclude_ssid("Guest_NOMAP"))

    def test_multi_delimiter_variants(self):
        """Verifies industry delimiters (_ , - , .) and casing."""
        variants = [
            "Office-nomap",
            "Office-optout",
            "Guest.nomap",
            "Lab.optout",
            "Private_nomap_5G",
            "Mesh-OPTOUT-IoT",
            "nomap",
            "optout",
            "AP-NOMAP",
            "AP.OPTOUT",
            "   Padded_nomap   ",
        ]
        for v in variants:
            self.assertTrue(PrivacyFilter.should_exclude_ssid(v), f"Failed to exclude variant: {v}")
            self.assertTrue(PrivacyFilter.contains_optout(v))

    def test_unicode_normalization_and_whitespace(self):
        """Verifies that Unicode lookalikes and trailing/leading whitespace do not evade the filter."""
        self.assertTrue(PrivacyFilter.should_exclude_ssid("  CoffeeShop_nomap  "))
        self.assertTrue(PrivacyFilter.should_exclude_ssid("Cafe\u0301-nomap"))  # Decomposed unicode e + acute
        self.assertTrue(PrivacyFilter.should_exclude_ssid("Office_optout\u200b"))  # Zero-width space

    def test_false_positive_resistance_in_labels(self):
        """Labels with substrings that contain 'nomap' or 'optout' inside words must not trigger false positives."""
        compliant = [
            "nomaple_syrup",
            "adoption_center",
            "optical_outlet",
            "synopsis_nomad",
        ]
        for c in compliant:
            self.assertFalse(PrivacyFilter.should_exclude_ssid(c), f"False positive excluded: {c}")
            self.assertFalse(PrivacyFilter.contains_optout({"label": c}))

    def test_direct_identifiers_and_ambient_dropped(self):
        """Proves that direct wireless identifiers (SSID, BSSID, MAC) and ambient markers are completely dropped."""
        valid_operational_frame = {
            "node_id": "qfx-yoga",
            "cpu_load_1m": 0.12,
            "ram_used_pct": 45.0,
            "status": "PULSE_OK"
        }
        direct_ssid_frame = {"ssid": "Archer_BE3600_Pro", "rssi": -45}
        direct_bssid_frame = {"bssid": "AA:BB:CC:DD:EE:FF", "rssi": -45}
        optout_frame = {"network_name": "PrivateNetwork-nomap", "vendor": "SecretCam"}

        sanitized_valid = PrivacyFilter.sanitize_telemetry_frame(valid_operational_frame)
        self.assertIsNotNone(sanitized_valid)
        self.assertEqual(sanitized_valid["node_id"], "qfx-yoga")

        # Direct SSID / BSSID / opt-out frames must all be dropped to None
        self.assertIsNone(PrivacyFilter.sanitize_telemetry_frame(direct_ssid_frame))
        self.assertIsNone(PrivacyFilter.sanitize_telemetry_frame(direct_bssid_frame))
        self.assertIsNone(PrivacyFilter.sanitize_telemetry_frame(optout_frame))

    def test_zero_ambient_data_policy_invariants(self):
        """QuantumFlex core telemetry policy must explicitly disallow ambient scanning and neighbor collection."""
        policy = PrivacyFilter.POLICY
        self.assertFalse(policy["wifi_scanning_enabled"])
        self.assertFalse(policy["neighbor_network_collection_enabled"])
        self.assertFalse(policy["ssid_collection_enabled"])
        self.assertFalse(policy["bssid_collection_enabled"])
        self.assertFalse(policy["personal_data_collection_enabled"])
        self.assertTrue(policy["fail_closed"])

    def test_prohibited_ambient_identifiers_detection(self):
        """Payloads containing neighbor networks, direct SSIDs, ambient scans, or personal data must be detected."""
        prohibited_payloads = [
            {"ssid": "TargetAP"},
            {"bssid": "02:00:00:00:00:01"},
            {"mac_address": "00:11:22:33:44:55"},
            {"access_points": [{"name": "AP1"}]},
            {"nearby_aps": [{"signal": -50}]},
            {"wifi_networks": ["Net1", "Net2"]},
            {"scan_results": []},
            {"neighbor_networks": ["AP-1", "AP-2"]},
            {"wifi_scan": {"results": []}},
            {"telemetry": {"ambient_radio": True}},
            {"bssid_list": ["00:11:22:33:44:55"]},
            {"personal_data": {"user": "Alice"}},
            {"gps_track": {"lat": 40.0, "lon": -75.0}},
            {"imei": "123456789012345"},
            {"imsi": "310410123456789"},
            {"phone_number": "+12155550199"},
            {"email": "operator@example.com"},
        ]
        for p in prohibited_payloads:
            self.assertTrue(
                PrivacyFilter.contains_prohibited_ambient_data(p),
                f"Failed to detect prohibited ambient data in: {p}",
            )
            # Frame sanitization must immediately drop it
            self.assertIsNone(PrivacyFilter.sanitize_telemetry_frame(p))

    def test_case_and_delimiter_variation_normalization(self):
        """Proves that casing, underscores, hyphens, and mixed delimiters cannot evade prohibited checks."""
        evasion_attempts = [
            {"SSID": "Hidden_AP"},
            {"BSSID": "00:11:22:33:44:55"},
            {"MAC_ADDRESS": "AA:BB:CC:DD:EE:FF"},
            {"Nearby-APs": ["AP-A"]},
            {"nearby_aps": ["AP-B"]},
            {"NEARBYAPS": ["AP-C"]},
            {"Access_Points": ["AP-D"]},
            {"access-points": ["AP-E"]},
            {"WiFi_Networks": ["Net-A"]},
            {"Scan_Results": ["Result-A"]},
            {"Personal_Data": {"pii": True}},
        ]
        for attempt in evasion_attempts:
            self.assertTrue(
                PrivacyFilter.contains_prohibited_ambient_data(attempt),
                f"Evasion attempt bypassed normalization: {attempt}",
            )
            self.assertIsNone(PrivacyFilter.sanitize_telemetry_frame(attempt))

    def test_deep_nesting_fails_closed(self):
        """Excessively nested objects (> 10 depth) must fail closed as prohibited/uninspectable."""
        nested = {"level_1": {"level_2": {"level_3": {"level_4": {"level_5": {"level_6": {"level_7": {"level_8": {"level_9": {"level_10": {"level_11": "deep"}}}}}}}}}}}
        self.assertTrue(PrivacyFilter.contains_prohibited_ambient_data(nested))

    def test_pure_host_operational_vitals_permitted(self):
        """Legitimate host vitals (CPU load, RAM, thermals, PQC state) must pass through safely."""
        pure_vitals = {
            "node_id": "qfx-yoga",
            "cpu_load_1m": 0.15,
            "ram_used_pct": 42.5,
            "temp_c": 38.0,
            "pqc_kem": "ML-KEM-768",
            "status": "PULSE_OK",
        }
        self.assertFalse(PrivacyFilter.contains_prohibited_ambient_data(pure_vitals))
        self.assertFalse(PrivacyFilter.contains_optout(pure_vitals))
        sanitized = PrivacyFilter.sanitize_telemetry_frame(pure_vitals)
        self.assertIsNotNone(sanitized)
        self.assertEqual(sanitized["node_id"], "qfx-yoga")

    def test_strictly_authorized_operational_allowlist(self):
        """Verifies that only documented, authorized operational fields pass the allowlist gate."""
        approved = {
            "node_id": "qfx-yoga",
            "timestamp": 1700000000,
            "cpu_load_1m": 0.12,
            "ram_used_pct": 45.0,
            "temp_c": 39.5,
            "configured_kem": "ML-KEM-768",
            "tpm": {"device_available": True, "attestation_status": "VERIFIED"},
            "status": "PULSE_OK",
        }
        self.assertTrue(PrivacyFilter.is_strictly_authorized_operational_data(approved))

        # Unknown or foreign sensor attributes must fail the allowlist
        unauthorized_inputs = [
            {"node_id": "qfx-yoga", "ambient_light_lux": 450},
            {"node_id": "qfx-yoga", "nearby_devices": ["dev-1"]},
            {"node_id": "qfx-yoga", "microphone_volume": 12},
            {"node_id": "qfx-yoga", "camera_detected": True},
        ]
        for unauth in unauthorized_inputs:
            self.assertFalse(
                PrivacyFilter.is_strictly_authorized_operational_data(unauth),
                f"Unauthorized attribute slipped through allowlist: {unauth}",
            )


if __name__ == "__main__":
    unittest.main()

