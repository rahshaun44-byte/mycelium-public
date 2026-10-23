"""
Tests for SHA-1 / MD5 detection in tools/qf_audit.py.

The CBOM verdict is NON-COMPLIANT exactly when a toxic finding survives, so these
tests pin both directions: live call sites must always be flagged (no keyword or
comment heuristic may hide them), and prose that merely names the algorithms must not.
"""

import importlib.util
import os
from pathlib import Path

import pytest

AUDIT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools", "qf_audit.py"))


def _load_audit():
    spec = importlib.util.spec_from_file_location("qf_audit_under_test", AUDIT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


qf_audit = _load_audit()


def _toxic(tmp_path: Path, name: str, source: str, allowlist=None):
    (tmp_path / name).write_text(source)
    original = dict(qf_audit.AUDITED_ALLOWLIST)
    try:
        if allowlist is not None:
            qf_audit.AUDITED_ALLOWLIST.clear()
            qf_audit.AUDITED_ALLOWLIST.update(allowlist)
        result = qf_audit.scan_target(tmp_path)
    finally:
        qf_audit.AUDITED_ALLOWLIST.clear()
        qf_audit.AUDITED_ALLOWLIST.update(original)
    found = {alg for alg in ("SHA-1", "MD5") if result["findings"].get(alg)}
    return found, result


@pytest.mark.parametrize(
    "name, source, expected",
    [
        # Guard words on the same line must not hide a live call
        ("guard.py", 'd = hashlib.sha1(data).digest(); assert d, "cannot be empty"\n', {"SHA-1"}),
        ("guard2.py", 'return hashlib.md5(u.encode()).hexdigest() if u else "invalid"\n', {"MD5"}),
        # Comment markers inside strings must not truncate a live call
        ("str_hash.py", 'tag = "#"; h = hashlib.md5(b"x")\n', {"MD5"}),
        ("url.js", 'fetch("https://x"); crypto.createHash("sha1").update(b);\n', {"SHA-1"}),
        # Constructors and APIs across languages
        ("crypt.py", "h = hashes.Hash(hashes.SHA1())\n", {"SHA-1"}),
        ("crypt2.py", "h = hashes.Hash(hashes.MD5())\n", {"MD5"}),
        ("node.ts", "const h = createHash('md5');\n", {"MD5"}),
        ("Legacy.java", 'MessageDigest md = MessageDigest.getInstance("SHA-1");\n', {"SHA-1"}),
        ("Legacy2.java", 'MessageDigest md = MessageDigest.getInstance("MD5");\n', {"MD5"}),
        ("dgst.sh", "openssl dgst -sha1 file.bin\n", {"SHA-1"}),
        ("cert.sh", "openssl req -new -md5 -key k.pem\n", {"MD5"}),
        ("legacy.go", 'import "crypto/sha1"\n', {"SHA-1"}),
        ("legacy2.go", 'import "crypto/md5"\n', {"MD5"}),
        ("hm.py", "hmac.new(key, msg, digestmod='sha1')\n", {"SHA-1"}),
        ("bare.py", "from hashlib import md5\nx = md5(b'a')\n", {"MD5"}),
        # Prose that only names the algorithms is not usage
        ("prose.rs", '//! SHA-1 template hashes cannot replay a SHA-256 PCR bank.\nlet e = "SHA-1 ascii logs cannot replay this bank";\n', set()),
        ("note.py", '"""MD5 and SHA-1 are disallowed in this codebase."""\n', set()),
        ("doc.md", "Never call hashlib.md5() here.\n", set()),
    ],
)
def test_toxic_detection(tmp_path, name, source, expected):
    found, _ = _toxic(tmp_path, name, source)
    assert found == expected


def test_allowlist_exempts_one_exact_line_only(tmp_path):
    source = "a = hashlib.sha1(x)  # legacy TPM 1.2 bank\nb = hashlib.sha1(y)\n"
    entry = {("legacy.py", "SHA-1", "a = hashlib.sha1(x)  # legacy TPM 1.2 bank"): "reviewed: TPM 1.2 bank read"}

    found, result = _toxic(tmp_path, "legacy.py", source, allowlist=entry)
    # The second, unreviewed call in the same file is still flagged
    assert found == {"SHA-1"}
    assert [f["line"] for f in result["findings"]["SHA-1"]] == [2]
    assert [f["line"] for f in result["allowlisted_findings"]] == [1]


def test_allowlist_entry_stops_matching_when_line_changes(tmp_path):
    entry = {("legacy.py", "SHA-1", "a = hashlib.sha1(x)"): "reviewed"}
    found, result = _toxic(tmp_path, "legacy.py", "a = hashlib.sha1(x2)\n", allowlist=entry)
    assert found == {"SHA-1"}
    assert result["allowlisted_findings"] == []


def test_allowlist_does_not_match_same_basename_elsewhere(tmp_path):
    (tmp_path / "other").mkdir()
    entry = {("legacy.py", "SHA-1", "a = hashlib.sha1(x)"): "reviewed"}
    found, _ = _toxic(tmp_path, os.path.join("other", "legacy.py"), "a = hashlib.sha1(x)\n", allowlist=entry)
    assert found == {"SHA-1"}


def test_repository_has_no_toxic_call_sites():
    repo_root = Path(AUDIT_PATH).parent.parent
    result = qf_audit.scan_target(repo_root)
    assert not result["findings"].get("SHA-1"), result["findings"].get("SHA-1")
    assert not result["findings"].get("MD5"), result["findings"].get("MD5")
