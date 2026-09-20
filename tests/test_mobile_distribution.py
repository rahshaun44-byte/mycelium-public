#!/usr/bin/env python3
"""
Cryptographic Verification Tests for QuantumFlex Mobile Distribution (QF-M1)
=============================================================================
Validates:
- Valid artifact signing and Ed25519 verification
- Tamper rejection: modified artifact bytes fail SHA-256 verification
- Forgery rejection: signature generated with rogue key fails verification
- Corrupt signature rejection
"""

import os
import sys
import shutil
import tempfile
import unittest
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from scripts.sign_mobile_artifacts import (
    generate_keypair,
    sign_mobile_artifact,
    verify_mobile_artifact,
    compute_file_sha256
)


class TestMobileDistribution(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="qf_mobile_test_")
        self.priv_key = os.path.join(self.test_dir, "test_priv.pem")
        self.pub_key = os.path.join(self.test_dir, "test_pub.pub")
        generate_keypair(self.priv_key, self.pub_key)

        # Create dummy artifact
        self.artifact = os.path.join(self.test_dir, "test_app.apk")
        with open(self.artifact, "wb") as f:
            f.write(b"QUANTUMFLEX_VERIFIED_MOBILE_BYTES_V1")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_valid_signature_passes(self):
        """Legitimately signed artifact passes verification."""
        manifest, sig = sign_mobile_artifact(self.artifact, self.priv_key, output_dir=self.test_dir)
        ok, reason = verify_mobile_artifact(self.artifact, manifest, sig, self.pub_key)
        self.assertTrue(ok, f"Expected verification to pass: {reason}")
        self.assertIn("Verified against trust anchor", reason)

    def test_tampered_artifact_fails_hash_check(self):
        """Modified artifact fails SHA-256 match despite valid signature."""
        manifest, sig = sign_mobile_artifact(self.artifact, self.priv_key, output_dir=self.test_dir)

        # Tamper with the artifact
        with open(self.artifact, "ab") as f:
            f.write(b"_MALICIOUS_INJECTION")

        ok, reason = verify_mobile_artifact(self.artifact, manifest, sig, self.pub_key)
        self.assertFalse(ok)
        self.assertIn("SHA-256 MISMATCH", reason)

    def test_rogue_key_fails_signature_verification(self):
        """Artifact signed by an untrusted key fails verification against pinned anchor."""
        rogue_priv = os.path.join(self.test_dir, "rogue_priv.pem")
        rogue_pub = os.path.join(self.test_dir, "rogue_pub.pub")
        generate_keypair(rogue_priv, rogue_pub)

        manifest, sig = sign_mobile_artifact(self.artifact, rogue_priv, output_dir=self.test_dir)

        # Attempt verification against legitimate public anchor
        ok, reason = verify_mobile_artifact(self.artifact, manifest, sig, self.pub_key)
        self.assertFalse(ok)
        self.assertIn("Signature verification FAILED", reason)

    def test_corrupted_signature_fails(self):
        """Corrupted signature bytes fail verification."""
        manifest, sig = sign_mobile_artifact(self.artifact, self.priv_key, output_dir=self.test_dir)

        # Corrupt signature bytes
        with open(sig, "wb") as f:
            f.write(b"CORRUPTED_SIGNATURE_BYTES_00000000000000000000000000000000000")

        ok, reason = verify_mobile_artifact(self.artifact, manifest, sig, self.pub_key)
        self.assertFalse(ok)
        self.assertIn("Signature verification FAILED", reason)


if __name__ == "__main__":
    unittest.main()
