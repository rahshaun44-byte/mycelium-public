"""Exercise the mesh publisher without changing the host's Tailscale state."""

import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/enable_quantumflex_mesh.sh"
DNS_NAME = "mesh-test.example.ts.net"
ACTIVE_BANNER = "QUANTUMFLEX MESH INGRESS ACTIVE"

# The external CLI persists ServeConfig as documented by Tailscale v1.104.1:
# https://github.com/tailscale/tailscale/blob/v1.104.1/ipn/serve.go
PRIVATE_CONFIG = {
    "TCP": {
        "443": {"HTTPS": True},
        "8000": {"TCPForward": "127.0.0.1:8000"},
        "8080": {"TCPForward": "127.0.0.1:8080"},
        "9000": {"TCPForward": "127.0.0.1:9000"},
    },
    "Web": {
        f"{DNS_NAME}:443": {
            "Handlers": {"/": {"Proxy": "http://127.0.0.1:9000"}}
        }
    },
}

FAKE_TAILSCALE = r'''
import json
import os
from pathlib import Path
import sys

directory = Path(os.environ["MESH_FAKE_DIR"])
options = json.loads((directory / "options.json").read_text())
args = sys.argv[1:]
with (directory / "calls.jsonl").open("a") as output:
    output.write(json.dumps(args) + "\n")

if args == ["status", "--json"]:
    print(json.dumps(options["node_status"]))
elif args == ["status"]:
    print("100.101.102.103 mesh-test linux active")
elif args == ["ip", "-4"]:
    print("100.101.102.103")
elif args == ["serve", "status", "--json"]:
    calls = (directory / "calls.jsonl").read_text().splitlines()
    has_writes = any(json.loads(call)[:3] == ["serve", "--bg", "--yes"] for call in calls)
    if has_writes and options.get("status_failure"):
        print("cannot read Serve configuration", file=sys.stderr)
        sys.exit(1)
    if has_writes and "result" in options:
        print(options["result"])
    else:
        print((directory / "state.json").read_text())
elif args == ["serve", "status"]:
    print("Fake human-readable Serve status")
elif args[:3] == ["serve", "--bg", "--yes"]:
    writes = sum(json.loads(call)[:3] == ["serve", "--bg", "--yes"]
                 for call in (directory / "calls.jsonl").read_text().splitlines())
    if writes == options.get("fail_write"):
        print("Access denied: serve config denied; check permissions", file=sys.stderr)
        sys.exit(1)
    state = json.loads((directory / "state.json").read_text())
    if not options.get("no_op"):
        if args[3:5] in (["--tcp", "8000"], ["--tcp", "8080"], ["--tcp", "9000"]):
            if args[5:] != [f"127.0.0.1:{args[4]}"]:
                sys.exit("unexpected TCP target")
            state.setdefault("TCP", {})[args[4]] = {"TCPForward": args[5]}
        elif args[3:] in (["9000"], ["--https", "443", "http://127.0.0.1:9000"]):
            state.setdefault("TCP", {})["443"] = {"HTTPS": True}
            handlers = state.setdefault("Web", {}).setdefault(
                "mesh-test.example.ts.net:443", {}).setdefault("Handlers", {})
            handlers["/"] = {"Proxy": "http://127.0.0.1:9000"}
        else:
            sys.exit("unexpected Serve mutation")
        (directory / "state.json").write_text(json.dumps(state))
    print("CLI accepted Serve configuration")
else:
    sys.exit("unexpected Tailscale command: " + repr(args))
'''


@pytest.fixture
def run_mesh(tmp_path):
    """Fake only the host-mutating CLI; execute the real saved Bash script."""
    executable = tmp_path / "tailscale"
    executable.write_text(f"#!{sys.executable}\n" + FAKE_TAILSCALE)
    executable.chmod(0o755)
    # An accidental elevation must fail safely during this subprocess test.
    sudo = tmp_path / "sudo"
    sudo.write_text("#!/bin/sh\necho 'unexpected automatic sudo' >&2\nexit 99\n")
    sudo.chmod(0o755)

    def run(*, initial=None, node_state="Running", **options):
        (tmp_path / "state.json").write_text(json.dumps(initial or {}))
        (tmp_path / "options.json").write_text(json.dumps({
            "node_status": {
                "BackendState": node_state,
                "Self": {
                    "DNSName": f"{DNS_NAME}.",
                    "TailscaleIPs": ["100.101.102.103", "fd7a:115c:a1e0::1"],
                },
            },
            **options,
        }))
        environment = os.environ.copy()
        environment.pop("TAILSCALE_BIN", None)
        environment.update({
            "PATH": f"{tmp_path}:{environment['PATH']}",
            "MESH_FAKE_DIR": str(tmp_path),
        })
        result = subprocess.run(
            ["bash", str(SCRIPT)], capture_output=True, text=True,
            env=environment, timeout=10,
        )
        calls = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
        state = json.loads((tmp_path / "state.json").read_text())
        return result, calls, state

    return run


def test_cli_success_with_empty_config_cannot_report_active(run_mesh):
    result, _, _ = run_mesh(no_op=True)
    assert result.returncode != 0
    assert ACTIVE_BANNER not in result.stdout
    assert "8000" in result.stderr


@pytest.mark.parametrize("port", ["443", "8000", "8080", "9000"])
def test_missing_mapping_cannot_report_active(run_mesh, port):
    incomplete = copy.deepcopy(PRIVATE_CONFIG)
    del incomplete["TCP"][port]
    result, _, _ = run_mesh(result=json.dumps(incomplete))
    assert result.returncode != 0
    assert ACTIVE_BANNER not in result.stdout
    assert port in result.stderr


@pytest.mark.parametrize("write", [1, 3])
def test_permission_failure_explains_sudo_and_stops_at_failed_write(run_mesh, write):
    result, calls, _ = run_mesh(fail_write=write)
    assert result.returncode != 0
    assert ACTIVE_BANNER not in result.stdout
    assert "Access denied" in result.stderr
    assert "sudo" in result.stderr
    assert "script" in result.stderr.lower()
    writes = [call for call in calls if call[:3] == ["serve", "--bg", "--yes"]]
    assert len(writes) == write


def test_all_four_private_mappings_are_read_back_before_active(run_mesh):
    result, calls, state = run_mesh()
    assert result.returncode == 0, result.stderr
    assert ACTIVE_BANNER in result.stdout
    assert "http://100.101.102.103:8080" in result.stdout
    assert f"https://{DNS_NAME}/" in result.stdout
    assert state == PRIVATE_CONFIG
    last_write = max(index for index, call in enumerate(calls) if call[:3] == ["serve", "--bg", "--yes"])
    assert ["serve", "status", "--json"] in calls[last_write + 1:]
    assert ["serve", "--bg", "--yes", "--https", "443", "http://127.0.0.1:9000"] in calls


@pytest.mark.parametrize("bad_result", ["null", "[]", "not-json"])
def test_invalid_serve_json_cannot_report_active(run_mesh, bad_result):
    result, _, _ = run_mesh(result=bad_result)
    assert result.returncode != 0
    assert ACTIVE_BANNER not in result.stdout
    assert "Serve" in result.stderr


def test_serve_status_read_failure_cannot_report_active(run_mesh):
    result, _, _ = run_mesh(status_failure=True)
    assert result.returncode != 0
    assert ACTIVE_BANNER not in result.stdout
    assert "cannot read Serve configuration" in result.stderr


def test_wrong_loopback_mapping_cannot_report_active(run_mesh):
    wrong = copy.deepcopy(PRIVATE_CONFIG)
    wrong["TCP"]["8080"]["TCPForward"] = "192.168.100.19:8080"
    result, _, _ = run_mesh(result=json.dumps(wrong))
    assert result.returncode != 0
    assert ACTIVE_BANNER not in result.stdout
    assert "8080" in result.stderr


def test_wrong_https_proxy_cannot_report_active(run_mesh):
    wrong = copy.deepcopy(PRIVATE_CONFIG)
    wrong["Web"][f"{DNS_NAME}:443"]["Handlers"]["/"]["Proxy"] = "http://127.0.0.1:8080"
    result, _, _ = run_mesh(result=json.dumps(wrong))
    assert result.returncode != 0
    assert ACTIVE_BANNER not in result.stdout
    assert "443" in result.stderr


def test_existing_funnel_on_requested_port_stops_before_mutating(run_mesh):
    initial = {"AllowFunnel": {f"{DNS_NAME}:443": True}}
    result, calls, state = run_mesh(initial=initial)
    assert result.returncode != 0
    assert ACTIVE_BANNER not in result.stdout
    assert "Funnel" in result.stderr
    assert not any(call[:3] == ["serve", "--bg", "--yes"] for call in calls)
    assert state == initial


def test_funnel_in_readback_cannot_report_private_active(run_mesh):
    public = copy.deepcopy(PRIVATE_CONFIG)
    public["Foreground"] = {"session": {"AllowFunnel": {f"{DNS_NAME}:443": True}}}
    result, _, _ = run_mesh(result=json.dumps(public))
    assert result.returncode != 0
    assert ACTIVE_BANNER not in result.stdout
    assert "Funnel" in result.stderr


def test_foreground_mapping_cannot_override_verified_background_mapping(run_mesh):
    overridden = copy.deepcopy(PRIVATE_CONFIG)
    overridden["Foreground"] = {
        "session": {"TCP": {"8080": {"TCPForward": "127.0.0.1:7000"}}}
    }
    result, _, _ = run_mesh(result=json.dumps(overridden))
    assert result.returncode != 0
    assert ACTIVE_BANNER not in result.stdout
    assert "Foreground" in result.stderr


def test_unrelated_mappings_and_funnel_are_preserved(run_mesh):
    initial = {
        "TCP": {"2222": {"TCPForward": "127.0.0.1:22"}},
        "Web": {f"{DNS_NAME}:443": {"Handlers": {"/other": {"Proxy": "http://127.0.0.1:7000"}}}},
        "AllowFunnel": {f"{DNS_NAME}:8443": True},
    }
    result, _, state = run_mesh(initial=initial)
    assert result.returncode == 0, result.stderr
    assert state["TCP"]["2222"] == initial["TCP"]["2222"]
    assert state["Web"][f"{DNS_NAME}:443"]["Handlers"]["/other"] == initial["Web"][f"{DNS_NAME}:443"]["Handlers"]["/other"]
    assert state["AllowFunnel"] == initial["AllowFunnel"]


def test_stopped_node_cannot_begin_serve_mutations(run_mesh):
    result, calls, _ = run_mesh(node_state="Stopped")
    assert result.returncode != 0
    assert ACTIVE_BANNER not in result.stdout
    assert "Stopped" in result.stderr
    assert not any(call[:3] == ["serve", "--bg", "--yes"] for call in calls)
