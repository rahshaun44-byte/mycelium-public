#!/usr/bin/env python3
"""
QuantumFlex — enroll the Pixel's StrongBox operator key with QF-Bot.

Runs over USB ADB only. Generates a fresh challenge, asks the cockpit app to create
a StrongBox key attested over that challenge, pulls the attestation chain, and pins
the public key only if:
  * every certificate in the chain is signed by the next one,
  * the chain ends at one of Google's hardware attestation roots
    (fetched from android.googleapis.com over TLS at enrollment time),
  * the attestation carries our challenge,
  * both attestation and key security levels are StrongBox.

  python3 scripts/enroll_pixel_key.py --serial PIXEL-SERIAL-REDACTED
"""

import argparse
import base64
import json
import os
import secrets
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import serialization

PACKAGE = "com.quantumflex.cockpit"
ACTIVITY = f"{PACKAGE}/.MainActivity"
KEY_DESCRIPTION_OID = x509.ObjectIdentifier("1.3.6.1.4.1.11129.2.1.17")
GOOGLE_ROOTS_URL = "https://android.googleapis.com/attestation/root"
STRONGBOX = 2


def adb(serial, *args, capture=True):
    return subprocess.run(["adb", "-s", serial, *args], capture_output=capture, check=True)


def der_elements(data):
    """Yields (tag, value) for a DER SEQUENCE's direct children."""
    assert data[0] == 0x30, "KeyDescription is not a SEQUENCE"
    i, end = _read_len(data, 1)
    while i < end:
        tag = data[i]
        j, l = _read_len_value(data, i + 1)
        yield tag, data[j:j + l]
        i = j + l


def _read_len(data, i):
    j, l = _read_len_value(data, i)
    return j, j + l


def _read_len_value(data, i):
    first = data[i]
    if first < 0x80:
        return i + 1, first
    n = first & 0x7F
    return i + 1 + n, int.from_bytes(data[i + 1:i + 1 + n], "big")


def parse_key_description(ext_value):
    fields = list(der_elements(ext_value))[:5]
    return {
        "attestation_version": int.from_bytes(fields[0][1], "big"),
        "attestation_security_level": int.from_bytes(fields[1][1], "big"),
        "keymint_security_level": int.from_bytes(fields[3][1], "big"),
        "challenge": fields[4][1],
    }


def spki(cert):
    return cert.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", required=True, help="USB serial of the Pixel (not a host:port wireless target)")
    ap.add_argument("--device-id", default="pixel-11-pro")
    ap.add_argument("--keys-dir", default=os.environ.get(
        "QF_DEVICE_KEYS_DIR", str(Path.home() / ".config" / "quantumflex" / "devices")))
    args = ap.parse_args()

    if ":" in args.serial:
        sys.exit("Refusing a network ADB target; enrollment must run over USB.")

    challenge = secrets.token_bytes(32)
    adb(args.serial, "shell", "run-as", PACKAGE, "rm", "-f", "files/qf_enroll.json")
    adb(args.serial, "shell", "am", "force-stop", PACKAGE)
    adb(args.serial, "shell", "am", "start", "-n", ACTIVITY, "--es", "qf_enroll_challenge", challenge.hex())

    raw = None
    for _ in range(30):
        time.sleep(1)
        p = subprocess.run(["adb", "-s", args.serial, "exec-out", "run-as", PACKAGE, "cat", "files/qf_enroll.json"],
                           capture_output=True)
        if p.returncode == 0 and p.stdout.strip().startswith(b"{"):
            raw = json.loads(p.stdout)
            break
    if raw is None:
        sys.exit("No enrollment result from the device (is the new APK installed and the screen unlocked?).")
    if "error" in raw:
        sys.exit(f"Device reported: {raw['error']}")

    chain = [x509.load_der_x509_certificate(base64.b64decode(c)) for c in raw["attestationChain"]]
    for child, issuer in zip(chain, chain[1:]):
        child.verify_directly_issued_by(issuer)

    with urllib.request.urlopen(GOOGLE_ROOTS_URL, timeout=15) as r:
        google_roots = [x509.load_pem_x509_certificate(pem.encode()) for pem in json.loads(r.read())]
    if spki(chain[-1]) not in {spki(root) for root in google_roots}:
        sys.exit("Attestation chain does not end at a Google hardware attestation root. NOT enrolled.")

    desc = parse_key_description(chain[0].extensions.get_extension_for_oid(KEY_DESCRIPTION_OID).value.value)
    if not secrets.compare_digest(desc["challenge"], challenge):
        sys.exit("Attestation challenge mismatch. NOT enrolled.")
    if desc["attestation_security_level"] != STRONGBOX or desc["keymint_security_level"] != STRONGBOX:
        sys.exit(f"Key is not StrongBox-backed ({desc}). NOT enrolled.")

    keys_dir = Path(args.keys_dir)
    keys_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(keys_dir, 0o700)
    out = keys_dir / f"{args.device_id}.pem"
    out.write_bytes(chain[0].public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    os.chmod(out, 0o600)
    adb(args.serial, "shell", "run-as", PACKAGE, "rm", "-f", "files/qf_enroll.json")

    print(f"Enrolled {args.device_id}: StrongBox key, attestation v{desc['attestation_version']}, "
          f"chain of {len(chain)} to Google root -> {out}")


if __name__ == "__main__":
    main()
