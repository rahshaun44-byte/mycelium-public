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

## 1. Stratum 0 Engine Unsealing (Shamir 3-of-5 Ceremony)

When the C++ Evidence Engine boots, it starts in a sealed `LOCKED` posture requiring a 3-of-5 threshold of cryptographic shards.

### Unlock Procedure:
1. Ensure the 3 required shard files are present (with permissions `0600`):
   ```bash
   chmod 600 ~/qfx-shards/shard_1.txt ~/qfx-shards/shard_2.txt
   ```
2. Execute the unseal script:
   ```bash
   cd /home/quant/mycelium && SHARD_FILES="$HOME/qfx-shards/shard_1.txt,$HOME/qfx-shards/shard_2.txt,$HOME/qfx-shards/shard_3.txt" ./scripts/unlock_engine.sh
   ```
3. Verify the engine state transitioned to `ACTIVE`:
   ```bash
   tail -n 15 /home/quant/.local/state/quantum-flex-mycelium/engine.log
   ```
   *Expected:* `[+] Node Unlocked. Superposition collapsed into ACTIVE state.`
4. Securely destroy any temporary memorized shard file:
   ```bash
   shred -u ~/qfx-shards/shard_3.txt
   ```

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
