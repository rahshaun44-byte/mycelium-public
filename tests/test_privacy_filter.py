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

    def test_false_positive_resistance(self):
        """Standard networks with substrings that contain 'nomap' or 'optout' inside words must be preserved."""
        compliant = [
            "Starlink-WiFi",
            "Archer_BE3600_Pro",
            "QuantumFlex_Node_01",
            "nomaple_syrup",
            "adoption_center",
            "optical_outlet",
            "synopsis_nomad",
        ]
        for c in compliant:
            self.assertFalse(PrivacyFilter.should_exclude_ssid(c), f"False positive excluded: {c}")
            self.assertFalse(PrivacyFilter.contains_optout({"ssid": c}))

    def test_frame_sanitization_and_bssid_copurging(self):
        """Proves that when an opted-out frame is dropped, all co-located metadata (BSSID, RSSI) is purged."""
        valid_frame = {"ssid": "Archer_BE3600_Pro", "bssid": "AA:BB:CC:DD:EE:FF", "rssi": -45}
        optout_frame = {"ssid": "PrivateNetwork-nomap", "bssid": "11:22:33:44:55:66", "rssi": -70, "vendor": "SecretCam"}

        sanitized_valid = PrivacyFilter.sanitize_telemetry_frame(valid_frame)
        self.assertIsNotNone(sanitized_valid)
        self.assertEqual(sanitized_valid["bssid"], "AA:BB:CC:DD:EE:FF")

        # Entire frame object must be purged to None (no orphaned BSSID)
        sanitized_optout = PrivacyFilter.sanitize_telemetry_frame(optout_frame)
        self.assertIsNone(sanitized_optout)

if __name__ == "__main__":
    unittest.main()
