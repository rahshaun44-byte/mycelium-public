"""Isolated policy/daemon regression checks. No live services or credentials."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sentinel.policies.wasm_gatekeeper import MembraneHealthWasmGatekeeper

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('strict_immune_daemon', ROOT / 'pqc-immune-daemon/immune_daemon.py')
daemon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daemon)


def cbom(kem='ML-KEM-768', profile='fips_strict'):
    return {'bomFormat': 'CycloneDX', 'specVersion': '1.5', 'requested_profile': profile,
            'metadata': {'timestamp': datetime.now(timezone.utc).isoformat()},
            'components': [{'type': 'crypto-asset', 'name': a,
                            'cryptoProperties': {'assetType': 'algorithm', 'algorithmProperties': {'algorithm': a}}}
                           for a in (kem, 'ML-DSA-65')]}


@pytest.mark.parametrize('kem', ['FrodoKEM-976-AES', 'FrodoKEM-640-AES', 'X25519', 'unknown'])
@pytest.mark.parametrize('flags', [{}, {'ML_KEM_COMPROMISED': True, 'FRODOKEM_COMPROMISED': True}])
def test_strict_rejects_non_approved_without_eval_conflict(kem, flags):
    verdict = MembraneHealthWasmGatekeeper().evaluate_verdict(cbom(kem), flags)
    assert verdict['node_status'] == 'TOXIC'
    assert verdict['recommended_fallback'] == 'NONE'
    assert verdict['toxic_count'] >= 1


@pytest.mark.parametrize('kem', ['ML-KEM-512', 'ML-KEM-768', 'ML-KEM-1024'])
def test_family_compromise_never_downgrades(kem):
    gate = MembraneHealthWasmGatekeeper()
    assert gate.evaluate_verdict(cbom(kem))['node_status'] == 'COMPLIANT'
    for flags in ({'ML_KEM_COMPROMISED': True}, {'ML_KEM_COMPROMISED': True, 'FRODOKEM_COMPROMISED': True}):
        verdict = gate.evaluate_verdict(cbom(kem), flags)
        assert verdict['node_status'] == 'TOXIC'
        assert verdict['recommended_fallback'] == 'NONE'


def test_unknown_profile_denied():
    assert MembraneHealthWasmGatekeeper().evaluate_verdict(cbom(profile='fips_strcit'))['node_status'] == 'TOXIC'


def test_profile_selection(tmp_path, monkeypatch):
    monkeypatch.delenv('PQC_COMPLIANCE_PROFILE', raising=False)
    state = daemon.ImmuneState(tmp_path / 'config')
    assert daemon.generate_cbom(state)['requested_profile'] == 'fips_strict'
    monkeypatch.setenv('PQC_COMPLIANCE_PROFILE', 'agility')
    assert daemon.ImmuneState(tmp_path / 'config').profile == 'agility'
    assert daemon.ImmuneState(tmp_path / 'config', profile='iso_strict').profile == 'iso_strict'
    monkeypatch.setenv('PQC_COMPLIANCE_PROFILE', 'typo')
    with pytest.raises(ValueError):
        daemon.ImmuneState(tmp_path / 'config')


@pytest.mark.parametrize('verdict', [None, {'node_status': 'DENIED'}, {'node_status': 'UNKNOWN'},
                                   {'node_status': 'TOXIC', 'recommended_fallback': 'ML-KEM-512'},
                                   {'node_status': 'TOXIC', 'recommended_fallback': 'FrodoKEM-976-AES'}])
@pytest.mark.parametrize('dry_run', [False, True])
def test_strict_halts_on_first_unhealthy_verdict(tmp_path, verdict, dry_run):
    conf = tmp_path / 'config'
    original = 'active_kem=ML-KEM-768\nactive_sig=ML-DSA-65\n'
    conf.write_text(original)
    state = daemon.ImmuneState(conf, profile='fips_strict')
    state.worker_pid = 123456
    with patch.object(daemon, 'query_opa', return_value=verdict), \
         patch.object(daemon, 'async_audit'), patch.object(daemon, 'halt_worker') as kill:
        with pytest.raises(SystemExit) as error:
            daemon.decision_loop(state, 'http://fake', 0, 3, dry_run, True, None, None,
                                 breaker=daemon.CircuitBreaker())
        assert error.value.code == 1
        if dry_run:
            kill.assert_not_called()
        else:
            kill.assert_called_once_with(state.worker_pid)
    assert conf.read_text() == original


def test_wasm_adapter_passes_threat_flags():
    with patch.object(daemon, 'fetch_threat_flags', return_value={'ML_KEM_COMPROMISED': True}) as fetch:
        verdict = daemon.query_opa('wasm', cbom())
    assert fetch.call_args.kwargs['required'] is True
    assert verdict['node_status'] == 'TOXIC'
    assert verdict['recommended_fallback'] == 'NONE'


def test_missing_threat_data_fails_closed():
    with patch.object(daemon, 'fetch_threat_flags', side_effect=ConnectionError('offline')):
        with pytest.raises(ConnectionError):
            daemon.query_opa('wasm', cbom())


def test_cli_profile_overrides_environment(tmp_path, monkeypatch):
    monkeypatch.setenv('PQC_COMPLIANCE_PROFILE', 'agility')
    monkeypatch.setattr(sys, 'argv', ['immune_daemon', '--profile', 'fips_strict', '--dry-run', '--once', '--conf', str(tmp_path / 'conf')])
    with patch.object(daemon, 'decision_loop') as loop:
        assert daemon.main() == 0
    assert loop.call_args.kwargs['state'].profile == 'fips_strict'


def test_halt_worker_stops_owned_child():
    import subprocess
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
    try:
        daemon.halt_worker(child.pid, timeout=0.2)
        child.wait(timeout=1)
        assert child.returncode != 0
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=1)
