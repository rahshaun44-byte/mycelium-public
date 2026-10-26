# tests/test_mcp_server_wiring.py
"""
FastAPI HTTP/JSON-RPC Integration Tests for qflex-mcp.service (:9000).
Proves end-to-end wiring of MCPToolDispatcher, AgentCircuitBreaker, and PrivacyFilter.
"""

import asyncio
import pytest
from fastapi.testclient import TestClient

import mcp_layer.server as mcp_server
from mcp_layer.circuit_breaker import AgentCircuitBreaker, BreakerConfig
from mcp_layer.dispatcher import MCPToolDispatcher


@pytest.fixture(autouse=True)
def reset_mcp_breaker(monkeypatch, tmp_path):
    """Provides a clean circuit breaker and isolated ghost sink file per test."""
    sink_file = tmp_path / "ghost_sink.jsonl"
    monkeypatch.setenv("QF_GHOST_SINK_LOG", str(sink_file))

    fresh_breaker = AgentCircuitBreaker(
        config=BreakerConfig(
            failure_threshold=2,
            window_seconds=60.0,
            cooldown_seconds=30.0,
            max_identical_calls=3,
            identical_window_seconds=15.0,
            half_open_max_calls=1,
        ),
        ghost_sink_callback=mcp_server._forward_to_ghost_sink,
    )
    fresh_dispatcher = MCPToolDispatcher(breaker=fresh_breaker, default_timeout_sec=0.1)
    fresh_dispatcher.register_tool("system_status", mcp_server._tool_system_status)
    fresh_dispatcher.register_tool("ping", mcp_server._tool_ping)

    monkeypatch.setattr(mcp_server, "circuit_breaker", fresh_breaker)
    monkeypatch.setattr(mcp_server, "dispatcher", fresh_dispatcher)
    yield sink_file


def test_root_and_health_endpoints_return_http_200():
    """Preserves test_endpoints.py compatibility on port 9000."""
    client = TestClient(mcp_server.app)
    r_root = client.get("/")
    assert r_root.status_code == 200
    assert r_root.json()["circuit_breaker"] == "ARMED"

    r_health = client.get("/health")
    assert r_health.status_code == 200


def test_identical_agent_calls_return_http_429_and_write_ghost_sink(reset_mcp_breaker):
    """3 identical tool calls within window return HTTP 429 + Retry-After and log to Ghost Sink."""
    client = TestClient(mcp_server.app)
    payload = {"agent_id": "agent-spin", "tool_name": "ping", "arguments": {"echo": "loop"}}

    assert client.post("/mcp/v1/tools/call", json=payload).status_code == 200
    assert client.post("/mcp/v1/tools/call", json=payload).status_code == 200

    # 3rd identical call trips loop detector -> HTTP 429
    r_trip = client.post("/mcp/v1/tools/call", json=payload)
    assert r_trip.status_code == 429
    assert "Retry-After" in r_trip.headers
    body = r_trip.json()
    assert body["status"] == "BLOCKED_BY_CIRCUIT_BREAKER"
    assert body["reason"] == "IDENTICAL_CALL_LOOP_EXCEEDED"
    assert body["ghost_sink_receipt"]["sink_target"] == "ghost-node-sink-01"
    assert reset_mcp_breaker.exists()


def test_consecutive_tool_failures_return_http_503():
    """2 consecutive tool failures open the breaker; 3rd call returns HTTP 503 without running tool."""
    client = TestClient(mcp_server.app)
    invocations = {"count": 0}

    def failing_tool(step: int):
        invocations["count"] += 1
        raise RuntimeError("Downstream subsystem fault")

    mcp_server.dispatcher.register_tool("faulty_op", failing_tool)

    # 2 failing calls with distinct args
    for step in (1, 2):
        r = client.post(
            "/mcp/v1/tools/call",
            json={"agent_id": "agent-err", "tool_name": "faulty_op", "arguments": {"step": step}},
        )
        assert r.status_code == 500

    assert invocations["count"] == 2

    # 3rd call blocked at gate with HTTP 503
    r_blocked = client.post(
        "/mcp/v1/tools/call",
        json={"agent_id": "agent-err", "tool_name": "faulty_op", "arguments": {"step": 3}},
    )
    assert r_blocked.status_code == 503
    assert r_blocked.json()["breaker_state"] == "OPEN"
    assert invocations["count"] == 2  # Handler was not executed


def test_privacy_optout_in_mcp_arguments_fails_closed_http_403():
    """Any MCP tool argument containing _optout or _nomap is rejected with HTTP 403 before dispatch."""
    client = TestClient(mcp_server.app)
    r = client.post(
        "/mcp/v1/tools/call",
        json={
            "agent_id": "agent-sec",
            "tool_name": "ping",
            "arguments": {"echo": "HomeRouter_nomap"},
        },
    )
    assert r.status_code == 403


def test_jsonrpc_messages_endpoint_enforces_breaker_and_timeout():
    """JSON-RPC /messages endpoint enforces timeout (504) and subsequent circuit open (503)."""
    client = TestClient(mcp_server.app)

    async def slow_op(idx: int):
        await asyncio.sleep(1.0)
        return {"idx": idx}

    mcp_server.dispatcher.register_tool("slow_op", slow_op)

    for idx in (1, 2):
        r_timeout = client.post(
            "/messages",
            headers={"X-QF-Agent-ID": "rpc-agent"},
            json={
                "jsonrpc": "2.0",
                "id": idx,
                "method": "tools/call",
                "params": {"name": "slow_op", "arguments": {"idx": idx}},
            },
        )
        assert r_timeout.status_code == 504

    # Circuit is now OPEN after 2 timeouts -> 3rd JSON-RPC call gets 503
    r_open = client.post(
        "/messages",
        headers={"X-QF-Agent-ID": "rpc-agent"},
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "slow_op", "arguments": {"idx": 3}},
        },
    )
    assert r_open.status_code == 503
    assert r_open.json()["breaker_state"] == "OPEN"
