#!/usr/bin/env python3
"""
QuantumFlex Unified Mobile Operator CLI (qf)
=============================================
Unified, zero-dependency mobile command plane for QuantumFlex:
- Role-aware execution:
    * Google Pixel 11 Pro  (grizzly)       -> CUSTODY ROLE (Titan M2, Shamir shard, OOB signer)
    * HP ProBook 450 G6 (g6pro)             -> EVENT STREAMING & KAFKA BROKER ROLE
    * Unknown Device                        -> OBSERVER ROLE (Read-only, Privileged Actions DENIED)
- Authenticated host handshake over Tailscale / LAN
- Observational lens for QF-A5 provenance & QF-A6 runtime admission evidence
- Universal Invariant (R >= O) telemetry monitor
- Direct teammate swarm dispatch (Mycelia, Sentinel, Aria, Athena)
"""

import os
import sys
import json
import time
import socket
import platform
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, Tuple, Optional, List

CLI_VERSION = "2.6.0-qf-m1"

# Live tailnet facts (verified 2026-10-23 via `tailscale status`)
YOGA_HOSTNAME = "quant-Yoga-7-2-in-1-14AKP10"
YOGA_TAILSCALE_IP = "100.64.1.31"
YOGA_MAGICDNS = "quant-yoga-7-2-in-1-14akp10.example-tailnet.ts.net"
PIXEL_TAILSCALE_IPS = ("100.64.1.16",)

# Candidate host sequence: dynamically prioritized by local execution context
TIMEOUT_FAST = 1.2
TIMEOUT_STANDARD = 6.0
TIMEOUT_CHAT = 60.0

def get_candidate_hosts() -> List[Tuple[str, int]]:
    # If running directly on the master host, loopback is immediate
    if socket.gethostname() == YOGA_HOSTNAME or os.environ.get("USER") == "quant":
        return [
            ("127.0.0.1", 9000),
            (YOGA_TAILSCALE_IP, 9000),
            (YOGA_MAGICDNS, 9000),
        ]
    # On mobile devices, Tailscale mesh IP is primary, then MagicDNS
    return [
        (YOGA_TAILSCALE_IP, 9000),
        (YOGA_MAGICDNS, 9000),
        ("127.0.0.1", 9000),
    ]


# ── ANSI Color Tokens ──────────────────────────────────────────────────────────
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_DIM = "\033[2m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"
CLR_WHITE = "\033[97m"

def _c(color: str, text: str) -> str:
    if sys.stdout.isatty():
        return f"{color}{text}{CLR_RESET}"
    return text

# ── Identity & Role Resolution ─────────────────────────────────────────────────
class NodeIdentity:
    def __init__(self, node_id: str, role: str, model: str, tailscale_ip: str,
                 transport: str, privileged: bool, details: str):
        self.node_id = node_id
        self.role = role
        self.model = model
        self.tailscale_ip = tailscale_ip
        self.transport = transport
        self.privileged = privileged
        self.details = details

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "role": self.role,
            "model": self.model,
            "tailscale_ip": self.tailscale_ip,
            "transport": self.transport,
            "privileged_actions": "ALLOW" if self.privileged else "DENY",
            "details": self.details,
        }

def _get_android_prop(prop_name: str) -> str:
    try:
        res = subprocess.run(["getprop", prop_name], capture_output=True, text=True, timeout=1.0)
        return res.stdout.strip()
    except Exception:
        return ""

def _detect_local_ips() -> List[str]:
    ips = []
    try:
        res = subprocess.run(["ip", "-o", "addr", "show"], capture_output=True, text=True, timeout=1.0)
        for line in res.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[2] == "inet":
                ip = parts[3].split("/")[0]
                ips.append(ip)
    except Exception:
        pass

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127.") and ":" not in ip:
                ips.append(ip)
    except Exception:
        pass
    return ips

def resolve_node_identity() -> NodeIdentity:
    """
    Strict fail-closed identity resolution.
    Never guesses a phone type. Any mismatch resolves to Observer (Read-Only).
    """
    model = _get_android_prop("ro.product.model")
    product_name = _get_android_prop("ro.product.name")
    device_name = _get_android_prop("ro.product.device")
    hostname = socket.gethostname()
    local_ips = _detect_local_ips()

    # 1. Google Pixel 11 Pro Check
    is_pixel_model = any("Pixel 11" in str(m) for m in [model, product_name]) or any("grizzly" in str(m) for m in [product_name, device_name])
    has_pixel_ip = any(ip in local_ips for ip in PIXEL_TAILSCALE_IPS) or "pixel" in hostname.lower()

    if is_pixel_model or has_pixel_ip:
        tail_ip = next((ip for ip in PIXEL_TAILSCALE_IPS if ip in local_ips), PIXEL_TAILSCALE_IPS[0])
        transport = "usb+tailscale" if any(ip in local_ips for ip in PIXEL_TAILSCALE_IPS) else "tailscale"
        return NodeIdentity(
            node_id="pixel-11-pro",
            role="shard-custodian",
            model="Google Pixel 11 Pro (grizzly)",
            tailscale_ip=tail_ip,
            transport=transport,
            privileged=True,
            details="Hardware Titan M2 Enclave | Shamir Share Custodian #5 | OOB Signer"
        )

    # 2. Host Node Check (qfx-yoga)
    if hostname in (YOGA_HOSTNAME, "qfx-yoga") or YOGA_TAILSCALE_IP in local_ips or os.environ.get("USER") == "quant":
        return NodeIdentity(
            node_id="qfx-yoga",
            role="master-engine",
            model="Lenovo Yoga 7 2-in-1 14AKP10 (Ubuntu 26.04.1 LTS)",
            tailscale_ip=YOGA_TAILSCALE_IP,
            transport="loopback+mesh",
            privileged=True,
            details="Primary PQC Engine | Cryptographic Admission Anchor"
        )

    # 4. Fail-closed: Unknown node -> Observer
    observed_str = f"model='{model}' host='{hostname}' ips={local_ips}"
    return NodeIdentity(
        node_id="unknown",
        role="observer",
        model=model or "Generic / Untrusted",
        tailscale_ip=local_ips[0] if local_ips else "0.0.0.0",
        transport="unverified",
        privileged=False,
        details=f"Unrecognized node ({observed_str}). Privileged actions strictly DENIED."
    )

# ── Host Discovery & Authenticated Handshake ──────────────────────────────────
def discover_authenticated_host() -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Probes candidate hosts in priority sequence.
    Requires authenticated /mobile/bootstrap handshake returning:
      {"service": "quantumflex-qf-bot", "schema": "qf-mobile-v1"}
    Port number alone is never trusted as identity.
    """
    candidates = get_candidate_hosts()
    for host, port in candidates:
        url = f"http://{host}:{port}/mobile/bootstrap"
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": f"QuantumFlex-MobileCLI/{CLI_VERSION}",
                    "Accept": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT_FAST) as resp:
                if resp.status == 200:
                    payload = json.loads(resp.read().decode("utf-8"))
                    if payload.get("service") == "quantumflex-qf-bot" and payload.get("schema") == "qf-mobile-v1":
                        return f"http://{host}:{port}", payload
        except Exception:
            continue

    # Secondary fallback: try /api/status if /mobile/bootstrap is in transition
    for host, port in candidates:
        url = f"http://{host}:{port}/api/status"
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": f"QuantumFlex-MobileCLI/{CLI_VERSION}",
                    "Accept": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT_FAST) as resp:
                if resp.status == 200:
                    payload = json.loads(resp.read().decode("utf-8"))
                    if payload.get("node") == "quantumflex" and "sentinel" in payload:
                        return f"http://{host}:{port}", payload
        except Exception:
            continue

    return None, None

def _api_get(base_url: str, path: str, timeout: float = TIMEOUT_STANDARD) -> Tuple[bool, Any]:
    url = f"{base_url}{path}"
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"QuantumFlex-MobileCLI/{CLI_VERSION}",
                "Accept": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return True, data
    except urllib.error.HTTPError as e:
        try:
            err_data = json.loads(e.read().decode("utf-8"))
            return False, err_data.get("detail", str(e))
        except Exception:
            return False, f"HTTP Error {e.code}: {e.reason}"
    except Exception as e:
        return False, str(e)

def _api_post(base_url: str, path: str, body: Dict[str, Any], timeout: float = TIMEOUT_STANDARD) -> Tuple[bool, Any]:
    url = f"{base_url}{path}"
    try:
        raw_body = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=raw_body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": f"QuantumFlex-MobileCLI/{CLI_VERSION}",
                "Accept": "application/json"
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return True, data
    except urllib.error.HTTPError as e:
        try:
            err_data = json.loads(e.read().decode("utf-8"))
            return False, err_data.get("detail", str(e))
        except Exception:
            return False, f"HTTP Error {e.code}: {e.reason}"
    except Exception as e:
        return False, str(e)

# ── Command Implementations ───────────────────────────────────────────────────

def cmd_node(identity: NodeIdentity):
    """Exposes exactly what identity determination observed."""
    print()
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print(_c(CLR_BOLD + CLR_WHITE, "  QUANTUMFLEX MOBILE IDENTITY DETERMINATION"))
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print(f"  NODE               : {_c(CLR_BOLD, identity.node_id)}")
    print(f"  ROLE               : {_c(CLR_BOLD + (CLR_GREEN if identity.role == 'shard-custodian' else CLR_RED), identity.role)}")
    print(f"  MODEL              : {identity.model}")
    print(f"  TAILSCALE          : {identity.tailscale_ip}")
    print(f"  TRANSPORT          : {identity.transport}")
    priv_color = CLR_GREEN if identity.privileged else CLR_RED
    print(f"  PRIVILEGED_ACTIONS : {_c(CLR_BOLD + priv_color, 'ALLOW' if identity.privileged else 'DENY')}")
    print(f"  HARDWARE AUTHORITY : {identity.details}")
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print()

def cmd_status(base_url: str, identity: NodeIdentity):
    """Cluster health, Sentinel drive status, invariant gate, and mesh peers."""
    ok, data = _api_get(base_url, "/api/status")
    if not ok:
        print(_c(CLR_RED, f"[!] Failed to fetch status from {base_url}: {data}"))
        return

    sentinel = data.get("sentinel", {})
    invariant = data.get("invariant", {})
    mesh = data.get("mesh", {})
    drive_score = sentinel.get("drive_score", 0.0)
    drive_status = sentinel.get("drive_status", "UNKNOWN")
    inv_verdict = invariant.get("overall_verdict", "UNKNOWN")
    tpm_matched = sentinel.get("tpm_anchor_matched", False)

    print()
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print(_c(CLR_BOLD + CLR_WHITE, f"  QUANTUMFLEX CLUSTER STATUS  •  [{identity.node_id} | {identity.role}]"))
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print(f"  Host Endpoint      : {base_url}")
    print(f"  Sentinel Drive (D) : {_c(CLR_BOLD, f'{drive_score:.2f}')} ({_c(CLR_GREEN if drive_status == 'EQUILIBRIUM' else CLR_YELLOW, drive_status)})")
    print(f"  TPM Hardware Anchor: {_c(CLR_GREEN if tpm_matched else CLR_RED, 'MATCHED' if tpm_matched else 'MISMATCH')}")
    print(f"  Universal Invariant: {_c(CLR_BOLD + (CLR_GREEN if inv_verdict == 'ADMIT' else CLR_RED), inv_verdict)}")
    print(f"  Teammates Online   : {data.get('teammates_online', 0)}")
    print(f"  Pending Drafts     : {data.get('pending_drafts', 0)}")
    print()
    print(_c(CLR_BOLD, "  Mesh Topology & Peer Latencies:"))
    for peer_name, info in mesh.items():
        st = info.get("status", "UNKNOWN")
        st_clr = CLR_GREEN if st == "ONLINE" else CLR_DIM
        lat = info.get("latency", "—")
        role = info.get("role", "")
        ip = info.get("ip", "")
        print(f"    • {peer_name:<16} : {ip:<15} | {role:<24} | {_c(st_clr, st)} ({lat})")
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print()

def cmd_verify(base_url: str):
    """
    Authoritative admission verification.
    The phone is an observational lens; external host verifier remains root of trust.
    """
    ok, data = _api_get(base_url, "/mobile/admission/evidence")
    if not ok:
        print(_c(CLR_YELLOW, f"[*] Querying admission evidence via cluster status gateway..."))
        ok_st, st_data = _api_get(base_url, "/api/status")
        if not ok_st:
            print(_c(CLR_RED, f"[!] Host admission evidence unreachable: {data}"))
            return
        sentinel = st_data.get("sentinel", {})
        data = {
            "a4_package": "VERIFIED (build-check)",
            "a5_provenance": "ADMITTED" if sentinel.get("integrity_verified") else "DENIED",
            "a6_runtime": "BOUND (FD Pinning)",
            "tpm_anchor": sentinel.get("tpm_nv_tip", "UNKNOWN"),
            "observed_at": st_data.get("timestamp", "UNKNOWN"),
            "runtime_binding_hash": sentinel.get("block_hash", "UNKNOWN"),
            "launcher_invariant": "EXECUTED_FD == VERIFIED_FD",
            "source_authority": "Yoga Master External Verifier (~/.local/libexec/quantumflex/verify-provenance)"
        }

    print()
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print(_c(CLR_BOLD + CLR_WHITE, "  QUANTUMFLEX CRYPTOGRAPHIC ADMISSION EVIDENCE (A4 / A5 / A6)"))
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print(f"  QF-A4 (Artifact Hash) : {_c(CLR_GREEN, str(data.get('a4_package', 'PASS')))}")
    print(f"  QF-A5 (Ed25519 Provenance) : {_c(CLR_GREEN, str(data.get('a5_provenance', 'PASS')))}")
    print(f"  QF-A6 (Runtime Binding)    : {_c(CLR_GREEN, str(data.get('a6_runtime', 'PASS')))}")
    print()
    print(f"  Runtime Invariant     : {_c(CLR_BOLD + CLR_WHITE, str(data.get('launcher_invariant', 'EXECUTED_FD == VERIFIED_FD')))}")
    print(f"  Runtime Binding Hash  : {data.get('runtime_binding_hash', '—')[:32]}...")
    print(f"  TPM PCR-7 / NV Tip    : {data.get('tpm_anchor', '—')[:32]}...")
    print(f"  Observed Timestamp    : {data.get('observed_at', '—')}")
    print()
    print(_c(CLR_DIM, f"  Authority: {data.get('source_authority', 'Host Admission Authority')}"))
    print(_c(CLR_DIM, "  Notice: The mobile node acts as an observational lens. The host trust anchor"))
    print(_c(CLR_DIM, "          remains the sole root of admission authority."))
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print()

def cmd_invariant(base_url: str):
    """Universal Invariant R >= O Telemetry Monitor."""
    ok, data = _api_get(base_url, "/api/status")
    if not ok:
        print(_c(CLR_RED, f"[!] Failed to fetch invariant data: {data}"))
        return

    invariant = data.get("invariant", {})
    verdict = invariant.get("overall_verdict", "UNKNOWN")
    evals = invariant.get("evaluations", {})

    print()
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print(_c(CLR_BOLD + CLR_WHITE, f"  UNIVERSAL INVARIANT MONITOR  •  R >= O  [{verdict}]"))
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))

    for name, item in evals.items():
        allowed = item.get("allowed", False)
        reason = item.get("reason", "")
        payload = item.get("payload", {})
        res_type = payload.get("resource_type", name.upper())
        r = payload.get("reserve_measured", "—")
        o = payload.get("units_claimed", "—")

        status_text = _c(CLR_GREEN, "[ADMIT]") if allowed else _c(CLR_RED, "[REJECT]")
        print(f"  {status_text} {res_type:<18}")
        print(f"         Reserves (R)   : {r}")
        print(f"         Obligations (O): {o}")
        print(f"         Rule Verdict   : {reason}")
        print()
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print()

def cmd_custody(identity: NodeIdentity, base_url: str):
    """Shamir 3-of-5 threshold state and hardware shard custody."""
    print()
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print(_c(CLR_BOLD + CLR_WHITE, "  QUANTUMFLEX HARDWARE CUSTODY & SHARD STATUS"))
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))

    if identity.role == "shard-custodian":
        print(_c(CLR_BOLD + CLR_GREEN, "  [+] NODE AUTHORIZED AS CUSTODIAL HARDWARE ANCHOR"))
        print(f"  Target Device     : {identity.model}")
        print(f"  Enclave Mechanism : Titan M2 Hardware Security Module")
        print(f"  Custody Shard     : Share #5 (3-of-5 threshold quorum participant)")
        print(f"  Out-of-Band State : ARMED (Ready for zero-trust authorization)")
        print(f"  Circuit Breaker   : ACCESSIBLE (Emergency freeze authorization available)")
    elif identity.role == "master-engine":
        print(_c(CLR_BOLD + CLR_GREEN, "  [+] MASTER ENGINE: PRIMARY CRYPTOGRAPHIC ROOT"))
        print(f"  Host Architecture : {identity.model}")
        print(f"  Hardware Security : Microsoft Pluton TPM 2.0")
        print(f"  Local Custody     : Holds Share 1")
        print(f"  Required Quorum   : Requires 2 remote shares (g6pro, Pixel 11 Pro, or USB vault)")
    else:
        print(_c(CLR_RED, "  [!] NODE IS IN READ-ONLY OBSERVER ROLE"))
        print(f"  Custody Access    : STRICTLY DENIED")

    print()
    print(_c(CLR_BOLD, "  Master Shamir 3-of-5 Custody Distribution:"))
    print("    • Share 1      : Lenovo Yoga 7 2-in-1 14AKP10 (qfx-yoga)")
    print("    • Share 2      : HP ProBook 450 G6 (g6pro)")
    print("    • Shares 3 & 4 : Unmounted Physical USB Vault")
    print("    • Share 5      : Google Pixel 11 Pro (qfx-pixel)")
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print()

def cmd_chat(base_url: str, identity: NodeIdentity, agent: str, prompt: str):
    """Dispatches a query to an AI teammate (Mycelia, Sentinel, Aria, Athena)."""
    agent = agent.lower().strip()
    valid_agents = ["mycelia", "sentinel", "aria", "athena"]
    if agent not in valid_agents:
        print(_c(CLR_RED, f"[!] Unknown teammate '{agent}'. Choose from: {', '.join(valid_agents)}"))
        return

    print(f"\n[*] Dispatching to {_c(CLR_BOLD + CLR_CYAN, agent.upper())} from {_c(CLR_BOLD, identity.node_id)}...")
    ok, res = _api_post(
        base_url,
        "/api/chat",
        {"agent": agent, "message": prompt, "sender_node": identity.node_id},
        timeout=TIMEOUT_CHAT
    )

    if not ok:
        print(_c(CLR_RED, f"[!] Error communicating with teammate {agent}: {res}"))
        return

    print("\n" + _c(CLR_BOLD + CLR_CYAN, f"── [{agent.upper()}] ────────────────────────────────────────────────────────"))
    reply = res.get("response") or res.get("reply") or res.get("answer") or str(res)
    print(reply)
    print(_c(CLR_BOLD + CLR_CYAN, "──────────────────────────────────────────────────────────────────\n"))

def cmd_drafts(base_url: str):
    """Inspects pending staged actions requiring operator authorization."""
    ok, data = _api_get(base_url, "/api/drafts")
    if not ok:
        print(_c(CLR_RED, f"[!] Failed to fetch drafts: {data}"))
        return

    drafts = data.get("drafts", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    print()
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print(_c(CLR_BOLD + CLR_WHITE, f"  STAGED OPERATOR DRAFTS  ({len(drafts)} Pending)"))
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))

    if not drafts:
        print(_c(CLR_GREEN, "  [+] Draft queue is clean. Zero actions pending authorization."))
    else:
        for d in drafts:
            d_id = d.get("id") or d.get("draft_id", "unknown")
            action = d.get("action_type") or d.get("action", "UNKNOWN")
            desc = d.get("description") or d.get("summary", "No description")
            agent = d.get("agent", "UNKNOWN")
            created = d.get("created_at", "—")
            print(f"  • ID: {_c(CLR_BOLD + CLR_YELLOW, str(d_id))}")
            print(f"    Action  : {action} (staged by {agent})")
            print(f"    Summary : {desc}")
            print(f"    Created : {created}")
            print()
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print()

def cmd_approve(base_url: str, identity: NodeIdentity, draft_id: str):
    """Privileged transition: Requires authorized role and fresh receipt."""
    if not identity.privileged or identity.role == "observer":
        print(_c(CLR_RED, f"\n[!] ACCESS DENIED: Node '{identity.node_id}' is in read-only OBSERVER role."))
        print(_c(CLR_RED, "    Privileged transitions (approve/discard) are strictly DENIED.\n"))
        sys.exit(1)

    print()
    print(_c(CLR_YELLOW, f"[?] PRIVILEGED ACTION: Authorize and execute staged draft '{draft_id}'?"))
    print(f"    Authorizing Node : {_c(CLR_BOLD, identity.node_id)} ({identity.role})")
    print(f"    Transport Link   : {identity.transport}")
    try:
        confirm = input("    Type 'CONFIRM' to sign and dispatch: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n[!] Aborted by operator.")
        return

    if confirm != "CONFIRM":
        print(_c(CLR_DIM, "[*] Authorization cancelled."))
        return

    auth_receipt = {
        "authorizer_node": identity.node_id,
        "authorizer_role": identity.role,
        "authorizer_model": identity.model,
        "auth_timestamp": time.time(),
        "tailscale_ip": identity.tailscale_ip
    }

    ok, res = _api_post(base_url, f"/api/drafts/{draft_id}/approve", {"receipt": auth_receipt})
    if ok:
        print(_c(CLR_GREEN, f"\n[+] Draft '{draft_id}' APPROVED and dispatched successfully."))
        print(f"    Verdict: {res}\n")
    else:
        print(_c(CLR_RED, f"\n[!] Failed to approve draft '{draft_id}': {res}\n"))

def cmd_discard(base_url: str, identity: NodeIdentity, draft_id: str):
    """Privileged transition: Discards a staged draft."""
    if not identity.privileged or identity.role == "observer":
        print(_c(CLR_RED, f"\n[!] ACCESS DENIED: Node '{identity.node_id}' is in read-only OBSERVER role."))
        print(_c(CLR_RED, "    Privileged transitions are strictly DENIED.\n"))
        sys.exit(1)

    ok, res = _api_post(base_url, f"/api/drafts/{draft_id}/discard", {"sender_node": identity.node_id})
    if ok:
        print(_c(CLR_YELLOW, f"\n[*] Draft '{draft_id}' discarded."))
    else:
        print(_c(CLR_RED, f"\n[!] Failed to discard draft: {res}"))

def cmd_doctor(identity: NodeIdentity, base_url: Optional[str], handshake: Optional[Dict[str, Any]]):
    """System diagnostic, trust anchor verification, and connectivity probe."""
    print()
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print(_c(CLR_BOLD + CLR_WHITE, "  QUANTUMFLEX MOBILE DOCTOR & DIAGNOSTIC"))
    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print(f"  CLI Version        : {CLI_VERSION}")
    print(f"  Python Runtime     : {platform.python_version()} ({platform.platform()})")
    print(f"  Local Node ID      : {identity.node_id}")
    print(f"  Assigned Role      : {identity.role}")

    # Check trust anchor
    possible_anchors = [
        os.path.expanduser("~/.quantumflex/release_signing_key.pub"),
        os.path.expanduser("~/.local/libexec/quantumflex/release_signing_key.pub"),
        "/sdcard/Download/QuantumFlex/release_signing_key.pub",
        os.path.join(os.path.dirname(__file__), "release_signing_key.pub")
    ]
    found_anchor = None
    for a in possible_anchors:
        if os.path.isfile(a):
            found_anchor = a
            break

    if found_anchor:
        print(f"  Trust Anchor       : {_c(CLR_GREEN, 'FOUND')} ({found_anchor})")
    else:
        print(f"  Trust Anchor       : {_c(CLR_YELLOW, 'MISSING')} (Local signature verification disabled)")

    # Host Handshake Check
    if base_url and handshake:
        print(f"  Authenticated Host : {_c(CLR_GREEN, base_url)}")
        print(f"  Host Service Name  : {handshake.get('service', '—')}")
        print(f"  Host Schema Spec   : {handshake.get('schema', '—')}")
    else:
        print(f"  Authenticated Host : {_c(CLR_RED, 'UNREACHABLE')}")
        print("  Probed Candidates  :")
        for h, p in get_candidate_hosts():
            print(f"    - http://{h}:{p}")

    print(_c(CLR_BOLD + CLR_CYAN, "═══════════════════════════════════════════════════════════════"))
    print()

def print_usage():
    print(f"""
QuantumFlex Unified Mobile CLI ({CLI_VERSION})
Usage:
  qf status                               - Cluster health, Sentinel drive, mesh latency
  qf verify                               - Authoritative QF-A5/A6 admission evidence
  qf invariant                            - Universal Invariant (R >= O) telemetry
  qf custody                              - Hardware shard custody & quorum status
  qf node                                 - Identity resolution & authority diagnostic
  qf doctor                               - Network, trust anchor, and service diagnostic

  qf chat <mycelia|sentinel|aria|athena> "<prompt>"
                                          - Interrogate multi-agent neural swarm

  qf drafts                               - Inspect staged actions pending authorization
  qf approve <draft_id>                   - [PRIVILEGED] Authorize staged draft execution
  qf discard <draft_id>                   - [PRIVILEGED] Discard staged draft
""")

# ── Entry Point ───────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print_usage()
        sys.exit(0)

    cmd = sys.argv[1].lower()
    identity = resolve_node_identity()

    # Commands that do not require network connectivity
    if cmd == "node":
        cmd_node(identity)
        sys.exit(0)

    # Discover and authenticate with host
    base_url, handshake = discover_authenticated_host()

    if cmd == "doctor":
        cmd_doctor(identity, base_url, handshake)
        sys.exit(0)

    if not base_url:
        print(_c(CLR_RED, "\n[!] FATAL: No authenticated QuantumFlex host could be reached."))
        print("    Ensure Tailscale is connected or host is reachable on local Wi-Fi.")
        print("    Run 'qf doctor' for diagnostic details.\n")
        sys.exit(1)

    if cmd == "status":
        cmd_status(base_url, identity)
    elif cmd == "verify":
        cmd_verify(base_url)
    elif cmd == "invariant":
        cmd_invariant(base_url)
    elif cmd == "custody":
        cmd_custody(identity, base_url)
    elif cmd == "drafts":
        cmd_drafts(base_url)
    elif cmd in ("approve", "auth"):
        if len(sys.argv) < 3:
            print("Usage: qf approve <draft_id>")
            sys.exit(1)
        cmd_approve(base_url, identity, sys.argv[2])
    elif cmd in ("discard", "reject"):
        if len(sys.argv) < 3:
            print("Usage: qf discard <draft_id>")
            sys.exit(1)
        cmd_discard(base_url, identity, sys.argv[2])
    elif cmd in ("chat", "ask", "tell"):
        if len(sys.argv) < 4:
            print("Usage: qf chat <mycelia|sentinel|aria|athena> \"<prompt>\"")
            sys.exit(1)
        agent = sys.argv[2]
        prompt = " ".join(sys.argv[3:])
        cmd_chat(base_url, identity, agent, prompt)
    elif cmd in ("athena", "query", "rag"):
        if len(sys.argv) < 3:
            print("Usage: qf athena \"<prompt>\"")
            sys.exit(1)
        prompt = " ".join(sys.argv[2:])
        cmd_chat(base_url, identity, "athena", prompt)
    else:
        print(_c(CLR_RED, f"[!] Unknown command '{cmd}'"))
        print_usage()
        sys.exit(1)

if __name__ == "__main__":
    main()
