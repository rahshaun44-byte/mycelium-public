# QuantumFlex: Master Technical & Operational Handoff

**Verified Date:** 2026-09-13  
**Target Silicon:** Lenovo Yoga 7i — AMD Ryzen AI 5 340 (Zen 5, 8 cores / 16 threads, AVX-512, VAES, GFNI, SHA-NI)  
**Host Environment:** Fedora Linux 44 (Rawhide / 7.2.4 kernel), User `quant` (uid 1000)  
**Repository Source of Truth:** `/home/quant/mycelium`  
**Active Git HEAD:** `b8e3ad6` (`feat(core): implement Phase 1 thermodynamic ghost node and Phase 2 zero-friction Wasm gatekeeper`)

---

## 1. Executive Summary

This handoff captures the complete operational baseline, security hardening, stale code purge, neural model provisioning, and the core optimizations implementing the **Equation of Truth**:

$$Y = f(x - h) + k$$

* **$x$ (Cryptographic Momentum):** FrodoKEM-976-AES and ML-KEM-768 post-quantum cryptographic primitives.
* **$h \rightarrow 0$ (Thermodynamic Ghost Node):** Complete elimination of NVMe SSD NAND flash block wear and persistent forensic residue by confining quarantined anomaly intake strictly to volatile DDR5 RAM disks (`tmpfs`).
* **$k$ (Zero-Friction Gatekeeper):** Microsecond in-process policy evaluation via compiled WebAssembly (`.wasm`) eliminating loopback HTTP serialization overhead.
* **$Y$:** Hardened, zero-trust autonomous operational state with fail-secure guarantees.

---

## 2. Completed Milestones & Architectural State

### 2.1 Security Baseline & "Locked Phase" Invariant
* **Engine Locked Posture:** The C++ evidence engine (`quantum-flex-engine-mycelium.service`) runs on `127.0.0.1:9444` (mTLS, TLS 1.3, client certificate required). Status queries return `ERR|NODE_LOCKED`.
* **Shamir 3-of-5 Custody:** Only `shard_1.txt` resides on the host at `~/qfx-shards/shard_1.txt` (`chmod 600`). Shards 2–5 were cryptographically shredded (`shred -u -z -n 3`), guaranteeing the engine cannot unseal without manual, multi-party physical presentation of offline shards.
* **Loopback Boundary:** All services (`5432`, `8000`, `8001`, `8080`, `8181`, `9000`, `9050`, `9444`, `11434`) are strictly bound to `127.0.0.1`. Interface `tailscale0` is in firewalld zone `qf-tailscale`. No unauthenticated LAN listeners exist on `0.0.0.0`.
* **Duplicate Process Pruning:** Crash-looping user-level `ollama.service` disabled in favor of system-level Ollama daemon.

### 2.2 Neural Provisioning (AMARA & The Claw)
Both required models are loaded in system Ollama (`127.0.0.1:11434`):
1. **`nomic-embed-text:latest` (274 MB):** Generates 768-dimensional dense vector embeddings for pulse telemetry ingestion into AMARA and Athena PostgreSQL vector tables.
2. **`gemma2:2b` (1.6 GB):** Verified low-latency local inference engine powering QF-Bot, task decomposition, and autonomous agents.

### 2.3 Stale Code Purge (Commit `ede9475`)
Purged 1,377 lines of dead code and obsolete prototypes:
* Removed `scripts/package_alpha_node.py` to enforce the Zero-Key Shipping Invariant.
* Removed unreferenced prototypes: `mcp_layer/ollama_agent.py`, `mcp_layer/amara_agent.py`, `mcp_layer/amara_sync.py`, `mcp_layer/init_shards.py`.
* Removed legacy monolithic runners: `qf_stack.py`, `qf_daemon.py`.
* Removed dead backups & benchmarks: `sentinel/tripwire_daemon.py.bak`, `sentinel/requirements.txt`, `experiments_windows_timer_and_lif.py`, `mobile-qf-kit.tar.gz`.
* Normalized broken symlink `compile_commands.json` to `/home/quant/mycelium/build_check/compile_commands.json`.
* Patched `tests/test_gateway_verification.py` to skip dead Tailscale IP, reducing test runtime from 133s to 1.1s.

### 2.4 Phase 1: Thermodynamic Ghost Node ($h \rightarrow 0$)
* **Volatile Host Staging (`run_sentinel.py`):** Payload intake switched from NVMe disk (`~/mycelium/sentinel`) to volatile DDR5 RAM at `/dev/shm/qflex_airlock` (`0700` permissions). Staged files are zero-wiped (`b"\x00"`) before unlinking on chamber exit.
* **Hardened Podman Execution:** Container runs with `--read-only`, `--cap-drop=ALL`, `--security-opt=no-new-privileges=true`.
* **Volatile RAM Anomaly Sink:** Container mounts `--tmpfs /opt/sentinel/quarantine:rw,size=64m,noexec,nosuid,nodev`. Zero bytes written to physical NAND flash storage.
* **Standalone Rootless Harness (`scripts/run_route_test.sh`):** Automates isolated bridge verification (`quantum-test-net`) and asserts read-only rootfs + tmpfs quarantine.
* **Setup Script Template (`scripts/fedora_yoga7i_setup.sh`):** Hardened harness deployed to `/usr/local/share/mesh-test-harness/run_route_test.sh`.

### 2.5 Phase 2: Zero-Friction Gatekeeper ($k$)
* **Standalone WebAssembly Binaries:**
  - `sentinel/policies/membrane_health.wasm` (148 KB): Compiled from `membrane_health.rego` with 5 entrypoints (`verdict`, `fallback_map`, `recovery_map`, `active_fallback_map`, `recommended_fallback`).
  - `sentinel/policies/reserve_invariant.wasm` (180 KB): Compiled from `reserve_invariant.rego` ($R \ge O$ solvency, freshness assertions, Pluton TPM 2.0 anchoring).
* **In-Process Wasm Engine (`sentinel/policies/wasm_gatekeeper.py`):**
  - Powered by `wasmtime` runtime.
  - Implements OPA Wasm ABI: linear memory management, context lifecycle, and Rego builtins (`sprintf` ID 4, `time.now_ns` ID 10).
  - Enforces Landauer heap preservation (`opa_heap_ptr_get` / `opa_heap_ptr_set`) for constant, zero-leak memory footprint.
* **System Integrations:**
  - `sentinel/invariant_gate.py`: Evaluates universal solvency in-process first, falling back to HTTP `:8181` if `FORCE_HTTP_OPA=1`.
  - `pqc-immune-daemon/immune_daemon.py`: Evaluates CycloneDX CBOM health in-process first via `--wasm` flag or automatic detection.

---

## 3. Verified Performance & Test Telemetry

### 3.1 Automated Pytest Suite
```bash
/home/quant/mycelium/venv/bin/pytest -v tests/ pqc-immune-daemon/test_immune_daemon.py
```
**Status: 27 PASSED, 1 SKIPPED (1.62 seconds)**

* `tests/test_ghost_node_tmpfs.py`: 2/2 PASSED (Tmpfs boundary + RAM zero-wipe)
* `tests/test_wasm_gatekeeper.py`: 7/7 PASSED (CBOM compliance, threat flag TOXIC, R >= O, sub-millisecond latency)
* `pqc-immune-daemon/test_immune_daemon.py`: 15/15 PASSED (Circuit breaker, quarantine, fail-secure, SIGHUP)
* `tests/test_privacy_filter.py`: 3/3 PASSED (Sanitization, opt-out)

### 3.2 Microsecond Gatekeeper Latency Benchmark (1,000 runs)
| Evaluation Engine | Mechanism | Mean Latency | Sockets / Ports Required |
| :--- | :--- | :--- | :--- |
| **OPA Sidecar Daemon** | Loopback REST to `127.0.0.1:8181` | **1,014.74 µs (1.01 ms)** | Open TCP port 8181 |
| **Zero-Friction Wasm Gatekeeper** | In-Process `wasmtime` (`.wasm`) | **298.89 µs (0.29 ms)** | **Zero ports, in-process** |
| **Net Optimization** | — | **3.4x faster** | **Immune to TCP socket jitter** |

### 3.3 Thermodynamic Ghost Node Isolation Benchmark
```bash
./scripts/run_route_test.sh
```
* Network RTT Across Bridge: **0.053 ms – 0.098 ms**
* Rootfs Mutation: **BLOCKED (`Read-only file system`)**
* Volatile Quarantine Partition: **64.0 MB tmpfs RAM mount**
* NVMe SSD Flash Block Wear: **0 bytes written**

---

## 4. Operator Command Reference & Day-to-Day Operations

### 4.1 Running the In-Process Wasm Gatekeeper
```bash
# 1. Evaluate Universal Invariant (R >= O) via Wasm
python3 sentinel/invariant_gate.py memory
python3 sentinel/invariant_gate.py all

# 2. Run Immune Daemon single cycle via Wasm
python3 pqc-immune-daemon/immune_daemon.py --conf pqc-immune-daemon/crypto_provider.conf --wasm --once -v

# 3. Force loopback HTTP benchmark comparison
FORCE_HTTP_OPA=1 python3 sentinel/invariant_gate.py memory
```

### 4.2 Detonating Suspicious Payloads via Thermodynamic Chamber
```bash
# Stages payload to /dev/shm/qflex_airlock, detonates in Podman tmpfs, and zero-wipes RAM
python3 run_sentinel.py /path/to/suspicious/payload.bin
```

### 4.3 Running Ghost Node & Routing Verification
```bash
# Rootless Podman bridge and volatile tmpfs test
./scripts/run_route_test.sh
```

### 4.4 Live Service Stack Management
```bash
# Check status of core services
systemctl --user status amara-matrix quantum-flex-engine-mycelium opa-immune

# Query mTLS engine status (locked phase verification)
python3 scripts/qf_ipc_client.py \
  --host 127.0.0.1 --port 9444 \
  --cert ~/.local/share/quantum-flex-mycelium/mtls/client.crt \
  --key ~/.local/share/quantum-flex-mycelium/mtls/client.key \
  --ca ~/.local/share/quantum-flex-mycelium/mtls/ca.crt \
  --line "STATUS"
```

### 4.5 Tailscale Mobile Linkage & HUD
```bash
# Check Tailscale SSH and IP
tailscale status
tailscale ip -4

# Serve Mobile Sovereign HUD over Tailnet
tailscale serve --bg 9050
```

---

## 5. Strategic Roadmap (Next Phases)

| Phase | Vector | Architectural Invariant | Target Action |
| :--- | :--- | :--- | :--- |
| **Phase 3** | **$x$ (Hardware Momentum)** | Native AVX-512, VAES & GFNI silicon acceleration | Compile `liboqs` with `-DOQS_USE_AVX2=ON -DOQS_USE_AES_INSTRUCTIONS=ON` and vectorize Shamir Lagrange interpolation in `src/crypto/crypto_shamir.cpp` |
| **Phase 4** | **$h$ (Pre-Ingress Shunt)** | Kernel bypass for malformed packets | Deploy eBPF / XDP driver hook on `tailscale0` to drop/redirect non-PQC packets before socket allocation |

---

## 6. Key Documentation Assets in Repository

* [docs/OPERATOR_CHEATSHEET.md](file:///home/quant/mycelium/docs/OPERATOR_CHEATSHEET.md): Master cheatsheet detailing Stratum 0–2 architecture, unsealing ceremony, HEX benefits, and advanced hardening.
* [docs/FEDORA44_YOGA_DUAL_ROLE_HANDOFF.md](file:///home/quant/mycelium/docs/FEDORA44_YOGA_DUAL_ROLE_HANDOFF.md): Original dual-role configuration notes.
* [scripts/fedora_yoga7i_setup.sh](file:///home/quant/mycelium/scripts/fedora_yoga7i_setup.sh): Clean, idempotent Yoga 7i hardware, network, and firewall provisioning script.
* [scripts/run_route_test.sh](file:///home/quant/mycelium/scripts/run_route_test.sh): Standalone rootless Podman route and tmpfs quarantine test harness.
