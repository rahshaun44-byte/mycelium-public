"""Native IPC exchange against a temporary engine, PKI and data directory.

Set QF_TEST_BUILD_DIR to a built tree. No running services are used.
"""
import os
from pathlib import Path
import socket
import ssl
import struct
import subprocess
import time
import pytest


def test_native_mlkem_ipc(tmp_path):
    build = Path(os.environ.get('QF_TEST_BUILD_DIR', 'build_check')).resolve()
    engine = build / 'quantum_flex_engine'
    fixture = build / 'test_mlkem768'
    assert engine.is_file() and fixture.is_file(), 'Build CMake targets first and set QF_TEST_BUILD_DIR'
    def openssl(*args):
        subprocess.run(['openssl', *args], cwd=tmp_path, check=True, capture_output=True)
    openssl('req', '-x509', '-newkey', 'ed25519', '-noenc', '-keyout', 'ca.key', '-out', 'ca.crt',
            '-subj', '/CN=Isolated Test CA', '-days', '1', '-addext', 'keyUsage=critical,keyCertSign,cRLSign')
    (tmp_path / 'leaf.ext').write_text('basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=serverAuth,clientAuth\nsubjectAltName=DNS:server\nauthorityKeyIdentifier=keyid,issuer\n')
    for name in ['server', 'client']:
        openssl('req', '-new', '-newkey', 'ed25519', '-noenc', '-keyout', name + '.key',
                '-out', name + '.csr', '-subj', '/CN=' + name)
        openssl('x509', '-req', '-in', name + '.csr', '-CA', 'ca.crt', '-CAkey', 'ca.key',
                '-CAcreateserial', '-out', name + '.crt', '-days', '1', '-extfile', 'leaf.ext')
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    env = os.environ.copy()
    env.update(QF_DATA_DIR=str(tmp_path), QF_POSTGRES_CONNINFO='', QF_BIND_ADDRESS='127.0.0.1', QF_BIND_PORT=str(port),
               QF_SERVER_CERT=str(tmp_path / 'server.crt'), QF_SERVER_KEY=str(tmp_path / 'server.key'),
               QF_ROOT_CA=str(tmp_path / 'ca.crt'), QF_ED_PRIVATE_KEY=str(tmp_path / 'missing-ed'),
               QF_PQC_PRIVATE_KEY=str(tmp_path / 'missing-pqc'), QF_KEM_PROPERTIES='provider=default')
    context = ssl.create_default_context(cafile=str(tmp_path / 'ca.crt'))
    context.load_cert_chain(str(tmp_path / 'client.crt'), str(tmp_path / 'client.key'))
    def exchange(kind, payload):
        with socket.create_connection(('127.0.0.1', port), timeout=3) as raw:
            with context.wrap_socket(raw, server_hostname='server') as conn:
                conn.sendall(struct.pack('!2sBBIII', b'QF', 1, kind, 0, len(payload), 0) + payload)
                def read_exact(count):
                    data = b''
                    while len(data) < count:
                        block = conn.recv(count - len(data))
                        assert block, 'Engine closed before completing its response'
                        data += block
                    return data
                magic, version, kind, _, length, _ = struct.unpack('!2sBBIII', read_exact(16))
                assert magic == b'QF' and version == 1 and length <= 1184
                return kind, read_exact(length)
    with (tmp_path / 'engine.log').open('w+') as log:
        process = subprocess.Popen([str(engine)], cwd=tmp_path, env=env, stdout=log, stderr=log)
        try:
            for _ in range(200):
                log.flush(); log.seek(0)
                if 'mTLS TCP Socket listening' in log.read():
                    # The log precedes bind; retry only connection refusals below.
                    break
                if process.poll() is not None:
                    log.seek(0); pytest.fail(log.read())
                time.sleep(0.01)
            for _ in range(100):
                try:
                    kind, pk = exchange(0x12, b'')
                    break
                except ConnectionRefusedError:
                    time.sleep(0.01)
            else:
                pytest.fail('Engine did not bind')
            assert kind == 0x12 and len(pk) == 1184
            (tmp_path / 'public.bin').write_bytes(pk)
            subprocess.run([str(fixture), '--prepare', str(tmp_path / 'public.bin'), str(tmp_path / 'ct.bin'),
                            str(tmp_path / 'tag.bin')], check=True, capture_output=True)
            ct = (tmp_path / 'ct.bin').read_bytes()
            expected = (tmp_path / 'tag.bin').read_bytes()
            assert exchange(0x13, ct) == (0x14, expected)
            assert exchange(0x03, b'legacy') == (0x7f, b'')
            assert exchange(0x13, b'truncated') == (0x7f, b'')
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=3)
