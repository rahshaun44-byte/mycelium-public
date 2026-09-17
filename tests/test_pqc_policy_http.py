"""Parity with an isolated local OPA process, never the deployed sidecar."""
import json
import socket
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import pytest
from sentinel.policies.wasm_gatekeeper import MembraneHealthWasmGatekeeper

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize('compromised', [False, True])
def test_http_wasm_strict_parity(tmp_path, compromised):
    flags = {'ML_KEM_COMPROMISED': compromised, 'FRODOKEM_COMPROMISED': compromised}
    data = tmp_path / 'data.json'
    data.write_text(json.dumps({'threat_flags': flags}))
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    with (tmp_path / 'opa.log').open('w+') as log:
        process = subprocess.Popen(['opa', 'run', '--server', '--addr', f'127.0.0.1:{port}',
                                    str(ROOT / 'pqc-immune-daemon/membrane_health.rego'), str(data)], stdout=log, stderr=log)
        try:
            base = f'http://127.0.0.1:{port}'
            for _ in range(100):
                try:
                    with urllib.request.urlopen(base + '/health', timeout=0.2):
                        break
                except OSError:
                    if process.poll() is not None:
                        log.seek(0)
                        pytest.fail(log.read())
                    time.sleep(0.02)
            else:
                pytest.fail('Isolated OPA did not become ready')
            gate = MembraneHealthWasmGatekeeper()
            for kem in ['FrodoKEM-976-AES', 'X25519', 'ML-KEM-512', 'ML-KEM-768', 'ML-KEM-1024']:
                cbom = {'requested_profile': 'fips_strict', 'metadata': {'timestamp': datetime.now(timezone.utc).isoformat()},
                        'components': [{'type': 'crypto-asset', 'cryptoProperties': {'algorithmProperties': {'algorithm': a}}}
                                       for a in [kem, 'ML-DSA-65']]}
                req = urllib.request.Request(base + '/v1/data/membrane/health/verdict',
                                             data=json.dumps({'input': cbom}).encode(), headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=2) as response:
                    http = json.load(response)['result']
                wasm = gate.evaluate_verdict(cbom, flags)
                assert http['node_status'] == wasm['node_status']
                assert http['recommended_fallback'] == wasm['recommended_fallback'] == 'NONE'
                assert http['node_status'] == ('TOXIC' if compromised or not kem.startswith('ML-KEM') else 'COMPLIANT')
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
