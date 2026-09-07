# Local Port Inventory & Security Exposure

| Port | Bound IP | Protocol | Process Owner | Purpose / Exposure |
| :--- | :--- | :--- | :--- | :--- |
| `9444` | `127.0.0.1` | TCP | `quantum_flex_engine` (PID 43567) | Primary IPC interface. Local only. |
| `8181` | `127.0.0.1` | TCP | `opa` | Open Policy Agent evaluation. Local only. |
| `11434` | `127.0.0.1` | TCP | `ollama` | Local LLM inference engine. Local only. |
| `5432` | `127.0.0.1` | TCP | `postgres` | Datastore. Local only. |
| `9000` | `127.0.0.1` | TCP | `python3` | MCP/Bot engine interface. Local only. |
| `5355` | `0.0.0.0` | TCP/UDP | `systemd-resolved` (assumed) | LLMNR. Local network exposure. |
| `27500` | `0.0.0.0` | TCP | `passimd` (root) | Fedora local caching server. Benign. |
| `36479` | `100.64.1.17` | TCP | `tailscaled` | Tailscale VPN listener. Encrypted mesh exposure. |

