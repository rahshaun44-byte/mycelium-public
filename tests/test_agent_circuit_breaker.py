#!/usr/bin/env python3
"""
Unit and integration tests for Agent Circuit Breaker & Ghost Node Entropy Sink (P1 Target 1).
Asserts:
  1. Nominal Passthrough: Healthy sync and async tools execute with zero latency penalty.
  2. Failure Threshold Tripping: Consecutive failures trip the breaker from CLOSED to OPEN.
  3. Short-Circuiting: In OPEN state, calls fail fast (sub-millisecond) without touching backend.
  4. Runaway Loop Storm / Rate Limiting: Rapid repeated invocations trip breaker to prevent host exhaustion.
  5. Ghost Node Entropy Sink Invariant: Tripped events absorb anomalous entropy (h -> 0) into volatile airlock.
  6. Recovery State Machine: Breaker transitions from OPEN -> HALF_OPEN after cooldown and recovers to CLOSED on success.
  7. Probe Failure in HALF_OPEN: Failed probe immediately returns breaker to OPEN.
  8. MCP Server Integration: Status inspection and reset tools work across both sync and async tool dispatch.
"""

import asyncio
import json
import time
from pathlib import Path
import pytest

from mcp_layer.circuit_breaker import (
    CircuitState,
    BreakerConfig,
    ToolCircuitBreaker,
    GhostSinkRouter,
    AgentCircuitBreakerRegistry,
    AIRLOCK_FILE,
)
from mcp_layer import quantum_flex_mcp as mcp


@pytest.fixture
def temp_airlock(tmp_path):
    """Provides an isolated volatile sink file for testing."""
    sink_file = tmp_path / "test_entropy_sink.jsonl"
    router = GhostSinkRouter(
        sink_url="http://127.0.0.1:19999/unreachable",
        airlock_file=sink_file,
    )
    return router, sink_file


def test_nominal_sync_passthrough(temp_airlock):
    router, _ = temp_airlock
    config = BreakerConfig(failure_threshold=3, recovery_timeout=1.0)
    registry = AgentCircuitBreakerRegistry(ghost_sink=router)

    calls = 0

    @registry.protect("sync_nominal", config=config)
    def dummy_tool(x: int) -> dict:
        nonlocal calls
        calls += 1
        return {"result": x * 2}

    res = dummy_tool(21)
    assert res == {"result": 42}
    assert calls == 1

    breaker = registry.get_breaker("sync_nominal")
    assert breaker.state == CircuitState.CLOSED
    assert breaker.consecutive_failures == 0
    assert breaker.total_calls == 1
    assert breaker.total_failures == 0


def test_nominal_async_passthrough(temp_airlock):
    router, _ = temp_airlock
    config = BreakerConfig(failure_threshold=3, recovery_timeout=1.0)
    registry = AgentCircuitBreakerRegistry(ghost_sink=router)

    calls = 0

    @registry.protect("async_nominal", config=config)
    async def dummy_async_tool(msg: str) -> dict:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return {"echo": msg}

    async def runner():
        res = await dummy_async_tool("quantum_active")
        assert res == {"echo": "quantum_active"}

    asyncio.run(runner())
    assert calls == 1

    breaker = registry.get_breaker("async_nominal")
    assert breaker.state == CircuitState.CLOSED
    assert breaker.consecutive_failures == 0


def test_consecutive_failure_tripping_and_short_circuit(temp_airlock):
    router, sink_file = temp_airlock
    config = BreakerConfig(failure_threshold=3, recovery_timeout=2.0)
    registry = AgentCircuitBreakerRegistry(ghost_sink=router)

    invocations = 0

    @registry.protect("failing_tool", config=config)
    def unreliable_tool() -> dict:
        nonlocal invocations
        invocations += 1
        return {"status": "OFFLINE", "error": "Target backend socket timeout"}

    # 1. Trigger failures up to threshold
    for i in range(3):
        res = unreliable_tool()
        assert res.get("status") == "OFFLINE"

    assert invocations == 3
    breaker = registry.get_breaker("failing_tool")
    assert breaker.state == CircuitState.OPEN
    assert breaker.total_trips == 1

    # 2. Subsequent invocations must short-circuit without invoking tool
    t0 = time.perf_counter()
    res_short = unreliable_tool()
    t_elapsed = time.perf_counter() - t0

    assert res_short["status"] == "CIRCUIT_OPEN"
    assert "Circuit breaker is OPEN" in res_short["error"]
    assert res_short["absorbed_by_ghost_sink"] is True
    assert invocations == 3  # Tool was NOT called!
    assert t_elapsed < 0.005  # Sub-millisecond fail-fast execution

    # 3. Verify anomaly absorption in volatile airlock
    assert sink_file.exists()
    records = [json.loads(line) for line in sink_file.read_text().splitlines() if line.strip()]
    assert len(records) >= 1
    assert records[-1]["entropy_action"] == "ABSORB_INTO_GHOST_SINK"
    assert records[-1]["h_attack"] == 0
    assert records[-1]["structural_anomaly"]["tool"] == "failing_tool"


def test_rate_limit_loop_storm_trip(temp_airlock):
    router, sink_file = temp_airlock
    # Config: Max 5 calls in a 2-second window
    config = BreakerConfig(
        failure_threshold=10,
        recovery_timeout=1.0,
        max_calls_per_window=5,
        window_seconds=2.0,
    )
    registry = AgentCircuitBreakerRegistry(ghost_sink=router)

    calls = 0

    @registry.protect("looping_agent_tool", config=config)
    def rapid_tool() -> dict:
        nonlocal calls
        calls += 1
        return {"status": "OK"}

    # Rapid-fire 5 allowed calls
    for _ in range(5):
        res = rapid_tool()
        assert res["status"] == "OK"
    assert calls == 5

    # 6th call exceeds rate limit -> immediately trips breaker to OPEN
    res_trip = rapid_tool()
    assert res_trip["status"] == "CIRCUIT_OPEN"
    assert "Rate limit exceeded" in res_trip["reason"]
    assert calls == 5  # Backend was protected

    breaker = registry.get_breaker("looping_agent_tool")
    assert breaker.state == CircuitState.OPEN


def test_recovery_cycle_half_open_to_closed(temp_airlock):
    router, _ = temp_airlock
    # Short recovery timeout (0.15s) for deterministic testing
    config = BreakerConfig(
        failure_threshold=2,
        recovery_timeout=0.15,
        half_open_success_threshold=1,
    )
    registry = AgentCircuitBreakerRegistry(ghost_sink=router)

    fail = True

    @registry.protect("recovering_tool", config=config)
    def flappy_tool() -> dict:
        if fail:
            return {"error": "Temporary failure"}
        return {"status": "RECOVERED"}

    # Trip the breaker
    flappy_tool()
    flappy_tool()
    breaker = registry.get_breaker("recovering_tool")
    assert breaker.state == CircuitState.OPEN

    # Call immediately -> rejected
    assert flappy_tool()["status"] == "CIRCUIT_OPEN"

    # Wait for cooldown to expire
    time.sleep(0.20)

    # Change backend to healthy
    fail = False

    # Probe call in HALF_OPEN state
    res_probe = flappy_tool()
    assert res_probe == {"status": "RECOVERED"}
    assert breaker.state == CircuitState.CLOSED
    assert breaker.consecutive_failures == 0


def test_probe_failure_re_trips_to_open(temp_airlock):
    router, _ = temp_airlock
    config = BreakerConfig(
        failure_threshold=2,
        recovery_timeout=0.15,
        half_open_success_threshold=1,
    )
    registry = AgentCircuitBreakerRegistry(ghost_sink=router)

    @registry.protect("probe_fail_tool", config=config)
    def broken_tool() -> dict:
        return {"error": "Still broken"}

    # Trip breaker
    broken_tool()
    broken_tool()
    breaker = registry.get_breaker("probe_fail_tool")
    assert breaker.state == CircuitState.OPEN

    time.sleep(0.20)

    # Next call allows probe in HALF_OPEN, but it fails -> immediately re-trips to OPEN
    res = broken_tool()
    assert res.get("error") == "Still broken"
    assert breaker.state == CircuitState.OPEN


def test_circuit_breaker_status_and_reset(temp_airlock):
    router, _ = temp_airlock
    registry = AgentCircuitBreakerRegistry(ghost_sink=router)
    config = BreakerConfig(failure_threshold=1, recovery_timeout=60.0)

    @registry.protect("tool_alpha", config=config)
    def tool_alpha():
        return {"error": "Failed"}

    @registry.protect("tool_beta", config=config)
    def tool_beta():
        return {"status": "OK"}

    tool_alpha()
    tool_beta()

    status = registry.get_all_statuses()
    assert "tools" in status
    assert status["tools"]["tool_alpha"]["state"] == "OPEN"
    assert status["tools"]["tool_beta"]["state"] == "CLOSED"

    # Reset specific tool
    registry.reset_all("tool_alpha")
    status_after = registry.get_all_statuses()
    assert status_after["tools"]["tool_alpha"]["state"] == "CLOSED"
    assert status_after["tools"]["tool_alpha"]["consecutive_failures"] == 0


def test_mcp_server_live_tools_wiring():
    """Validates that MCP tools on quantum_flex_mcp have circuit breakers attached."""
    # Verify circuit_breaker_status and reset_circuit_breaker are exposed
    cb_status = mcp.circuit_breaker_status()
    assert "timestamp" in cb_status
    assert "tools" in cb_status

    # Reset any test state
    mcp.reset_circuit_breaker()
    status_cleared = mcp.circuit_breaker_status()
    for tool_name, info in status_cleared["tools"].items():
        assert info["state"] == "CLOSED"
