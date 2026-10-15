"""Exercise the MCP runner's actual SDK Host/Origin checks without opening sockets."""

import asyncio
import json
import subprocess

import httpx
import pytest

from mcp_layer import quantum_flex_mcp as mcp


DNS_NAME = "quant-yoga-7-2-in-1-14akp10.example-tailnet.ts.net"
LOCAL_STATUS = {
    "BackendState": "Running",
    "MagicDNSSuffix": "example-tailnet.ts.net",
    "Self": {
        "HostName": "quant-yoga-7-2-in-1-14akp10",
        "DNSName": DNS_NAME + ".",
        "TailscaleIPs": ["100.64.1.31", "fd7a:115c:a1e0::4e2e:37c"],
    },
    "Peer": {
        "other": {
            "DNSName": "other.example-tailnet.ts.net.",
            "TailscaleIPs": ["100.64.1.32"],
        },
    },
}


async def _runner_app(monkeypatch, status=LOCAL_STATUS):
    def local_status(*args, **kwargs):
        if isinstance(status, Exception):
            raise status
        output = status if isinstance(status, str) else json.dumps(status)
        return subprocess.CompletedProcess(args[0], 0, stdout=output, stderr="")

    app = None

    async def build_app(*, host, port, **options):
        nonlocal app
        app = mcp.server.sse_app(host=host, **options)

    monkeypatch.setattr(mcp, "MCP_HOST", "127.0.0.1")
    monkeypatch.setattr(mcp, "MCP_PORT", 9000)
    monkeypatch.setattr(mcp.subprocess, "run", local_status)
    monkeypatch.setattr(mcp.server, "run_sse_async", build_app)
    await mcp.main()
    return app


async def _post_message(app, authority, origin=None):
    headers = {"Host": authority}
    if origin is not None:
        headers["Origin"] = origin
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:9000"
    ) as client:
        # An absent session returns 400 only after the SDK accepts Host and Origin.
        return await client.post("/messages/", headers=headers, json={})


@pytest.mark.parametrize(
    "authority,origin",
    [
        ("127.0.0.1:9000", "http://127.0.0.1:9000"),
        ("localhost:9000", "http://localhost:9000"),
        ("[::1]:9000", "http://[::1]:9000"),
        ("100.64.1.31:9000", "http://100.64.1.31:9000"),
        ("[fd7a:115c:a1e0::4e2e:37c]:9000", "http://[fd7a:115c:a1e0::4e2e:37c]:9000"),
        (DNS_NAME, "https://" + DNS_NAME),
        (DNS_NAME + ":443", "https://" + DNS_NAME + ":443"),
        (DNS_NAME + ":9000", "http://" + DNS_NAME + ":9000"),
    ],
)
def test_local_node_hosts_and_origins_reach_sse_transport(monkeypatch, authority, origin):
    async def exercise():
        app = await _runner_app(monkeypatch)
        response = await _post_message(app, authority, origin)
        assert response.status_code == 400
        assert response.text == "session_id is required"

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "authority,origin,status",
    [
        ("attacker.example:9000", None, 421),
        ("100.64.1.32:9000", None, 421),
        ("100.64.1.31:8080", None, 421),
        (DNS_NAME + ".attacker.example", None, 421),
        (DNS_NAME, "https://attacker.example", 403),
        (DNS_NAME, "https://other.example-tailnet.ts.net", 403),
    ],
)
def test_unrelated_hosts_ports_and_origins_remain_rejected(monkeypatch, authority, origin, status):
    async def exercise():
        app = await _runner_app(monkeypatch)
        response = await _post_message(app, authority, origin)
        assert response.status_code == status

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "status",
    [
        FileNotFoundError("tailscale unavailable"),
        subprocess.TimeoutExpired(["tailscale", "status", "--json"], 5),
        "invalid JSON",
        {"Self": []},
        {"Self": {"TailscaleIPs": "100.64.1.31", "DNSName": "*.ts.net"}},
    ],
)
def test_unavailable_or_malformed_identity_keeps_loopback_protection(monkeypatch, status):
    async def exercise():
        app = await _runner_app(monkeypatch, status)
        assert (await _post_message(app, "127.0.0.1:9000")).status_code == 400
        assert (await _post_message(app, "100.64.1.31:9000")).status_code == 421
        assert (await _post_message(app, DNS_NAME)).status_code == 421

    asyncio.run(exercise())


@pytest.mark.parametrize("ip", ["192.168.100.11", "8.8.8.8", "::1", "2001:db8::1", "100.64.1.31:*"])
def test_identity_does_not_allow_non_tailnet_ips_or_patterns(monkeypatch, ip):
    async def exercise():
        app = await _runner_app(monkeypatch, {"Self": {"TailscaleIPs": [ip]}})
        authority = "[2001:db8::1]:9000" if ip == "2001:db8::1" else ip + ":9000"
        assert (await _post_message(app, authority)).status_code == 421

    asyncio.run(exercise())
