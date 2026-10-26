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
    def contains_optout(cls, obj: Any) -> bool:
        """
        Recursively scans strings, dicts, lists, and tuples for privacy opt-out tags.
        Fails closed (returns True) on uninspectable or error-producing structures.
        """
        try:
            if isinstance(obj, str):
                return bool(OPTOUT_PATTERN.search(obj))
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(k, str) and OPTOUT_PATTERN.search(k):
                        return True
                    if cls.contains_optout(v):
                        return True
            elif isinstance(obj, (list, tuple, set)):
                for item in obj:
                    if cls.contains_optout(item):
                        return True
            return False
        except Exception:
            # Fail closed: treat exceptions during inspection as potential opt-out violations
            return True

    @classmethod
    def sanitize_telemetry_frame(cls, frame: Any) -> Optional[Dict[str, Any]]:
        """
        Evaluates a raw telemetry frame.
        Returns the sanitized frame if compliant, or None if the frame is dropped.
        Fails closed on non-dict structures, nested opt-out markers, or unexpected exceptions.
        """
        try:
            if not isinstance(frame, dict):
                return None
            ssid = frame.get("ssid", "")
            if cls.should_exclude_ssid(ssid):
                return None
            if cls.contains_optout(frame):
                return None
            return frame
        except Exception:
            # Fail-closed: any sanitizer exception prevents downstream processing
            return None
