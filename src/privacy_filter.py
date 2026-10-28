#!/usr/bin/env python3
"""
Quantum Flex: Technical Opt-Out & Identifier Dropping Filter
============================================================
Technical Implementation: Industry Convention (_nomap / _optout)
Drops wireless broadcasts containing `_optout` or `_nomap` markers
at the edge prior to hashing, encryption, or database persistence.
Note: Legal applicability, ROPA, data inventory, and consumer rights
handling require distinct legal governance procedures.
"""

import re
import unicodedata
from typing import Dict, Any, Optional

# Case-insensitive pattern matching standard privacy opt-out tags across industry delimiters
# Delimiters: [_.-] or word boundary \b before nomap|optout, and [_.-], \b, or end of string after
OPTOUT_PATTERN = re.compile(r'([_.\-]|\b)(nomap|optout)(?=[_.\-]|\b|$)', re.IGNORECASE)

class PrivacyFilter:
    @staticmethod
    def should_exclude_ssid(ssid: str) -> bool:
        """Returns True if the SSID contains an opt-out or nomap privacy tag."""
        if not ssid or not isinstance(ssid, str):
            return False
        clean_ssid = unicodedata.normalize("NFKC", ssid).strip()
        return bool(OPTOUT_PATTERN.search(clean_ssid))

    @classmethod
    def contains_optout(cls, obj: Any) -> bool:
        """
        Recursively scans strings, dicts, lists, and tuples for privacy opt-out tags.
        Fails closed (returns True) on uninspectable or error-producing structures.
        """
        try:
            if isinstance(obj, str):
                clean_str = unicodedata.normalize("NFKC", obj).strip()
                return bool(OPTOUT_PATTERN.search(clean_str))
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(k, str):
                        clean_k = unicodedata.normalize("NFKC", k).strip()
                        if OPTOUT_PATTERN.search(clean_k):
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
