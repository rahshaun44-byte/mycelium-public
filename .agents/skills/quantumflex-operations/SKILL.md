---
name: quantumflex-operations
description: >-
  Operational procedures for QuantumFlex: Stratum 0 Shamir 3-of-5 unsealing ceremony,
  systemd stack lifecycle, dual Postgres routing, Tailscale private mesh, C++ engine builds,
  and host kernel performance tuning.
---

# QuantumFlex Core Operations Playbook

This skill provides operational procedures for managing, maintaining, and inspecting the core QuantumFlex sovereign operating system stack.

---

## 1. Stratum 0 Engine Verification & Epoch-1 Direct-to-Active State

With the Epoch-1 Sovereign Genesis Reboot, legacy Shamir Secret Sharing (SSS) ceremony overhead has been permanently tombstoned in `evidence_ledger.jsonl`. The C++ Evidence Engine (`quantum_flex_engine`) boots directly into the `ACTIVE` posture authenticated against the local Microsoft Pluton TPM 2.0 hardware anchor and local OPA policy (`127.0.0.1:8181`).

### Verification Procedure:
1. Verify the engine state transitioned directly to `ACTIVE`:
   ```bash
   tail -n 15 /home/quant/.local/state/quantum-flex-mycelium/engine.log
   ```
   *Expected:* `[+] Ledger authenticated on Pluton TPM 2.0 host. Engine is ACTIVE.`
2. Verify mTLS TCP socket listening:
   ```bash
   ss -tulpn | grep 9444
   ```
   *Expected:* Listening on `127.0.0.1:9444` (pid of `quantum_flex_engine`).
3. (Historical Reference) The legacy SSS ceremony scripts and tests have been archived in `/home/quant/mycelium/archive/legacy_ceremony/`.

---

## 2. Systemd Service Stack Management

QuantumFlex services run as systemd **user** services under `~/.config/systemd/user/`.

### Checking Stack Status:
```bash
systemctl --user status quantum-flex-engine-mycelium.service witness.service ghost-sink.service amara-dashboard.service athena-node.service qf-monitor.service
```

### Starting the Core Stack:
```bash
systemctl --user start quantum-flex-engine-mycelium.service witness.service ghost-sink.service
```

### Restarting the Dashboard & Monitoring:
```bash
systemctl --user restart amara-dashboard.service qf-monitor.service
```

---

## 3. Dual Postgres Backend Verification

QuantumFlex isolates application memory into two distinct Postgres instances:
1. **Native Postgres (`127.0.0.1:5432`, DB `telemetry`)**: Used by Sentinel, MCP layer, and task swarm.
   ```bash
   pg_isready -h 127.0.0.1 -p 5432 -d telemetry
   ```
2. **Podman Logistics Postgres (`127.0.0.1:5433`, DB `amara_matrix`)**: Used exclusively by the C++ engine (`BaeNode`).
   ```bash
   podman ps --filter name=logistics-pg
   pg_isready -h 127.0.0.1 -p 5433 -d amara_matrix
   ```

---

## 4. Private Tailscale Mesh Management

All QuantumFlex services bind to loopback (`127.0.0.1`) and are routed inside the private encrypted Tailnet via Tailscale Serve.

### Enabling the Mesh:
```bash
./scripts/enable_quantumflex_mesh.sh
```
*Published Endpoints:*
- `8000` -> AMARA Matrix Real-Time Dashboard
- `8080` -> Quantum Flex Core API Gateway
- `9000` -> QF-Bot AI Teammates & MCP SSE Stream
- `443` (HTTPS) -> Mobile Cockpit Web HUD

### Verifying Endpoint Health:
```bash
/home/quant/mycelium/venv/bin/python3 test_endpoints.py
```

---

## 5. C++ Engine Compilation & Verification

To build the native C++20 evidence engine and sentinel push binaries:
```bash
cmake -S . -B build_check -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build_check -j"$(nproc)"
```
*Output Binaries:* `build_check/quantum_flex_engine`, `build_check/sentinel_push`.

---

## 6. Host Performance & Kernel Network Optimization

Applies Google BBR congestion control, Fair Queueing `fq`, and 16MB socket buffers:
```bash
sudo /home/quant/mycelium/scripts/update_and_optimize_host.sh
```
