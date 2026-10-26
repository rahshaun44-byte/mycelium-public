#!/usr/bin/env python3
"""
QuantumFlex MCP Layer — Deterministic Fail-Closed Agent Circuit Breaker.
Enforces Y = f(x - h) + k across autonomous agent tool invocations.
"""

from __future__ import annotations

import collections
import enum
import functools
import hashlib
import inspect
import json
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("qflex-mcp.circuit_breaker")


class BreakerState(str, enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


# Compatibility alias
CircuitState = BreakerState


class CircuitBreakerOpenError(PermissionError):
    """Raised when an MCP tool call is blocked by an OPEN or saturated HALF_OPEN breaker."""

    def __init__(
        self,
        key: str,
        state: BreakerState,
        reason: str,
        retry_after_sec: float,
        sink_receipt: Dict[str, Any],
    ):
        self.key = key
        self.state = state
        self.reason = reason
        self.retry_after_sec = round(max(0.0, retry_after_sec), 3)
        self.sink_receipt = sink_receipt
        super().__init__(
            f"[QF-CIRCUIT-BREAKER] Tool execution blocked for '{key}' "
            f"(state={state.value}, reason={reason}, retry_after={self.retry_after_sec}s)"
        )


@dataclass(frozen=True)
class BreakerConfig:
    failure_threshold: int = 3
    window_seconds: float = 60.0
    cooldown_seconds: float = 30.0
    max_identical_calls: int = 3
    identical_window_seconds: float = 15.0
    half_open_max_calls: int = 1
    recovery_timeout: Optional[float] = None
    max_calls_per_window: Optional[int] = None
    half_open_success_threshold: Optional[int] = None

    def __post_init__(self) -> None:
        if self.recovery_timeout is not None:
            object.__setattr__(self, "cooldown_seconds", float(self.recovery_timeout))
        if self.half_open_success_threshold is not None:
            object.__setattr__(self, "half_open_max_calls", int(self.half_open_success_threshold))

        if (
            not isinstance(self.failure_threshold, int)
            or isinstance(self.failure_threshold, bool)
            or self.failure_threshold < 1
        ):
            raise ValueError("failure_threshold must be an integer >= 1")
        if (
            self.window_seconds <= 0
            or self.cooldown_seconds <= 0
            or self.identical_window_seconds <= 0
        ):
            raise ValueError("Time windows and cooldown_seconds must be > 0")
        if (
            not isinstance(self.max_identical_calls, int)
            or isinstance(self.max_identical_calls, bool)
            or self.max_identical_calls < 2
        ):
            raise ValueError("max_identical_calls must be an integer >= 2")
        if (
            not isinstance(self.half_open_max_calls, int)
            or isinstance(self.half_open_max_calls, bool)
            or self.half_open_max_calls < 1
        ):
            raise ValueError("half_open_max_calls must be an integer >= 1")


@dataclass
class _KeyBucket:
    state: BreakerState = BreakerState.CLOSED
    failure_timestamps: Deque[float] = field(default_factory=deque)
    call_Loop_hashes: Deque[Tuple[float, str]] = field(default_factory=deque)
    opened_at: Optional[float] = None
    last_trip_reason: str = "NONE"
    half_open_in_flight: int = 0
    total_sunk_events: int = 0


class AgentCircuitBreaker:
    """
    Thread-safe, per-(agent_id, tool_name) circuit breaker with Ghost Sink telemetry emission.
    Uses monotonic clock exclusively to prevent wall-clock drift bypasses.
    """

    def __init__(
        self,
        config: Optional[BreakerConfig] = None,
        clock: Callable[[], float] = time.monotonic,
        ghost_sink_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> None:
        self.config = config or BreakerConfig()
        self._clock = clock
        self._ghost_sink_callback = ghost_sink_callback
        self._lock = threading.RLock()
        self._buckets: Dict[str, _KeyBucket] = {}
        self._ghost_ledger: List[Dict[str, Any]] = []

    @staticmethod
    def _make_key(agent_id: str, tool_name: str) -> str:
        if not agent_id or not isinstance(agent_id, str) or not agent_id.strip():
            raise ValueError("Invalid agent_id: fail-closed rejection on empty/non-string identifier")
        if not tool_name or not isinstance(tool_name, str) or not tool_name.strip():
            raise ValueError("Invalid tool_name: fail-closed rejection on empty/non-string identifier")
        return f"{agent_id.strip()}::{tool_name.strip()}"

    @staticmethod
    def _hash_payload(tool_name: str, arguments: Any) -> str:
        """Computes a canonical SHA-256 digest of the tool invocation arguments."""
        try:
            canonical = json.dumps(
                {"tool": tool_name, "args": arguments},
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
        except Exception:
            # Fail closed on unserializable structures by treating them as hostile entropy
            canonical = f"UNSERIALIZABLE::{tool_name}"
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _emit_to_ghost_sink(
        self, key: str, state: BreakerState, reason: str, payload_hash: str
    ) -> Dict[str, Any]:
        """Routes rejected/anomalous invocation metadata to the Ghost Node entropy sink."""
        receipt = {
            "status": "SUNK_GHOST_NODE",
            "sink_target": "ghost-node-sink-01",
            "breaker_key": key,
            "breaker_state": state.value,
            "reason": reason,
            "payload_sha256": payload_hash,
            "monotonic_ts": round(self._clock(), 6),
        }
        self._ghost_ledger.append(receipt)
        if self._ghost_sink_callback is not None:
            try:
                self._ghost_sink_callback(receipt)
            except Exception:
                # Sink callback exceptions must never open a bypass path
                pass
        return receipt

    def before_call(self, agent_id: str, tool_name: str, arguments: Any = None) -> str:
        """
        Pre-execution admission gate. Returns breaker key if admitted, or raises
        CircuitBreakerOpenError (fail-closed) if tripped or malformed.
        """
        try:
            key = self._make_key(agent_id, tool_name)
            payload_hash = self._hash_payload(tool_name, arguments)
            now = float(self._clock())
        except Exception as exc:
            receipt = self._emit_to_ghost_sink(
                "MALFORMED_KEY", BreakerState.OPEN, f"INVALID_INPUT:{exc}", "0" * 64
            )
            raise CircuitBreakerOpenError(
                key="MALFORMED_KEY",
                state=BreakerState.OPEN,
                reason="FAIL_CLOSED_INVALID_INPUT",
                retry_after_sec=self.config.cooldown_seconds,
                sink_receipt=receipt,
            ) from exc

        with self._lock:
            bucket = self._buckets.setdefault(key, _KeyBucket())

            # 1. Evaluate OPEN state & cooldown expiration (k)
            if bucket.state == BreakerState.OPEN:
                elapsed = now - (bucket.opened_at or now)
                if elapsed >= self.config.cooldown_seconds:
                    bucket.state = BreakerState.HALF_OPEN
                    bucket.half_open_in_flight = 0
                else:
                    bucket.total_sunk_events += 1
                    retry_after = self.config.cooldown_seconds - elapsed
                    receipt = self._emit_to_ghost_sink(
                        key, BreakerState.OPEN, bucket.last_trip_reason, payload_hash
                    )
                    raise CircuitBreakerOpenError(
                        key, BreakerState.OPEN, bucket.last_trip_reason, retry_after, receipt
                    )

            # 2. Evaluate HALF_OPEN probe concurrency limit
            if bucket.state == BreakerState.HALF_OPEN:
                if bucket.half_open_in_flight >= self.config.half_open_max_calls:
                    bucket.total_sunk_events += 1
                    receipt = self._emit_to_ghost_sink(
                        key, BreakerState.HALF_OPEN, "HALF_OPEN_PROBE_SATURATED", payload_hash
                    )
                    raise CircuitBreakerOpenError(
                        key,
                        BreakerState.HALF_OPEN,
                        "HALF_OPEN_PROBE_SATURATED",
                        self.config.cooldown_seconds,
                        receipt,
                    )
                bucket.half_open_in_flight += 1
                return key

            # 3. Evaluate CLOSED state: check for rapid identical tool-call loop (agent spin)
            cutoff_loop = now - self.config.identical_window_seconds
            while bucket.call_Loop_hashes and bucket.call_Loop_hashes[0][0] < cutoff_loop:
                bucket.call_Loop_hashes.popleft()

            bucket.call_Loop_hashes.append((now, payload_hash))
            identical_count = sum(1 for _, h in bucket.call_Loop_hashes if h == payload_hash)

            if identical_count >= self.config.max_identical_calls:
                self._trip_bucket(bucket, now, "IDENTICAL_CALL_LOOP_EXCEEDED")
                bucket.total_sunk_events += 1
                receipt = self._emit_to_ghost_sink(
                    key, BreakerState.OPEN, bucket.last_trip_reason, payload_hash
                )
                raise CircuitBreakerOpenError(
                    key,
                    BreakerState.OPEN,
                    bucket.last_trip_reason,
                    self.config.cooldown_seconds,
                    receipt,
                )

            return key

    def record_success(self, key: str) -> None:
        """Called when the downstream tool completes without error."""
        with self._lock:
            bucket = self._buckets.get(key)
            if not bucket:
                return
            if bucket.state == BreakerState.HALF_OPEN:
                # Probe succeeded -> restore baseline equilibrium (CLOSED)
                bucket.state = BreakerState.CLOSED
                bucket.failure_timestamps.clear()
                bucket.call_Loop_hashes.clear()
                bucket.opened_at = None
                bucket.half_open_in_flight = 0
                bucket.last_trip_reason = "NONE"

    def record_failure(self, key: str, reason: str = "TOOL_EXECUTION_ERROR") -> None:
        """Called when the downstream tool raises an exception, times out, or returns an error code."""
        now = float(self._clock())
        with self._lock:
            bucket = self._buckets.setdefault(key, _KeyBucket())

            if bucket.state == BreakerState.HALF_OPEN:
                # Probe failed -> immediately re-open for a full cooldown cycle
                self._trip_bucket(bucket, now, f"HALF_OPEN_PROBE_FAILED:{reason}")
                return

            cutoff = now - self.config.window_seconds
            while bucket.failure_timestamps and bucket.failure_timestamps[0] < cutoff:
                bucket.failure_timestamps.popleft()

            bucket.failure_timestamps.append(now)
            if len(bucket.failure_timestamps) >= self.config.failure_threshold:
                self._trip_bucket(bucket, now, reason)

    def _trip_bucket(self, bucket: _KeyBucket, now: float, reason: str) -> None:
        bucket.state = BreakerState.OPEN
        bucket.opened_at = now
        bucket.half_open_in_flight = 0
        bucket.last_trip_reason = reason

    def get_status(self, agent_id: str, tool_name: str) -> Dict[str, Any]:
        """Returns current telemetry snapshot for a specific (agent_id, tool_name) pair."""
        key = self._make_key(agent_id, tool_name)
        with self._lock:
            bucket = self._buckets.get(key)
            if not bucket:
                return {
                    "key": key,
                    "state": BreakerState.CLOSED.value,
                    "failures_in_window": 0,
                    "total_sunk_events": 0,
                    "last_trip_reason": "NONE",
                }
            return {
                "key": key,
                "state": bucket.state.value,
                "failures_in_window": len(bucket.failure_timestamps),
                "total_sunk_events": bucket.total_sunk_events,
                "last_trip_reason": bucket.last_trip_reason,
            }

    def reset(self, agent_id: Optional[str] = None, tool_name: Optional[str] = None) -> None:
        """Resets specified or all bucket states to CLOSED."""
        with self._lock:
            if agent_id and tool_name:
                key = self._make_key(agent_id, tool_name)
                if key in self._buckets:
                    b = self._buckets[key]
                    b.state = BreakerState.CLOSED
                    b.failure_timestamps.clear()
                    b.call_Loop_hashes.clear()
                    b.opened_at = None
                    b.half_open_in_flight = 0
                    b.last_trip_reason = "NONE"
            else:
                for b in self._buckets.values():
                    b.state = BreakerState.CLOSED
                    b.failure_timestamps.clear()
                    b.call_Loop_hashes.clear()
                    b.opened_at = None
                    b.half_open_in_flight = 0
                    b.last_trip_reason = "NONE"

    @property
    def ghost_ledger(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._ghost_ledger)


# ── Global Adapter for quantum_flex_mcp Server Tools ─────────────────────────
AIRLOCK_FILE = Path("/dev/shm/qflex_airlock/mcp_circuit_breaker_sink.jsonl")


class GhostSinkRouter:
    """Fallback router to volatile RAM tmpfs and ghost-node-sink-01."""

    def __init__(
        self,
        sink_url: str = "http://127.0.0.1:19443/v1/sink/anomaly",
        airlock_file: Path = AIRLOCK_FILE,
    ):
        self.sink_url = sink_url
        self.airlock_file = airlock_file
        self.recent_absorptions: Deque[Dict[str, Any]] = deque(maxlen=50)

    def absorb_anomaly(
        self,
        event_type: str,
        tool_name: str,
        reason: str,
        caller_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        record = {
            "status": "SUNK_GHOST_NODE",
            "sink_target": "ghost-node-sink-01",
            "entropy_action": "ABSORB_INTO_GHOST_SINK",
            "event": event_type,
            "tool": tool_name,
            "reason": reason,
            "h_attack": 0,
            "timestamp": time.time(),
            "structural_anomaly": {
                "event": event_type,
                "tool": tool_name,
                "reason": reason,
                "metadata": caller_metadata or {},
            },
            "metadata": caller_metadata or {},
        }
        self.recent_absorptions.append(record)
        try:
            self.airlock_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with open(self.airlock_file, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        except Exception as e:
            logger.warning(f"Failed writing anomaly to airlock: {e}")
        return record


class ToolCircuitBreaker:
    """Per-tool circuit breaker instance used by AgentCircuitBreakerRegistry."""

    def __init__(
        self,
        tool_name: str,
        config: Optional[BreakerConfig] = None,
        ghost_sink: Optional[GhostSinkRouter] = None,
    ):
        self.tool_name = tool_name
        self.config = config or BreakerConfig()
        self.ghost_sink = ghost_sink or GhostSinkRouter()
        self.state: CircuitState = CircuitState.CLOSED
        self.consecutive_failures: int = 0
        self.total_calls: int = 0
        self.total_failures: int = 0
        self.total_trips: int = 0
        self.opened_at: Optional[float] = None
        self._lock = threading.RLock()
        self._call_timestamps: Deque[float] = deque()
        self._half_open_successes: int = 0

    def before_call(self) -> None:
        now = time.monotonic()
        with self._lock:
            # Check rate limiting if max_calls_per_window is configured
            if self.config.max_calls_per_window is not None:
                cutoff = now - self.config.window_seconds
                while self._call_timestamps and self._call_timestamps[0] < cutoff:
                    self._call_timestamps.popleft()
                if len(self._call_timestamps) >= self.config.max_calls_per_window:
                    self.trip("Rate limit exceeded")
                    receipt = self.ghost_sink.absorb_anomaly(
                        "RATE_LIMIT_TRIPPED", self.tool_name, "Rate limit exceeded"
                    )
                    raise CircuitBreakerOpenError(
                        key=self.tool_name,
                        state=BreakerState.OPEN,
                        reason="Rate limit exceeded",
                        retry_after_sec=self.config.cooldown_seconds,
                        sink_receipt=receipt,
                    )
                self._call_timestamps.append(now)

            if self.state == CircuitState.OPEN:
                elapsed = now - (self.opened_at or now)
                if elapsed >= self.config.cooldown_seconds:
                    self.state = CircuitState.HALF_OPEN
                    self._half_open_successes = 0
                else:
                    retry_after = self.config.cooldown_seconds - elapsed
                    receipt = self.ghost_sink.absorb_anomaly(
                        "CIRCUIT_BREAKER_TRIPPED", self.tool_name, "Circuit breaker is OPEN"
                    )
                    raise CircuitBreakerOpenError(
                        key=self.tool_name,
                        state=BreakerState.OPEN,
                        reason="Circuit breaker is OPEN",
                        retry_after_sec=retry_after,
                        sink_receipt=receipt,
                    )

            self.total_calls += 1

    def record_success(self) -> None:
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.config.half_open_max_calls:
                    self.reset()
            else:
                self.consecutive_failures = 0

    def record_failure(self, reason: str = "ERROR") -> None:
        with self._lock:
            self.total_failures += 1
            self.consecutive_failures += 1
            if self.state == CircuitState.HALF_OPEN:
                self.trip(f"Probe failure in HALF_OPEN: {reason}")
            elif self.consecutive_failures >= self.config.failure_threshold:
                self.trip(f"Consecutive failures exceeded ({self.consecutive_failures}): {reason}")

    def trip(self, reason: str) -> None:
        self.state = CircuitState.OPEN
        self.opened_at = time.monotonic()
        self.total_trips += 1

    def reset(self) -> None:
        with self._lock:
            self.state = CircuitState.CLOSED
            self.consecutive_failures = 0
            self.opened_at = None
            self._half_open_successes = 0


class AgentCircuitBreakerRegistry:
    """Registry providing per-tool wrapping for MCP server decorators."""

    def __init__(self, ghost_sink: Optional[GhostSinkRouter] = None):
        self.ghost_sink = ghost_sink or GhostSinkRouter()
        self._breakers: Dict[str, ToolCircuitBreaker] = {}
        self._lock = threading.RLock()

    def get_breaker(self, tool_name: str, config: Optional[BreakerConfig] = None) -> ToolCircuitBreaker:
        with self._lock:
            if tool_name not in self._breakers:
                self._breakers[tool_name] = ToolCircuitBreaker(
                    tool_name=tool_name,
                    config=config or BreakerConfig(),
                    ghost_sink=self.ghost_sink,
                )
            return self._breakers[tool_name]

    def protect(self, tool_name: str, config: Optional[BreakerConfig] = None):
        breaker = self.get_breaker(tool_name, config)

        def decorator(fn: Callable):
            if inspect.iscoroutinefunction(fn):

                @functools.wraps(fn)
                async def async_wrapper(*args, **kwargs):
                    try:
                        breaker.before_call()
                    except CircuitBreakerOpenError as exc:
                        return {
                            "status": "CIRCUIT_OPEN",
                            "error": str(exc),
                            "tool": tool_name,
                            "reason": exc.reason,
                            "retry_after_sec": exc.retry_after_sec,
                            "absorbed_by_ghost_sink": True,
                        }

                    try:
                        res = await fn(*args, **kwargs)
                        if isinstance(res, dict) and (res.get("error") or res.get("status") in ("OFFLINE", "ERROR")):
                            breaker.record_failure(str(res.get("error") or res.get("status")))
                        else:
                            breaker.record_success()
                        return res
                    except Exception as e:
                        breaker.record_failure(str(e))
                        raise

                return async_wrapper
            else:

                @functools.wraps(fn)
                def sync_wrapper(*args, **kwargs):
                    try:
                        breaker.before_call()
                    except CircuitBreakerOpenError as exc:
                        return {
                            "status": "CIRCUIT_OPEN",
                            "error": str(exc),
                            "tool": tool_name,
                            "reason": exc.reason,
                            "retry_after_sec": exc.retry_after_sec,
                            "absorbed_by_ghost_sink": True,
                        }

                    try:
                        res = fn(*args, **kwargs)
                        if isinstance(res, dict) and (res.get("error") or res.get("status") in ("OFFLINE", "ERROR")):
                            breaker.record_failure(str(res.get("error") or res.get("status")))
                        else:
                            breaker.record_success()
                        return res
                    except Exception as e:
                        breaker.record_failure(str(e))
                        raise

                return sync_wrapper

        return decorator

    def get_all_statuses(self) -> Dict[str, Any]:
        with self._lock:
            tools_info = {}
            for name, b in self._breakers.items():
                tools_info[name] = {
                    "state": b.state.value,
                    "consecutive_failures": b.consecutive_failures,
                    "total_calls": b.total_calls,
                    "total_failures": b.total_failures,
                    "total_trips": b.total_trips,
                }
            return {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "tools": tools_info,
                "ghost_ledger_count": len(self.ghost_sink.recent_absorptions),
                "recent_absorptions": list(self.ghost_sink.recent_absorptions)[-10:],
            }

    def reset_all(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            if tool_name:
                if tool_name in self._breakers:
                    self._breakers[tool_name].reset()
            else:
                for b in self._breakers.values():
                    b.reset()
            return {"status": "SUCCESS", "message": "All circuit breakers reset to nominal CLOSED state"}


circuit_registry = AgentCircuitBreakerRegistry()
