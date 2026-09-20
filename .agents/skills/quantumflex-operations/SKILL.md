---
name: quantumflex-operations
description: >-
  Operational procedures for QuantumFlex: Shamir 3-of-5 unsealing ceremony,
  Tailscale mesh service management, mobile node synchronization, neural Oracle
  queries, and host performance optimization.
---

# QuantumFlex Operations Playbook

This skill provides step-by-step procedures for managing and maintaining the QuantumFlex sovereign operating system.

---

## 1. Stratum 0 Engine Unsealing (Shamir 3-of-5 Ceremony)

When the C++ Evidence Engine (`quantum-flex-engine-mycelium.service`) boots, it starts in a sealed `LOCKED` posture.

### Procedure:
1. **Mount Transient USB Vault:**
   ```bash
   udisksctl mount -b /dev/sda1
   ```
2. **Execute Unlock Script with Shard Triad:**
   ```bash
   SHARD_FILES="/home/quant/qfx-shards/shard_1.txt,/home/quant/qfx-shards/shard_2.txt,/run/media/quant/QFX_VAULT/shard_3.txt" ./scripts/unlock_engine.sh
   ```
   *Expected Output:* `ACK|NODE_UNLOCKED`
3. **Enforce Airgap Media Hygiene:**
   ```bash
   udisksctl unmount -b /dev/sda1
   ```

---

## 2. Private Tailscale Mesh Service Management

QuantumFlex strictly isolates application sockets to loopback (`127.0.0.1`) and exposes authorized services inside the encrypted Tailnet via Tailscale Serve.

### Activation:
```bash
./scripts/enable_quantumflex_mesh.sh
```
*Publishes:*
- Port `8000` -> AMARA Matrix Real-Time Dashboard
- Port `8080` -> Quantum Flex Core API Gateway
- Port `9000` -> QF-Bot AI Teammates & MCP SSE Stream
- Port `443` (HTTPS) -> Mobile Cockpit Web HUD

### Endpoint Health Verification:
```bash
/home/quant/mycelium/venv/bin/python3 test_endpoints.py
```

---

## 3. Mobile Node Synchronization (QF-M1)

Deploys verified CLI, bootstrap scripts, and Cockpit APK to connected Android devices (Pixel 11 Pro, Galaxy S23 FE) over ADB with remote cryptographic SHA-256 validation.

### Inspection Only:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/sync_mobile_nodes.py
```

### Full Cryptographic Deployment:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/sync_mobile_nodes.py --push --apk
```

---

## 4. Athena Cognitive Memory & Local Oracle

Interrogates the local Athena Oracle backed by `nomic-embed-text` dense vector embeddings and `gemma2:2b` offline neural inference.

### Ingesting New Knowledge Vault Documents:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/ingest_vault.py
```

### Querying Athena Oracle:
```bash
/home/quant/mycelium/venv/bin/python3 scripts/ask_athena.py "Your prompt or inquiry here"
```

---

## 5. Host Performance & Kernel Network Optimization

Applies Google BBR congestion control, Fair Queueing `fq`, and 16MB socket buffers for Astound Broadband:
```bash
sudo /home/quant/mycelium/scripts/update_and_optimize_host.sh
```
