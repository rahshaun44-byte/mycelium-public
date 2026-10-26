# tests/test_mcp_circuit_breaker.py
"""
Unit & Integration Proof for QuantumFlex MCP AgentCircuitBreaker.
Verifies fail-closed thresholds, Ghost Sink routing, and HALF_OPEN probe recovery.
"""

import asyncio
import pytest

from mcp_layer.circuit_breaker import (
    AgentCircuitBreaker,
    BreakerConfig,
    BreakerState,
    CircuitBreakerOpenError,
)
from mcp_layer.dispatcher import MCPToolDispatcher


class FakeClock:
    def __init__(self, initial: float = 1000.0) -> None:
        self.current = initial

    def __call__(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


def test_config_validation_fails_closed():
    """Invalid thresholds or non-positive windows must raise ValueError immediately."""
    with pytest.raises(ValueError):
        BreakerConfig(failure_threshold=0)
    with pytest.raises(ValueError):
        BreakerConfig(cooldown_seconds=-5.0)
    with pytest.raises(ValueError):
        BreakerConfig(max_identical_calls=1)


def test_consecutive_failures_trip_breaker_and_sink_to_ghost_node():
    """3 failures within window_seconds must trip breaker to OPEN and block 4th call without invoking handler."""
    clock = FakeClock()
    sunk_events = []
    breaker = AgentCircuitBreaker(
        config=BreakerConfig(failure_threshold=3, window_seconds=60.0, cooldown_seconds=30.0, max_identical_calls=10),
        clock=clock,
        ghost_sink_callback=sunk_events.append,
    )
    dispatcher = MCPToolDispatcher(breaker=breaker)

    call_counter = {"count": 0}

    def flaky_db_query(query: str):
        call_counter["count"] += 1
        raise ConnectionError("PostgreSQL connection refused")

    dispatcher.register_tool("query_ledger", flaky_db_query)

    # 3 failing calls with distinct payloads
    for i in range(3):
        with pytest.raises(ConnectionError):
            dispatcher.dispatch_sync("agent-alpha", "query_ledger", {"query": f"SELECT {i}"})

    assert call_counter["count"] == 3
    status = breaker.get_status("agent-alpha", "query_ledger")
    assert status["state"] == BreakerState.OPEN.value

    # 4th call must fail closed BEFORE touching flaky_db_query
    with pytest.raises(CircuitBreakerOpenError) as exc_info:
        dispatcher.dispatch_sync("agent-alpha", "query_ledger", {"query": "SELECT 4"})

    assert call_counter["count"] == 3  # Handler was NOT called
    assert exc_info.value.sink_receipt["status"] == "SUNK_GHOST_NODE"
    assert exc_info.value.sink_receipt["sink_target"] == "ghost-node-sink-01"
    assert len(sunk_events) == 1


def test_half_open_single_probe_and_recovery_to_closed():
    """After cooldown_seconds (k), breaker transitions to HALF_OPEN, admits 1 probe, and resets to CLOSED on success."""
    clock = FakeClock()
    breaker = AgentCircuitBreaker(
        config=BreakerConfig(failure_threshold=2, cooldown_seconds=20.0, max_identical_calls=10),
        clock=clock,
    )
    dispatcher = MCPToolDispatcher(breaker=breaker)

    should_fail = {"flag": True}

    def toggle_tool(val: int):
        if should_fail["flag"]:
            raise RuntimeError("Downstream failure")
        return {"ok": val}

    dispatcher.register_tool("toggle_tool", toggle_tool)

    for i in range(2):
        with pytest.raises(RuntimeError):
            dispatcher.dispatch_sync("agent-1", "toggle_tool", {"val": i})

    assert breaker.get_status("agent-1", "toggle_tool")["state"] == BreakerState.OPEN.value

    # Advance clock past cooldown (20.0s)
    clock.advance(20.5)
    should_fail["flag"] = False

    res = dispatcher.dispatch_sync("agent-1", "toggle_tool", {"val": 99})
    assert res["status"] == "OK"
    assert breaker.get_status("agent-1", "toggle_tool")["state"] == BreakerState.CLOSED.value


def test_half_open_probe_failure_immediately_reopens_circuit():
    """If the single probe in HALF_OPEN fails, the circuit immediately snaps back to OPEN for a full cooldown."""
    clock = FakeClock()
    breaker = AgentCircuitBreaker(
        config=BreakerConfig(failure_threshold=2, cooldown_seconds=15.0, max_identical_calls=10),
        clock=clock,
    )
    dispatcher = MCPToolDispatcher(breaker=breaker)

    def broken_tool(x: int):
        raise ValueError("Still broken")

    dispatcher.register_tool("broken_tool", broken_tool)

    for i in range(2):
        with pytest.raises(ValueError):
            dispatcher.dispatch_sync("agent-1", "broken_tool", {"x": i})

    clock.advance(16.0)  # Enter HALF_OPEN window

    # Probe fails
    with pytest.raises(ValueError):
        dispatcher.dispatch_sync("agent-1", "broken_tool", {"x": 99})

    status = breaker.get_status("agent-1", "broken_tool")
    assert status["state"] == BreakerState.OPEN.value
    assert "HALF_OPEN_PROBE_FAILED" in status["last_trip_reason"]


def test_half_open_blocks_concurrent_second_probe():
    """While 1 probe is in-flight in HALF_OPEN, a second concurrent call must fail closed."""
    clock = FakeClock()
    breaker = AgentCircuitBreaker(
        config=BreakerConfig(failure_threshold=1, cooldown_seconds=10.0, half_open_max_calls=1),
        clock=clock,
    )

    key = breaker.before_call("agent-x", "tool-y", {"a": 1})
    breaker.record_failure(key, "INITIAL_FAIL")
    assert breaker.get_status("agent-x", "tool-y")["state"] == BreakerState.OPEN.value

    clock.advance(11.0)
    # First probe admitted -> transitions to HALF_OPEN with 1 in-flight call
    probe_key = breaker.before_call("agent-x", "tool-y", {"a": 2})
    assert probe_key == key

    # Second concurrent call before record_success must fail closed
    with pytest.raises(CircuitBreakerOpenError) as exc_info:
        breaker.before_call("agent-x", "tool-y", {"a": 3})
    assert exc_info.value.reason == "HALF_OPEN_PROBE_SATURATED"


def test_identical_payload_loop_detection_trips_even_on_success():
    """An agent repeating the exact same (tool, args) >= max_identical_calls within identical_window_seconds trips OPEN."""
    clock = FakeClock()
    breaker = AgentCircuitBreaker(
        config=BreakerConfig(failure_threshold=5, max_identical_calls=3, identical_window_seconds=15.0),
        clock=clock,
    )
    dispatcher = MCPToolDispatcher(breaker=breaker)
    dispatcher.register_tool("echo", lambda msg: {"echo": msg})

    # Calls 1 and 2 succeed
    assert dispatcher.dispatch_sync("looping-agent", "echo", {"msg": "ping"})["status"] == "OK"
    assert dispatcher.dispatch_sync("looping-agent", "echo", {"msg": "ping"})["status"] == "OK"

    # 3rd identical call within 15s trips loop detector BEFORE execution
    with pytest.raises(CircuitBreakerOpenError) as exc_info:
        dispatcher.dispatch_sync("looping-agent", "echo", {"msg": "ping"})

    assert exc_info.value.reason == "IDENTICAL_CALL_LOOP_EXCEEDED"
    assert breaker.get_status("looping-agent", "echo")["state"] == BreakerState.OPEN.value


def test_malformed_agent_or_tool_identifiers_fail_closed():
    """Empty or non-string agent_id / tool_name must fail closed via CircuitBreakerOpenError and log to Ghost Sink."""
    breaker = AgentCircuitBreaker()
    with pytest.raises(CircuitBreakerOpenError) as exc_info:
        breaker.before_call("", "valid_tool", {})
    assert exc_info.value.reason == "FAIL_CLOSED_INVALID_INPUT"
    assert len(breaker.ghost_ledger) == 1


def test_per_agent_and_per_tool_isolation():
    """Tripping agent-bad::tool-a must not block agent-good::tool-a or agent-bad::tool-b."""
    clock = FakeClock()
    breaker = AgentCircuitBreaker(config=BreakerConfig(failure_threshold=1), clock=clock)
    dispatcher = MCPToolDispatcher(breaker=breaker)

    dispatcher.register_tool("tool_a", lambda fail=False: (_ for _ in ()).throw(RuntimeError()) if fail else "ok")
    dispatcher.register_tool("tool_b", lambda: "ok_b")

    with pytest.raises(RuntimeError):
        dispatcher.dispatch_sync("agent-bad", "tool_a", {"fail": True})

    # agent-bad::tool_a is OPEN
    with pytest.raises(CircuitBreakerOpenError):
        dispatcher.dispatch_sync("agent-bad", "tool_a", {"fail": False})

    # agent-good::tool_a and agent-bad::tool_b remain CLOSED and operational
    assert dispatcher.dispatch_sync("agent-good", "tool_a", {"fail": False})["data"] == "ok"
    assert dispatcher.dispatch_sync("agent-bad", "tool_b", {})["data"] == "ok_b"


def test_async_dispatcher_timeout_trips_circuit_breaker():
    """Async tool exceeding timeout_sec must raise TimeoutError and increment circuit breaker failure count."""
    clock = FakeClock()
    breaker = AgentCircuitBreaker(config=BreakerConfig(failure_threshold=1), clock=clock)
    dispatcher = MCPToolDispatcher(breaker=breaker, default_timeout_sec=0.05)

    async def hung_tool():
        await asyncio.sleep(1.0)
        return "never_reached"

    dispatcher.register_tool("hung_tool", hung_tool)

    with pytest.raises(TimeoutError):
        asyncio.run(dispatcher.dispatch_async("agent-async", "hung_tool"))

    assert breaker.get_status("agent-async", "hung_tool")["state"] == BreakerState.OPEN.value
