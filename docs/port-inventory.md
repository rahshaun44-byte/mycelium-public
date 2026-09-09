# Local Port Inventory & Zero-Trust Exposure Matrix

## 1. Core Architectural Invariant

> **No QuantumFlex application service binds to `0.0.0.0` or the physical LAN interface unless explicitly justified and documented.**

- **Loopback (`127.0.0.1`)** = Application trust boundary (all services bind here by default).
- **Tailscale (`100.x.x.x`)** = Authenticated encrypted overlay transport plane.
- **Tailscale Serve** = Controlled publication layer for authorized remote access.
- **Physical LAN / Wi-Fi (`192.168.0.x`)** = Zero application exposure (`NO ACCESS`).
- **Internet / WAN** = Never directly reaches internal application sockets.

---

## 2. Master Node (`fedora` — Lenovo Yoga 7)

| Port | Bound IP | Protocol | Process Owner | Purpose / Exposure | Remote Access Method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `8000` | `127.0.0.1` | TCP | `uvicorn` (`amara-dashboard`) | AMARA Matrix HUD | Tailscale Serve (`:8000`) |
| `8001` | `127.0.0.1` | TCP | `uvicorn` (`athena-node`) | Athena Vector RAG Memory | Loopback only |
| `8080` | `127.0.0.1` | TCP | `uvicorn` (`api-node`) | Quantum Flex Core API Gateway | Tailscale Serve (`:8080`) |
| `8181` | `127.0.0.1` | TCP | `opa` (`opa-immune`) | Open Policy Agent evaluation | Loopback only |
| `9000` | `127.0.0.1` | TCP | `python3` (`qflex-mcp`) | Model Context Protocol SSE stream | Tailscale Serve (`:9000`) |
| `9050` | `127.0.0.1` | TCP | `python3` (`qf-bot`) | AI Teammate & Mobile PWA Host | Tailscale Serve (`:9050`) |
| `9060` | `127.0.0.1` | TCP | `python3` (`school-bot`) | Independent School Bot | Loopback only |
| `9444` | `127.0.0.1` | TCP | `quantum_flex_engine` | Primary C++ IPC Interface | Loopback only |
| `11434`| `127.0.0.1` | TCP | `ollama` | Local LLM inference engine | Loopback only |
| `5432` | `127.0.0.1` | TCP | `postgres` (`amara-matrix`) | System Datastore | Loopback only |

---

## 3. Worker Node 2 (`qflex` — HP Pavilion Desktop Tower)

| Port | Bound IP | Protocol | Process Owner | Purpose / Exposure | Remote Access Method |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `9092` | `127.0.0.1` | TCP | `docker-proxy` (`qf-kafka-broker`) | Layer 4 KRaft Kafka Broker | Tailscale Serve (`tcp:9092`) |
| `8090` | `127.0.0.1` | TCP | `docker-proxy` (`qf-kafka-ui`) | Real-time Kafka Topic UI | Tailscale Serve (`http:8090` / HTTPS 443) |
| `22`   | `127.0.0.1`, `100.64.1.34`, `192.168.100.17` | TCP | `sshd` | Secure Shell Admin Access | Interface-restricted only (No `0.0.0.0`) |
| `41641`| `0.0.0.0` | UDP | `tailscaled` | Tailscale WireGuard Transport | Mesh transport plane |

