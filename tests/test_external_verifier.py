"""
Tests for QuantumFlex External Trust-Anchored Verifier
Validates architectural separation:
  "The repository supplies the object being verified.
   It does not supply the key that determines whether that object is trusted."
"""

import base64
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
import pytest

from scripts.build_external_verifier import transform_verifier, OLD_PATTERN

EXTERNAL_VERIFIER = os.path.expanduser("~/.local/libexec/quantumflex/verify-provenance")
TRUST_ANCHOR = os.path.expanduser("~/.local/libexec/quantumflex/release_signing_key.pub")
WORKSPACE = os.environ.get("QUANTUMFLEX_WORKSPACE", str(Path(__file__).resolve().parents[1]))


def test_trust_anchor_exists_and_permissions():
    """Trust anchor must exist outside the git repository and have restricted permissions."""
    assert os.path.isfile(TRUST_ANCHOR), "Trust anchor public key must exist in ~/.local/libexec/quantumflex/"
    mode = oct(os.stat(TRUST_ANCHOR).st_mode & 0o777)
    # Should be 0400 (read-only by owner)
    assert mode == "0o400", f"Expected permissions 0o400 on trust anchor, got {mode}"


def test_external_verifier_binary_installed():
    """External verifier binary must exist and be executable."""
    assert os.path.isfile(EXTERNAL_VERIFIER), "External verifier binary must exist"
    assert os.access(EXTERNAL_VERIFIER, os.X_OK), "External verifier must be executable"


def test_repository_provenance_stale_manifest_fails_closed():
    """
    When artifacts drift from PROVENANCE_MANIFEST.json,
    the verifier must refuse stale provenance and fail closed (exit code 1).
    """
    res = subprocess.run([EXTERNAL_VERIFIER, WORKSPACE], capture_output=True, text=True)
    if res.returncode == 0:
        # Active workspace is clean/valid. Verify that tampering causes fail-closed
        with tempfile.TemporaryDirectory() as tmp_repo:
            shutil.copytree(os.path.join(WORKSPACE, "release"), os.path.join(tmp_repo, "release"))
            with open(os.path.join(tmp_repo, "tampered.txt"), "w") as f:
                f.write("tampered content")
            res_tampered = subprocess.run([EXTERNAL_VERIFIER, tmp_repo], capture_output=True, text=True)
            assert res_tampered.returncode == 1, "Verifier must fail-closed on tampered artifacts"
            assert "FAIL-CLOSED" in res_tampered.stdout or "DENY" in res_tampered.stdout
    else:
        assert res.returncode == 1, "Verifier must fail-closed on stale repository artifacts"
        assert "FAIL-CLOSED" in res.stdout


def test_package_admission_verification():
    """Test package admission mode of external verifier using signed admission fixture."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        receipt_file = tmp_path / "QuantumFlexAdmission.json"
        receipt_data = {
            "schema": "QuantumFlexAdmission/v1",
            "package": "QuantumFlex",
            "version": "2.1.0",
            "artifacts": []
        }
        receipt_file.write_text(json.dumps(receipt_data, indent=2))

        # We can test admission rejection when provenance files are missing
        res = subprocess.run([
            EXTERNAL_VERIFIER,
            "--admit-package",
            "--receipt", str(receipt_file)
        ], capture_output=True, text=True)
        assert res.returncode == 1
        assert "FAIL-CLOSED" in res.stdout


def test_build_transformation_assertions():
    """Build transformation must halt and refuse to mutate if pattern is missing."""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as f_source:
        f_source.write(f"# header\n{OLD_PATTERN}\n# footer\n")
        source_path = f_source.name

    try:
        transformed = transform_verifier(source_path)
        assert "TRUST_ANCHOR_DIR = os.path.dirname(os.path.abspath(__file__))" in transformed
        assert "PUB_KEY_PATH = os.path.join(TRUST_ANCHOR_DIR, \"release_signing_key.pub\")" in transformed
        assert OLD_PATTERN not in transformed
    finally:
        os.unlink(source_path)

    # Negative test: corrupted source raises error
    with tempfile.NamedTemporaryFile("w", encoding="utf-8") as f_bad:
        f_bad.write("# empty file with no matching block\n")
        f_bad.flush()
        with pytest.raises(ValueError, match=r"\[HALT\] Expected old path pattern NOT FOUND"):
            transform_verifier(f_bad.name)


def test_adversarial_trust_anchor_substitution_fails_closed():
    """
    Simulate an untrusted repository attempting trust-anchor substitution.
    The external verifier must reject the re-signed manifest and fail closed.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Attacker generates their own Ed25519 keypair
        attacker_key = os.path.join(tmpdir, "attacker_key.pem")
        attacker_pub = os.path.join(tmpdir, "attacker_pub.pub")
        subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519", "-out", attacker_key],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["openssl", "pkey", "-in", attacker_key, "-pubout", "-out", attacker_pub],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 2. Rogue repo mirrors release artifacts
        rogue_repo = os.path.join(tmpdir, "rogue_repo")
        os.makedirs(os.path.join(rogue_repo, "release"))

        # Copy authentic manifest into rogue repo
        shutil.copy(os.path.join(WORKSPACE, "release/PROVENANCE_MANIFEST.json"),
                    os.path.join(rogue_repo, "release/PROVENANCE_MANIFEST.json"))

        # Attacker replaces release_signing_key.pub in repo
        shutil.copy(attacker_pub, os.path.join(rogue_repo, "release/release_signing_key.pub"))

        # Attacker signs manifest with attacker private key
        sig_raw = os.path.join(tmpdir, "sig.raw")
        subprocess.run(["openssl", "pkeyutl", "-sign", "-rawin", "-inkey", attacker_key,
                        "-in", os.path.join(rogue_repo, "release/PROVENANCE_MANIFEST.json"),
                        "-out", sig_raw], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        with open(sig_raw, "rb") as f:
            sig_b64 = base64.b64encode(f.read()).decode("utf-8")

        with open(os.path.join(rogue_repo, "release/PROVENANCE_MANIFEST.sig"), "w") as f:
            f.write(f"SIGNATURE_ALGORITHM=Ed25519\nPUBLIC_KEY_PIN=release_signing_key.pub\nSIGNATURE_B64={sig_b64}\nTIMESTAMP=2026-09-19T00:00:00+00:00\n")

        # 3. External verifier must reject the rogue repo
        res = subprocess.run([EXTERNAL_VERIFIER, rogue_repo], capture_output=True, text=True)
        assert res.returncode == 1, "External verifier must exit with code 1"
        assert "[FAIL-CLOSED] Cryptographic signature invalid!" in res.stdout
