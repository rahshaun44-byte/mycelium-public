# QUANTUM FLEX ARCHITECTURE v2.0 (The Swarm)
**Senior Software Executive Chief:** Rahshaun Chambers
**System Posture:** Zero-Trust, Decentralized, Rootless Podman, Native Fedora SELinux.

## 1. Ghost Node (The Nervous System)
- **Path:** `/home/USERNAME/mycelium/mcp_layer/`
- **Function:** The capture gateway for raw telemetry. It actively monitors `/proc`, `vmstat`, and kernel metrics, funneling the raw system noise into the matrix for upstream analysis.

## 2. A.M.A.R.A. Matrix & Task Queue (The Truth Log)
- **Container:** `amara-matrix` (Rootless Podman, `postgres:15-alpine`)
- **Port:** `127.0.0.1:5432`
- **Security Constraint:** Locked to a strict 2GB memory bound (`podman update --memory 2g`).
- **Function:** Houses the `telemetry_log`, `task_queue` (SKIP LOCKED for concurrent worker safety), and `memory_logs` (pgvector semantic cache).

## 3. Sentinel: Euclidean Drive Monitor (The Homeostatic Reflex)
- **Path:** `/home/USERNAME/mycelium/sentinel/sentinel.py`
- **Service:** `sentinel-drive.service` (Systemd User Daemon)
- **Mathematical Bound:** $D = \sqrt{\sum_{i=1}^{4} (Sc_i - Sb_i)^2}$
- **Variables:** $V_1$ (Memory), $V_2$ (CPU), $V_3$ (I/O Wait), $V_4$ (Cryptographic Integrity Penalty).
- **Function:** If $D$ exceeds the 1500 tolerance threshold, Sentinel executes a Hardstop (`SIGSTOP`) on the deviant container and logs the lockdown to the Truth Log.

## 4. A.T.H.E.N.A. Cognitive Node (The Mind)
- **Service:** `athena-node.service` (Systemd User Daemon)
- **Port:** `127.0.0.1:8001`
- **Model:** `gemma2:2b` / `gemma2:9b` (Ollama)
- **Function:** Local RAG interface housing the persistent Knowledge Base via ChromaDB, bound by the System Truth Directive.

## 5. Remote Ledger Push (The Sync Protocol)
- **Function:** Automated Truth Log replication across the encrypted Tailscale mesh.
- **Protocol:** Configuration drift and architecture manifests are tracked via local Git. Upon verified system state modification, a deterministic commit is generated and pushed to the remote decentralized ledger (Git over Tailscale SSH), ensuring the swarm's memory is backed up off-node securely without public internet exposure.

**OPERATIONAL PROTOCOL:** Before executing commands, read this document. Do not hallucinate paths or use Docker. We use rootless Podman and Systemd user services (`loginctl enable-linger`).
