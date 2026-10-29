#!/usr/bin/env python3
"""
Quantum Flex: Technical Opt-Out & Identifier Dropping Filter
============================================================
Technical Implementation: Industry Convention (_nomap / _optout)
Zero Ambient Data Invariant: Prohibits ambient wireless discovery,
neighbor network collection, direct SSIDs/BSSIDs, MAC addresses,
and personal identifiers at the edge prior to hashing, encryption,
or database persistence.
"""

import json
import re
import unicodedata
from typing import Dict, Any, Optional

# Case-insensitive pattern matching standard privacy opt-out tags across industry delimiters
# Delimiters: [_.-] or word boundary \b before nomap|optout, and [_.-], \b, or end of string after
OPTOUT_PATTERN = re.compile(r'([_.\-]|\b)(nomap|optout)(?=[_.\-]|\b|$)', re.IGNORECASE)

# QuantumFlex Zero Ambient Data & Zero-Collection Policy
QUANTUMFLEX_TELEMETRY_POLICY = {
    "wifi_scanning_enabled": False,
    "neighbor_network_collection_enabled": False,
    "ssid_collection_enabled": False,
    "bssid_collection_enabled": False,
    "personal_data_collection_enabled": False,
    "raw_payload_logging_enabled": False,
    "fail_closed": True,
}

# Strict denylist of prohibited ambient discovery and device/personal identifiers
PROHIBITED_AMBIENT_FIELDS = {
    # Direct Wi-Fi identifiers
    "ssid",
    "bssid",
    "mac_address",
    "mac",
    "access_point",
    "access_points",
    "accesspoint",
    "accesspoints",
    "nearby_ap",
    "nearby_aps",
    "nearbyap",
    "nearbyaps",
    "wifi_network",
    "wifi_networks",
    "wifinetwork",
    "wifinetworks",
    "scan_result",
    "scan_results",
    "scanresult",
    "scanresults",
    "wireless_network",
    "wireless_networks",
    # Ambient discovery markers
    "neighbor_network",
    "neighbor_networks",
    "neighbor_ssid",
    "neighbor_ssids",
    "wifi_scan",
    "ambient_radio",
    "bssid_list",
    # Personal & cellular identifiers
    "personal_data",
    "gps_track",
    "user_identity",
    "contact_list",
    "imei",
    "imsi",
    "phone_number",
    "email",
}

# Strict Allowlist of permitted QuantumFlex host operational telemetry fields
ALLOWED_OPERATIONAL_FIELDS = {
    # Node identity and sequencing
    "node_id",
    "hostname",
    "timestamp",
    "seq",
    "signature",
    "public_key",
    "payload",
    "recorded_at",
    "created_at",
    "status",
    "note",
    "verdict",
    "event_type",
    "duration_ms",
    # Host hardware vitals
    "cpu_load_1m",
    "load_1m",
    "cpu_usage",
    "ram_used_pct",
    "ram_usage",
    "ram_total_mb",
    "ram_available_mb",
    "swap_usage",
    "swap_used_mb",
    "disk_usage",
    "iowait_pct",
    "temp_c",
    # Cryptographic & attestation state
    "configured_kem",
    "runtime_kem",
    "runtime_kem_verified",
    "cmvp_certificate",
    "tpm",
    "device_available",
    "pcr_bank",
    "pcr_selection",
    "quote_verified",
    "attestation_status",
    # Batch & envelope structures
    "frames",
    "data",
    "vitals",
    "metadata",
    "probe",
}


class PrivacyFilter:
    POLICY = QUANTUMFLEX_TELEMETRY_POLICY
    PROHIBITED_FIELDS = PROHIBITED_AMBIENT_FIELDS
    ALLOWED_FIELDS = ALLOWED_OPERATIONAL_FIELDS

    @classmethod
    def is_strictly_authorized_operational_data(cls, obj: Any, depth: int = 0) -> bool:
        """
        Validates that every field in a telemetry payload belongs to the authorized
        operational schema allowlist. Rejects any unexpected, untrusted, or ambient fields.
        """
        try:
            if depth > 10:
                return False
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if not isinstance(k, str) or k.lower() not in cls.ALLOWED_FIELDS:
                        return False
                    if isinstance(v, (dict, list, tuple, set)):
                        if not cls.is_strictly_authorized_operational_data(v, depth + 1):
                            return False
            elif isinstance(obj, (list, tuple, set)):
                for item in obj:
                    if isinstance(item, (dict, list, tuple, set)):
                        if not cls.is_strictly_authorized_operational_data(item, depth + 1):
                            return False
            return True
        except Exception:
            return False

    @staticmethod
    def normalize_key(k: str) -> str:
        """Strips all non-alphanumeric characters and lowercases to defeat casing/delimiter bypasses."""
        return re.sub(r'[^a-z0-9]', '', str(k).lower())

    @classmethod
    def contains_prohibited_ambient_data(cls, obj: Any, depth: int = 0) -> bool:
        """
        Recursively scans payloads for prohibited ambient discovery or personal tracking fields.
        Fails closed (returns True) if any prohibited field is detected, on inspection error,
        or on excessively deep nesting (DoS resistance).
        """
        try:
            if depth > 10:
                # Fail closed on excessively deep nesting
                return True

            if isinstance(obj, str):
                # If a JSON string is passed, parse and inspect its inner structures
                stripped = obj.strip()
                if (stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]")):
                    try:
                        parsed = json.loads(stripped)
                        if isinstance(parsed, (dict, list)):
                            return cls.contains_prohibited_ambient_data(parsed, depth + 1)
                    except Exception:
                        pass
                return False

            normalized_prohibited = {cls.normalize_key(f) for f in cls.PROHIBITED_FIELDS}

            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(k, str):
                        norm_k = cls.normalize_key(k)
                        if norm_k in normalized_prohibited:
                            return True
                    if cls.contains_prohibited_ambient_data(v, depth + 1):
                        return True
            elif isinstance(obj, (list, tuple, set)):
                for item in obj:
                    if cls.contains_prohibited_ambient_data(item, depth + 1):
                        return True
            return False
        except Exception:
            return True

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
        Fails closed on non-dict structures, prohibited ambient fields, nested opt-out markers,
        or unexpected exceptions.
        """
        try:
            if not isinstance(frame, dict):
                return None
            # Reject any frame containing prohibited ambient discovery or personal tracking fields
            if cls.contains_prohibited_ambient_data(frame):
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
