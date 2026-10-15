"""Exercise the offline checker with native, synthetic-only Shamir fixtures."""

from __future__ import annotations

import hashlib
import itertools
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
CHECKER_SOURCE = ROOT / "tools/qf_legacy_recovery_check.cpp"
SHAMIR_SOURCE = ROOT / "quantumflex/src/crypto/crypto_shamir.cpp"
INCLUDE = ROOT / "quantumflex/include"
SYNTHETIC_SECRET = bytes(range(32))
EMPTY_ROOT = hashlib.sha256(b"QUANTUM_FLEX_EMPTY_STATE").hexdigest()


@pytest.fixture(scope="module")
def native_tools(tmp_path_factory):
    compiler = shutil.which("g++")
    if compiler is None:
        pytest.fail("The native recovery tests require the C++ compiler.")
    build = tmp_path_factory.mktemp("synthetic-recovery-native")
    checker = build / "checker"
    common = [compiler, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror",
              "-I", str(INCLUDE)]
    build_result = subprocess.run(
        [*common, str(CHECKER_SOURCE), str(SHAMIR_SOURCE), "-lcrypto", "-o", str(checker)],
        capture_output=True, text=True, timeout=60,
    )
    fixture_source = build / "synthetic_fixture.cpp"
    fixture_source.write_text(r'''
#include "quantum-flex/crypto_shamir.hpp"
#include <iomanip>
#include <iostream>
#include <string>
int main() {
    std::string synthetic_secret(32, '\0');
    for (unsigned int index = 0; index < 32; ++index) {
        synthetic_secret[index] = static_cast<char>(index);
    }
    const auto shards = quantumflex::crypto::ShamirSecretSharing::split_secret(synthetic_secret, 5, 3);
    for (const auto& shard : shards) {
        std::cout << static_cast<unsigned int>(shard.id) << ':';
        for (unsigned char value : shard.payload) {
            std::cout << std::hex << std::setfill('0') << std::setw(2)
                      << static_cast<unsigned int>(value);
        }
        std::cout << '\n';
    }
}
''', encoding="utf-8")
    fixture = build / "synthetic_fixture"
    fixture_result = subprocess.run(
        [*common, str(fixture_source), str(SHAMIR_SOURCE), "-lcrypto", "-o", str(fixture)],
        capture_output=True, text=True, timeout=60,
    )
    assert fixture_result.returncode == 0, fixture_result.stderr
    generated = subprocess.run([str(fixture)], capture_output=True, text=True, timeout=5)
    assert generated.returncode == 0
    shares = generated.stdout.splitlines()
    assert len(shares) == 5
    return checker, build_result, shares


def ledger_text(*, secret=SYNTHETIC_SECRET, root=EMPTY_ROOT, timestamp="1791979200"):
    payload = f"STATE_ROOT|{root}\nTIMESTAMP|{timestamp}\n".encode("ascii")
    signature = hashlib.sha256(payload + secret).hexdigest()
    return payload + f"LEDGER_SIGNATURE|{signature}\nSTATUS|ACTIVE\n".encode("ascii")


def invoke(native_tools, ledger, share_input, *extra):
    checker, build_result, _ = native_tools
    assert build_result.returncode == 0, "Native checker build failed:\n" + build_result.stderr
    return subprocess.run(
        [str(checker), "--ledger", str(ledger), *extra],
        input=share_input, capture_output=True, timeout=5,
    )


def share_bytes(shares):
    return ("\n".join(shares) + "\n").encode("ascii")


def assert_result(result, code, output):
    assert result.returncode == code
    assert result.stdout == output.encode("ascii")
    assert result.stderr == b""


def test_native_shares_match_exact_raw_binary_salt(native_tools, tmp_path):
    ledger = tmp_path / "ledger.dat"
    original = ledger_text()
    ledger.write_bytes(original)
    before = ledger.stat()
    for selected in itertools.combinations(native_tools[2], 3):
        result = invoke(native_tools, ledger, share_bytes(selected))
        assert_result(result, 0, "MATCH\n")
        for share in selected:
            assert share.encode() not in result.stdout + result.stderr
    assert ledger.read_bytes() == original
    assert ledger.stat().st_mtime_ns == before.st_mtime_ns
    assert sorted(path.name for path in tmp_path.iterdir()) == ["ledger.dat"]


def test_share_mismatch_is_safe_and_does_not_modify_ledger(native_tools, tmp_path):
    ledger = tmp_path / "ledger.dat"
    original = ledger_text(secret=b"a" * 32)
    ledger.write_bytes(original)
    result = invoke(native_tools, ledger, share_bytes(native_tools[2][:3]))
    assert_result(result, 1, "MISMATCH\n")
    assert ledger.read_bytes() == original


def test_signature_covers_timestamp_and_state_root(native_tools, tmp_path):
    ledger = tmp_path / "ledger.dat"
    for changed in (
        ledger_text().replace(b"1791979200", b"1791979201"),
        ledger_text().replace(EMPTY_ROOT.encode(), b"a" * 64),
    ):
        ledger.write_bytes(changed)
        assert_result(invoke(native_tools, ledger, share_bytes(native_tools[2][:3])),
                      1, "MISMATCH\n")


@pytest.mark.parametrize("transform", [
    lambda shares: [shares[0], shares[0], shares[2]],
    lambda shares: ["0" + shares[0][1:], *shares[1:3]],
    lambda shares: ["6" + shares[0][1:], *shares[1:3]],
    lambda shares: ["01" + shares[0][1:], *shares[1:3]],
    lambda shares: [shares[0] + "0", *shares[1:3]],
    lambda shares: [shares[0][:-1], *shares[1:3]],
    lambda shares: [shares[0][:-1] + "g", *shares[1:3]],
    lambda shares: [shares[0] + " ", *shares[1:3]],
    lambda shares: shares[:2],
    lambda shares: shares[:4],
])
def test_rejects_malformed_or_incomplete_share_sets(native_tools, tmp_path, transform):
    ledger = tmp_path / "ledger.dat"
    ledger.write_bytes(ledger_text())
    result = invoke(native_tools, ledger, share_bytes(transform(native_tools[2])))
    assert_result(result, 2, "ERROR_SHARES\n")


@pytest.mark.parametrize("suffix", [b"", b"\n", b"trailing", b"\x00", b"X" * 100000])
def test_requires_exactly_three_complete_lines(native_tools, tmp_path, suffix):
    ledger = tmp_path / "ledger.dat"
    ledger.write_bytes(ledger_text())
    valid = share_bytes(native_tools[2][:3])
    data = valid[:-1] if suffix == b"" else valid + suffix
    assert_result(invoke(native_tools, ledger, data), 2, "ERROR_SHARES\n")


def test_accepts_hex_case_without_changing_share_identity(native_tools, tmp_path):
    ledger = tmp_path / "ledger.dat"
    ledger.write_bytes(ledger_text())
    upper = [share.upper() for share in native_tools[2][:3]]
    assert_result(invoke(native_tools, ledger, share_bytes(upper)), 0, "MATCH\n")


@pytest.mark.parametrize("mutate", [
    lambda data: data.replace(b"STATUS|ACTIVE", b"STATUS|UNINITIALIZED"),
    lambda data: data.replace(b"TIMESTAMP|1791979200", b"TIMESTAMP|-1"),
    lambda data: data.replace(b"TIMESTAMP|1791979200", b"TIMESTAMP|01"),
    lambda data: data.replace(b"TIMESTAMP|1791979200", b"TIMESTAMP|18446744073709551616"),
    lambda data: data.replace(EMPTY_ROOT.encode(), b"g" * 64),
    lambda data: data.replace(EMPTY_ROOT.encode(), b"a" * 63),
    lambda data: data.replace(b"LEDGER_SIGNATURE|", b"LEDGER_SIGNATURE|g"),
    lambda data: data + b"STATUS|ACTIVE\n",
    lambda data: data + b"UNKNOWN|value\n",
    lambda data: data.replace(b"\n", b"\r\n"),
    lambda data: data[:-1],
    lambda data: data.replace(b"STATUS|ACTIVE", b"STATUS|ACTIVE\x00"),
    lambda data: data + b"X" * 10000,
    lambda data: b"",
])
def test_rejects_noncanonical_ledger_envelopes(native_tools, tmp_path, mutate):
    ledger = tmp_path / "ledger.dat"
    ledger.write_bytes(mutate(ledger_text()))
    assert_result(invoke(native_tools, ledger, share_bytes(native_tools[2][:3])),
                  2, "ERROR_LEDGER\n")


def test_nonempty_root_can_be_checked_offline(native_tools, tmp_path):
    ledger = tmp_path / "ledger.dat"
    ledger.write_bytes(ledger_text(root=hashlib.sha256(b"synthetic evidence").hexdigest()))
    assert_result(invoke(native_tools, ledger, share_bytes(native_tools[2][:3])),
                  0, "MATCH\n")


def test_missing_or_nonregular_ledger_has_fixed_error(native_tools, tmp_path):
    for ledger in (tmp_path / "missing", tmp_path):
        assert_result(invoke(native_tools, ledger, share_bytes(native_tools[2][:3])),
                      2, "ERROR_LEDGER_IO\n")


def test_ledger_symlink_is_refused(native_tools, tmp_path):
    target = tmp_path / "actual.dat"
    target.write_bytes(ledger_text())
    link = tmp_path / "ledger.dat"
    link.symlink_to(target)
    assert_result(invoke(native_tools, link, share_bytes(native_tools[2][:3])),
                  2, "ERROR_LEDGER_IO\n")


def test_unknown_argument_has_fixed_error(native_tools, tmp_path):
    ledger = tmp_path / "ledger.dat"
    ledger.write_bytes(ledger_text())
    assert_result(invoke(native_tools, ledger, share_bytes(native_tools[2][:3]), "--unsafe"),
                  2, "ERROR_USAGE\n")
