# QUANTUM FLEX ARCHITECTURE v1.0
**Senior Software Executive Chief:** Rahshaun Chambers
**System Posture:** Zero-Trust, Decentralized, Rootless Podman, Native Fedora SELinux.

## 1. Core API Node (The Brain)
- **Path:** `/home/chambers/quantum_flex/api_node/`
- **Framework:** FastAPI (Python 3.11)
- **Container:** `qflex/api-node:v1` (Podman)
- **Network:** Strictly bound to `127.0.0.1:8001`. No external wildcard exposure.
- **Function:** Receives JSON `{"file_path": "..."}` payloads and triggers `run_sentinel.py`.

## 2. Sentinel Pipeline (The Muscle)
- **Path:** `/home/chambers/quantum_flex/sentinel/`
- **Permissions:** Restricted to `600` (Owner-only).
- **Container:** `qflex/sentinel:v2` (Rootless Podman, mapped with `:Z` flag).
- **Network:** `--network=none` (Complete vacuum).
- **Function:** Cryptographically identifies (SHA-256), isolates (`.isolated`), and strips DAC permissions (`000`) from payloads.

## 3. The Orchestrator
- **Path:** `/home/chambers/quantum_flex/run_sentinel.py`
- **Function:** Stages files to the airlock, aligns namespaces (`--user 0`), and detonates the Sentinel vacuum.

## 4. A.T.H.E.N.A. Loop (Goose Overseer)
- **Path:** `/home/chambers/quantum_flex/goose_overseer.sh`
- **Function:** 15-minute cron daemon that executes headless Goose to audit airlock integrity. Logs to `truth_audit.log`.

**OPERATIONAL PROTOCOL:** Before executing any commands, analyze this document to understand the current file paths, network bounds, and system architecture. Do not hallucinate paths or use Docker. We use Podman.
