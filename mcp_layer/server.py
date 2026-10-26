# mcp_layer/server.py
"""
QuantumFlex MCP Server (qflex-mcp.service on :9000).
Wires MCPToolDispatcher + AgentCircuitBreaker + PrivacyFilter into FastAPI/SSE endpoints.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from mcp_layer.circuit_breaker import (
    AgentCircuitBreaker,
    BreakerConfig,
    CircuitBreakerOpenError,
)
from mcp_layer.dispatcher import MCPToolDispatcher
from src.privacy_filter import PrivacyFilter

logger = logging.getLogger("qflex-mcp")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")


def _forward_to_ghost_sink(receipt: Dict[str, Any]) -> None:
    """
    Appends tripped circuit breaker telemetry to the local Ghost Node entropy sink JSONL ledger.
    Fails safe without opening an execution bypass.
    """
    sink_path = os.environ.get("QF_GHOST_SINK_LOG", "/tmp/qf_ghost_sink_mcp.jsonl")
    try:
        with open(sink_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(receipt, sort_keys=True) + "\n")
            fh.flush()
    except Exception as exc:
        logger.warning("Ghost sink file write warning: %s", exc)


# 1. Initialize deterministic fail-closed Circuit Breaker & Dispatcher
BREAKER_CONFIG = BreakerConfig(
    failure_threshold=int(os.environ.get("QF_MCP_FAILURE_THRESHOLD", "3")),
    window_seconds=float(os.environ.get("QF_MCP_WINDOW_SEC", "60.0")),
    cooldown_seconds=float(os.environ.get("QF_MCP_COOLDOWN_SEC", "30.0")),
    max_identical_calls=int(os.environ.get("QF_MCP_MAX_IDENTICAL", "3")),
    identical_window_seconds=float(os.environ.get("QF_MCP_IDENTICAL_WINDOW_SEC", "15.0")),
    half_open_max_calls=1,
)

circuit_breaker = AgentCircuitBreaker(
    config=BREAKER_CONFIG,
    ghost_sink_callback=_forward_to_ghost_sink,
)
dispatcher = MCPToolDispatcher(
    breaker=circuit_breaker,
    default_timeout_sec=float(os.environ.get("QF_MCP_TIMEOUT_SEC", "10.0")),
)

app = FastAPI(
    title="QuantumFlex MCP Server",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)


# 2. Register baseline verified MCP tools
async def _tool_system_status() -> Dict[str, Any]:
    """Read-only status probe for MCP agents."""
    return {
        "engine_port": 9444,
        "mcp_port": 9000,
        "posture": "ACTIVE_PLUTON_TPM2",
        "breaker_sunk_events": len(circuit_breaker.ghost_ledger),
    }


def _tool_ping(echo: str = "pong") -> Dict[str, Any]:
    """Deterministic liveness echo."""
    if PrivacyFilter.contains_optout(echo):
        raise PermissionError("Privacy opt-out marker rejected inside tool execution")
    return {"reply": echo}


dispatcher.register_tool("system_status", _tool_system_status)
dispatcher.register_tool("ping", _tool_ping)


# 3. Request Schemas
class MCPToolCallRequest(BaseModel):
    agent_id: str = Field(..., description="Unique calling agent identifier")
    tool_name: str = Field(..., description="Registered MCP tool name")
    arguments: Dict[str, Any] = Field(default_factory=dict)
    timeout_sec: Optional[float] = Field(default=None, gt=0.0, le=60.0)


# 4. Deterministic Exception Handler for CircuitBreakerOpenError
@app.exception_handler(CircuitBreakerOpenError)
async def circuit_breaker_exception_handler(request: Request, exc: CircuitBreakerOpenError) -> JSONResponse:
    """
    Maps CircuitBreakerOpenError to deterministic HTTP status codes:
    - 400 Bad Request: Malformed/empty agent_id or tool_name (FAIL_CLOSED_INVALID_INPUT)
    - 429 Too Many Requests: Identical payload loop tripped (IDENTICAL_CALL_LOOP_EXCEEDED)
    - 503 Service Unavailable: Consecutive failure threshold or HALF_OPEN saturation
    """
    if exc.reason == "FAIL_CLOSED_INVALID_INPUT":
        status_code = 400
    elif exc.reason == "IDENTICAL_CALL_LOOP_EXCEEDED":
        status_code = 429
    else:
        status_code = 503

    retry_after_int = max(1, int(round(exc.retry_after_sec)))
    return JSONResponse(
        status_code=status_code,
        headers={"Retry-After": str(retry_after_int)},
        content={
            "status": "BLOCKED_BY_CIRCUIT_BREAKER",
            "key": exc.key,
            "breaker_state": exc.state.value,
            "reason": exc.reason,
            "retry_after_sec": exc.retry_after_sec,
            "ghost_sink_receipt": exc.sink_receipt,
        },
    )


# 5. Endpoints (Preserving test_endpoints.py HTTP 200 compatibility on / and /sse)
@app.get("/")
@app.get("/health")
async def health_check() -> Dict[str, Any]:
    return {
        "status": "ONLINE",
        "service": "qflex-mcp.service",
        "port": 9000,
        "circuit_breaker": "ARMED",
        "total_ghost_sunk_events": len(circuit_breaker.ghost_ledger),
    }


@app.get("/sse")
async def mcp_sse_stream(request: Request) -> StreamingResponse:
    """SSE transport endpoint for Model Context Protocol clients."""
    async def event_generator():
        yield f"event: endpoint\ndata: /messages\n\n"
        while not await request.is_disconnected():
            heartbeat = json.dumps({
                "ts": int(time.time()),
                "status": "ARMED",
                "sunk": len(circuit_breaker.ghost_ledger),
            })
            yield f"event: heartbeat\ndata: {heartbeat}\n\n"
            await asyncio.sleep(15.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/mcp/v1/tools/call")
async def call_mcp_tool(payload: MCPToolCallRequest) -> JSONResponse:
    """
    Primary REST tool invocation endpoint gated by PrivacyFilter and AgentCircuitBreaker.
    """
    # 1. Edge Privacy Filter check before dispatcher execution
    if PrivacyFilter.contains_optout(payload.arguments) or PrivacyFilter.contains_optout(payload.agent_id):
        raise HTTPException(status_code=403, detail="Forbidden: Privacy opt-out marker detected in MCP tool call")

    # 2. Dispatch through fail-closed AgentCircuitBreaker
    try:
        result = await dispatcher.dispatch_async(
            agent_id=payload.agent_id,
            tool_name=payload.tool_name,
            arguments=payload.arguments,
            timeout_sec=payload.timeout_sec,
        )
        return JSONResponse(status_code=200, content=result)
    except CircuitBreakerOpenError:
        # Handled by circuit_breaker_exception_handler
        raise
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {exc}") from exc


@app.post("/messages")
async def mcp_jsonrpc_messages(
    request: Request,
    x_qf_agent_id: Optional[str] = Header(default=None, alias="X-QF-Agent-ID"),
) -> JSONResponse:
    """
    JSON-RPC 2.0 MCP message ingress (`tools/call`) wired to the same circuit breaker gate.
    """
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Malformed JSON-RPC body") from exc

    if PrivacyFilter.contains_optout(body):
        raise HTTPException(status_code=403, detail="Forbidden: Privacy opt-out marker detected in JSON-RPC body")

    rpc_id = body.get("id")
    method = body.get("method", "")
    params = body.get("params") if isinstance(body.get("params"), dict) else {}

    if method != "tools/call":
        return JSONResponse(
            status_code=200,
            content={"jsonrpc": "2.0", "id": rpc_id, "result": {"ack": method}},
        )

    agent_id = x_qf_agent_id or params.get("agent_id") or ""
    tool_name = params.get("name") or ""
    arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}

    try:
        result = await dispatcher.dispatch_async(
            agent_id=agent_id,
            tool_name=tool_name,
            arguments=arguments,
        )
        return JSONResponse(
            status_code=200,
            content={"jsonrpc": "2.0", "id": rpc_id, "result": result},
        )
    except CircuitBreakerOpenError:
        raise
    except KeyError as exc:
        return JSONResponse(
            status_code=404,
            content={"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32601, "message": str(exc)}},
        )
    except TimeoutError as exc:
        return JSONResponse(
            status_code=504,
            content={"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32000, "message": str(exc)}},
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32603, "message": str(exc)}},
        )


@app.get("/mcp/v1/breaker/status/{agent_id}/{tool_name}")
async def breaker_status(agent_id: str, tool_name: str) -> Dict[str, Any]:
    """Inspect live circuit breaker state for a specific (agent_id, tool_name) bucket."""
    return circuit_breaker.get_status(agent_id, tool_name)
