#!/usr/bin/env python3
"""
Quantum Flex: Edge Privacy & Opt-Out Enforcement Filter
======================================================
Compliance Standard: CCPA/CPRA & Global Privacy Guidelines
Ensures that any wireless broadcast containing `_optout` or `_nomap`
is dropped at the edge before hashing, encryption, or database persistence.
"""

import re
from typing import Dict, Any, Optional

# Case-insensitive pattern matching standard privacy opt-out tags
OPTOUT_PATTERN = re.compile(r'(_optout|_nomap)', re.IGNORECASE)

class PrivacyFilter:
    @staticmethod
    def should_exclude_ssid(ssid: str) -> bool:
        """Returns True if the SSID contains an opt-out or nomap privacy tag."""
        if not ssid or not isinstance(ssid, str):
            return False
        return bool(OPTOUT_PATTERN.search(ssid))

    @classmethod
    def sanitize_telemetry_frame(cls, frame: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Evaluates a raw telemetry frame.
        Returns the sanitized frame if compliant, or None if the frame is dropped.
        """
        ssid = frame.get("ssid", "")
        if cls.should_exclude_ssid(ssid):
            return None
        return frame
