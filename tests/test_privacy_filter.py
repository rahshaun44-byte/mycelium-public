#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from src.privacy_filter import PrivacyFilter

class TestPrivacyFilter(unittest.TestCase):
    def test_optout_detection(self):
        self.assertTrue(PrivacyFilter.should_exclude_ssid("HomeNetwork_optout"))
        self.assertTrue(PrivacyFilter.should_exclude_ssid("CoffeeShop_nomap"))
        self.assertTrue(PrivacyFilter.should_exclude_ssid("Office_OPTOUT_5G"))
        self.assertTrue(PrivacyFilter.should_exclude_ssid("Guest_NOMAP"))

    def test_compliant_networks_allowed(self):
        self.assertFalse(PrivacyFilter.should_exclude_ssid("Starlink-WiFi"))
        self.assertFalse(PrivacyFilter.should_exclude_ssid("Archer_BE3600_Pro"))
        self.assertFalse(PrivacyFilter.should_exclude_ssid("QuantumFlex_Node_01"))

    def test_frame_sanitization(self):
        valid_frame = {"ssid": "Archer_BE3600_Pro", "bssid": "AA:BB:CC:DD:EE:FF", "rssi": -45}
        optout_frame = {"ssid": "PrivateNetwork_nomap", "bssid": "11:22:33:44:55:66", "rssi": -70}

        self.assertIsNotNone(PrivacyFilter.sanitize_telemetry_frame(valid_frame))
        self.assertIsNone(PrivacyFilter.sanitize_telemetry_frame(optout_frame))

if __name__ == "__main__":
    unittest.main()
