#!/usr/bin/env python3
"""
Unit and Contract Tests for QuantumFlex Unified Mobile CLI (qflex_cli.py)
========================================================================
Validates:
- Strict role resolution (Observer fail-closed, shard custodian, field workstation)
- Observer privileged action denial (approve/discard fail-closed)
- Host candidate ordering
- Format and schema of CLI node diagnostics
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "mobile"))

import qflex_cli


class TestMobileCLI(unittest.TestCase):

    def test_observer_role_fails_closed(self):
        """Unrecognized device must resolve to Observer with privileged actions DENIED."""
        with patch("qflex_cli._get_android_prop", return_value=""), \
             patch("qflex_cli.socket.gethostname", return_value="untrusted-device"), \
             patch.dict("os.environ", {"USER": "guest"}, clear=True), \
             patch("qflex_cli._detect_local_ips", return_value=["192.168.100.20"]):
            identity = qflex_cli.resolve_node_identity()
            self.assertEqual(identity.node_id, "unknown")
            self.assertEqual(identity.role, "observer")
            self.assertFalse(identity.privileged)

    def test_observer_cannot_approve(self):
        """Observer role must raise SystemExit(1) on approve attempt."""
        identity = qflex_cli.NodeIdentity(
            node_id="unknown",
            role="observer",
            model="Untrusted",
            tailscale_ip="0.0.0.0",
            transport="unverified",
            privileged=False,
            details="Observer test"
        )
        with self.assertRaises(SystemExit) as cm:
            qflex_cli.cmd_approve("http://127.0.0.1:9000", identity, "draft-123")
        self.assertEqual(cm.exception.code, 1)

    def test_observer_cannot_discard(self):
        """Observer role must raise SystemExit(1) on discard attempt."""
        identity = qflex_cli.NodeIdentity(
            node_id="unknown",
            role="observer",
            model="Untrusted",
            tailscale_ip="0.0.0.0",
            transport="unverified",
            privileged=False,
            details="Observer test"
        )
        with self.assertRaises(SystemExit) as cm:
            qflex_cli.cmd_discard("http://127.0.0.1:9000", identity, "draft-123")
        self.assertEqual(cm.exception.code, 1)

    def test_host_candidate_priority(self):
        """On master host, loopback is checked first; on mobile, Tailscale IP is checked first."""
        with patch("qflex_cli.socket.gethostname", return_value=qflex_cli.YOGA_HOSTNAME):
            candidates = qflex_cli.get_candidate_hosts()
            self.assertEqual(candidates[0], ("127.0.0.1", 9001))

        with patch("qflex_cli.socket.gethostname", return_value="android-client"), \
             patch.dict("os.environ", {"USER": "u0_a123"}, clear=True):
            candidates = qflex_cli.get_candidate_hosts()
            self.assertEqual(candidates[0], ("100.64.1.31", 9001))

    def test_node_dict_schema(self):
        """Node identity to_dict() returns expected keys."""
        identity = qflex_cli.NodeIdentity(
            node_id="test-node",
            role="shard-custodian",
            model="Test Enclave",
            tailscale_ip="100.64.1.16",
            transport="tailscale",
            privileged=True,
            details="Test Details"
        )
        d = identity.to_dict()
        self.assertEqual(d["node_id"], "test-node")
        self.assertEqual(d["role"], "shard-custodian")
        self.assertEqual(d["privileged_actions"], "ALLOW")


if __name__ == "__main__":
    unittest.main()
