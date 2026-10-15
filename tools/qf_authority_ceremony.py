#!/usr/bin/env python3
"""Retire the exposed engine authority and seal a fresh one, without plaintext shares.

Two operator-run subcommands, each refusing unless its preconditions hold:

  archive-legacy --expect-sha256 <hex>
      Engine must be stopped. Renames ledger.dat to a read-only
      ledger.dat.archive-legacy-authority-<UTC> (no overwrite) and records its
      SHA-256 in a manifest. The old secret then authenticates nothing live.

  genesis --dest DIR1,DIR2,DIR3,DIR4,DIR5 --expect-engine-sha256 <hex>
          --expect-splitter-sha256 <hex> --expect-checker-sha256 <hex>
      Engine must be running UNINITIALIZED on the configured unit, and the loaded
      engine, splitter and checker must match their pinned SHA-256 values. Collects
      five distinct hidden passphrases first, then generates a new 32-byte secret
      with the native splitter (3-of-5), seals each share with gpg (AES-256,
      iterated S2K) straight from memory, re-opens every sealed file to compare,
      sends INIT, and checks all ten 3-share subsets against the new ledger. The
      engine PID and start time must not change between checks or across INIT.

Operator notes for genesis:
  - Stop all agents and every other qf service first.
  - Enter passphrases only in a plain terminal with no agent attached. Use a
    5-word diceware passphrase per share (at least 20 bytes).
  - btrfs destinations are refused: the disk behind them cannot be determined.
  - USB SSDs that report removable=0 count as fixed disks and hold one share each.
  - Once INIT is sent the sealed files are never deleted by this tool.

No share, secret or passphrase is printed, put in process arguments, or written
unencrypted. This does not promise complete erasure of Python or gpg memory.
"""
import argparse
import collections
import contextlib
import datetime
import hashlib
import importlib.util
import io
import itertools
import json
import os
from pathlib import Path
import re
import resource
import stat
import subprocess
import sys


REPO = Path(__file__).resolve().parents[1]
HOME = Path.home()
UNIT = 'quantum-flex-engine-mycelium.service'
STATE_DIR = HOME / '.local/state/quantum-flex-mycelium'
DEFAULT_SPLITTER = REPO / 'build_recovery_check/qf_authority_split'
TOTAL = 5
THRESHOLD = 3
MIN_PASSPHRASE_BYTES = 20
SEALED_NAME = 'qf-authority-{stamp}-share{share_id}.gpg'
FORBIDDEN_ROOTS = ('.gemini', '.codex', '.claude', '.cursor', '.agents', 'qf-public', 'mycelium')
TEMP_ROOTS = ('/tmp', '/var/tmp', '/dev/shm')
VOLATILE_FS = ('tmpfs', 'ramfs', 'devtmpfs')


def _load_recovery():
    spec = importlib.util.spec_from_file_location('checked_qf_recovery', Path(__file__).with_name('qf_recovery.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


recovery = _load_recovery()
RecoveryError = recovery.RecoveryError
wipe = recovery.wipe
DATA_DIR = recovery.DATA_DIR
DEFAULT_LEDGER = recovery.DEFAULT_LEDGER
DEFAULT_CHECKER = recovery.DEFAULT_CHECKER
EMPTY_ROOT = recovery.EMPTY_ROOT
ENGINE_PATH = recovery.ENGINE_PATH
PROC = recovery.PROC


def utc_stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_manifest(state_dir, name, record):
    """Write a non-secret JSON record without overwriting an existing one."""
    state_dir = Path(state_dir)
    state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = state_dir / name
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as out:
        json.dump(record, out, indent=2, sort_keys=True)
        out.write('\n')
    return path


# ── Legacy archive ──────────────────────────────────────────────────────────

def systemd_active_state(unit=UNIT):
    try:
        result = subprocess.run(['systemctl', '--user', 'show', unit, '-p', 'ActiveState'],
                                capture_output=True, timeout=5, check=True)
        return result.stdout.decode('ascii').strip().partition('=')[2]
    except (OSError, subprocess.SubprocessError, UnicodeError):
        raise RecoveryError('Could not read the engine unit state; nothing was archived.') from None


def archive_legacy(expect_sha256, ledger=DEFAULT_LEDGER, state_dir=STATE_DIR, engine_state=systemd_active_state):
    if not re.fullmatch(r'[0-9a-f]{64}', expect_sha256 or ''):
        raise RecoveryError('--expect-sha256 must be the full lowercase SHA-256 of the current ledger.')
    if engine_state() in ('active', 'activating', 'reloading', 'deactivating'):
        raise RecoveryError('Stop the engine first; a running engine may rewrite the ledger. Nothing was archived.')
    raw = recovery.read_regular(ledger, 4096)
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expect_sha256:
        raise RecoveryError('The ledger does not match --expect-sha256. Nothing was archived.')
    stamp = utc_stamp()
    archive = Path(ledger).with_name(f'{Path(ledger).name}.archive-legacy-authority-{stamp}')
    # link + unlink: never overwrites, and the bytes are never rewritten.
    try:
        os.link(ledger, archive)
        os.chmod(archive, 0o400)
        if hashlib.sha256(recovery.read_regular(archive, 4096)).hexdigest() != actual:
            os.unlink(archive)
            raise RecoveryError('Archive verification failed; the original ledger was kept.')
        os.unlink(ledger)
    except FileExistsError:
        raise RecoveryError('An archive with this name already exists. Nothing was changed.') from None
    except OSError:
        raise RecoveryError('The ledger could not be archived. Check the data directory.') from None
    manifest = write_manifest(state_dir, f'authority-legacy-archive-{stamp}.json', {
        'event': 'legacy_authority_archived',
        'utc': stamp,
        'archive_path': str(archive),
        'archive_sha256': actual,
        'reason': 'legacy 3-of-5 shares exposed on-host (2026-10-14); authority retired, not recovered',
    })
    return archive, manifest


# ── Destinations and passphrases ────────────────────────────────────────────

def _inside(path, roots):
    resolved = path.resolve()
    return any(resolved == root.resolve() or root.resolve() in resolved.parents for root in roots)


def filesystem_type(path, mountinfo='/proc/self/mountinfo'):
    """fstype of the longest mount point containing path, or None if unknown."""
    resolved = Path(path).resolve()
    try:
        lines = Path(mountinfo).read_text().splitlines()
    except (OSError, UnicodeError):
        return None
    best, fstype = None, None
    for line in lines:
        left, separator, right = line.partition(' - ')
        fields, tail = left.split(), right.split()
        if not separator or len(fields) < 5 or not tail:
            continue
        mount = Path(re.sub(r'\\([0-7]{3})', lambda m: chr(int(m.group(1), 8)), fields[4]))
        # '>=': a later entry on the same mount point is mounted on top.
        if (resolved == mount or mount in resolved.parents) and (best is None or len(mount.parts) >= len(best.parts)):
            best, fstype = mount, tail[0]
    return fstype


def _whole_disks(node, depth=0):
    """Leaf physical disks behind a /sys/dev/block node: {(name, removable)}, or None if unknown."""
    if depth > 8:
        return None
    if (node / 'partition').exists():
        node = node.parent
    if node.name.startswith(('loop', 'zram', 'ram', 'nbd')):
        return None
    slaves = node / 'slaves'
    lower = sorted(slaves.iterdir()) if slaves.is_dir() else []
    if not lower:
        return frozenset({(node.name, (node / 'removable').read_text().strip() == '1')})
    disks = set()
    for entry in lower:
        below = _whole_disks(entry.resolve(strict=True), depth + 1)
        if below is None:
            return None
        disks |= below
    return frozenset(disks)


def disks_of_device(device, sys_root=Path('/sys')):
    major, minor = os.major(device), os.minor(device)
    if major == 0:
        return None
    try:
        return _whole_disks((Path(sys_root) / 'dev/block' / f'{major}:{minor}').resolve(strict=True))
    except (OSError, UnicodeError):
        return None


def block_disks_of(path):
    return disks_of_device(os.stat(path).st_dev)


def validate_destinations(directories, stamp, enforce_separation=True, device_of=lambda p: os.stat(p).st_dev,
                          disk_of=block_disks_of, fs_type_of=filesystem_type):
    if len(directories) != TOTAL or len({str(Path(d).expanduser().resolve()) for d in directories}) != TOTAL:
        raise RecoveryError(f'Give exactly {TOTAL} distinct destination directories, one per share.')
    targets = []
    for share_id, directory in enumerate(directories, start=1):
        directory = Path(directory).expanduser()
        if not directory.is_absolute() or not directory.is_dir() or directory.is_symlink():
            raise RecoveryError(f'Share {share_id}: destination must be an existing absolute directory, not a link.')
        if _inside(directory, [HOME / name for name in FORBIDDEN_ROOTS] + [DATA_DIR, REPO]):
            raise RecoveryError(f'Share {share_id}: destination is inside a repository, agent or engine directory.')
        if _inside(directory, [Path(p) for p in TEMP_ROOTS]):
            raise RecoveryError(f'Share {share_id}: destination is inside a temporary directory.')
        fstype = fs_type_of(directory)
        if fstype is None or fstype in VOLATILE_FS:
            raise RecoveryError(f'Share {share_id}: destination is on a temporary memory filesystem or one of unknown type.')
        if not os.access(directory, os.W_OK):
            raise RecoveryError(f'Share {share_id}: destination is not writable.')
        target = directory / SEALED_NAME.format(stamp=stamp, share_id=share_id)
        if target.exists() or target.is_symlink():
            raise RecoveryError(f'Share {share_id}: a sealed file with this name already exists.')
        targets.append(target)
    if enforce_separation:
        disks = []
        for share_id, target in enumerate(targets, start=1):
            found = disk_of(target.parent)
            if not found:
                raise RecoveryError(f'Share {share_id}: the physical disk behind this destination could not be determined '
                                    '(network, virtual or memory filesystem). Use a local disk or USB partition.')
            disks.append(found)
        per_disk = collections.Counter(name for found in disks for name, _ in found)
        removable = {name: flag for found in disks for name, flag in found}
        for name, count in per_disk.items():
            if count >= THRESHOLD:
                raise RecoveryError(f'{THRESHOLD} or more shares would share one physical disk; that alone would rebuild the secret.')
            if count > 1 and not removable[name]:
                raise RecoveryError('At most one share may live on any fixed (non-removable) disk.')
        devices = [device_of(target.parent) for target in targets]
        if devices.count(device_of(HOME)) > 1:
            raise RecoveryError('At most one share may live on this computer\'s home filesystem.')
    return targets


def collect_passphrases(prompt):
    """prompt(share_id) -> bytearray. Requires length and distinctness before any secret exists."""
    passphrases = []
    digests = set()
    try:
        for share_id in range(1, TOTAL + 1):
            passphrase = prompt(share_id)
            if len(passphrase) < MIN_PASSPHRASE_BYTES:
                raise RecoveryError(f'Share {share_id}: passphrase must be at least {MIN_PASSPHRASE_BYTES} bytes.')
            digest = hashlib.sha256(passphrase).digest()
            if digest in digests:
                raise RecoveryError('Each share needs its own passphrase; one was reused.')
            digests.add(digest)
            passphrases.append(passphrase)
        return passphrases
    except BaseException:
        for passphrase in passphrases:
            wipe(passphrase)
        raise


def terminal_passphrase(share_id):
    first = recovery.private_password(f'Share {share_id} passphrase (hidden; use a 5-word diceware passphrase, '
                                      f'at least {MIN_PASSPHRASE_BYTES} bytes): ')
    second = recovery.private_password(f'Share {share_id} passphrase again (hidden): ')
    try:
        if first != second:
            raise RecoveryError(f'Share {share_id}: the two entries differ. Nothing was generated.')
        return first
    except BaseException:
        wipe(first)
        raise
    finally:
        wipe(second)


# ── Secret generation and sealing ───────────────────────────────────────────

def executable_ready(path):
    recovery.checker_ready(Path(path))


def generate_shares(splitter, expected_sha256):
    with recovery.opened_executable(splitter, 'native splitter', expected_sha256) as (program, fd):
        try:
            result = subprocess.run([str(splitter)], executable=program, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, pass_fds=(fd,), timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            raise RecoveryError('The native splitter could not run. Nothing was generated.') from None
    output = bytearray(result.stdout)
    try:
        if result.returncode != 0:
            raise RecoveryError('The native splitter refused or failed. Nothing was generated.')
        lines = bytes(output).split(b'\n')
        if len(lines) != TOTAL + 1 or lines[-1] != b'':
            raise RecoveryError('The native splitter produced unexpected output.')
        shares = [bytearray(recovery.parse_share(line)) for line in lines[:TOTAL]]
        if [share[:1] for share in shares] != [str(i).encode() for i in range(1, TOTAL + 1)]:
            raise RecoveryError('The native splitter produced unexpected share identifiers.')
        return shares
    finally:
        wipe(output)


def seal_share(share, passphrase, target, gnupghome, written):
    """Seal one share; target joins `written` as soon as gpg has created it."""
    command = recovery.gpg_base(gnupghome) + [
        '--symmetric', '--cipher-algo', 'AES256', '--s2k-mode', '3', '--s2k-digest-algo', 'SHA512',
        '--s2k-count', '65011712', '--compress-algo', 'none', '--output', str(target)]
    recovery.run_gpg(command, passphrase, bytes(share) + b'\n', gnupghome)
    if not target.is_file() or target.is_symlink():
        raise RecoveryError('gpg did not produce the sealed share file.')
    written.append(target)
    os.chmod(target, 0o400)
    # Push the file and its directory entry to the device before the reopen check.
    try:
        for path, flags in ((target, os.O_RDONLY | os.O_NOFOLLOW), (target.parent, os.O_RDONLY | os.O_DIRECTORY)):
            fd = os.open(path, flags)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    except OSError:
        raise RecoveryError('A sealed share could not be flushed to its device.') from None


# ── Engine guards ───────────────────────────────────────────────────────────

def uninitialized_ledger(raw):
    lines = raw.split(b'\n')
    return (len(lines) == 5 and lines[4] == b'' and lines[0] == b'STATE_ROOT|' + EMPTY_ROOT
            and re.fullmatch(rb'TIMESTAMP\|[1-9][0-9]{0,19}', lines[1]) is not None
            and lines[2] == b'LEDGER_SIGNATURE|UNINITIALIZED' and lines[3] == b'STATUS|UNINITIALIZED')


def probe(transport, request):
    client = recovery.ipc_client()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        client.transmit(bytearray(request), *transport, None)
    return output.getvalue()


def live_transport():
    return ('127.0.0.1', 9444, str(DATA_DIR / 'mtls/client.crt'),
            str(DATA_DIR / 'mtls/client.key'), str(DATA_DIR / 'mtls/ca.crt'))


def unit_main_pid():
    result = subprocess.run(['systemctl', '--user', 'show', UNIT, '-p', 'MainPID', '-p', 'ActiveState'],
                            capture_output=True, timeout=5, check=True)
    values = dict(line.split('=', 1) for line in result.stdout.decode('ascii').splitlines())
    pid = int(values.get('MainPID', '0'))
    if values.get('ActiveState') != 'active' or pid <= 0:
        raise RecoveryError('Start the engine first; it must be running UNINITIALIZED.')
    return pid


def start_time(proc):
    """Field 22 of /proc/<pid>/stat (clock ticks after boot); fields after the comm ')' start at 3."""
    return int((proc / 'stat').read_text().rsplit(')', 1)[1].split()[19])


def live_identity():
    """(pid, start time) of the unit's current main process."""
    try:
        pid = unit_main_pid()
        return pid, start_time(PROC / str(pid))
    except RecoveryError:
        raise
    except (OSError, ValueError, IndexError, subprocess.SubprocessError, UnicodeError):
        raise RecoveryError('The running engine identity could not be read.') from None


def live_guard(ledger, transport, expect_engine_sha256):
    """The configured unit runs the pinned binary UNINITIALIZED on the configured endpoint; returns (pid, start)."""
    if Path(ledger).resolve() != DEFAULT_LEDGER.resolve():
        raise RecoveryError('Genesis is restricted to the configured local ledger.')
    try:
        pid = unit_main_pid()
        proc = PROC / str(pid)
        started = start_time(proc)
        if proc.stat().st_uid != os.getuid() or (proc / 'exe').resolve() != ENGINE_PATH.resolve():
            raise RecoveryError('The running engine does not match the expected local executable.')
        # Hash the loaded file through the kernel link, not the path on disk.
        recovery.require_sha256(proc / 'exe', expect_engine_sha256, 'running engine executable', follow=True)
        environment = set((proc / 'environ').read_bytes().split(b'\0'))
        if any(entry.startswith(b'LD_') for entry in environment):
            raise RecoveryError('The running engine has a dynamic-loader (LD_*) override in its environment.')
        expected = {b'QF_DATA_DIR=' + os.fsencode(DATA_DIR), b'QF_BIND_ADDRESS=127.0.0.1', b'QF_BIND_PORT=9444'}
        if not expected.issubset(environment):
            raise RecoveryError('The running engine uses an unexpected data directory or endpoint.')
        if start_time(proc) != started:
            raise RecoveryError('The engine process changed while it was being checked.')
    except RecoveryError:
        raise
    except (OSError, ValueError, IndexError, subprocess.SubprocessError, UnicodeError):
        raise RecoveryError('The running engine could not be bound safely. Nothing was generated.') from None
    probe_guard(ledger, transport)
    return pid, started


def probe_guard(ledger, transport):
    if not uninitialized_ledger(recovery.read_regular(ledger, 4096)):
        raise RecoveryError('The ledger is not a fresh UNINITIALIZED envelope. Archive the legacy ledger and restart the engine first.')
    if probe(transport, b'STATUS') != 'ERR|NODE_UNINITIALIZED_CALL_INIT\n':
        raise RecoveryError('The engine did not confirm UNINITIALIZED state. Nothing was generated.')


# ── Genesis ─────────────────────────────────────────────────────────────────

class EngineChanged(RecoveryError):
    """The engine PID or start time differs from the first guard."""


def _remove_sealed(written):
    for target in written:
        with contextlib.suppress(OSError):
            os.chmod(target, 0o600)
        with contextlib.suppress(OSError):
            os.unlink(target)


def _record_kept(state_dir, stamp, ledger, written, error):
    """Non-secret record of sealed files kept after INIT; returns its path or None."""
    def digest(path):
        with contextlib.suppress(OSError):
            return file_sha256(path)
        return None

    try:
        ledger_sha256 = hashlib.sha256(recovery.read_regular(ledger, 4096)).hexdigest()
    except RecoveryError:
        ledger_sha256 = None
    try:
        return write_manifest(state_dir, f'authority-genesis-{stamp}-INCOMPLETE.json', {
            'event': 'authority_genesis_incomplete',
            'utc': stamp,
            'reason': str(error) if isinstance(error, RecoveryError) else type(error).__name__,
            'ledger_path': str(ledger),
            'ledger_sha256': ledger_sha256,
            'sealed_shares': [{'share_id': i, 'path': str(t), 'ciphertext_sha256': digest(t)}
                              for i, t in enumerate(written, start=1)],
        })
    except OSError:
        return None

def genesis(directories, prompt, *, expect_engine_sha256, expect_splitter_sha256, expect_checker_sha256,
            ledger=DEFAULT_LEDGER, transport=None, guard=None, identity=None, splitter=DEFAULT_SPLITTER,
            checker=DEFAULT_CHECKER, state_dir=STATE_DIR, enforce_separation=True, gnupghome_parent=None):
    transport = transport or live_transport()
    guard = guard or live_guard
    identity = identity or live_identity
    stamp = utc_stamp()
    recovery.require_hex_sha256(expect_engine_sha256, 'running engine executable')
    executable_ready(splitter)
    recovery.require_sha256(splitter, expect_splitter_sha256, 'native splitter')
    recovery.checker_ready(Path(checker))
    recovery.require_sha256(checker, expect_checker_sha256, 'native checker')
    engine = guard(ledger, transport, expect_engine_sha256)
    targets = validate_destinations(directories, stamp, enforce_separation)
    passphrases = collect_passphrases(prompt)
    shares = []
    written = []
    init_sent = False

    def same_engine(seen, when):
        if seen != engine:
            raise EngineChanged(f'The engine process (PID or start time) changed {when}. Nothing was sent.')

    try:
        # Re-check after the human pause: nothing may have changed while typing.
        same_engine(guard(ledger, transport, expect_engine_sha256), 'while passphrases were entered')
        shares = generate_shares(splitter, expect_splitter_sha256)
        with recovery.private_gnupghome(gnupghome_parent) as gnupghome:
            for share, passphrase, target in zip(shares, passphrases, targets):
                seal_share(share, passphrase, target, gnupghome, written)
                reopened = recovery.gpg_open(target, passphrase, gnupghome)
                try:
                    if recovery.parse_share(reopened) != bytes(share):
                        raise RecoveryError('A sealed share did not reopen to the same value. Nothing was sent.')
                finally:
                    wipe(reopened)
        same_engine(guard(ledger, transport, expect_engine_sha256), 'before INIT')
        request = bytearray(b'INIT|' + b','.join(bytes(s) for s in shares[:THRESHOLD]))
        try:
            # From here on the engine may seal with these shares at any moment
            # (INIT runs before the ACK), so the files are never removed.
            init_sent = True
            reply = probe(transport, request)
        finally:
            wipe(request)
        if identity() != engine:
            raise EngineChanged('engine identity changed during INIT')
        ledger_bytes = recovery.read_regular(ledger, 4096)
        active = (ledger_bytes.startswith(b'STATE_ROOT|' + EMPTY_ROOT + b'\n')
                  and ledger_bytes.endswith(b'\nSTATUS|ACTIVE\n'))
        if not active:
            raise RecoveryError('The engine did not seal an ACTIVE ledger.')
        if reply != 'ACK|GENESIS_SECURED\n':
            print('[!] No INIT acknowledgement was read, but the ledger is ACTIVE; verifying it against the new shares.',
                  file=sys.stderr)
        for subset in itertools.combinations(shares, THRESHOLD):
            if not recovery.check_ledger([bytes(s) for s in subset], Path(ledger), Path(checker), expect_checker_sha256):
                raise RecoveryError('A 3-share subset does not authenticate the new ledger. Stop and inspect; another client may have sent INIT first.')
        manifest = write_manifest(state_dir, f'authority-genesis-{stamp}.json', {
            'event': 'authority_genesis',
            'utc': stamp,
            'threshold': THRESHOLD,
            'total': TOTAL,
            'ledger_path': str(ledger),
            'ledger_sha256': hashlib.sha256(ledger_bytes).hexdigest(),
            'subsets_verified': 10,
            'sealed_shares': [{'share_id': i, 'path': str(t), 'ciphertext_sha256': file_sha256(t)}
                              for i, t in enumerate(targets, start=1)],
            'engine_sha256': expect_engine_sha256,
            'splitter_sha256': expect_splitter_sha256,
            'checker_sha256': expect_checker_sha256,
            'sealing': 'gpg symmetric AES256, S2K iterated+salted SHA512 count 65011712',
        })
        return manifest
    except BaseException as error:
        if not init_sent:
            _remove_sealed(written)
            raise
        record = _record_kept(state_dir, stamp, ledger, written, error)
        where = f' Record: {record}' if record else ' No record could be written; the files carry this run\'s stamp.'
        if isinstance(error, EngineChanged):
            raise RecoveryError('ENGINE IDENTITY CHANGED DURING INIT: the shares may have reached a different process. '
                                f'Treat all {TOTAL} shares as EXPOSED and do not use this authority. '
                                f'The {len(written)} sealed files were KEPT for inspection; stop all services and investigate.'
                                + where) from None
        raise RecoveryError(f'INIT was sent, so the engine may have sealed with these shares. The {len(written)} sealed '
                            'files were KEPT in their destinations. Remove them only after a later STATUS reply and a '
                            'ledger read both confirm UNINITIALIZED. Stop and inspect the ledger before anything else.'
                            + where) from None
    finally:
        for value in shares:
            wipe(value)
        for value in passphrases:
            wipe(value)


def main(argv=None):
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        parser = recovery.SafeParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
        commands = parser.add_subparsers(dest='command', required=True)
        archive = commands.add_parser('archive-legacy')
        archive.add_argument('--expect-sha256', required=True)
        create = commands.add_parser('genesis', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
        create.add_argument('--dest', required=True, help='Five comma-separated directories, share 1 first')
        create.add_argument('--expect-engine-sha256', required=True, help='SHA-256 of the engine executable')
        create.add_argument('--expect-splitter-sha256', required=True, help='SHA-256 of qf_authority_split')
        create.add_argument('--expect-checker-sha256', required=True, help='SHA-256 of qf_legacy_recovery_check')
        args = parser.parse_args(argv)
        if args.command == 'archive-legacy':
            path, manifest = archive_legacy(args.expect_sha256)
            print(f'ARCHIVED — legacy ledger moved to {path} (read-only).')
            print(f'Manifest: {manifest}')
            return 0
        directories = args.dest.split(',')
        if len(directories) != TOTAL or any(not d or any(c in d for c in '\r\n') for d in directories):
            raise RecoveryError('Give five comma-separated directory paths.')
        for value, what in ((args.expect_engine_sha256, 'running engine executable'),
                            (args.expect_splitter_sha256, 'native splitter'),
                            (args.expect_checker_sha256, 'native checker')):
            recovery.require_hex_sha256(value, what)
        manifest = genesis(directories, terminal_passphrase, expect_engine_sha256=args.expect_engine_sha256,
                           expect_splitter_sha256=args.expect_splitter_sha256,
                           expect_checker_sha256=args.expect_checker_sha256)
        print('GENESIS SEALED — new authority active; all 10 three-share subsets authenticate the new ledger.')
        print(f'Manifest: {manifest}')
        print('Unmount (sync) each USB medium before unplugging it, e.g. `udisksctl unmount -b <device>`, '
              'so no sealed file is lost in a write cache.')
        return 0
    except RecoveryError as error:
        print(str(error), file=sys.stderr)
        return 2
    except (OSError, ValueError, subprocess.SubprocessError):
        print('The ceremony could not finish safely.', file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print('Ceremony cancelled.', file=sys.stderr)
        return 130


if __name__ == '__main__':
    sys.exit(main())
