#!/usr/bin/env python3
"""
Route and Contract Tests for QF-Bot Mobile OTA Endpoints (QF-M1)
================================================================
Validates:
- /mobile/bootstrap returns valid schema and authenticated service identity
- /mobile/manifest returns available mobile distribution artifacts
- /mobile/admission/evidence returns authoritative host admission proofs
- /mobile/download/cli returns proper Content-Disposition and X-QuantumFlex-SHA256 headers
- /mobile/download/apk returns application/vnd.android.package-archive
"""

import sys
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "mcp_layer"))
sys.path.insert(0, str(ROOT_DIR))

try:
    from qf_bot.bot_server import APK_FILE, app
    HAS_QF_BOT = True
except ImportError:
    HAS_QF_BOT = False
    APK_FILE = Path("/dev/null")
    app = None


@unittest.skipUnless(HAS_QF_BOT, "qf_bot service module in sovereign-isolated mcp_layer is not present in public CI tree")
class TestMobileOTARoutes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not HAS_QF_BOT or app is None:
            raise unittest.SkipTest("qf_bot module not available")
        cls.client = TestClient(app)

    def test_mobile_bootstrap_endpoint_does_not_claim_anonymous_client_is_authenticated(self):
        """Bootstrap reports caller authentication separately from service identity."""
        resp = self.client.get("/mobile/bootstrap")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("service"), "quantumflex-qf-bot")
        self.assertEqual(data.get("schema"), "qf-mobile-v1")
        self.assertFalse(data.get("authenticated"))
        self.assertFalse(data.get("authorized"))
        self.assertEqual(data.get("authentication_method"), "none")
        self.assertIn("signed-ota-distribution", data.get("capabilities", []))

        # Cryptographic Identity & Verification Procedure Verification (Beyond boolean true)
        srv_id = data.get("service_identity", {})
        self.assertEqual(srv_id.get("key_type"), "Ed25519")
        self.assertTrue(len(srv_id.get("public_key", "")) > 30)
        self.assertEqual(len(srv_id.get("fingerprint_sha256", "")), 64)
        self.assertIn("Ed25519", srv_id.get("verification_procedure", ""))

        # Governance & Authorization Disclosures
        gov = data.get("governance", {})
        self.assertEqual(gov.get("policy_standard"), "QF-LEGAL-001")
        self.assertIn("PRIVACY", gov.get("privacy_policy_url", ""))
        self.assertIn("AUTHORIZED", gov.get("authorized_operations_policy_url", ""))
        self.assertEqual(len(data.get("service_handshake_digest", "")), 64)

    def test_mobile_manifest_endpoint(self):
        """Manifest index lists signed mobile artifacts with valid sha256."""
        resp = self.client.get("/mobile/manifest")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("schema"), "quantumflex-mobile-manifest-index-v1")
        artifacts = data.get("artifacts", {})
        self.assertIn("qflex_cli.py", artifacts)
        self.assertEqual(len(artifacts["qflex_cli.py"]["sha256"]), 64)

    def test_mobile_admission_evidence_endpoint(self):
        """Admission evidence endpoint exposes A4/A5/A6 verification proof."""
        resp = self.client.get("/mobile/admission/evidence")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("schema"), "quantumflex-admission-evidence-v1")
        self.assertEqual(data.get("launcher_invariant"), "EXECUTED_FD == VERIFIED_FD")
        self.assertIn("a4_package", data)
        self.assertIn("a5_provenance", data)
        self.assertIn("a6_runtime", data)

    def test_cli_download_headers(self):
        """CLI download endpoint emits required cryptographic headers."""
        resp = self.client.get("/mobile/download/cli")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("qflex_cli.py", resp.headers.get("content-disposition", ""))
        self.assertIn("text/x-python", resp.headers.get("content-type", ""))
        sha256 = resp.headers.get("x-quantumflex-sha256")
        self.assertIsNotNone(sha256)
        self.assertEqual(len(sha256), 64)

    @unittest.skipUnless(APK_FILE.is_file(), "Android APK not built on this host (gitignored build output)")
    def test_apk_download_headers(self):
        """APK download endpoint emits proper MIME type and SHA-256 header."""
        resp = self.client.get("/mobile/download/apk")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/vnd.android.package-archive", resp.headers.get("content-type", ""))
        self.assertIn("qf-cockpit.apk", resp.headers.get("content-disposition", ""))
        sha256 = resp.headers.get("x-quantumflex-sha256")
        self.assertIsNotNone(sha256)
        self.assertEqual(len(sha256), 64)


if __name__ == "__main__":
    unittest.main()
