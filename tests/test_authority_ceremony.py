"""Authority migration ceremony: archive the exposed ledger, seal a fresh 3-of-5.

Uses synthetic passphrases, temporary directories and an isolated engine only.
"""
import importlib.util
import itertools
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
INCLUDE = ROOT / "quantumflex/include"
SHAMIR_SOURCE = ROOT / "quantumflex/src/crypto/crypto_shamir.cpp"
ENGINE = Path(os.environ.get("QF_TEST_BUILD_DIR", ROOT / "build_check")).resolve() / "quantum_flex_engine"
PASSPHRASES = {i: bytearray(f"synthetic-passphrase-{i}-xyz".encode()) for i in range(1, 6)}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ceremony = load("qf_authority_ceremony_under_test", ROOT / "tools/qf_authority_ceremony.py")
recovery = ceremony.recovery


@pytest.fixture(autouse=True)
def allow_pytest_temp(monkeypatch):
    # pytest's tmp_path lives under /tmp (tmpfs here), which the live ceremony refuses.
    monkeypatch.setattr(ceremony, "TEMP_ROOTS", ())
    monkeypatch.setattr(ceremony, "VOLATILE_FS", ())


@pytest.fixture(scope="module")
def natives(tmp_path_factory):
    if shutil.which("g++") is None or shutil.which("gpg") is None:
        pytest.fail("The ceremony tests require g++ and gpg.")
    out = tmp_path_factory.mktemp("natives")
    common = ["g++", "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(INCLUDE)]
    built = {}
    for name, source in (("split", "tools/qf_authority_split.cpp"), ("check", "tools/qf_legacy_recovery_check.cpp")):
        target = out / name
        subprocess.run([*common, str(ROOT / source), str(SHAMIR_SOURCE), "-lcrypto", "-o", str(target)],
                       check=True, capture_output=True, timeout=120)
        target.chmod(0o700)
        built[name] = target
    return built


def prompt(share_id):
    return bytearray(PASSPHRASES[share_id])


def start_engine(data_dir, pki, port):
    env = os.environ.copy()
    env.update(QF_DATA_DIR=str(data_dir), QF_POSTGRES_CONNINFO="", QF_BIND_ADDRESS="127.0.0.1",
               QF_BIND_PORT=str(port), QF_SERVER_CERT=str(pki / "server.crt"),
               QF_SERVER_KEY=str(pki / "server.key"), QF_ROOT_CA=str(pki / "ca.crt"),
               QF_ED_PRIVATE_KEY=str(data_dir / "missing-ed"), QF_PQC_PRIVATE_KEY=str(data_dir / "missing-pqc"),
               QF_KEM_PROPERTIES="provider=default")
    proc = subprocess.Popen([str(ENGINE)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return proc
        except OSError:
            time.sleep(0.05)
    proc.kill()
    pytest.fail("Isolated engine did not start.")


def stop_engine(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@pytest.fixture
def engine(tmp_path):
    if not ENGINE.is_file():
        pytest.skip(f"Engine binary not built: {ENGINE}")
    pki = tmp_path / "pki"
    pki.mkdir()

    def openssl(*args):
        subprocess.run(["openssl", *args], cwd=pki, check=True, capture_output=True)

    openssl("req", "-x509", "-newkey", "ed25519", "-noenc", "-keyout", "ca.key", "-out", "ca.crt",
            "-subj", "/CN=Ceremony Test CA", "-days", "1", "-addext", "keyUsage=critical,keyCertSign,cRLSign")
    (pki / "leaf.ext").write_text("basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\n"
                                  "extendedKeyUsage=serverAuth,clientAuth\nsubjectAltName=DNS:localhost,IP:127.0.0.1\n"
                                  "authorityKeyIdentifier=keyid,issuer\n")
    for name, cn in (("server", "127.0.0.1"), ("client", "operator")):
        openssl("req", "-new", "-newkey", "ed25519", "-noenc", "-keyout", f"{name}.key", "-out", f"{name}.csr",
                "-subj", f"/CN={cn}")
        openssl("x509", "-req", "-in", f"{name}.csr", "-CA", "ca.crt", "-CAkey", "ca.key", "-CAcreateserial",
                "-out", f"{name}.crt", "-days", "1", "-extfile", "leaf.ext")
    data = tmp_path / "data"
    data.mkdir()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    state = {"data": data, "pki": pki, "port": port, "proc": start_engine(data, pki, port),
             "transport": ("127.0.0.1", port, str(pki / "client.crt"), str(pki / "client.key"), str(pki / "ca.crt"))}
    yield state
    stop_engine(state["proc"])


def destinations(tmp_path):
    dirs = []
    for i in range(1, 6):
        d = tmp_path / f"custody{i}"
        d.mkdir()
        dirs.append(str(d))
    return dirs


STABLE = (4242, 1000)


def probing_guard(identities=None):
    """Real UNINITIALIZED probe; returns the next fake (pid, start) or STABLE."""
    sequence = iter(identities or [])

    def guard(ledger, transport, expect_engine_sha256):
        ceremony.probe_guard(ledger, transport)
        return next(sequence, STABLE)

    return guard


def pins(natives):
    return dict(expect_engine_sha256=ceremony.file_sha256(ENGINE),
                expect_splitter_sha256=ceremony.file_sha256(natives["split"]),
                expect_checker_sha256=ceremony.file_sha256(natives["check"]))


def run_genesis(engine, natives, tmp_path, prompt=prompt, **overrides):
    kwargs = dict(ledger=engine["data"] / "ledger.dat", transport=engine["transport"], guard=probing_guard(),
                  identity=lambda: STABLE, splitter=natives["split"], checker=natives["check"],
                  state_dir=tmp_path / "state", enforce_separation=False, gnupghome_parent=str(tmp_path), **pins(natives))
    kwargs.update(overrides)
    return ceremony.genesis(destinations(tmp_path), prompt, **kwargs)


# ── splitter ────────────────────────────────────────────────────────────────

def test_splitter_emits_five_distinct_shares(natives):
    out = subprocess.run([str(natives["split"])], capture_output=True, check=True).stdout.split(b"\n")
    assert out[-1] == b"" and len(out) == 6
    shares = [recovery.parse_share(line) for line in out[:5]]
    assert [s[:1] for s in shares] == [b"1", b"2", b"3", b"4", b"5"]
    assert len(set(shares)) == 5


def test_splitter_is_fresh_each_run(natives):
    first = subprocess.run([str(natives["split"])], capture_output=True, check=True).stdout
    second = subprocess.run([str(natives["split"])], capture_output=True, check=True).stdout
    assert first != second


def test_splitter_refuses_terminal_stdout(natives):
    if shutil.which("script") is None:
        pytest.skip("util-linux script(1) unavailable")
    result = subprocess.run(["script", "-qec", str(natives["split"]), "/dev/null"], capture_output=True, timeout=10)
    assert result.returncode != 0
    assert b"ERROR_STDOUT_IS_TERMINAL" in result.stdout
    assert not any(recovery.SHARE_PATTERN.search(line) for line in result.stdout.splitlines())


def test_splitter_rejects_arguments(natives):
    result = subprocess.run([str(natives["split"]), "--total", "2"], capture_output=True)
    assert result.returncode == 2 and result.stdout == b""


# ── genesis end to end ──────────────────────────────────────────────────────

def test_genesis_seals_verifies_and_unlocks_after_restart(engine, natives, tmp_path):
    manifest_path = run_genesis(engine, natives, tmp_path)
    ledger = engine["data"] / "ledger.dat"
    raw = ledger.read_bytes()
    assert raw.endswith(b"\nSTATUS|ACTIVE\n")

    sealed = sorted(Path(tmp_path).glob("custody*/qf-authority-*-share*.gpg"))
    assert len(sealed) == 5
    plain = []
    with recovery.private_gnupghome(str(tmp_path)) as home:
        for share_id, path in enumerate(sealed, start=1):
            assert stat_mode(path) == 0o400
            body = path.read_bytes()
            assert not recovery.SHARE_PATTERN.search(body)
            opened = recovery.gpg_open(path, PASSPHRASES[share_id], home)
            plain.append(recovery.parse_share(opened))
            with pytest.raises(recovery.RecoveryError):
                recovery.gpg_open(path, bytearray(b"wrong-passphrase-entirely"), home)

    manifest = manifest_path.read_text()
    recorded = ceremony.json.loads(manifest)
    expected = pins(natives)
    assert (recorded["engine_sha256"], recorded["splitter_sha256"], recorded["checker_sha256"]) == (
        expected["expect_engine_sha256"], expected["expect_splitter_sha256"], expected["expect_checker_sha256"])
    for share in plain:
        assert share[2:].decode() not in manifest
    for subset in itertools.combinations(plain, 3):
        assert recovery.check_ledger(list(subset), ledger, natives["check"])

    # Restart: the engine must boot LOCKED and accept any three sealed shares.
    stop_engine(engine["proc"])
    engine["proc"] = start_engine(engine["data"], engine["pki"], engine["port"])
    assert ceremony.probe(engine["transport"], b"STATUS") == "ERR|NODE_LOCKED\n"
    request = bytearray(b"UNLOCK|" + b",".join([plain[4], plain[1], plain[3]]))
    assert ceremony.probe(engine["transport"], request) == "ACK|NODE_UNLOCKED\n"


def stat_mode(path):
    return os.stat(path).st_mode & 0o777


def test_genesis_refuses_an_already_sealed_engine(engine, natives, tmp_path):
    first = tmp_path / "first"
    first.mkdir()
    run_genesis(engine, natives, first)
    before = (engine["data"] / "ledger.dat").read_bytes()
    second = tmp_path / "second"
    second.mkdir()
    with pytest.raises(recovery.RecoveryError, match="UNINITIALIZED"):
        run_genesis(engine, natives, second)
    assert (engine["data"] / "ledger.dat").read_bytes() == before
    assert not list(second.glob("custody*/*.gpg"))


def test_genesis_refuses_legacy_locked_ledger(engine, natives, tmp_path):
    stop_engine(engine["proc"])
    ledger = engine["data"] / "ledger.dat"
    ledger.write_text("STATE_ROOT|" + recovery.EMPTY_ROOT.decode() + "\nTIMESTAMP|1791766984\n"
                      "LEDGER_SIGNATURE|" + "ab" * 32 + "\nSTATUS|ACTIVE\n")
    engine["proc"] = start_engine(engine["data"], engine["pki"], engine["port"])
    with pytest.raises(recovery.RecoveryError, match="not a fresh UNINITIALIZED"):
        run_genesis(engine, natives, tmp_path)
    assert not list(tmp_path.glob("custody*/*.gpg"))


def test_failed_sealing_leaves_no_files_and_engine_uninitialized(engine, natives, tmp_path, monkeypatch):
    calls = {"n": 0}
    real = ceremony.seal_share

    def flaky(*args):
        calls["n"] += 1
        if calls["n"] == 3:
            raise recovery.RecoveryError("simulated sealing failure")
        return real(*args)

    monkeypatch.setattr(ceremony, "seal_share", flaky)
    with pytest.raises(recovery.RecoveryError, match="simulated"):
        run_genesis(engine, natives, tmp_path)
    assert not list(tmp_path.glob("custody*/*.gpg"))
    assert ceremony.probe(engine["transport"], b"STATUS") == "ERR|NODE_UNINITIALIZED_CALL_INIT\n"


# ── destination and passphrase rules ────────────────────────────────────────

def test_destinations_reject_agent_repo_and_temp_dirs(tmp_path, monkeypatch):
    stamp = "T"
    good = destinations(tmp_path)
    monkeypatch.setattr(ceremony, "TEMP_ROOTS", ("/var/tmp", "/dev/shm", "/tmp"))
    with pytest.raises(recovery.RecoveryError, match=r"Share 1: .*temporary"):
        ceremony.validate_destinations(good, stamp, enforce_separation=False)
    monkeypatch.setattr(ceremony, "TEMP_ROOTS", ())
    # No "/tmp" here: TEMP_ROOTS was just cleared so tmp_path (under /tmp) can
    # serve as the other four destinations, which means /tmp itself is allowed.
    for bad in (str(ceremony.REPO), str(Path.home() / ".gemini")):
        if not Path(bad).is_dir():
            continue
        with pytest.raises(recovery.RecoveryError, match=r"Share 1: .*repository"):
            ceremony.validate_destinations([bad] + good[1:], stamp, enforce_separation=False)


def separated(dirs, devices, disks, home_device=9):
    """Fake filesystem ids and physical disks; disks maps dir -> (name, removable)."""
    def device_of(path):
        return home_device if Path(path) == Path.home() else devices[str(path)]

    def disk_of(path):
        found = disks[str(path)]
        return None if found is None else frozenset({found})

    return dict(enforce_separation=True, device_of=device_of, disk_of=disk_of)


def test_destinations_reject_threshold_on_one_disk(tmp_path):
    dirs = destinations(tmp_path)
    devices = dict(zip(dirs, [1, 2, 3, 4, 5]))
    disks = dict(zip(dirs, [("sda", False), ("sdb", True), ("sdb", True), ("sdb", True), ("sdc", True)]))
    with pytest.raises(recovery.RecoveryError, match="one physical disk"):
        ceremony.validate_destinations(dirs, "T", **separated(dirs, devices, disks))


def test_destinations_reject_two_partitions_of_one_fixed_disk(tmp_path):
    dirs = destinations(tmp_path)
    devices = dict(zip(dirs, [1, 2, 3, 4, 5]))  # five distinct filesystems
    disks = dict(zip(dirs, [("nvme0n1", False), ("nvme0n1", False), ("sdb", True), ("sdc", True), ("sdd", True)]))
    with pytest.raises(recovery.RecoveryError, match="fixed"):
        ceremony.validate_destinations(dirs, "T", **separated(dirs, devices, disks))


def test_destinations_reject_unknown_disk(tmp_path):
    dirs = destinations(tmp_path)
    devices = dict(zip(dirs, [1, 2, 3, 4, 5]))
    disks = dict(zip(dirs, [("sda", False), ("sdb", True), None, ("sdc", True), ("sdd", True)]))
    with pytest.raises(recovery.RecoveryError, match=r"Share 3: .*could not be determined"):
        ceremony.validate_destinations(dirs, "T", **separated(dirs, devices, disks))


def test_destinations_allow_one_share_on_home(tmp_path):
    dirs = destinations(tmp_path)
    devices = {dirs[0]: 9, dirs[1]: 2, dirs[2]: 2, dirs[3]: 3, dirs[4]: 3}
    disks = dict(zip(dirs, [("nvme0n1", False), ("sdb", True), ("sdb", True), ("sdc", True), ("sdc", True)]))
    assert len(ceremony.validate_destinations(dirs, "T", **separated(dirs, devices, disks))) == 5
    devices[dirs[1]] = 9
    with pytest.raises(recovery.RecoveryError, match="home filesystem"):
        ceremony.validate_destinations(dirs, "T", **separated(dirs, devices, disks))


def test_destinations_reject_existing_sealed_file(tmp_path):
    dirs = destinations(tmp_path)
    (Path(dirs[2]) / ceremony.SEALED_NAME.format(stamp="T", share_id=3)).write_bytes(b"x")
    with pytest.raises(recovery.RecoveryError, match="already exists"):
        ceremony.validate_destinations(dirs, "T", enforce_separation=False)


def test_passphrases_must_be_long_and_distinct():
    with pytest.raises(recovery.RecoveryError, match="at least 20"):
        ceremony.collect_passphrases(lambda i: bytearray(b"short"))
    with pytest.raises(recovery.RecoveryError, match="at least 20"):
        ceremony.collect_passphrases(lambda i: bytearray(b"x" * 18 + str(i).encode()))  # 19 bytes
    assert len(ceremony.collect_passphrases(lambda i: bytearray(b"y" * 19 + str(i).encode()))) == 5
    with pytest.raises(recovery.RecoveryError, match="reused"):
        ceremony.collect_passphrases(lambda i: bytearray(b"same-passphrase-for-all"))
    assert len(ceremony.collect_passphrases(prompt)) == 5


# ── legacy archive ──────────────────────────────────────────────────────────

def legacy_ledger(tmp_path):
    ledger = tmp_path / "ledger.dat"
    ledger.write_bytes(b"STATE_ROOT|" + recovery.EMPTY_ROOT + b"\nTIMESTAMP|1791766984\nLEDGER_SIGNATURE|"
                       + b"cd" * 32 + b"\nSTATUS|ACTIVE\n")
    return ledger


def test_archive_refuses_running_engine(tmp_path):
    ledger = legacy_ledger(tmp_path)
    digest = ceremony.hashlib.sha256(ledger.read_bytes()).hexdigest()
    with pytest.raises(recovery.RecoveryError, match="Stop the engine"):
        ceremony.archive_legacy(digest, ledger, tmp_path / "state", lambda: "active")
    assert ledger.exists()


def test_archive_refuses_wrong_digest(tmp_path):
    ledger = legacy_ledger(tmp_path)
    with pytest.raises(recovery.RecoveryError, match="does not match"):
        ceremony.archive_legacy("0" * 64, ledger, tmp_path / "state", lambda: "inactive")
    assert ledger.exists()


def test_archive_moves_read_only_and_records(tmp_path):
    ledger = legacy_ledger(tmp_path)
    original = ledger.read_bytes()
    digest = ceremony.hashlib.sha256(original).hexdigest()
    archive, manifest = ceremony.archive_legacy(digest, ledger, tmp_path / "state", lambda: "failed")
    assert not ledger.exists()
    assert archive.read_bytes() == original
    assert stat_mode(archive) == 0o400
    assert digest in manifest.read_text()


def test_engine_writes_fresh_envelope_after_archive(engine, natives, tmp_path):
    # Mirrors the live order: stop, archive, start -> UNINITIALIZED envelope.
    stop_engine(engine["proc"])
    ledger = engine["data"] / "ledger.dat"
    if ledger.exists():
        digest = ceremony.hashlib.sha256(ledger.read_bytes()).hexdigest()
        ceremony.archive_legacy(digest, ledger, tmp_path / "state", lambda: "inactive")
    engine["proc"] = start_engine(engine["data"], engine["pki"], engine["port"])
    assert ceremony.uninitialized_ledger(ledger.read_bytes())


# ── after INIT: keep or remove sealed files ─────────────────────────────────

def intercept_init(monkeypatch, on_init):
    real = ceremony.probe

    def fake(transport, request):
        if bytes(request).startswith(b"INIT|"):
            return on_init(real, transport, request)
        return real(transport, request)

    monkeypatch.setattr(ceremony, "probe", fake)


def sealed_files(tmp_path):
    return sorted(tmp_path.glob("custody*/qf-authority-*-share*.gpg"))


def test_interrupt_after_init_keeps_sealed_files(engine, natives, tmp_path, monkeypatch):
    def interrupted(real, transport, request):
        real(transport, request)
        raise KeyboardInterrupt

    intercept_init(monkeypatch, interrupted)
    with pytest.raises(recovery.RecoveryError, match="KEPT"):
        run_genesis(engine, natives, tmp_path)
    assert len(sealed_files(tmp_path)) == 5
    assert (engine["data"] / "ledger.dat").read_bytes().endswith(b"\nSTATUS|ACTIVE\n")
    assert len(list((tmp_path / "state").glob("*-INCOMPLETE.json"))) == 1


def test_init_sent_but_ledger_untouched_keeps_files(engine, natives, tmp_path, monkeypatch):
    # The engine may still be running initialize_node when the client gives up;
    # an UNINITIALIZED read at that moment proves nothing, so nothing is deleted.
    def dropped(real, transport, request):
        raise ConnectionResetError

    intercept_init(monkeypatch, dropped)
    with pytest.raises(recovery.RecoveryError, match="KEPT.*confirm UNINITIALIZED"):
        run_genesis(engine, natives, tmp_path)
    assert len(sealed_files(tmp_path)) == 5
    assert ceremony.uninitialized_ledger((engine["data"] / "ledger.dat").read_bytes())
    assert len(list((tmp_path / "state").glob("*-INCOMPLETE.json"))) == 1


def test_lost_reply_with_active_ledger_succeeds_and_keeps_files(engine, natives, tmp_path, monkeypatch):
    def lost(real, transport, request):
        real(transport, request)
        return ""

    intercept_init(monkeypatch, lost)
    manifest = run_genesis(engine, natives, tmp_path)
    assert manifest.is_file()
    assert len(sealed_files(tmp_path)) == 5


def test_active_ledger_subset_mismatch_keeps_files_and_records_them(engine, natives, tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "check_ledger", lambda *args: False)
    with pytest.raises(recovery.RecoveryError, match="KEPT") as raised:
        run_genesis(engine, natives, tmp_path)
    files = sealed_files(tmp_path)
    assert len(files) == 5
    records = list((tmp_path / "state").glob("*-INCOMPLETE.json"))
    assert len(records) == 1 and str(records[0]) in str(raised.value)
    record = ceremony.json.loads(records[0].read_text())
    assert "does not authenticate" in record["reason"]
    assert sorted(entry["path"] for entry in record["sealed_shares"]) == [str(f) for f in files]
    assert all(entry["ciphertext_sha256"] == ceremony.file_sha256(entry["path"]) for entry in record["sealed_shares"])
    assert not list((tmp_path / "state").glob("authority-genesis-*Z.json"))


# ── filesystem type and physical disk discovery ─────────────────────────────

def test_destinations_reject_tmpfs_by_type(tmp_path, monkeypatch):
    monkeypatch.setattr(ceremony, "VOLATILE_FS", ("tmpfs", "ramfs", "devtmpfs"))
    dirs = destinations(tmp_path)
    kinds = {dirs[0]: "tmpfs"}
    with pytest.raises(recovery.RecoveryError, match=r"Share 1: .*temporary memory"):
        ceremony.validate_destinations(dirs, "T", enforce_separation=False,
                                       fs_type_of=lambda p: kinds.get(str(p), "ext4"))
    kinds = {dirs[2]: None}
    with pytest.raises(recovery.RecoveryError, match=r"Share 3: .*unknown type"):
        ceremony.validate_destinations(dirs, "T", enforce_separation=False,
                                       fs_type_of=lambda p: kinds.get(str(p), "ext4"))


def test_filesystem_type_uses_longest_mount_point(tmp_path):
    mountinfo = tmp_path / "mountinfo"
    mountinfo.write_text(
        "1 0 259:2 / / rw shared:1 - ext4 /dev/nvme0n1p2 rw\n"
        "2 1 0:25 / /run rw shared:2 - tmpfs tmpfs rw\n"
        "3 2 8:17 / /run/media/me/USB\\040ONE rw shared:3 - vfat /dev/sdb1 rw\n"
        "4 2 0:30 / /run/user/1000 rw - tmpfs tmpfs rw\n")
    assert ceremony.filesystem_type("/run/media/me/USB ONE/x", mountinfo) == "vfat"
    assert ceremony.filesystem_type("/run/user/1000/x", mountinfo) == "tmpfs"
    assert ceremony.filesystem_type("/run/other", mountinfo) == "tmpfs"
    assert ceremony.filesystem_type("/home/me", mountinfo) == "ext4"
    assert ceremony.filesystem_type("/home/me", tmp_path / "missing") is None


def test_disks_of_device_follows_partition_and_slaves(tmp_path):
    sys = tmp_path / "sys"
    nvme = sys / "devices/nvme0n1"
    (nvme / "nvme0n1p2").mkdir(parents=True)
    (nvme / "nvme0n1p2/partition").write_text("2\n")
    (nvme / "removable").write_text("0\n")
    usb = sys / "devices/sdb"
    (usb / "sdb1").mkdir(parents=True)
    (usb / "sdb1/partition").write_text("1\n")
    (usb / "removable").write_text("1\n")
    dm = sys / "devices/dm-0"
    (dm / "slaves").mkdir(parents=True)
    (dm / "slaves/sdb1").symlink_to(usb / "sdb1")
    (sys / "dev/block").mkdir(parents=True)
    for name, node in (("259:2", nvme / "nvme0n1p2"), ("8:17", usb / "sdb1"), ("253:0", dm)):
        (sys / "dev/block" / name).symlink_to(node)
    assert ceremony.disks_of_device(os.makedev(259, 2), sys) == frozenset({("nvme0n1", False)})
    assert ceremony.disks_of_device(os.makedev(8, 17), sys) == frozenset({("sdb", True)})
    assert ceremony.disks_of_device(os.makedev(253, 0), sys) == frozenset({("sdb", True)})
    # dm (e.g. LUKS) on an NVMe partition resolves to the fixed NVMe disk.
    (nvme / "nvme0n1p3").mkdir()
    (nvme / "nvme0n1p3/partition").write_text("3\n")
    dm1 = sys / "devices/dm-1"
    (dm1 / "slaves").mkdir(parents=True)
    (dm1 / "slaves/nvme0n1p3").symlink_to(nvme / "nvme0n1p3")
    (sys / "dev/block/253:1").symlink_to(dm1)
    assert ceremony.disks_of_device(os.makedev(253, 1), sys) == frozenset({("nvme0n1", False)})
    assert ceremony.disks_of_device(os.makedev(0, 44), sys) is None  # network/virtual fs
    assert ceremony.disks_of_device(os.makedev(8, 99), sys) is None  # no sysfs node


def test_destinations_reject_expanduser_duplicate(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    dirs = destinations(tmp_path)
    with pytest.raises(recovery.RecoveryError, match="distinct"):
        ceremony.validate_destinations(["~/custody1"] + dirs[:4], "T", enforce_separation=False)


# ── gpg_open reads once ─────────────────────────────────────────────────────

def test_gpg_open_passes_bounded_bytes_not_path(tmp_path, monkeypatch):
    sealed = tmp_path / "share.gpg"
    sealed.write_bytes(b"sealed-bytes")
    seen = {}

    def fake_run_gpg(command, passphrase, stdin_bytes, gnupghome):
        seen.update(command=command, stdin=stdin_bytes)
        return b"1:" + b"a" * 64 + b"\n"

    monkeypatch.setattr(recovery, "run_gpg", fake_run_gpg)
    recovery.gpg_open(sealed, bytearray(b"synthetic-passphrase"), str(tmp_path))
    assert seen["stdin"] == b"sealed-bytes"
    assert seen["command"][-1] == "--decrypt"
    assert not any(str(sealed) in part for part in seen["command"])


# ── live guard (fake systemctl and /proc only) ──────────────────────────────

def fake_systemctl(monkeypatch, stdout=None, error=None):
    def run(command, **kwargs):
        assert command[:3] == ["systemctl", "--user", "show"]
        if error:
            raise error
        return subprocess.CompletedProcess(command, 0, stdout, b"")

    monkeypatch.setattr(ceremony.subprocess, "run", run)


def test_live_guard_refuses_other_ledger(tmp_path):
    with pytest.raises(recovery.RecoveryError, match="configured local ledger"):
        ceremony.live_guard(tmp_path / "ledger.dat", None, "0" * 64)


def test_live_guard_refuses_stopped_engine(monkeypatch):
    fake_systemctl(monkeypatch, b"MainPID=0\nActiveState=inactive\n")
    with pytest.raises(recovery.RecoveryError, match="Start the engine"):
        ceremony.live_guard(ceremony.DEFAULT_LEDGER, None, "0" * 64)


def test_live_guard_refuses_unexpected_executable(monkeypatch):
    fake_systemctl(monkeypatch, f"MainPID={os.getpid()}\nActiveState=active\n".encode())
    with pytest.raises(recovery.RecoveryError, match="expected local executable"):
        ceremony.live_guard(ceremony.DEFAULT_LEDGER, None, "0" * 64)


def test_live_guard_refuses_when_systemctl_fails(monkeypatch):
    fake_systemctl(monkeypatch, error=subprocess.TimeoutExpired("systemctl", 5))
    with pytest.raises(recovery.RecoveryError, match="could not be bound"):
        ceremony.live_guard(ceremony.DEFAULT_LEDGER, None, "0" * 64)


# ── command line ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("argv", [
    ["genesis", "--dest", "/a,/b,/c,/d"],
    ["genesis", "--dest", "/a,/b,/c,/d,/e"],
    ["genesis", "--dest", "/a,/b,/c,/d,/e", "--expect-engine-sha256", "0" * 64,
     "--expect-splitter-sha256", "0" * 64],
    ["genesis", "--dest", "/a,/b,/c,/d,/e", "--expect-engine-sha256", "0" * 64,
     "--expect-splitter-sha256", "0" * 64, "--expect-checker-sha256", "ABC"],
    ["genesis", "--dest", "/a,/b,/c,/d,/e,/f"],
    ["genesis", "--dest", "/a,,/c,/d,/e"],
    ["genesis"],
    ["archive-legacy", "--expect-sha256", "not-hex"],
    ["no-such-command"],
])
def test_main_refuses_bad_arguments_before_any_action(argv, monkeypatch, capsys):
    def never(*args, **kwargs):
        raise AssertionError("must not run")

    monkeypatch.setattr(ceremony, "genesis", never)
    monkeypatch.setattr(ceremony, "systemd_active_state", never)
    assert ceremony.main(argv) == 2
    assert capsys.readouterr().out == ""


# ── integrity pins (B1) ─────────────────────────────────────────────────────

def never_prompt(share_id):
    raise AssertionError("passphrase requested before the integrity check")


def never_guard(*args):
    raise AssertionError("engine guard reached before the integrity check")


@pytest.mark.parametrize("pin", ["expect_splitter_sha256", "expect_checker_sha256"])
def test_genesis_refuses_pinned_binary_mismatch_before_passphrases(natives, tmp_path, pin):
    kwargs = dict(expect_engine_sha256="0" * 64,
                  expect_splitter_sha256=ceremony.file_sha256(natives["split"]),
                  expect_checker_sha256=ceremony.file_sha256(natives["check"]))
    kwargs[pin] = "f" * 64
    with pytest.raises(recovery.RecoveryError, match="does not match its pinned SHA-256"):
        ceremony.genesis(destinations(tmp_path), never_prompt, ledger=tmp_path / "ledger.dat", transport=("x",),
                         guard=never_guard, splitter=natives["split"], checker=natives["check"],
                         state_dir=tmp_path / "state", enforce_separation=False, gnupghome_parent=str(tmp_path), **kwargs)
    assert not list(tmp_path.glob("custody*/*.gpg"))


def test_splitter_rehashed_immediately_before_use(natives, tmp_path):
    copy = tmp_path / "split"
    shutil.copy2(natives["split"], copy)
    pinned = ceremony.file_sha256(copy)
    assert len(ceremony.generate_shares(copy, pinned)) == 5
    with open(copy, "ab") as out:
        out.write(b"\0")
    with pytest.raises(recovery.RecoveryError, match="native splitter does not match"):
        ceremony.generate_shares(copy, pinned)


def test_check_ledger_rehashes_checker(natives, tmp_path):
    with pytest.raises(recovery.RecoveryError, match="native checker does not match"):
        recovery.check_ledger([b"1:" + b"a" * 64, b"2:" + b"b" * 64, b"3:" + b"c" * 64],
                              tmp_path / "ledger.dat", natives["check"], "f" * 64)


GOOD_ENV = [b"QF_DATA_DIR=" + os.fsencode(ceremony.DATA_DIR), b"QF_BIND_ADDRESS=127.0.0.1", b"QF_BIND_PORT=9444"]


def fake_proc(tmp_path, monkeypatch, module, env=GOOD_ENV, start=777):
    """A fake /proc/<pid> whose exe link points at a synthetic engine file; returns its SHA-256."""
    binary = tmp_path / "engine-bin"
    binary.write_bytes(b"synthetic engine")
    proc = tmp_path / "proc" / "4242"
    proc.mkdir(parents=True)
    (proc / "exe").symlink_to(binary)
    (proc / "environ").write_bytes(b"\0".join(env) + b"\0")
    (proc / "stat").write_text("4242 (quantum) flex) S " + " ".join(["0"] * 18) + f" {start} 0 0\n")
    ledger = tmp_path / "live-ledger.dat"
    ledger.write_bytes(b"x")
    monkeypatch.setattr(module, "PROC", tmp_path / "proc")
    monkeypatch.setattr(module, "ENGINE_PATH", binary)
    monkeypatch.setattr(module, "DEFAULT_LEDGER", ledger)
    fake_systemctl(monkeypatch, b"MainPID=4242\nActiveState=active\n")
    return ceremony.file_sha256(binary)


def test_live_guard_binds_pinned_engine_and_returns_identity(tmp_path, monkeypatch):
    digest = fake_proc(tmp_path, monkeypatch, ceremony)
    monkeypatch.setattr(ceremony, "probe_guard", lambda ledger, transport: None)
    assert ceremony.live_guard(ceremony.DEFAULT_LEDGER, None, digest) == (4242, 777)
    assert ceremony.live_identity() == (4242, 777)


def test_live_guard_refuses_engine_hash_mismatch(tmp_path, monkeypatch):
    fake_proc(tmp_path, monkeypatch, ceremony)
    with pytest.raises(recovery.RecoveryError, match="running engine executable does not match"):
        ceremony.live_guard(ceremony.DEFAULT_LEDGER, None, "f" * 64)


def test_genesis_refuses_engine_hash_mismatch_before_passphrases(natives, tmp_path, monkeypatch):
    fake_proc(tmp_path, monkeypatch, ceremony)
    kwargs = pins_without_engine(natives)
    with pytest.raises(recovery.RecoveryError, match="running engine executable does not match"):
        ceremony.genesis(destinations(tmp_path), never_prompt, ledger=ceremony.DEFAULT_LEDGER, transport=("x",),
                         splitter=natives["split"], checker=natives["check"], state_dir=tmp_path / "state",
                         enforce_separation=False, expect_engine_sha256="f" * 64, **kwargs)


def pins_without_engine(natives):
    return dict(expect_splitter_sha256=ceremony.file_sha256(natives["split"]),
                expect_checker_sha256=ceremony.file_sha256(natives["check"]))


@pytest.mark.parametrize("module", [ceremony, recovery], ids=["ceremony", "recovery"])
def test_guards_refuse_loader_override(tmp_path, monkeypatch, module):
    digest = fake_proc(tmp_path, monkeypatch, module, env=GOOD_ENV + [b"LD_PRELOAD=/x/evil.so"])
    with pytest.raises(recovery.RecoveryError, match=r"LD_\*"):
        if module is ceremony:
            ceremony.live_guard(ceremony.DEFAULT_LEDGER, None, digest)
        else:
            recovery.runtime_guard(recovery.DEFAULT_LEDGER, digest)


def test_runtime_guard_refuses_engine_hash_mismatch_and_missing_pin(tmp_path, monkeypatch):
    fake_proc(tmp_path, monkeypatch, recovery)
    with pytest.raises(recovery.RecoveryError, match="running engine executable does not match"):
        recovery.runtime_guard(recovery.DEFAULT_LEDGER, "f" * 64)
    with pytest.raises(recovery.RecoveryError, match="64 lowercase hex"):
        recovery.runtime_guard(recovery.DEFAULT_LEDGER, None)


def test_recovery_unlock_without_engine_pin_refuses_before_engine_contact(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "HOLD_FILE", tmp_path / "no-hold")
    ledger = tmp_path / "ledger.dat"
    ledger.write_bytes(b"STATE_ROOT|" + recovery.EMPTY_ROOT + b"\nTIMESTAMP|1\n")
    monkeypatch.setattr(recovery, "DEFAULT_LEDGER", ledger)
    monkeypatch.setattr(recovery.subprocess, "run", lambda *a, **k: pytest.fail("reached systemctl"))
    monkeypatch.setattr(recovery, "ipc_client", lambda: pytest.fail("reached transport"))
    digest = ceremony.hashlib.sha256(ledger.read_bytes()).digest()
    args = recovery.argparse.Namespace(expect_engine_sha256=None)
    with pytest.raises(recovery.RecoveryError, match="running engine executable must be 64 lowercase hex"):
        recovery.unlock_checked([b"1:" + b"a" * 64, b"2:" + b"b" * 64, b"3:" + b"c" * 64], ledger, digest, args)


def test_recovery_checker_pin_checked_before_any_password(natives, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(recovery, "private_password", never_prompt)
    assert recovery.main(["--check", "--checker", str(natives["check"]), "--expect-checker-sha256", "f" * 64,
                          "--ledger", str(tmp_path / "ledger.dat")]) == 2
    assert "native checker does not match" in capsys.readouterr().err


# ── engine identity across checkpoints (B2) ─────────────────────────────────

OTHER = (4242, 2000)


@pytest.mark.parametrize("identities, when", [([STABLE, OTHER], "while passphrases"),
                                              ([STABLE, STABLE, OTHER], "before INIT")])
def test_engine_identity_change_before_init_refuses_and_removes(engine, natives, tmp_path, identities, when):
    with pytest.raises(ceremony.EngineChanged, match=when):
        run_genesis(engine, natives, tmp_path, guard=probing_guard(identities))
    assert not sealed_files(tmp_path)
    assert ceremony.probe(engine["transport"], b"STATUS") == "ERR|NODE_UNINITIALIZED_CALL_INIT\n"


def test_engine_identity_change_during_init_keeps_files_as_exposed(engine, natives, tmp_path):
    with pytest.raises(recovery.RecoveryError, match="IDENTITY CHANGED DURING INIT.*EXPOSED.*KEPT") as raised:
        run_genesis(engine, natives, tmp_path, identity=lambda: OTHER)
    assert len(sealed_files(tmp_path)) == 5
    records = list((tmp_path / "state").glob("*-INCOMPLETE.json"))
    assert len(records) == 1 and str(records[0]) in str(raised.value)
    assert not list((tmp_path / "state").glob("authority-genesis-*Z.json"))


# ── orphan ciphertext after gpg (L2) ────────────────────────────────────────

def test_flush_failure_after_gpg_removes_the_new_ciphertext(engine, natives, tmp_path, monkeypatch):
    calls = {"n": 0}
    real = os.fsync

    def failing(fd):
        calls["n"] += 1
        if calls["n"] == 5:  # share 3, file fsync: gpg has already written it
            raise OSError("simulated")
        return real(fd)

    monkeypatch.setattr(ceremony.os, "fsync", failing)
    with pytest.raises(recovery.RecoveryError, match="flushed"):
        run_genesis(engine, natives, tmp_path)
    assert not sealed_files(tmp_path)
    assert ceremony.probe(engine["transport"], b"STATUS") == "ERR|NODE_UNINITIALIZED_CALL_INIT\n"


# ── private gpg home (B4) ───────────────────────────────────────────────────

def test_private_gnupghome_refuses_missing_or_shared_runtime_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    with pytest.raises(recovery.RecoveryError, match="refusing to fall back to /tmp"):
        with recovery.private_gnupghome():
            pass
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    shared.chmod(0o755)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(shared))
    with pytest.raises(recovery.RecoveryError, match="XDG_RUNTIME_DIR"):
        with recovery.private_gnupghome():
            pass
    private = tmp_path / "private"
    private.mkdir()
    private.chmod(0o700)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(private))
    with recovery.private_gnupghome() as home:
        assert Path(home).parent == private
    with recovery.private_gnupghome(str(shared)) as home:  # explicit parent is the caller's choice
        assert Path(home).parent == shared


# ── checked binary runs from the hashed bytes, not the path ─────────────────

FAKE_MATCH = "#!/bin/sh\necho MATCH\n"


def swap_before_exec(monkeypatch, path, how):
    """Replace or rewrite `path` on disk after it was opened and hashed, just before exec."""
    real = subprocess.run

    def run(command, **kwargs):
        if how == "rename":
            fake = path.with_name("fake")
            fake.write_text(FAKE_MATCH)
            fake.chmod(0o700)
            os.replace(fake, path)
        else:
            with open(path, "r+b") as out:
                out.write(FAKE_MATCH.encode())
        assert kwargs["executable"].startswith("/proc/self/fd/") and command[0] == str(path)
        return real(command, **kwargs)

    monkeypatch.setattr(ceremony.subprocess, "run", run)


@pytest.mark.parametrize("how", ["rename", "rewrite"])
def test_swapped_splitter_does_not_run(natives, tmp_path, monkeypatch, how):
    copy = tmp_path / "split"
    shutil.copy2(natives["split"], copy)
    pinned = ceremony.file_sha256(copy)
    swap_before_exec(monkeypatch, copy, how)
    shares = ceremony.generate_shares(copy, pinned)
    assert [s[:1] for s in shares] == [b"1", b"2", b"3", b"4", b"5"]
    assert ceremony.file_sha256(copy) != pinned  # the disk copy really changed


@pytest.mark.parametrize("pin", [True, False])
def test_swapped_checker_does_not_run(natives, tmp_path, monkeypatch, pin):
    copy = tmp_path / "check"
    shutil.copy2(natives["check"], copy)
    pinned = ceremony.file_sha256(copy) if pin else None
    ledger = legacy_ledger(tmp_path)
    swap_before_exec(monkeypatch, copy, "rename")
    shares = [b"1:" + b"a" * 64, b"2:" + b"b" * 64, b"3:" + b"c" * 64]
    assert recovery.check_ledger(shares, ledger, copy, pinned) is False  # the fake would say MATCH
    assert copy.read_text() == FAKE_MATCH


def test_opened_executable_refuses_link_and_unsafe_mode(natives, tmp_path):
    link = tmp_path / "link"
    link.symlink_to(natives["split"])
    with pytest.raises(recovery.RecoveryError, match="unavailable"):
        with recovery.opened_executable(link, "native splitter"):
            pass
    copy = tmp_path / "split"
    shutil.copy2(natives["split"], copy)
    copy.chmod(0o722)
    with pytest.raises(recovery.RecoveryError, match="unsafe permissions"):
        with recovery.opened_executable(copy, "native splitter"):
            pass
