"""Recovery boundaries: synthetic inputs only, no real vault or live engine."""
import gzip
import importlib.util
import io
from pathlib import Path
import tarfile

from PIL import Image
import pytest
from tests.test_legacy_recovery_check import native_tools, ledger_text


REPO = Path(__file__).resolve().parents[1]
SHARES = [b'1:' + b'11' * 32, b'4:' + b'44' * 32, b'5:' + b'55' * 32]


@pytest.fixture
def recovery(tmp_path):
    spec = importlib.util.spec_from_file_location('vault_recovery', REPO / 'tools/qf_recovery.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.HOLD_FILE = tmp_path / 'unlock.hold'
    return module


def image_payload(shares=SHARES[1:]):
    message = b'QFX_STEGO|' + b'|'.join(shares) + b'|END'
    image = Image.new('RGB', (64, 64), (20, 30, 40))
    pixels = image.load()
    for index in range(len(message) * 8):
        x, y = index % 64, index // 64
        bit = (message[index // 8] >> (7 - index % 8)) & 1
        pixels[x, y] = (20, 30, 40 | bit)
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def archive(name='quantumflex_watermark.png', content=None, link=False, duplicate=False):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w') as tar:
        member = tarfile.TarInfo(name)
        if link:
            member.type = tarfile.SYMTYPE
            member.linkname = '/tmp/elsewhere'
            tar.addfile(member)
        else:
            content = image_payload() if content is None else content
            member.size = len(content)
            tar.addfile(member, io.BytesIO(content))
            if duplicate:
                tar.addfile(member, io.BytesIO(content))
    return gzip.compress(output.getvalue())


def test_vault_read_is_memory_only_and_strict(recovery, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert recovery.vault_shares(archive()) == SHARES[1:]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('options', [
    {'name': '../quantumflex_watermark.png'},
    {'name': '/quantumflex_watermark.png'},
    {'link': True}, {'duplicate': True}, {'content': b'not a PNG'},
    {'name': 'different.png'},
])
def test_bad_archives_never_recover(recovery, options):
    with pytest.raises(recovery.RecoveryError):
        recovery.vault_shares(archive(**options))


def test_decompression_is_bounded(recovery, monkeypatch):
    monkeypatch.setattr(recovery, 'MAX_ARCHIVE_BYTES', 128)
    with pytest.raises(recovery.RecoveryError):
        recovery.vault_shares(gzip.compress(b'x' * 129))


@pytest.mark.parametrize('raw', [b'Salted__' + b'x' * 60, b'1:' + b'z' * 64,
    SHARES[0] + b'\n' + SHARES[1], b'0:' + b'00' * 32, b'6:' + b'00' * 32])
def test_bad_or_encrypted_plaintext_refused_before_checker(recovery, raw):
    with pytest.raises(recovery.RecoveryError):
        recovery.parse_share(raw)


def test_duplicate_share_ids_refused(recovery):
    with pytest.raises(recovery.RecoveryError):
        recovery.validate_shares([SHARES[0], SHARES[0], SHARES[2]])


def test_check_mode_never_opens_transport(recovery, tmp_path, monkeypatch, capsys):
    paths = []
    for index, share in enumerate(SHARES):
        path = tmp_path / f'share{index}.txt'
        path.write_bytes(share + b'\n')
        paths.append(str(path))
    ledger = tmp_path / 'ledger.dat'
    ledger.write_bytes(b'synthetic ledger')
    monkeypatch.setattr(recovery, 'check_ledger', lambda *a: True)
    monkeypatch.setattr(recovery, 'checker_ready', lambda *a: None)
    monkeypatch.setattr(recovery, 'unlock_checked', lambda *a: pytest.fail('check contacted engine'))
    assert recovery.main(['--share-files', ','.join(paths), '--ledger', str(ledger), '--check']) == 0
    output = capsys.readouterr()
    assert 'MATCH' in output.out
    assert all(share.decode() not in output.out + output.err for share in SHARES)


def test_mismatch_never_opens_transport_or_changes_files(recovery, tmp_path, monkeypatch, capsys):
    paths = []
    for index, share in enumerate(SHARES):
        path = tmp_path / f'share{index}.txt'
        path.write_bytes(share)
        paths.append(str(path))
    ledger = tmp_path / 'ledger.dat'
    ledger.write_bytes(b'unchanged')
    monkeypatch.setattr(recovery, 'check_ledger', lambda *a: False)
    monkeypatch.setattr(recovery, 'checker_ready', lambda *a: None)
    monkeypatch.setattr(recovery, 'unlock_checked', lambda *a: pytest.fail('mismatch contacted engine'))
    assert recovery.main(['--share-files', ','.join(paths), '--ledger', str(ledger), '--unlock']) == 1
    assert ledger.read_bytes() == b'unchanged'
    assert all(Path(path).read_bytes() == share for path, share in zip(paths, SHARES))
    assert capsys.readouterr().out.strip() == 'MISMATCH — no unlock attempted.'


def test_no_password_echo_fallback(recovery, monkeypatch):
    monkeypatch.setattr(recovery.sys.stdin, 'isatty', lambda: False)
    monkeypatch.setattr(recovery.getpass, 'getpass', lambda *a: pytest.fail('prompt without private terminal'))
    with pytest.raises(recovery.RecoveryError):
        recovery.private_password('Password: ')


def test_password_never_enters_arguments(recovery, tmp_path, monkeypatch):
    path = tmp_path / 'secret.enc'
    path.write_bytes(b'Salted__' + b'0' * 24)
    captured = {}
    def fake_run(argv, **kwargs):
        captured['argv'], captured['input'] = argv, bytes(kwargs['input'])
        class Result:
            returncode, stdout, stderr = 0, b'plaintext', b''
        return Result()
    monkeypatch.setattr(recovery.subprocess, 'run', fake_run)
    assert recovery.decrypt_file(path, bytearray(b'synthetic password')) == b'plaintext'
    assert 'synthetic password' not in ' '.join(captured['argv'])
    assert captured['input'] == b'synthetic password\n'


def test_real_openssl_roundtrip_and_wrong_password(recovery, tmp_path):
    import subprocess
    plaintext = archive()
    # Only synthetic fixture material is encrypted in this test.
    import os
    read_fd, write_fd = os.pipe()
    os.write(write_fd, b'synthetic-test-password\n')
    os.close(write_fd)
    try:
        encrypted = subprocess.run(['openssl', 'enc', '-aes-256-cbc', '-pbkdf2',
            '-iter', '100000', '-pass', f'fd:{read_fd}'], input=plaintext,
            pass_fds=(read_fd,), capture_output=True, check=True).stdout
    finally:
        os.close(read_fd)
    path = tmp_path / 'vault.enc'
    path.write_bytes(encrypted)
    assert recovery.vault_shares(recovery.decrypt_file(path, bytearray(b'synthetic-test-password'))) == SHARES[1:]
    with pytest.raises(recovery.RecoveryError):
        recovery.decrypt_file(path, bytearray(b'wrong-password'))


def test_nonempty_legacy_root_refused_before_runtime_or_transport(recovery, tmp_path, monkeypatch):
    ledger = tmp_path / 'ledger.dat'
    ledger.write_bytes(b'STATE_ROOT|' + b'0' * 64 + b'\n')
    monkeypatch.setattr(recovery, 'runtime_guard', lambda *a: pytest.fail('nonempty root reached runtime'))
    with pytest.raises(recovery.RecoveryError):
        recovery.unlock_checked(SHARES, ledger, b'digest', None)


def test_local_picture_is_not_a_fallback(recovery):
    source = (REPO / 'tools/qf_recovery.py').read_text()
    assert '.gemini' not in source
    assert 'sovereign_stego_watermark' not in source


def test_missing_checker_prevents_password_prompt(recovery, tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, 'private_password', lambda *a: pytest.fail('missing checker prompted password'))
    assert recovery.main(['--checker', str(tmp_path / 'missing'), '--check']) == 2


def test_exposure_hold_prevents_passwords_native_and_transport(recovery, monkeypatch, capsys):
    recovery.HOLD_FILE.write_text('Authority exposed; reviewed migration required.\n')
    monkeypatch.setattr(recovery, 'private_password', lambda *a: pytest.fail('hold prompted password'))
    monkeypatch.setattr(recovery, 'checker_ready', lambda *a: pytest.fail('hold reached native checker'))
    monkeypatch.setattr(recovery, 'unlock_checked', lambda *a: pytest.fail('hold reached transport'))
    assert recovery.main(['--unlock']) == 2
    assert 'hold' in capsys.readouterr().err.lower()


def test_offline_check_still_allowed_during_exposure_hold(recovery, tmp_path, monkeypatch, capsys):
    recovery.HOLD_FILE.write_text('hold\n')
    paths = []
    for index, share in enumerate(SHARES):
        path = tmp_path / f'share{index}.txt'
        path.write_bytes(share)
        paths.append(str(path))
    ledger = tmp_path / 'ledger.dat'
    ledger.write_bytes(b'offline fixture')
    monkeypatch.setattr(recovery, 'checker_ready', lambda *a: None)
    monkeypatch.setattr(recovery, 'check_ledger', lambda *a: True)
    assert recovery.main(['--check', '--share-files', ','.join(paths), '--ledger', str(ledger)]) == 0
    assert 'MATCH' in capsys.readouterr().out


def synthetic_empty_ledger():
    import hashlib
    root = hashlib.sha256(b'QUANTUM_FLEX_EMPTY_STATE').hexdigest().encode()
    return b'STATE_ROOT|' + root + b'\nTIMESTAMP|1791979200\nLEDGER_SIGNATURE|' + b'1' * 64 + b'\nSTATUS|ACTIVE\n'


def test_checked_unlock_probes_then_transmits_in_memory(recovery, tmp_path, monkeypatch, capsys):
    import hashlib
    ledger = tmp_path / 'ledger.dat'
    ledger.write_bytes(synthetic_empty_ledger())
    calls = []
    monkeypatch.setattr(recovery, 'runtime_guard', lambda *a: 123)
    class Client:
        @staticmethod
        def transmit(payload, *args):
            calls.append(bytes(payload))
            if payload == b'STATUS':
                print('ERR|NODE_LOCKED')
                return 1
            assert args[-1] == 'ACK|NODE_UNLOCKED'
            print('ACK|NODE_UNLOCKED')
            return 0
    monkeypatch.setattr(recovery, 'ipc_client', lambda: Client)
    assert recovery.unlock_checked(SHARES, ledger, hashlib.sha256(ledger.read_bytes()).digest(), None) == 0
    assert calls == [b'STATUS', b'UNLOCK|' + b','.join(SHARES)]
    assert capsys.readouterr().out == 'ACK|NODE_UNLOCKED\n'


@pytest.mark.parametrize('status', ['ACK|NODE_UNLOCKED', 'ERR|INVALID_STATE', 'ERR|NODE_LOCKED extra'])
def test_unknown_runtime_state_never_receives_shares(recovery, tmp_path, monkeypatch, status):
    import hashlib
    ledger = tmp_path / 'ledger.dat'
    ledger.write_bytes(synthetic_empty_ledger())
    monkeypatch.setattr(recovery, 'runtime_guard', lambda *a: 123)
    class Client:
        @staticmethod
        def transmit(payload, *args):
            assert payload == b'STATUS'
            print(status)
            return 1
    monkeypatch.setattr(recovery, 'ipc_client', lambda: Client)
    with pytest.raises(recovery.RecoveryError):
        recovery.unlock_checked(SHARES, ledger, hashlib.sha256(ledger.read_bytes()).digest(), None)


def test_ledger_changed_after_status_never_receives_shares(recovery, tmp_path, monkeypatch):
    import hashlib
    ledger = tmp_path / 'ledger.dat'
    ledger.write_bytes(synthetic_empty_ledger())
    digest = hashlib.sha256(ledger.read_bytes()).digest()
    monkeypatch.setattr(recovery, 'runtime_guard', lambda *a: 123)
    class Client:
        @staticmethod
        def transmit(payload, *args):
            assert payload == b'STATUS'
            ledger.write_bytes(b'changed')
            print('ERR|NODE_LOCKED')
            return 1
    monkeypatch.setattr(recovery, 'ipc_client', lambda: Client)
    with pytest.raises(recovery.RecoveryError):
        recovery.unlock_checked(SHARES, ledger, digest, None)


def encrypt_synthetic(plaintext, password):
    import os
    import subprocess
    read_fd, write_fd = os.pipe()
    os.write(write_fd, password + b'\n')
    os.close(write_fd)
    try:
        return subprocess.run(['openssl', 'enc', '-aes-256-cbc', '-pbkdf2',
            '-iter', '100000', '-pass', f'fd:{read_fd}'], input=plaintext,
            pass_fds=(read_fd,), capture_output=True, check=True).stdout
    finally:
        os.close(read_fd)


@pytest.mark.parametrize('matching', [True, False])
def test_encrypted_vault_to_native_ledger_end_to_end(recovery, native_tools, tmp_path, monkeypatch, capsys, matching):
    checker, built, native_shares = native_tools
    assert built.returncode == 0
    checker.chmod(0o700)
    shares = [share.encode() for share in native_shares]
    vault = tmp_path / 'vault.enc'
    local = tmp_path / 'local.enc'
    ledger = tmp_path / 'ledger.dat'
    vault.write_bytes(encrypt_synthetic(archive(content=image_payload(shares[3:5])), b'vault-test-password'))
    local.write_bytes(encrypt_synthetic(shares[0] + b'\n', b'local-test-password'))
    ledger.write_bytes(ledger_text() if matching else ledger_text(secret=b'wrong synthetic authority'[:32].ljust(32, b'x')))
    before = {path: path.read_bytes() for path in (vault, local, ledger)}
    passwords = iter((b'vault-test-password', b'local-test-password'))
    monkeypatch.setattr(recovery, 'private_password', lambda *a: bytearray(next(passwords)))
    monkeypatch.setattr(recovery, 'unlock_checked', lambda *a: pytest.fail('offline check contacted engine'))
    assert recovery.main(['--vault', str(vault), '--local-encrypted', str(local),
        '--ledger', str(ledger), '--checker', str(checker), '--check']) == (0 if matching else 1)
    output = capsys.readouterr()
    assert ('MATCH —' if matching else 'MISMATCH —') in output.out
    assert all(share.decode() not in output.out + output.err for share in shares)
    assert {path: path.read_bytes() for path in before} == before
    assert {path.name for path in tmp_path.iterdir()} == {'vault.enc', 'local.enc', 'ledger.dat'}
