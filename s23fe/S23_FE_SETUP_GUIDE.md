# Quantum Flex: Samsung Galaxy S23 FE Operations Guide

Complete operational guide for connecting and controlling the Quantum Flex node stack and MCP tools from your Samsung Galaxy S23 FE (`rahshauns-s23-fe` / `100.64.1.33`) over Tailscale.

---

## 1. Network Topology

| Component | Node / Device | Tailscale IP | MagicDNS Hostname | Listening Port |
| :--- | :--- | :--- | :--- | :--- |
| **Host System** | Windows PC | `100.64.1.29` | `quantumflex` | — |
| **Mobile Client** | Samsung Galaxy S23 FE | `100.64.1.33` | `rahshauns-s23-fe` | — |
| **AMARA Dashboard** | Windows Host | `100.64.1.29` | — | `8000` |
| **Athena RAG Node** | Windows Host | `127.0.0.1` | — | `8001` (proxied) |
| **API Gateway Node** | Windows Host | `100.64.1.29` | — | `8080` |
| **Quantum Flex MCP** | Windows Host | `100.64.1.29` | — | `9000` |

---

## 2. Web Access from Samsung S23 FE (Browser)

Open **Samsung Internet** or **Chrome** on your S23 FE while Tailscale is active:

1. **AMARA Intelligence Sync Dashboard**:
   - URL: **`http://100.64.1.29:8000`**
   - Features: Real-time Euclidean Drive metric ($D$), CPU/RAM/IO utilization, cryptographic integrity status, Athena RAG interactive console, and threat injection kill-switch.
2. **API Gateway Health Check**:
   - URL: **`http://100.64.1.29:8080/status`**

> [!TIP]
> In Samsung Internet or Chrome, tap **Menu -> Add page to -> Home screen** to install the AMARA Dashboard as a standalone Web App on your phone.

---

## 3. MCP Client Configuration (Termux / Claude Code / Antigravity)

To connect any mobile MCP client to your Quantum Flex host, use:

### SSE Transport (Recommended)
```json
{
  "mcpServers": {
    "quantum-flex": {
      "url": "http://100.64.1.29:9000/sse"
    }
  }
}
```

### Config File Locations on Android / Termux:
- Claude Code / CLI: `~/.claude.json` or `~/.config/claude/config.json`
- Open-WebUI / Mobile Agent: Set remote MCP server URL to `http://100.64.1.29:9000/sse`

---

## 4. Termux Quick Setup (1-Command Install)

In Termux on your S23 FE, run:

```bash
# Download and execute the automated setup script from the host
curl -s http://100.64.1.29:8080/s23fe/setup-s23fe.sh | bash
# OR copy setup-s23fe.sh directly and run:
bash setup-s23fe.sh
```

---

## 5. Mobile CLI Usage (`qf`)

After running the setup script, you have the `qf` CLI in Termux:

| Command | Description |
| :--- | :--- |
| `qf status` | Query full health of all nodes, services, and live Euclidean Drive ($D$). |
| `qf athena "<question>"` | Ask Athena RAG a question (e.g. `qf athena "What is the Euclidean Drive tolerance?"`). |
| `qf mcp` | Display MCP server endpoints and available tools. |
| `qf dash` | Print the direct AMARA Dashboard URL. |

---

## 6. Available MCP Tools Reference

When connected via MCP, the following tools are available to AI agents:

1. **`list_services`**: List status, PIDs, and active listening ports for all 6 core services.
2. **`ask_athena`**: Query the ChromaDB + Ollama RAG knowledge base.
3. **`dashboard_snapshot`**: Fetch real-time Euclidean Drive score, RAM, CPU, I/O wait, and integrity flags.
4. **`api_node_status`**: Check API Gateway health and connected nodes.
5. **`tailnet_mesh_status`**: Verify Tailscale connection and peer status for the Samsung S23 FE.
6. **`service_status`**: Inspect recent stdout and stderr logs for any service.
7. **`service_action`**: Start, stop, or restart any node service remotely.
