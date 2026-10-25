#!/usr/bin/env python3
"""Check legacy QuantumFlex recovery shares before any explicitly requested unlock.

Default: hidden terminal passwords, encrypted USB vault + local encrypted share,
and an offline match against the existing ledger. No plaintext files are created.
This does not promise complete erasure of Python, OpenSSL or TLS process memory.
The historical OpenSSL CBC container is not authenticated encryption.
"""
import argparse
import contextlib
import fcntl
import getpass
import gzip
import hashlib
import importlib.util
import io
import os
from pathlib import Path, PurePosixPath
import re
import resource
import stat
import subprocess
import sys
import tarfile
import warnings
import zlib


REPO = Path(__file__).resolve().parents[1]
DATA_DIR = Path.home() / '.local/share/quantum-flex-mycelium'
DEFAULT_LEDGER = DATA_DIR / 'ledger.dat'
DEFAULT_CHECKER = REPO / 'build_recovery_check/qf_legacy_recovery_check'
ENGINE_PATH = REPO / 'build_check/quantum_flex_engine'
PROC = Path('/proc')
HOLD_FILE = Path.home() / '.local/state/quantum-flex-mycelium/unlock.hold'
MAX_CIPHER_BYTES = 8 * 1024 * 1024
MAX_ARCHIVE_BYTES = 24 * 1024 * 1024
MAX_IMAGE_PIXELS = 4 * 1024 * 1024
MAX_NATIVE_BYTES = 64 * 1024 * 1024
MFD_EXEC = getattr(os, 'MFD_EXEC', 0x10)
EMPTY_ROOT = hashlib.sha256(b'QUANTUM_FLEX_EMPTY_STATE').hexdigest().encode()
SHARE_PATTERN = re.compile(rb'[1-5]:[0-9a-fA-F]{64}')
SHA256_HEX = re.compile(r'[0-9a-f]{64}')


class RecoveryError(Exception):
    """Fixed, safe user-facing message; never wrap external exception text."""


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise RecoveryError('Invalid options. Use --help; never put passwords or shares in arguments.')


def wipe(value):
    if isinstance(value, bytearray):
        value[:] = b'\0' * len(value)


def enforce_unlock_hold():
    if HOLD_FILE.exists() or HOLD_FILE.is_symlink():
        raise RecoveryError('Live unlock is on hold after authority exposure; offline --check remains available. Reviewed migration is required.')


def read_regular(path, limit):
    """Read once with a bound, rejecting special files and symbolic links."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as source:
            info = os.fstat(source.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                raise RecoveryError('Recovery input must be a bounded regular file.')
            result = source.read(limit + 1)
            if len(result) > limit:
                raise RecoveryError('Recovery input exceeds its size limit.')
            return result
    except OSError:
        raise RecoveryError('A required recovery file is missing or unreadable.') from None


def require_hex_sha256(value, what):
    if not isinstance(value, str) or not SHA256_HEX.fullmatch(value):
        raise RecoveryError(f'The pinned SHA-256 for the {what} must be 64 lowercase hex digits.')


def sha256_of(path, follow=False):
    """Streamed SHA-256 of a regular file. follow=True only for /proc/<pid>/exe, a kernel link to the loaded file."""
    fd = os.open(path, os.O_RDONLY | (0 if follow else os.O_NOFOLLOW))
    with os.fdopen(fd, 'rb') as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise RecoveryError('A pinned file is not a regular file.')
        digest = hashlib.sha256()
        for chunk in iter(lambda: source.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def require_sha256(path, expected, what, follow=False):
    """Refuse unless the file hashes to the operator-pinned value; returns the hash."""
    require_hex_sha256(expected, what)
    try:
        actual = sha256_of(path, follow)
    except OSError:
        raise RecoveryError(f'The {what} could not be read for its integrity check. Nothing was done.') from None
    if actual != expected:
        raise RecoveryError(f'The {what} does not match its pinned SHA-256. Nothing was done.')
    return actual


def parse_share(raw):
    # Accept a single optional LF/CRLF; no whitespace stripping or multiple lines.
    raw = bytes(raw)
    if raw.endswith(b'\r\n'):
        raw = raw[:-2]
    elif raw.endswith(b'\n'):
        raw = raw[:-1]
    if not SHARE_PATTERN.fullmatch(raw):
        raise RecoveryError('Invalid plaintext share format; encrypted files need the vault mode.')
    return raw[:2] + raw[2:].lower()


def validate_shares(shares):
    if len(shares) != 3:
        raise RecoveryError('Exactly three matching shares are required.')
    parsed = [parse_share(share) for share in shares]
    if len({share[0] for share in parsed}) != 3:
        raise RecoveryError('Three distinct share identifiers are required.')
    return parsed


def private_password(prompt):
    if not sys.stdin.isatty():
        raise RecoveryError('Run this tool in your private terminal for hidden password entry.')
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        try:
            password = getpass.getpass(prompt)
        except (getpass.GetPassWarning, EOFError):
            raise RecoveryError('Hidden password entry is unavailable; nothing was decrypted.') from None
    if not password or any(char in password for char in ('\n', '\r', '\0')) or len(password.encode('utf-8')) > 4096:
        raise RecoveryError('A nonempty single-line password is required.')
    return bytearray(password.encode('utf-8'))


def decrypt_file(path, password):
    cipher = read_regular(path, MAX_CIPHER_BYTES)
    if len(cipher) < 32 or not cipher.startswith(b'Salted__'):
        raise RecoveryError('Unsupported encrypted container; nothing was unlocked.')
    # Use the already bounded ciphertext in a sealed memory file. Reopening the
    # original path would permit a replacement file to evade the input bound.
    cipher_fd = None
    password_line = bytearray(password)
    password_line.append(10)
    try:
        cipher_fd = os.memfd_create('qf-encrypted-input', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
        with os.fdopen(os.dup(cipher_fd), 'wb') as memory:
            memory.write(cipher)
            memory.flush()
        os.lseek(cipher_fd, 0, os.SEEK_SET)
        fcntl.fcntl(cipher_fd, fcntl.F_ADD_SEALS,
            fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL)
        result = subprocess.run(['openssl', 'enc', '-d', '-aes-256-cbc', '-pbkdf2',
            '-iter', '100000', '-pass', 'stdin', '-in', f'/proc/self/fd/{cipher_fd}'],
            input=password_line, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            pass_fds=(cipher_fd,), timeout=30, check=False)
        if result.returncode or len(result.stdout) > MAX_CIPHER_BYTES:
            raise RecoveryError('Decryption failed: check the password or container format. No unlock attempted.')
        return result.stdout
    except (OSError, subprocess.TimeoutExpired):
        raise RecoveryError('Decryption could not finish. No unlock attempted.') from None
    finally:
        wipe(password_line)
        if cipher_fd is not None:
            os.close(cipher_fd)


@contextlib.contextmanager
def private_gnupghome(parent=None):
    """A throwaway 0700 GnuPG home, so no keyring, agent cache or config is shared.

    Without an explicit parent it lives in the user's private XDG_RUNTIME_DIR; never /tmp.
    """
    import shutil
    import tempfile
    base = parent
    if base is None:
        runtime = os.environ.get('XDG_RUNTIME_DIR', '')
        try:
            info = os.lstat(runtime) if os.path.isabs(runtime) else None
        except OSError:
            info = None
        if (info is None or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise RecoveryError('No private runtime directory (XDG_RUNTIME_DIR, 0700, yours) is available for gpg; '
                                'refusing to fall back to /tmp.')
        base = runtime
    home = tempfile.mkdtemp(prefix='qf-gnupg-', dir=base)
    try:
        os.chmod(home, 0o700)
        yield home
    finally:
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(['gpgconf', '--homedir', home, '--kill', 'all'],
                           capture_output=True, timeout=10, check=False)
        shutil.rmtree(home, ignore_errors=True)


def gpg_base(gnupghome):
    return ['gpg', '--homedir', str(gnupghome), '--batch', '--quiet', '--no-tty', '--no-greeting',
            '--pinentry-mode', 'loopback', '--no-symkey-cache']


def run_gpg(command, passphrase, stdin_bytes, gnupghome):
    """Run gpg with the passphrase on an inherited pipe (never argv); return stdout or raise a fixed error."""
    read_fd, write_fd = os.pipe()
    # Name the inherited fd itself: subprocess closes non-pass_fds descriptors
    # after preexec_fn, so a dup2 onto a fixed number would not survive.
    command = command[:1] + ['--passphrase-fd', str(read_fd)] + command[1:]
    line = bytearray(passphrase)
    line.append(10)
    try:
        if len(line) > 4096:
            raise RecoveryError('Passphrase is too long.')
        os.write(write_fd, line)
        os.close(write_fd)
        write_fd = None
        result = subprocess.run(command, input=stdin_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                pass_fds=(read_fd,), env={**os.environ, 'GNUPGHOME': str(gnupghome)}, timeout=120, check=False)
        if result.returncode:
            raise RecoveryError('gpg failed: check the passphrase or sealed file. No unlock attempted.')
        return result.stdout
    except (OSError, subprocess.TimeoutExpired):
        raise RecoveryError('gpg could not finish. No unlock attempted.') from None
    finally:
        wipe(line)
        os.close(read_fd)
        if write_fd is not None:
            os.close(write_fd)


def gpg_open(path, passphrase, gnupghome):
    """Decrypt one sealed share file into memory and return its bytes as a bytearray."""
    # Hand gpg the bytes already read and bounded; it never reopens the path.
    sealed = read_regular(path, 4096)
    return bytearray(run_gpg(gpg_base(gnupghome) + ['--decrypt'], passphrase, sealed, gnupghome))


def sealed_shares(paths):
    shares = []
    with private_gnupghome() as gnupghome:
        for index, path in enumerate(paths, start=1):
            passphrase = private_password(f'Passphrase for sealed share {index} (hidden): ')
            try:
                raw = gpg_open(Path(path).expanduser(), passphrase, gnupghome)
                try:
                    shares.append(parse_share(raw))
                finally:
                    wipe(raw)
            finally:
                wipe(passphrase)
    return shares


def picture_shares(png):
    try:
        from PIL import Image
    except ImportError:
        raise RecoveryError('Use the QuantumFlex Python environment with Pillow installed.') from None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(png)) as image:
                if image.format != 'PNG' or image.width * image.height > MAX_IMAGE_PIXELS:
                    raise RecoveryError('Unsupported or oversized recovery picture.')
                rgb = image.convert('RGB')
                pixels = rgb.load()
                message = bytearray()
                value = 0
                for index in range(min(image.width * image.height, 256 * 8)):
                    value = (value << 1) | (pixels[index % image.width, index // image.width][2] & 1)
                    if index % 8 == 7:
                        message.append(value)
                        value = 0
                        if message.endswith(b'|END'):
                            break
                try:
                    parts = bytes(message).split(b'|')
                    if len(parts) != 4 or parts[0] != b'QFX_STEGO' or parts[-1] != b'END':
                        raise RecoveryError('The vault picture has no supported recovery payload.')
                    parsed = [parse_share(part) for part in parts[1:3]]
                    if parsed[0][0] == parsed[1][0]:
                        raise RecoveryError('The vault picture has duplicate share identifiers.')
                    return parsed
                finally:
                    wipe(message)
    except RecoveryError:
        raise
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        raise RecoveryError('The recovery picture could not be decoded safely.') from None


def vault_shares(raw):
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as compressed:
            archive = compressed.read(MAX_ARCHIVE_BYTES + 1)
        if len(archive) > MAX_ARCHIVE_BYTES:
            raise RecoveryError('The decrypted vault exceeds its size limit.')
        picture = None
        with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as tar:
            for count, member in enumerate(tar):
                path = PurePosixPath(member.name)
                if count >= 32 or path.is_absolute() or '..' in path.parts or '\\' in member.name:
                    raise RecoveryError('The vault archive contains an unsafe entry.')
                if not (member.isfile() or member.isdir()) or member.size > MAX_CIPHER_BYTES:
                    raise RecoveryError('The vault archive contains an unsupported entry.')
                if path.name == 'quantumflex_watermark.png':
                    if picture is not None or not member.isfile():
                        raise RecoveryError('The vault must contain one recovery picture.')
                    with tar.extractfile(member) as source:
                        picture = source.read(MAX_CIPHER_BYTES + 1)
                    if len(picture) != member.size:
                        raise RecoveryError('The recovery picture is truncated.')
        if picture is None:
            raise RecoveryError('The encrypted vault has no expected recovery picture.')
        return picture_shares(picture)
    except RecoveryError:
        raise
    except (OSError, EOFError, tarfile.TarError, zlib.error):
        raise RecoveryError('The decrypted vault is not a supported gzip/tar container.') from None


def checker_ready(checker):
    try:
        info = checker.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022 or not os.access(checker, os.X_OK):
            raise RecoveryError('The native checker is unavailable or has unsafe permissions.')
    except OSError:
        raise RecoveryError('The native checker is unavailable. No unlock attempted.') from None


@contextlib.contextmanager
def opened_executable(path, what, expected_sha256=None):
    """Yield (executable, fd): run with subprocess executable=, pass_fds=(fd,).

    The path is opened once (no links), checked with fstat, read, and copied into a
    write-sealed memory file; a rename or in-place rewrite on disk afterwards cannot
    change what runs. argv[0] may stay the path; both natives ignore it.
    """
    if expected_sha256 is not None:
        require_hex_sha256(expected_sha256, what)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        with os.fdopen(fd, 'rb') as source:
            info = os.fstat(source.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022
                    or not info.st_mode & stat.S_IXUSR):
                raise RecoveryError(f'The {what} is unavailable or has unsafe permissions.')
            image = source.read(MAX_NATIVE_BYTES + 1)
    except OSError:
        raise RecoveryError(f'The {what} is unavailable. Nothing was run.') from None
    if len(image) > MAX_NATIVE_BYTES:
        raise RecoveryError(f'The {what} exceeds its size limit.')
    if expected_sha256 is not None and hashlib.sha256(image).hexdigest() != expected_sha256:
        raise RecoveryError(f'The {what} does not match its pinned SHA-256. Nothing was done.')
    try:
        memory = os.memfd_create('qf-native', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING | MFD_EXEC)
    except OSError:
        raise RecoveryError(f'The {what} could not be staged for a checked run. Nothing was run.') from None
    try:
        try:
            view = memoryview(image)
            while view:
                view = view[os.write(memory, view):]
            fcntl.fcntl(memory, fcntl.F_ADD_SEALS,
                        fcntl.F_SEAL_WRITE | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_SEAL)
        except OSError:
            raise RecoveryError(f'The {what} could not be staged for a checked run. Nothing was run.') from None
        yield f'/proc/self/fd/{memory}', memory
    finally:
        os.close(memory)


def check_ledger(shares, ledger, checker, expected_sha256=None):
    request = bytearray(b'\n'.join(validate_shares(shares)) + b'\n')
    try:
        with opened_executable(checker, 'native checker', expected_sha256) as (program, fd):
            result = subprocess.run([str(checker), '--ledger', str(ledger)], executable=program,
                input=request, pass_fds=(fd,),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False)
        if result.returncode == 0 and result.stdout == b'MATCH\n':
            return True
        if result.returncode == 1 and result.stdout == b'MISMATCH\n':
            return False
        raise RecoveryError('Native recovery validation failed. No unlock attempted.')
    except (OSError, subprocess.TimeoutExpired):
        raise RecoveryError('The native checker is unavailable. No unlock attempted.') from None
    finally:
        wipe(request)


def runtime_guard(ledger, expected_engine_sha256=None):
    """Conservatively bind a live request to the local legacy engine's loaded file."""
    require_hex_sha256(expected_engine_sha256, 'running engine executable')
    if ledger.resolve() != DEFAULT_LEDGER.resolve():
        raise RecoveryError('Live unlock is restricted to the configured local ledger.')
    try:
        result = subprocess.run(['systemctl', '--user', 'show',
            'quantum-flex-engine-mycelium.service', '-p', 'MainPID', '-p', 'ActiveState'],
            capture_output=True, timeout=5, check=True)
        values = dict(line.split('=', 1) for line in result.stdout.decode('ascii').splitlines())
        pid = int(values.get('MainPID', '0'))
        if values.get('ActiveState') != 'active' or pid <= 0:
            raise RecoveryError('The existing engine must be running in LOCKED state.')
        proc = PROC / str(pid)
        if proc.stat().st_uid != os.getuid() or (proc / 'exe').resolve() != ENGINE_PATH.resolve():
            raise RecoveryError('The running engine does not match the expected local executable.')
        # Hash the loaded file through the kernel link, not the path on disk.
        require_sha256(proc / 'exe', expected_engine_sha256, 'running engine executable', follow=True)
        environment = (proc / 'environ').read_bytes().split(b'\0')
        if any(entry.startswith(b'LD_') for entry in environment):
            raise RecoveryError('The running engine has a dynamic-loader (LD_*) override in its environment.')
        expected = {
            b'QF_DATA_DIR=' + os.fsencode(DATA_DIR),
            b'QF_BIND_ADDRESS=127.0.0.1', b'QF_BIND_PORT=9444',
        }
        if not expected.issubset(set(environment)):
            raise RecoveryError('The running engine uses an unexpected data directory or endpoint.')
        fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
        ticks = int(fields[19])
        boot = next(int(line.split()[1]) for line in Path('/proc/stat').read_text().splitlines()
                    if line.startswith('btime '))
        started = boot + ticks / os.sysconf('SC_CLK_TCK')
        info = ledger.stat()
        if max(info.st_mtime, info.st_ctime) >= started:
            raise RecoveryError('The ledger changed after engine startup. No unlock attempted.')
        return pid
    except RecoveryError:
        raise
    except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError):
        raise RecoveryError('The running ledger could not be bound safely. No unlock attempted.') from None


def ipc_client():
    spec = importlib.util.spec_from_file_location('checked_qf_ipc', REPO / 'scripts/qf_ipc_client.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def unlock_checked(shares, ledger, digest, args):
    enforce_unlock_hold()
    raw = read_regular(ledger, 4096)
    if not raw.startswith(b'STATE_ROOT|' + EMPTY_ROOT + b'\n'):
        raise RecoveryError('Nonempty legacy evidence cannot be restored by this engine. No unlock attempted.')
    if hashlib.sha256(raw).digest() != digest:
        raise RecoveryError('The ledger changed during recovery. No unlock attempted.')
    expected_engine = getattr(args, 'expect_engine_sha256', None)
    pid = runtime_guard(ledger, expected_engine)
    client = ipc_client()
    transport = ('127.0.0.1', 9444, str(DATA_DIR / 'mtls/client.crt'),
                 str(DATA_DIR / 'mtls/client.key'), str(DATA_DIR / 'mtls/ca.crt'))
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        status_result = client.transmit(bytearray(b'STATUS'), *transport, None)
    if status_result != 1 or output.getvalue() != 'ERR|NODE_LOCKED\n':
        raise RecoveryError('The engine did not confirm LOCKED state. No unlock attempted.')
    if runtime_guard(ledger, expected_engine) != pid or hashlib.sha256(read_regular(ledger, 4096)).digest() != digest:
        raise RecoveryError('The running engine or ledger changed. No unlock attempted.')
    request = bytearray(b'UNLOCK|' + b','.join(validate_shares(shares)))
    try:
        return client.transmit(request, *transport, 'ACK|NODE_UNLOCKED')
    finally:
        wipe(request)


def main(argv=None):
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        parser = SafeParser(description=__doc__)
        action = parser.add_mutually_exclusive_group()
        action.add_argument('--check', action='store_true', help='Offline check only (default)')
        action.add_argument('--unlock', action='store_true', help='Explicitly unlock only after a match and runtime checks')
        sources = parser.add_mutually_exclusive_group()
        sources.add_argument('--share-files', help='Exactly three comma-separated plaintext file paths; no values')
        sources.add_argument('--sealed-shares', help='Exactly three comma-separated gpg-sealed share paths from qf_authority_ceremony.py')
        parser.add_argument('--local-encrypted', type=Path, default=Path.home() / 'qfx-shards-genesis/shard_1.enc')
        parser.add_argument('--vault', type=Path,
            default=Path('/run/media') / getpass.getuser() / 'QFX_BACKUP/quantumflex_vault.enc')
        parser.add_argument('--ledger', type=Path, default=DEFAULT_LEDGER)
        parser.add_argument('--checker', type=Path, default=DEFAULT_CHECKER)
        parser.add_argument('--expect-engine-sha256',
                            help='Required with --unlock (checked before any engine contact): SHA-256 of the engine executable')
        parser.add_argument('--expect-checker-sha256', help='Optional: SHA-256 of the native checker')
        args = parser.parse_args(argv)
        if args.unlock:
            enforce_unlock_hold()
        checker_ready(args.checker)
        if args.expect_checker_sha256 is not None:
            require_sha256(args.checker, args.expect_checker_sha256, 'native checker')
        ledger_bytes = read_regular(args.ledger, 4096)
        digest = hashlib.sha256(ledger_bytes).digest()
        shares = []
        try:
            if args.share_files is not None:
                paths = args.share_files.split(',')
                if len(paths) != 3 or len(set(paths)) != 3 or any(not path or any(char in path for char in '<>\r\n') for path in paths):
                    raise RecoveryError('Supply exactly three existing plaintext file paths, never share values.')
                shares = validate_shares([read_regular(Path(path).expanduser(), 128) for path in paths])
            elif args.sealed_shares is not None:
                paths = args.sealed_shares.split(',')
                if len(paths) != 3 or len(set(paths)) != 3 or any(not path or any(char in path for char in '<>\r\n') for path in paths):
                    raise RecoveryError('Supply exactly three distinct sealed share paths, never share values.')
                shares = validate_shares(sealed_shares(paths))
            else:
                # Validate ciphertext file availability before requesting either password.
                read_regular(args.vault, MAX_CIPHER_BYTES)
                read_regular(args.local_encrypted, 1024)
                vault_password = private_password('USB vault password (hidden): ')
                try:
                    shares = vault_shares(decrypt_file(args.vault, vault_password))
                finally:
                    wipe(vault_password)
                local_password = private_password('Local encrypted share password (hidden): ')
                try:
                    shares.insert(0, parse_share(decrypt_file(args.local_encrypted, local_password)))
                finally:
                    wipe(local_password)
                shares = validate_shares(shares)
            if not check_ledger(shares, args.ledger, args.checker, args.expect_checker_sha256):
                print('MISMATCH — no unlock attempted.')
                return 1
            if hashlib.sha256(read_regular(args.ledger, 4096)).digest() != digest:
                raise RecoveryError('The ledger changed during the check. No unlock attempted.')
            if args.unlock:
                return unlock_checked(shares, args.ledger, digest, args)
            print('MATCH — shares authenticate this saved ledger; no unlock attempted.')
            print('Ledger SHA-256: ' + digest.hex())
            return 0
        finally:
            shares.clear()
    except RecoveryError as error:
        print(str(error), file=sys.stderr)
        return 2
    except (OSError, ValueError, ImportError, subprocess.SubprocessError):
        print('Recovery could not finish safely. No unlock attempted.', file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('Recovery cancelled.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
