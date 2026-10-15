"""Local containment entrypoints must refuse before touching recovery state."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
PACKER = ROOT.parent / "qf-public/tools/qf_shard_packer.py"
ROTATION = ROOT / "scripts/rotate_shards.sh"
FULL_SHARE = re.compile(r"(?<![A-Za-z0-9])[1-5]:[0-9a-fA-F]{64}(?![0-9a-fA-F])")
PACKER_REFUSAL = (
    b"[!] Shard packaging is disabled: the previous authority is exposed.\n"
    b"[!] Secure custody packaging requires a reviewed authority migration.\n"
    b"[!] No shares, vaults, passwords, or files were created or changed.\n"
)
ROTATION_REFUSAL = (
    b"[!] Shard rotation is unavailable: authenticated ledger resealing is not implemented.\n"
    b"[!] No state or recovery files were changed.\n"
    b"[!] Preserve existing shares and backups. Verify the original threshold against the saved ledger before recovery.\n"
)


def assert_fixed_refusal(path):
    """Static guard: never execute an old entrypoint while testing containment."""
    source = path.read_text(encoding="utf-8")
    complete_shares_present = FULL_SHARE.search(source) is not None
    assert complete_shares_present is False, "Recovery entrypoints must not embed complete shares."
    if path == PACKER:
        disabled = "Shard packaging is disabled:" in source
        assert disabled is True, "The packer must be disabled before it may be exercised."
        parsed = ast.parse(source)
        imports = [name.name for node in ast.walk(parsed) if isinstance(node, ast.Import)
                   for name in node.names]
        from_imports = [node.module for node in ast.walk(parsed) if isinstance(node, ast.ImportFrom)]
        assert imports == ["sys"]
        assert from_imports == []
        calls = []
        for node in ast.walk(parsed):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.append(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.append(node.func.attr)
                else:
                    calls.append("UNSUPPORTED_CALL")
        assert set(calls) <= {"write", "main", "SystemExit"}
    else:
        disabled = "Shard rotation is unavailable: authenticated ledger resealing is not implemented." in source
        assert disabled is True, "The rotation helper must refuse before it may be exercised."
        permitted = ("set -euo pipefail", "echo '", "exit 2")
        safe_lines = all(line.strip().startswith(permitted) for line in source.splitlines()
                         if line.strip() and not line.lstrip().startswith("#"))
        assert safe_lines is True, "Disabled rotation may contain only fixed shell builtins."


def state_snapshot(root):
    entries = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        entries[str(path.relative_to(root))] = (
            stat.S_IFMT(info.st_mode), info.st_mode & 0o777, info.st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
        )
    return entries


def test_both_entrypoints_are_disabled_without_embedded_shares():
    # The assertions report booleans only; even failure must not echo old source.
    assert_fixed_refusal(PACKER)
    assert_fixed_refusal(ROTATION)


@pytest.mark.parametrize("path,expected", [(PACKER, PACKER_REFUSAL), (ROTATION, ROTATION_REFUSAL)])
def test_refusal_leaves_synthetic_ledger_and_custody_unchanged(tmp_path, path, expected):
    assert_fixed_refusal(path)
    state = tmp_path / "synthetic-state"
    data = state / "engine"
    custody = state / "custody"
    new_custody = state / "new-custody"
    for directory in (data, custody, new_custody):
        directory.mkdir(parents=True)
    (data / "ledger.dat").write_bytes(b"SYNTHETIC_LEDGER_MUST_STAY_UNCHANGED\n")
    (data / "ledger.dat.backup").write_bytes(b"SYNTHETIC_BACKUP_MUST_STAY_UNCHANGED\n")
    for index in range(1, 6):
        (custody / f"shard_{index}.txt").write_text("synthetic-only-not-a-share\n", encoding="ascii")
    (custody / "vault.enc").write_bytes(b"SYNTHETIC_CUSTODY_CONTAINER\n")
    calls = tmp_path / "forbidden-call.log"
    executables = tmp_path / "forbidden-tools"
    executables.mkdir()
    for name in ("systemctl", "openssl", "tar", "shred", "rm", "mv", "cp", "ss", "qf_genesis_tool"):
        trap = executables / name
        trap.write_text('#!/bin/sh\nprintf "%s\\n" "$0" >> "$QF_FORBIDDEN_CALLS"\nexit 99\n',
                        encoding="ascii")
        trap.chmod(0o700)
    before = state_snapshot(state)
    env = {
        "PATH": str(executables), "HOME": str(state), "QF_DATA_DIR": str(data),
        "SHARDS_DIR": str(custody), "NEW_SHARDS_DIR": str(new_custody),
        "SHARD_FILES": ",".join(str(custody / f"shard_{index}.txt") for index in range(1, 4)),
        "QF_FORBIDDEN_CALLS": str(calls),
    }
    if path == PACKER:
        command = [sys.executable, str(path), "opaque-unused-argument"]
    else:
        bash = shutil.which("bash")
        assert bash is not None
        command = [bash, str(path), "opaque-unused-argument"]
    result = subprocess.run(command, env=env, cwd=state, input=b"unused-input\n",
                            capture_output=True, timeout=5)
    assert result.returncode == 2
    assert result.stdout == b""
    assert result.stderr == expected
    assert calls.exists() is False
    assert state_snapshot(state) == before
