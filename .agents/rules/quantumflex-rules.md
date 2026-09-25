# QuantumFlex Sovereign Operating System — Development & Security Rules

## Core Architectural Invariants

1. **Zero-Trust Loopback Boundary:**
   - No application database, daemon, or engine may bind to `0.0.0.0` or physical LAN interfaces (`enp6s0f3u1i1`).
   - Sockets `5432` (PostgreSQL), `8001` (Athena RAG), `8181` (OPA), `9444` (C++ Engine), and `11434` (Ollama) MUST bind strictly to `127.0.0.1`.
   - Remote access across the tailnet is mediated exclusively via **Tailscale Serve** reverse proxy tunnels.

2. **Shamir Secret Sharing & Airgap Media Hygiene:**
   - Master unlock entropy is fractured into 5 shards with a 3-of-5 threshold.
   - Shards 1 & 2 reside on encrypted host LUKS (`~/qfx-shards/`).
   - Shard 3 resides on the airgapped physical USB vault (`QFX_VAULT` / `/dev/sda1`).
   - **MANDATORY INVARIANT:** `QFX_VAULT` must be mounted strictly for the duration of the unseal ceremony and unmounted immediately post-reconstruction (`udisksctl unmount -b /dev/sda1`), leaving zero lingering storage mounts.

3. **Verify-Before-Execute on Mobile Fleet:**
   - Never pipe unverified HTTP responses directly into execution shells on mobile nodes.
   - Every artifact pushed to mobile devices (`qflex_cli.py`, `setup-mobile.sh`, `app-debug.apk`) must have a signed manifest and detached Ed25519 signature verified against the pinned trust anchor (`release_signing_key.pub`).
   - Remote SHA-256 byte validation via `adb shell sha256sum` must confirm file integrity on the target filesystem.

4. **Network Throughput & Buffer Sizing:**
   - Astound Broadband high-throughput routing requires Google BBR congestion control (`net.ipv4.tcp_congestion_control = bbr`) and Fair Queueing (`net.core.default_qdisc = fq`).
   - WireGuard/Tailscale UDP socket buffers must remain tuned to 16MB (`net.core.rmem_max = 16777216`, `net.core.wmem_max = 16777216`) to prevent packet drops during multi-megabyte burst synchronizations.

5. **Python Environment & Testing:**
   - The virtual environment is located at `/home/quant/mycelium/venv` (pointing to `/home/quant/.venv/qflex`).
   - Use `pytest.ini` for automatic module resolution. Tests should run with zero warnings where possible.

6. **Decoupled Observability & Control Authority (Telemetry Never Self-Authorizes):**
   - Monitoring and analytics software (PostHog, Q1 Observer, dashboards) operate strictly as passive sensory inputs producing untrusted advisory claims.
   - Observability tools have zero actuation rights, shell execution channels, or direct control authority over host containers or systemd units.
   - Any remediation action must pass through the deterministic Sentinel/OPA judgment gate, obtain cryptographic/operator authorization, and adhere to lease-fenced execution (`PENDING_HUMAN_APPROVAL`).
   - Post-remediation health is verified independently via kernel reality checks (`statvfs`, socket listeners), never trusting self-reported worker status.

