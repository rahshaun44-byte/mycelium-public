import json
import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from amara_channel import Archivist


def test_archivist_appends_to_valid_chain(tmp_path):
    log_path = tmp_path / "amara_audit.jsonl"
    archivist = Archivist(log_path)

    archivist.record("test", "created", {"value": 1})

    assert archivist.verify_chain() == (True, 1, "Verified 1 hash-chained entries intact.")


def test_archivist_refuses_to_append_to_invalid_chain(tmp_path):
    log_path = tmp_path / "amara_audit.jsonl"
    log_path.write_text(
        '{"event":"legacy","entry_hash":"bad","prev_hash":"bad"}\n',
        encoding="utf-8",
    )
    before = log_path.read_bytes()
    archivist = Archivist(log_path)

    with pytest.raises(RuntimeError, match="Refusing to append to invalid audit log"):
        archivist.record("test", "must_not_append", {})

    assert log_path.read_bytes() == before


@pytest.mark.parametrize(
    ("contents", "reason"),
    [
        ('{"timestamp":\n', "Malformed JSON at entry #1"),
        ("[]\n", "Invalid record type at entry #1"),
        ('{"timestamp":"t","capability":"c"}\n', "Invalid record schema at entry #1"),
        (
            json.dumps(
                {
                    "timestamp": "t",
                    "capability": "c",
                    "event_type": "e",
                    "details": {},
                    "prev_sha256": "1" * 64,
                    "entry_sha256": "0" * 64,
                }
            )
            + "\n",
            "Broken prev_sha256 link at entry #1",
        ),
        (
            json.dumps(
                {
                    "timestamp": "t",
                    "capability": "c",
                    "event_type": "e",
                    "details": "not-an-object",
                    "prev_sha256": "0" * 64,
                    "entry_sha256": "0" * 64,
                }
            )
            + "\n",
            "Invalid record field types at entry #1",
        ),
    ],
)
def test_archivist_rejects_malformed_or_broken_records_without_appending(
    tmp_path, contents, reason
):
    log_path = tmp_path / "amara_audit.jsonl"
    log_path.write_text(contents, encoding="utf-8")
    before = log_path.read_bytes()
    archivist = Archivist(log_path)

    with pytest.raises(RuntimeError, match="Refusing to append"):
        archivist.record("test", "must_not_append", {})

    assert reason in archivist.verify_chain()[2]
    assert log_path.read_bytes() == before


def test_archivist_rejects_tampered_entry_hash(tmp_path):
    log_path = tmp_path / "amara_audit.jsonl"
    archivist = Archivist(log_path)
    archivist.record("test", "created", {"value": 1})
    record = json.loads(log_path.read_text(encoding="utf-8"))
    record["details"]["value"] = 2
    log_path.write_text(json.dumps(record) + "\n", encoding="utf-8")
    before = log_path.read_bytes()

    with pytest.raises(RuntimeError, match="Refusing to append"):
        archivist.record("test", "must_not_append", {})

    assert "SHA-256 mismatch at entry #1" in archivist.verify_chain()[2]
    assert log_path.read_bytes() == before


def test_archivist_rejects_invalid_utf8_without_appending(tmp_path):
    log_path = tmp_path / "amara_audit.jsonl"
    log_path.write_bytes(b"\xff\n")
    before = log_path.read_bytes()
    archivist = Archivist(log_path)

    with pytest.raises(RuntimeError, match="Refusing to append"):
        archivist.record("test", "must_not_append", {})

    assert "invalid UTF-8" in archivist.verify_chain()[2]
    assert log_path.read_bytes() == before


def test_normal_amara_startup_fails_clearly_before_loading_memory(monkeypatch, capsys):
    import amara_channel

    class InvalidArchivist:
        def verify_chain(self):
            return False, 41, "Invalid record schema at entry #41."

    class MemoryMustNotLoad:
        def __init__(self):
            raise AssertionError("memory vault must not load for an invalid ledger")

    monkeypatch.setattr(amara_channel, "Archivist", InvalidArchivist)
    monkeypatch.setattr(amara_channel, "MemoryVault", MemoryMustNotLoad)

    assert amara_channel.main(["--assess"]) == 1
    assert "refusing to start with invalid audit log" in capsys.readouterr().err


def test_archivist_serializes_concurrent_writers(tmp_path):
    log_path = tmp_path / "amara_audit.jsonl"
    scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
    worker = (
        "import sys; from pathlib import Path; "
        f"sys.path.insert(0, {str(scripts_dir)!r}); "
        "from amara_channel import Archivist; "
        f"archivist = Archivist(Path({str(log_path)!r})); "
        "[(archivist.record('test', 'concurrent', {'n': i})) for i in range(10)]"
    )
    processes = [
        subprocess.Popen([sys.executable, "-c", worker], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(4)
    ]

    for process in processes:
        stdout, stderr = process.communicate(timeout=30)
        assert process.returncode == 0, (stdout.decode(), stderr.decode())

    assert Archivist(log_path).verify_chain() == (
        True,
        40,
        "Verified 40 hash-chained entries intact.",
    )
