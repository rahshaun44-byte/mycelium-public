"""Private recovery boundaries, using synthetic material and no live IPC."""
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


REPO = Path(__file__).resolve().parents[1]
SHARES = ['1:' + '11' * 32, '2:' + '22' * 32, '5:' + '55' * 32]
UNLOCK = 'UNLOCK|' + ','.join(SHARES)


@pytest.fixture
def client():
    spec = importlib.util.spec_from_file_location(
        'private_unlock_client', REPO / 'scripts' / 'qf_ipc_client.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def peer(client, monkeypatch):
    # Only the external TLS/socket boundary is replaced. CLI/input handling,
    # response validation, and observable output remain production code.
    class Connection:
        response = b'ACK|NODE_UNLOCKED\n'
        received = b''
        receive_size = 7

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def sendall(self, data):
            self.received = bytes(data)

        def recv(self, size):
            count = min(size, self.receive_size)
            block, self.response = self.response[:count], self.response[count:]
            return block

    conn = Connection()

    class TLS:
        def __init__(self, *args):
            pass

        def load_verify_locations(self, **kwargs):
            pass

        def load_cert_chain(self, **kwargs):
            pass

        def wrap_socket(self, sock, **kwargs):
            return conn

    monkeypatch.setattr(client.ssl, 'SSLContext', TLS)
    monkeypatch.setattr(client.socket, 'create_connection', lambda *a, **k: conn)
    return conn


def set_args(monkeypatch, *args):
    monkeypatch.setattr(sys, 'argv', ['qf_ipc_client.py', '--port', '9444',
                                     '--cert', 'client.crt', '--key', 'client.key',
                                     '--ca', 'ca.crt', *args])


def set_stdin(monkeypatch, content):
    monkeypatch.setattr(sys, 'stdin', io.TextIOWrapper(io.BytesIO(content)))


def forbid_transport(client, monkeypatch):
    def fail(*args, **kwargs):
        pytest.fail('Invalid input reached the transport')
    monkeypatch.setattr(client.ssl, 'SSLContext', fail)


@pytest.mark.parametrize('command', [UNLOCK, 'INIT|' + ','.join(SHARES),
                                      'TELEMETRY|synthetic-secret'])
def test_secret_argv_commands_are_refused_without_echo(client, monkeypatch, capsys, command):
    # Removing the argv guard must fail this before certificate/socket access.
    set_args(monkeypatch, '--line', command)
    forbid_transport(client, monkeypatch)
    assert client.main() == 2
    output = capsys.readouterr()
    assert command not in output.out + output.err


def test_stdin_unlock_requires_complete_exact_ack_without_echo(client, peer, monkeypatch, capsys):
    # Accepting a single recv would fail because the peer fragments its ACK.
    set_args(monkeypatch, '--stdin')
    set_stdin(monkeypatch, (UNLOCK + '\n').encode())
    assert client.main() == 0
    assert peer.received == UNLOCK.encode()
    output = capsys.readouterr()
    assert output.out == 'ACK|NODE_UNLOCKED\n'
    assert UNLOCK not in output.out + output.err


@pytest.mark.parametrize('response', [b'', b'ACK|GENESIS_SECURED\n',
    b'ACK|NODE_UNLOCKED|extra\n', b'ACK|NODE_UNLOCKED\nERR|later\n',
    ('ERR|' + UNLOCK + '\n').encode(), b'\xff', b'A' * 4097,
    b' ACK|NODE_UNLOCKED\n', b'\tACK|NODE_UNLOCKED\n',
    b'ACK|NODE_UNLOCKED \n', b'ACK|NODE_UNLOCKED\n\n'])
def test_unexpected_response_fails_closed_without_echo(client, peer, monkeypatch, capsys, response):
    # Accepting an ACK prefix or printing an unknown reply must fail this.
    peer.response = response
    set_args(monkeypatch, '--stdin', '--expect-response', 'ACK|NODE_UNLOCKED')
    set_stdin(monkeypatch, (UNLOCK + '\n').encode())
    assert client.main() == 1
    output = capsys.readouterr()
    assert 'ACK|NODE_UNLOCKED' not in output.out
    assert UNLOCK not in output.out + output.err


@pytest.mark.parametrize('payload', [b'', b'UNLOCK|one\nUNLOCK|two\n',
    b'UNLOCK|bad\x00input', b'UNLOCK|' + b'x' * 65536])
def test_invalid_stdin_is_refused_before_transport(client, monkeypatch, capsys, payload):
    # Removing framing/size checks must allow one of these to reach transport.
    set_args(monkeypatch, '--stdin')
    set_stdin(monkeypatch, payload)
    forbid_transport(client, monkeypatch)
    assert client.main() == 2
    assert not capsys.readouterr().out


def test_terminal_unlock_refuses_unchecked_share_injection(client, monkeypatch, capsys):
    # Restoring direct terminal share submission would bypass the ledger check.
    set_args(monkeypatch, '--interactive-unlock')
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
    forbid_transport(client, monkeypatch)
    assert client.main() == 2
    output = capsys.readouterr()
    assert not output.out
    assert 'recovery' in output.err.lower()


def test_transport_failure_does_not_print_exception_material(client, monkeypatch, capsys):
    # Printing an exception would disclose sensitive material supplied by a peer.
    set_args(monkeypatch, '--stdin')
    set_stdin(monkeypatch, (UNLOCK + '\n').encode())

    def fail(*args, **kwargs):
        raise OSError(UNLOCK)

    monkeypatch.setattr(client.ssl, 'SSLContext', fail)
    assert client.main() == 1
    output = capsys.readouterr()
    assert not output.out
    assert UNLOCK not in output.err


def test_checked_helper_can_transmit_without_secret_process_arguments(client, peer, monkeypatch, capsys):
    # Removing the reusable transport would force recovery back through argv or a
    # second implementation that could accept partial acknowledgements.
    monkeypatch.setattr(sys, 'argv', ['checked-recovery-helper'])
    payload = bytearray((UNLOCK + '\n').encode())
    assert client.transmit(payload, '127.0.0.1', 9444, 'client.crt', 'client.key',
                           'ca.crt', 'ACK|NODE_UNLOCKED') == 0
    assert peer.received == payload
    assert sys.argv == ['checked-recovery-helper']
    output = capsys.readouterr()
    assert output.out == 'ACK|NODE_UNLOCKED\n'
    assert UNLOCK not in output.out + output.err


def script_fixture(tmp_path):
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    shutil.copyfile(REPO / 'scripts' / 'unlock_engine.sh', scripts / 'unlock_engine.sh')
    tools = tmp_path / 'tools'
    tools.mkdir()
    # Replace only the checked recovery boundary. Script path validation is real;
    # no native recovery or IPC transport is executed by this synthetic fixture.
    recovery = tools / 'qf_recovery.py'
    recovery.write_text('import json, os, pathlib, sys\n'
                        'pathlib.Path(os.environ["CAPTURE_FILE"]).write_text('
                        'json.dumps({"argv": sys.argv[1:]}))\n'
                        'sys.exit(int(os.environ.get("RECOVERY_EXIT", "0")))\n')
    shard_files = []
    for index, share in enumerate(SHARES):
        path = tmp_path / f'shard_{index}.txt'
        path.write_text(share + '\n')
        shard_files.append(path)
    env = os.environ.copy()
    env.update(SHARD_FILES=','.join(map(str, shard_files)),
               SHARDS_DIR=str(tmp_path / 'unused'), QF_DATA_DIR=str(tmp_path / 'data'),
               CAPTURE_FILE=str(tmp_path / 'capture.json'))
    return scripts / 'unlock_engine.sh', env, shard_files


def test_script_uses_checked_recovery_and_retains_shard_files(tmp_path):
    # Returning to qf_genesis_tool/--line would bypass the mandatory ledger check.
    script, env, shard_files = script_fixture(tmp_path)
    result = subprocess.run(['bash', str(script)], env=env, capture_output=True, text=True)
    assert result.returncode == 0
    captured = json.loads(Path(env['CAPTURE_FILE']).read_text())
    assert captured['argv'] == ['--share-files', env['SHARD_FILES'], '--unlock']
    assert all(share not in str(captured) for share in SHARES)
    assert [path.read_text() for path in shard_files] == [s + '\n' for s in SHARES]
    assert UNLOCK not in result.stdout + result.stderr


def test_script_propagates_checked_recovery_failure(tmp_path):
    script, env, _ = script_fixture(tmp_path)
    env['RECOVERY_EXIT'] = '1'
    result = subprocess.run(['bash', str(script)], env=env, capture_output=True, text=True)
    assert result.returncode != 0


def test_script_refuses_pasted_values_as_file_paths_without_echo(tmp_path):
    script, env, _ = script_fixture(tmp_path)
    env['SHARD_FILES'] = ','.join(SHARES)
    result = subprocess.run(['bash', str(script)], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert not Path(env['CAPTURE_FILE']).exists()
    assert all(share not in result.stdout + result.stderr for share in SHARES)


@pytest.mark.parametrize('invalid', ['missing', 'placeholder', 'encrypted', 'directory',
                                   'too-few', 'too-many', 'empty-entry', 'newline'])
def test_script_refuses_bad_file_paths_before_recovery(tmp_path, invalid):
    # Removing the file-path guard would allow invalid input into native recovery.
    script, env, shard_files = script_fixture(tmp_path)
    paths = list(map(str, shard_files))
    if invalid == 'missing':
        paths[0] = str(tmp_path / 'missing.txt')
    elif invalid == 'placeholder':
        paths[0] = '/media/quant/<USB_NAME>/shard_1.txt'
    elif invalid == 'encrypted':
        encrypted = tmp_path / 'shard_1.txt.gpg'
        encrypted.write_bytes(b'synthetic encrypted file')
        paths[0] = str(encrypted)
    elif invalid == 'directory':
        paths[0] = str(tmp_path)
    elif invalid == 'too-few':
        paths.pop()
    elif invalid == 'too-many':
        paths.append(paths[0])
    elif invalid == 'empty-entry':
        paths[0] = ''
    elif invalid == 'newline':
        paths[0] += '\n'
    env['SHARD_FILES'] = ','.join(paths)
    result = subprocess.run(['bash', str(script)], env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert not Path(env['CAPTURE_FILE']).exists()
    assert all(share not in result.stdout + result.stderr for share in SHARES)


def checked_script_fixture(tmp_path, *, native_mismatch=False):
    script, env, shard_files = script_fixture(tmp_path)
    ledger = tmp_path / 'ledger.dat'
    ledger.write_text('STATE_ROOT|' + '0' * 64 + '\nTIMESTAMP|1773660000\n'
                      'LEDGER_SIGNATURE|' + '0' * 64 + '\nSTATUS|ACTIVE\n')
    checker = tmp_path / 'checker'
    checker.touch()
    checker.chmod(0o700)
    external_marker = tmp_path / 'external-call'
    tls_marker = tmp_path / 'tls-call'
    launcher = tmp_path / 'tools' / 'qf_recovery.py'
    native_boundary = (
        'def native_boundary(argv, **kwargs):\n'
        f'    pathlib.Path({str(external_marker)!r}).write_text(json.dumps(argv))\n'
        '    return types.SimpleNamespace(returncode=1, stdout=b"MISMATCH\\n", stderr=b"")\n'
        if native_mismatch else
        'def native_boundary(*args, **kwargs):\n'
        f'    pathlib.Path({str(external_marker)!r}).touch()\n'
        '    raise RuntimeError("Invalid input reached an external boundary")\n')
    launcher.write_text(
        'import importlib.util, json, pathlib, ssl, types\n'
        f'spec = importlib.util.spec_from_file_location("recovery_under_test", {str(REPO / "tools/qf_recovery.py")!r})\n'
        'module = importlib.util.module_from_spec(spec)\n'
        'spec.loader.exec_module(module)\n'
        f'module.DEFAULT_LEDGER = pathlib.Path({str(ledger)!r})\n'
        f'module.DEFAULT_CHECKER = pathlib.Path({str(checker)!r})\n'
        f'module.HOLD_FILE = pathlib.Path({str(tmp_path / "missing-hold")!r})\n'
        + native_boundary +
        'def forbid_tls(*args, **kwargs):\n'
        f'    pathlib.Path({str(tls_marker)!r}).touch()\n'
        '    raise RuntimeError("Invalid input reached TLS")\n'
        'module.subprocess.run = native_boundary\n'
        'ssl.SSLContext = forbid_tls\n'
        'raise SystemExit(module.main())\n')
    return script, env, shard_files, ledger, checker, external_marker, tls_marker


@pytest.mark.parametrize('invalid', [b'Salted__' + b'x' * 24,
    b'-----BEGIN PGP MESSAGE-----\nsynthetic ciphertext\n',
    b'1:' + b'gg' * 32, b'1:' + b'11' * 31,
    SHARES[1].encode(), SHARES[0].encode() + b'\n\n',
    b' ' + SHARES[0].encode()],
    ids=['openssl-encrypted-txt', 'armored-encrypted-txt', 'non-hex',
         'short-share', 'duplicate-id', 'extra-line', 'padded-share'])
def test_script_and_real_helper_refuse_invalid_content_before_native_or_tls(tmp_path, invalid):
    # Accepting opaque ciphertext or malformed shares would reach native recovery
    # or TLS. Only external boundaries and the default input locations are replaced.
    script, env, shard_files, ledger, _, external_marker, tls_marker = checked_script_fixture(tmp_path)
    shard_files[0].write_bytes(invalid)
    before = [path.read_bytes() for path in shard_files]
    ledger_before = ledger.read_bytes()
    result = subprocess.run(['bash', str(script)], env=env, capture_output=True, text=True)
    assert result.returncode == 2
    assert not external_marker.exists()
    assert not tls_marker.exists()
    assert not result.stdout
    assert all(share not in result.stderr for share in SHARES)
    assert [path.read_bytes() for path in shard_files] == before
    assert ledger.read_bytes() == ledger_before


def test_script_and_real_helper_require_native_match_before_tls(tmp_path):
    # Skipping the native match would submit a syntactically valid, wrong share
    # generation to the running engine. The real helper must stop at MISMATCH.
    script, env, shard_files, ledger, checker, native_call, tls_call = checked_script_fixture(
        tmp_path, native_mismatch=True)
    before = [path.read_bytes() for path in shard_files]
    ledger_before = ledger.read_bytes()
    result = subprocess.run(['bash', str(script)], env=env, capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(native_call.read_text()) == [str(checker), '--ledger', str(ledger)]
    assert not tls_call.exists()
    assert result.stdout == 'MISMATCH — no unlock attempted.\n'
    assert all(share not in result.stdout + result.stderr + native_call.read_text() for share in SHARES)
    assert [path.read_bytes() for path in shard_files] == before
    assert ledger.read_bytes() == ledger_before
