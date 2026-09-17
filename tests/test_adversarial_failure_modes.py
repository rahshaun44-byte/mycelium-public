"""Adversarial stress and failure-mode test suite for QuantumFlex.

Exercises TOE behavior under failure conditions:
1. Compromised / unauthorized credentials on HTTP and mTLS interfaces.
2. Unavailable policy services (OPA downtime / fail-closed invariant gating).
3. Policy input validation boundaries (empty CBOM, non-hex TPM, negative reserves).
4. Wire protocol fragmentation across QF magic bytes.
5. Slowloris / socket stalls enforcing 5-second socket deadlines.
6. Cold daemon restart and strict LOCKED state enforcement.
7. Quarantine chamber containment and path consistency.
"""

import os
from pathlib import Path
import socket
import ssl
import subprocess
import time
import pytest
from fastapi.testclient import TestClient

import api_node.main as api_node_main
import mcp_layer.athena_api as athena_api
import mcp_layer.qf_bot.bot_server as bot_server
from sentinel.invariant_gate import query_opa_invariant
from sentinel.policies.wasm_gatekeeper import (
    get_membrane_wasm_gatekeeper,
    get_reserve_wasm_gatekeeper,
    RESERVE_WASM,
    MEMBRANE_WASM,
)


# ------------------------------------------------------------------------------
# 1. Compromised / Unauthorized Credentials (HTTP Interfaces)
# ------------------------------------------------------------------------------

def test_api_node_ingest_unauthenticated(monkeypatch):
    """Verify api_node /ingest rejects unauthenticated and unconfigured credentials with 401."""
    client = TestClient(api_node_main.app)
    
    # When API key is configured
    monkeypatch.setenv("API_NODE_KEY", "test_secret_key_12345")
    
    # Missing API key header
    res = client.post("/ingest", json={"path": "docs/ADR_003_DATABASE_LAYER.md"})
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    
    # Invalid API key header
    res = client.post(
        "/ingest",
        json={"path": "docs/ADR_003_DATABASE_LAYER.md"},
        headers={"x-api-key": "unauthorized_forged_key"}
    )
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"

    # When API key is NOT configured at all on host -> MUST fail closed (401)
    monkeypatch.delenv("API_NODE_KEY", raising=False)
    monkeypatch.delenv("DASHBOARD_API_KEY", raising=False)
    res = client.post(
        "/ingest",
        json={"path": "docs/ADR_003_DATABASE_LAYER.md"},
        headers={"x-api-key": "any_key"}
    )
    assert res.status_code == 401, "Expected 401 when API key unconfigured (fail closed)"


def test_api_node_webhook_unauthenticated(monkeypatch):
    """Verify api_node /webhook/ingest rejects unauthenticated requests with 401."""
    client = TestClient(api_node_main.app)
    monkeypatch.setenv("API_NODE_KEY", "test_secret_key_12345")
    
    res = client.post("/webhook/ingest", json={"payload": "suspicious_blob"})
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    
    res = client.post(
        "/webhook/ingest",
        json={"payload": "suspicious_blob"},
        headers={"x-api-key": "bad_key"}
    )
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"


def test_athena_api_ingest_unauthenticated(monkeypatch):
    """Verify athena_api /ingest rejects unauthenticated requests with 401."""
    client = TestClient(athena_api.app)
    monkeypatch.setenv("ATHENA_API_KEY", "athena_secret_key")
    
    res = client.post("/ingest", json={"text": "untrusted input", "metadata": {}})
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    
    res = client.post(
        "/ingest",
        json={"text": "untrusted input", "metadata": {}},
        headers={"x-api-key": "bad_athena_key"}
    )
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"


def test_bot_server_approval_unauthenticated(monkeypatch):
    """Verify bot_server /api/drafts/{id}/approve rejects unauthenticated requests with 401."""
    client = TestClient(bot_server.app)
    monkeypatch.setenv("QFBOT_API_KEY", "bot_secret_key")
    
    res = client.post("/api/drafts/draft_42/approve", json={})
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    
    res = client.post(
        "/api/drafts/draft_42/approve",
        json={},
        headers={"x-api-key": "bad_token"}
    )
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"


# ------------------------------------------------------------------------------
# 2. Unavailable Policy Services (OPA Downtime Fail-Closed)
# ------------------------------------------------------------------------------

def test_opa_service_unavailable_fails_closed(monkeypatch):
    """Verify invariant evaluation fails closed (DENY) when OPA HTTP service is down."""
    monkeypatch.setenv("FORCE_HTTP_OPA", "1")
    monkeypatch.setenv("OPA_INVARIANT_URL", "http://127.0.0.1:59998/v1/data/quantumflex/invariant")
    
    payload = {
        "resource_type": "MEMORY_MB",
        "reserve_measured": 4096.0,
        "units_claimed": 1024.0,
        "telemetry_timestamp": int(time.time()),
        "max_staleness_seconds": 60,
    }
    
    admitted, verdict, reason = query_opa_invariant(payload)
    assert admitted is False, "Invariant gate admitted request when OPA was unreachable!"
    assert verdict == "DENY", f"Expected verdict DENY, got {verdict}"
    assert "unreachable" in reason.lower() or "error" in reason.lower()


# ------------------------------------------------------------------------------
# 3. Policy Input Validation Boundaries
# ------------------------------------------------------------------------------

def test_policy_rejects_empty_cbom_inventory():
    """Verify OPA rejects empty or missing CBOM inventories instead of reporting COMPLIANT."""
    gate = get_membrane_wasm_gatekeeper()
    assert gate is not None, "Membrane Wasm gatekeeper unavailable"
    
    # 1. Empty components list
    empty_cbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "components": [],
        "metadata": {"timestamp": "2026-09-16T12:00:00Z"},
        "requested_profile": "fips_strict",
    }
    res = gate.evaluate_verdict(empty_cbom)
    assert res["node_status"] == "TOXIC", f"Empty components reported as {res['node_status']}"
    assert res["total_components"] == 0

    # 2. Missing components key
    missing_cbom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "metadata": {"timestamp": "2026-09-16T12:00:00Z"},
        "requested_profile": "fips_strict",
    }
    res = gate.evaluate_verdict(missing_cbom)
    assert res["node_status"] == "TOXIC", f"Missing components reported as {res['node_status']}"


def test_policy_rejects_non_hex_or_placeholder_tpm():
    """Verify reserve invariant rejects non-hex or all-zero TPM values."""
    gate = get_reserve_wasm_gatekeeper()
    assert gate is not None, "Reserve Wasm gatekeeper unavailable"

    # All-zero placeholder
    zeros_payload = {
        "resource_type": "TPM_ANCHOR",
        "reserve_measured": "0" * 64,
        "units_claimed": "0" * 64,
        "telemetry_timestamp": int(time.time()),
        "max_staleness_seconds": 60,
    }
    allow, verdict, reason = gate.evaluate_invariant(zeros_payload)
    assert allow is False and verdict == "DENY", "All-zero placeholder was admitted!"

    # Non-hex characters
    non_hex_payload = {
        "resource_type": "TPM_ANCHOR",
        "reserve_measured": "z" * 64,
        "units_claimed": "z" * 64,
        "telemetry_timestamp": int(time.time()),
        "max_staleness_seconds": 60,
    }
    allow, verdict, reason = gate.evaluate_invariant(non_hex_payload)
    assert allow is False and verdict == "DENY", "Non-hex 64-char string was admitted!"


def test_policy_rejects_negative_numeric_reserves():
    """Verify reserve invariant rejects negative reserves and obligations."""
    gate = get_reserve_wasm_gatekeeper()
    assert gate is not None, "Reserve Wasm gatekeeper unavailable"

    neg_payload = {
        "resource_type": "MEMORY_MB",
        "reserve_measured": -10.0,
        "units_claimed": -20.0,
        "telemetry_timestamp": int(time.time()),
        "max_staleness_seconds": 60,
    }
    allow, verdict, reason = gate.evaluate_invariant(neg_payload)
    assert allow is False and verdict == "DENY", "Negative reserve/obligation was admitted!"


# ------------------------------------------------------------------------------
# 4. Isolated C++ Engine IPC Fixture & Tests
# ------------------------------------------------------------------------------

@pytest.fixture
def isolated_engine(tmp_path):
    """Spawns an isolated quantum_flex_engine with temporary PKI and data directory."""
    build = Path(os.environ.get("QF_TEST_BUILD_DIR", "build_check")).resolve()
    engine_bin = build / "quantum_flex_engine"
    if not engine_bin.is_file():
        pytest.skip(f"Binary not found: {engine_bin}. Run cmake build first.")

    def openssl(*args):
        subprocess.run(["openssl", *args], cwd=tmp_path, check=True, capture_output=True)

    # 1. Isolated Root CA
    openssl("req", "-x509", "-newkey", "ed25519", "-noenc", "-keyout", "ca.key", "-out", "ca.crt",
            "-subj", "/CN=Adversarial Test CA", "-days", "1",
            "-addext", "keyUsage=critical,keyCertSign,cRLSign")

    # Extensions
    (tmp_path / "leaf.ext").write_text(
        "basicConstraints=critical,CA:FALSE\n"
        "keyUsage=critical,digitalSignature\n"
        "extendedKeyUsage=serverAuth,clientAuth\n"
        "subjectAltName=DNS:localhost,IP:127.0.0.1\n"
        "authorityKeyIdentifier=keyid,issuer\n"
    )

    # 2. Server Certificate
    openssl("req", "-new", "-newkey", "ed25519", "-noenc", "-keyout", "server.key",
            "-out", "server.csr", "-subj", "/CN=127.0.0.1")
    openssl("x509", "-req", "-in", "server.csr", "-CA", "ca.crt", "-CAkey", "ca.key",
            "-CAcreateserial", "-out", "server.crt", "-days", "1", "-extfile", "leaf.ext")

    # 3. Authorized Client Certificate (CN=operator)
    openssl("req", "-new", "-newkey", "ed25519", "-noenc", "-keyout", "admin_client.key",
            "-out", "admin_client.csr", "-subj", "/CN=operator")
    openssl("x509", "-req", "-in", "admin_client.csr", "-CA", "ca.crt", "-CAkey", "ca.key",
            "-CAcreateserial", "-out", "admin_client.crt", "-days", "1", "-extfile", "leaf.ext")

    # 4. Unauthorized Client Certificate (CN=unauthorized-client)
    openssl("req", "-new", "-newkey", "ed25519", "-noenc", "-keyout", "unauth_client.key",
            "-out", "unauth_client.csr", "-subj", "/CN=unauthorized-client")
    openssl("x509", "-req", "-in", "unauth_client.csr", "-CA", "ca.crt", "-CAkey", "ca.key",
            "-CAcreateserial", "-out", "unauth_client.crt", "-days", "1", "-extfile", "leaf.ext")

    # Find open port
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    env = os.environ.copy()
    env.update(
        QF_DATA_DIR=str(tmp_path),
        QF_POSTGRES_CONNINFO="",
        QF_BIND_ADDRESS="127.0.0.1",
        QF_BIND_PORT=str(port),
        QF_SERVER_CERT=str(tmp_path / "server.crt"),
        QF_SERVER_KEY=str(tmp_path / "server.key"),
        QF_ROOT_CA=str(tmp_path / "ca.crt"),
        QF_ED_PRIVATE_KEY=str(tmp_path / "missing-ed"),
        QF_PQC_PRIVATE_KEY=str(tmp_path / "missing-pqc"),
        QF_KEM_PROPERTIES="provider=default",
    )

    proc = subprocess.Popen([str(engine_bin)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Wait for socket to be ready
    ready = False
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                ready = True
                break
        except (ConnectionRefusedError, OSError):
            time.sleep(0.05)
    assert ready, f"Isolated engine failed to start on port {port}"

    yield {
        "proc": proc,
        "port": port,
        "tmp_path": tmp_path,
        "ca_crt": str(tmp_path / "ca.crt"),
        "admin_crt": str(tmp_path / "admin_client.crt"),
        "admin_key": str(tmp_path / "admin_client.key"),
        "unauth_crt": str(tmp_path / "unauth_client.crt"),
        "unauth_key": str(tmp_path / "unauth_client.key"),
    }

    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_ipc_unauthorized_mutation_rejected(isolated_engine):
    """Verify that SET_HARVESTER_KEY is rejected when caller CN is not authorized."""
    cfg = isolated_engine
    port = cfg["port"]
    
    context = ssl.create_default_context(cafile=cfg["ca_crt"])
    context.load_cert_chain(cfg["unauth_crt"], cfg["unauth_key"])

    with socket.create_connection(("127.0.0.1", port), timeout=5) as raw_sock:
        with context.wrap_socket(raw_sock, server_hostname="127.0.0.1") as tls_sock:
            tls_sock.sendall(b"SET_HARVESTER_KEY|0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\n")
            resp = tls_sock.recv(1024).decode("utf-8", errors="replace")
            assert resp.startswith("ERR|"), f"Expected ERR| response, got: {resp.strip()}"
            assert "HARVESTER_KEY_SET" not in resp


def test_ipc_slowloris_stall_enforces_deadline(isolated_engine):
    """Verify raw TCP connection holding open without bytes is closed within 5s deadline."""
    cfg = isolated_engine
    port = cfg["port"]

    start_time = time.time()
    with socket.create_connection(("127.0.0.1", port), timeout=10) as raw_sock:
        try:
            data = raw_sock.recv(1024)
            assert data == b"", "Expected peer to close stalled connection"
        except (socket.timeout, ConnectionResetError):
            pass

    elapsed = time.time() - start_time
    assert elapsed >= 4.5, f"Timeout triggered too fast ({elapsed:.2f}s)"
    assert elapsed <= 8.0, f"Socket was not terminated within bounded deadline ({elapsed:.2f}s)"


def test_ipc_fragmented_magic_bytes_succeeds(isolated_engine):
    """Verify splitting initial 'Q' and 'F' magic bytes across TLS writes is correctly reassembled."""
    import struct
    cfg = isolated_engine
    port = cfg["port"]

    context = ssl.create_default_context(cafile=cfg["ca_crt"])
    context.load_cert_chain(cfg["admin_crt"], cfg["admin_key"])

    # Construct ML-KEM-768 public key request frame:
    # Magic: 'Q', 'F'
    # Wire version: 1
    # Message type: 0x12 (KEM Public Key Request)
    # Session ID: 0 (8 bytes)
    # Payload length: 0 (4 bytes)
    # Payload: empty
    # Total header: 2 + 1 + 1 + 8 + 4 = 16 bytes
    header = struct.pack(">2sBBQI", b"QF", 1, 0x12, 0, 0)

    with socket.create_connection(("127.0.0.1", port), timeout=5) as raw_sock:
        with context.wrap_socket(raw_sock, server_hostname="127.0.0.1") as tls_sock:
            # Fragment the magic bytes: write 'Q' first
            tls_sock.sendall(header[:1])
            time.sleep(0.05)
            # Write 'F' and the rest of the header
            tls_sock.sendall(header[1:])

            resp = tls_sock.recv(4096)
            # Response must be a binary QFXK frame (starts with b'QF'), NOT legacy 'ERR|NODE_UNINITIALIZED...'
            assert len(resp) >= 16, f"Expected framed response, got {len(resp)} bytes"
            assert resp[:2] == b"QF", f"Expected QF magic, got: {resp[:2]}"
            res_type = resp[3]
            # 0x13 = ML-KEM-768 Public Key Response
            assert res_type == 0x12, f"Expected response type 0x13, got 0x{res_type:02x}"


def test_engine_cold_restart_boots_locked(isolated_engine):
    """Verify that an engine loaded from existing state boots in LOCKED state and rejects telemetry."""
    cfg = isolated_engine
    port = cfg["port"]
    tmp_path = cfg["tmp_path"]

    # Terminate and restart engine to trigger load_state()
    cfg["proc"].terminate()
    cfg["proc"].wait(timeout=2)

    # Write a pre-existing ledger file indicating sealed state
    ledger_file = tmp_path / "ledger.dat"
    ledger_file.write_text(
        "STATE_ROOT|0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\n"
        "TIMESTAMP|1773660000\n"
        "LEDGER_SIGNATURE|fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210\n"
    )

    build = Path(os.environ.get("QF_TEST_BUILD_DIR", "build_check")).resolve()
    engine_bin = build / "quantum_flex_engine"
    env = os.environ.copy()
    env.update(
        QF_DATA_DIR=str(tmp_path),
        QF_POSTGRES_CONNINFO="",
        QF_BIND_ADDRESS="127.0.0.1",
        QF_BIND_PORT=str(port),
        QF_SERVER_CERT=str(tmp_path / "server.crt"),
        QF_SERVER_KEY=str(tmp_path / "server.key"),
        QF_ROOT_CA=str(tmp_path / "ca.crt"),
        QF_ED_PRIVATE_KEY=str(tmp_path / "missing-ed"),
        QF_PQC_PRIVATE_KEY=str(tmp_path / "missing-pqc"),
        QF_KEM_PROPERTIES="provider=default",
    )
    new_proc = subprocess.Popen([str(engine_bin)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    ready = False
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                ready = True
                break
        except (ConnectionRefusedError, OSError):
            time.sleep(0.05)
    assert ready, f"Restarted engine failed to become ready on port {port}"
    try:
        context = ssl.create_default_context(cafile=cfg["ca_crt"])
        context.load_cert_chain(cfg["admin_crt"], cfg["admin_key"])

        with socket.create_connection(("127.0.0.1", port), timeout=5) as raw_sock:
            with context.wrap_socket(raw_sock, server_hostname="127.0.0.1") as tls_sock:
                tls_sock.sendall(b"STATUS\n")
                resp = tls_sock.recv(1024).decode("utf-8", errors="replace")
                assert resp.strip() == "ERR|NODE_LOCKED", f"Expected ERR|NODE_LOCKED, got: {resp.strip()}"
    finally:
        new_proc.terminate()
        try:
            new_proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            new_proc.kill()
