# mcp_layer/dispatcher.py
"""
QuantumFlex MCP Tool Dispatcher with wired AgentCircuitBreaker enforcement.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable, Dict, Optional

from mcp_layer.circuit_breaker import (
    AgentCircuitBreaker,
    BreakerConfig,
    CircuitBreakerOpenError,
)


class MCPToolDispatcher:
    """
    Dispatches MCP tool invocations through a fail-closed AgentCircuitBreaker gate.
    """

    def __init__(
        self,
        breaker: Optional[AgentCircuitBreaker] = None,
        default_timeout_sec: float = 10.0,
    ) -> None:
        self.breaker = breaker or AgentCircuitBreaker(BreakerConfig())
        self.default_timeout_sec = default_timeout_sec
        self._registry: Dict[str, Callable[..., Any]] = {}

    def register_tool(self, tool_name: str, handler: Callable[..., Any]) -> None:
        if not tool_name or not isinstance(tool_name, str) or not callable(handler):
            raise ValueError("Tool registration requires non-empty tool_name and callable handler")
        self._registry[tool_name.strip()] = handler

    def dispatch_sync(
        self,
        agent_id: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Synchronous MCP dispatch path. Fails closed if tool is unregistered,
        breaker is OPEN/HALF_OPEN-saturated, or tool execution raises.
        """
        args = arguments if arguments is not None else {}

        # 1. Fail-closed admission check (raises CircuitBreakerOpenError if tripped)
        key = self.breaker.before_call(agent_id, tool_name, args)

        # 2. Verify tool registration
        handler = self._registry.get(tool_name.strip())
        if handler is None:
            self.breaker.record_failure(key, reason="UNREGISTERED_MCP_TOOL")
            raise KeyError(f"Unregistered MCP tool: '{tool_name}'")

        # 3. Execute handler under breaker failure tracking
        try:
            result = handler(**args)
            if isinstance(result, dict) and result.get("error") is True:
                self.breaker.record_failure(key, reason="TOOL_RETURNED_ERROR_FLAG")
                raise RuntimeError(f"Tool '{tool_name}' returned explicit error payload")
            self.breaker.record_success(key)
            return {
                "status": "OK",
                "agent_id": agent_id,
                "tool": tool_name,
                "data": result,
            }
        except Exception as exc:
            # Ensure failure is recorded if not already recorded above
            if "explicit error payload" not in str(exc):
                self.breaker.record_failure(key, reason=type(exc).__name__)
            raise

    async def dispatch_async(
        self,
        agent_id: str,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        timeout_sec: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Asynchronous MCP dispatch path with strict asyncio.wait_for timeout enforcement.
        """
        args = arguments if arguments is not None else {}
        timeout = timeout_sec if timeout_sec is not None else self.default_timeout_sec

        # 1. Fail-closed admission check
        key = self.breaker.before_call(agent_id, tool_name, args)

        # 2. Verify tool registration
        handler = self._registry.get(tool_name.strip())
        if handler is None:
            self.breaker.record_failure(key, reason="UNREGISTERED_MCP_TOOL")
            raise KeyError(f"Unregistered MCP tool: '{tool_name}'")

        # 3. Execute with timeout guard
        try:
            if inspect.iscoroutinefunction(handler):
                result = await asyncio.wait_for(handler(**args), timeout=timeout)
            else:
                result = handler(**args)

            if isinstance(result, dict) and result.get("error") is True:
                self.breaker.record_failure(key, reason="TOOL_RETURNED_ERROR_FLAG")
                raise RuntimeError(f"Tool '{tool_name}' returned explicit error payload")

            self.breaker.record_success(key)
            return {
                "status": "OK",
                "agent_id": agent_id,
                "tool": tool_name,
                "data": result,
            }
        except asyncio.TimeoutError as exc:
            self.breaker.record_failure(key, reason="MCP_TOOL_TIMEOUT")
            raise TimeoutError(f"MCP tool '{tool_name}' timed out after {timeout}s") from exc
        except Exception as exc:
            if "explicit error payload" not in str(exc):
                self.breaker.record_failure(key, reason=type(exc).__name__)
            raise
