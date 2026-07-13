#!/usr/bin/env python3
"""
A.M.A.R.A. Sync Dashboard — Quantum Flex
==========================================
Premium real-time dashboard. Pulls live telemetry from:
  - sentinel/ledger/ledger.json (ghost-node heartbeat)
  - PostgreSQL amara-matrix (throttle events, telemetry history)
  - Athena node /health (RAG node status)
  - Ollama /api/tags (model inventory)
Port: 8000 (0.0.0.0 — Tailscale mesh accessible)
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

# ── PostgreSQL (optional — falls back gracefully) ─────────────────────────────
try:
    import psycopg2
    import psycopg2.extras
    PG_AVAILABLE = True
except ImportError:
    PG_AVAILABLE = False

PG_CONFIG = {
    "host": "127.0.0.1", "port": 5432,
    "dbname": "telemetry", "user": "ghostnode",
    "password": "quantum_flex_auth",
}

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="A.M.A.R.A. Dashboard", version="2.0.0")

LEDGER_PATH  = Path(__file__).parent.parent / "sentinel/ledger/ledger.json"
ATHENA_URL   = "http://127.0.0.1:8001"
OLLAMA_URL   = "http://127.0.0.1:11434"
API_NODE_URL = "http://127.0.0.1:8002"


# ── Data helpers ──────────────────────────────────────────────────────────────
def read_ledger() -> dict:
    if not LEDGER_PATH.exists():
        return {"status": "NO_DATA", "message": "Ghost Node ledger not found"}
    try:
        with open(LEDGER_PATH) as f:
            return json.load(f)
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}


def get_pg_history(limit: int = 10) -> list:
    if not PG_AVAILABLE:
        return []
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT timestamp, iowait_pct, ram_used_pct, swap_used_mb,
                   cpu_load_1m, status
            FROM telemetry_log
            ORDER BY timestamp DESC LIMIT %s
        """, (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception:
        return []


def get_throttle_events(limit: int = 5) -> list:
    if not PG_AVAILABLE:
        return []
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        cur  = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT timestamp, trigger_metric, trigger_value,
                   threshold, action, result
            FROM throttle_events
            ORDER BY timestamp DESC LIMIT %s
        """, (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception:
        return []


async def probe_athena() -> dict:
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{ATHENA_URL}/health")
            return r.json()
    except Exception as e:
        return {"status": "OFFLINE", "error": str(e)}


async def probe_ollama() -> dict:
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            r = await c.get(f"{OLLAMA_URL}/api/tags")
            models = [m["name"] for m in r.json().get("models", [])]
            return {"status": "ONLINE", "models": models}
    except Exception as e:
        return {"status": "OFFLINE", "error": str(e)}


# ── API endpoints ─────────────────────────────────────────────────────────────
@app.get("/api/telemetry")
async def get_telemetry():
    ledger  = read_ledger()
    athena  = await probe_athena()
    ollama  = await probe_ollama()
    history = get_pg_history(10)
    throttle = get_throttle_events(5)
    return {
        "ledger":          ledger,
        "athena":          athena,
        "ollama":          ollama,
        "telemetry_history": history,
        "throttle_events": throttle,
        "timestamp":       datetime.now().isoformat(),
    }


@app.post("/api/query")
async def proxy_query(request: Request):
    """Proxy a RAG query to Athena from the dashboard."""
    data = await request.json()
    try:
        async with httpx.AsyncClient(timeout=120.0) as c:
            r = await c.post(f"{ATHENA_URL}/query", json=data)
            return r.json()
    except Exception as e:
        return JSONResponse(status_code=503, content={"error": str(e)})


# ── Premium HTML dashboard ────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    ledger   = read_ledger()
    athena   = await probe_athena()
    ollama   = await probe_ollama()
    history  = get_pg_history(8)
    throttle = get_throttle_events(5)

    # Extract live metrics
    tel = ledger.get("telemetry", {})
    iowait   = tel.get("iowait_pct", "—")
    ram_pct  = tel.get("ram_used_pct", "—")
    swap_mb  = tel.get("swap_used_mb", "—")
    load_1m  = tel.get("cpu_load_1m", "—")
    status   = ledger.get("status", "UNKNOWN")
    conf     = ledger.get("confidence", 0)
    ts       = ledger.get("timestamp", "—")
    alerts   = ledger.get("alerts", [])

    athena_status = athena.get("status", "OFFLINE")
    athena_vecs   = athena.get("vector_count", "—")
    ollama_status = ollama.get("status", "OFFLINE")
    ollama_models = ", ".join(ollama.get("models", [])) or "none"

    status_color = {
        "OPTIMAL":  "#00ff88",
        "WARNING":  "#ffcc00",
        "CRITICAL": "#ff4444",
    }.get(status, "#888888")

    athena_color = "#00ff88" if athena_status == "ONLINE" else "#ff4444"
    ollama_color = "#00ff88" if ollama_status == "ONLINE" else "#ff4444"

    # Build telemetry history rows
    history_rows = ""
    for row in history:
        s = row.get("status", "")
        sc = {"OPTIMAL": "#00ff88", "WARNING": "#ffcc00", "CRITICAL": "#ff4444"}.get(s, "#888")
        ts_short = str(row.get("timestamp", ""))[:19]
        history_rows += f"""
        <tr>
          <td>{ts_short}</td>
          <td>{row.get('iowait_pct', '—')}%</td>
          <td>{row.get('ram_used_pct', '—')}%</td>
          <td>{row.get('swap_used_mb', '—')} MB</td>
          <td>{row.get('cpu_load_1m', '—')}</td>
          <td style="color:{sc};font-weight:bold">{s}</td>
        </tr>"""

    # Build throttle events
    throttle_rows = ""
    for ev in throttle:
        ts_short = str(ev.get("timestamp", ""))[:19]
        action_color = "#ff4444" if ev.get("action") == "pause" else "#00ff88"
        throttle_rows += f"""
        <tr>
          <td>{ts_short}</td>
          <td>{ev.get('trigger_metric', '—')}</td>
          <td>{ev.get('trigger_value', '—')}</td>
          <td>{ev.get('threshold', '—')}</td>
          <td style="color:{action_color};font-weight:bold">{ev.get('action','—').upper()}</td>
          <td>{ev.get('result', '—')[:40]}</td>
        </tr>"""

    alerts_html = ""
    for a in alerts:
        alerts_html += f'<div class="alert-item">{a}</div>'
    if not alerts_html:
        alerts_html = '<div class="alert-item ok">No active alerts</div>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <meta name="description" content="A.M.A.R.A. Quantum Flex Infrastructure Dashboard — Live node telemetry and RAG interface"/>
  <title>A.M.A.R.A. | Quantum Flex</title>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet"/>
  <style>
    :root {{
      --bg-primary:   #080c14;
      --bg-card:      #0d1422;
      --bg-card2:     #111927;
      --accent:       #00e5ff;
      --accent2:      #7c3aed;
      --green:        #00ff88;
      --yellow:       #ffcc00;
      --red:          #ff4444;
      --text:         #e2e8f0;
      --text-muted:   #64748b;
      --border:       #1e2d40;
      --glow:         0 0 20px rgba(0,229,255,0.15);
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', sans-serif;
      background: var(--bg-primary);
      color: var(--text);
      min-height: 100vh;
      overflow-x: hidden;
    }}
    /* Animated background grid */
    body::before {{
      content: '';
      position: fixed;
      inset: 0;
      background-image:
        linear-gradient(rgba(0,229,255,0.03) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,229,255,0.03) 1px, transparent 1px);
      background-size: 40px 40px;
      pointer-events: none;
      z-index: 0;
    }}
    .container {{ position: relative; z-index: 1; max-width: 1400px; margin: 0 auto; padding: 24px; }}

    /* Header */
    .header {{
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 32px; padding: 24px 32px;
      background: linear-gradient(135deg, rgba(0,229,255,0.08), rgba(124,58,237,0.08));
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: var(--glow);
    }}
    .header-left h1 {{
      font-size: 1.8rem; font-weight: 700; letter-spacing: -0.02em;
      background: linear-gradient(135deg, var(--accent), var(--accent2));
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
    .header-left .subtitle {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;
    }}
    .header-right .last-sync {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.7rem; color: var(--text-muted); text-align: right;
    }}
    .live-dot {{
      display: inline-block; width: 8px; height: 8px;
      background: var(--green); border-radius: 50%;
      margin-right: 6px;
      animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 1; box-shadow: 0 0 0 0 rgba(0,255,136,0.4); }}
      50% {{ opacity: 0.8; box-shadow: 0 0 0 6px rgba(0,255,136,0); }}
    }}

    /* Status banner */
    .status-banner {{
      display: flex; align-items: center; justify-content: space-between;
      padding: 20px 32px; margin-bottom: 24px;
      border-radius: 12px; border: 1px solid var(--border);
      background: var(--bg-card);
    }}
    .status-main {{
      display: flex; align-items: center; gap: 16px;
    }}
    .status-badge {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 1.1rem; font-weight: 700;
      padding: 8px 20px; border-radius: 8px;
      border: 1px solid currentColor;
    }}
    .confidence-bar-wrap {{ flex: 1; max-width: 300px; }}
    .confidence-label {{
      font-size: 0.75rem; color: var(--text-muted);
      margin-bottom: 6px; font-family: 'JetBrains Mono', monospace;
    }}
    .confidence-bar {{
      height: 8px; background: #1e2d40; border-radius: 4px; overflow: hidden;
    }}
    .confidence-fill {{
      height: 100%;
      background: linear-gradient(90deg, var(--accent2), var(--accent));
      border-radius: 4px;
      transition: width 1s ease;
    }}

    /* Metric cards grid */
    .metrics-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 16px; margin-bottom: 24px;
    }}
    .metric-card {{
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 12px; padding: 20px;
      transition: transform 0.2s, box-shadow 0.2s;
      position: relative; overflow: hidden;
    }}
    .metric-card::before {{
      content: ''; position: absolute;
      top: 0; left: 0; right: 0; height: 2px;
      background: linear-gradient(90deg, var(--accent), var(--accent2));
    }}
    .metric-card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 8px 32px rgba(0,229,255,0.1);
    }}
    .metric-label {{
      font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em;
      color: var(--text-muted); margin-bottom: 8px;
    }}
    .metric-value {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 2rem; font-weight: 700;
      background: linear-gradient(135deg, #fff, var(--accent));
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }}
    .metric-unit {{
      font-size: 0.8rem; color: var(--text-muted);
      font-family: 'JetBrains Mono', monospace;
    }}

    /* Node status row */
    .nodes-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 16px; margin-bottom: 24px;
    }}
    .node-card {{
      background: var(--bg-card); border: 1px solid var(--border);
      border-radius: 12px; padding: 18px;
      display: flex; align-items: center; gap: 14px;
    }}
    .node-icon {{
      width: 40px; height: 40px; border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-size: 1.2rem;
      background: rgba(0,229,255,0.1);
    }}
    .node-info .node-name {{
      font-weight: 600; font-size: 0.9rem; margin-bottom: 4px;
    }}
    .node-info .node-detail {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.7rem; color: var(--text-muted);
    }}
    .node-status-dot {{
      margin-left: auto; width: 10px; height: 10px;
      border-radius: 50%;
    }}

    /* Tables */
    .section-header {{
      font-size: 0.75rem; text-transform: uppercase;
      letter-spacing: 0.12em; color: var(--text-muted);
      margin-bottom: 12px; font-weight: 600;
    }}
    .card {{
      background: var(--bg-card); border: 1px solid var(--border);
      border-radius: 12px; padding: 20px; margin-bottom: 20px;
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.65rem; text-transform: uppercase;
      letter-spacing: 0.08em; color: var(--text-muted);
      padding: 8px 12px; text-align: left;
      border-bottom: 1px solid var(--border);
    }}
    td {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem; padding: 10px 12px;
      border-bottom: 1px solid rgba(30,45,64,0.6);
      color: var(--text);
    }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: rgba(0,229,255,0.03); }}

    /* Alerts */
    .alerts-box {{ margin-bottom: 20px; }}
    .alert-item {{
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.75rem; padding: 10px 14px;
      margin-bottom: 6px; border-radius: 8px;
      border-left: 3px solid var(--red);
      background: rgba(255,68,68,0.07);
      color: #fca5a5;
    }}
    .alert-item.ok {{
      border-left-color: var(--green);
      background: rgba(0,255,136,0.05);
      color: var(--green);
    }}

    /* RAG query box */
    .query-box {{
      background: var(--bg-card); border: 1px solid var(--border);
      border-radius: 12px; padding: 20px; margin-bottom: 20px;
    }}
    .query-input-row {{
      display: flex; gap: 12px; margin-top: 12px;
    }}
    #rag-input {{
      flex: 1; background: var(--bg-card2);
      border: 1px solid var(--border); border-radius: 8px;
      padding: 12px 16px; color: var(--text);
      font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;
      outline: none;
    }}
    #rag-input:focus {{ border-color: var(--accent); }}
    #rag-btn {{
      padding: 12px 24px; border-radius: 8px; border: none; cursor: pointer;
      background: linear-gradient(135deg, var(--accent2), var(--accent));
      color: #fff; font-weight: 600; font-size: 0.85rem;
      transition: opacity 0.2s;
    }}
    #rag-btn:hover {{ opacity: 0.85; }}
    #rag-btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
    #rag-output {{
      margin-top: 14px; padding: 14px;
      background: var(--bg-primary); border-radius: 8px;
      font-family: 'JetBrains Mono', monospace; font-size: 0.8rem;
      color: var(--green); min-height: 60px; white-space: pre-wrap;
      display: none;
    }}

    /* Two-column layout */
    .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
    @media (max-width: 900px) {{ .two-col {{ grid-template-columns: 1fr; }} }}

    .footer {{
      text-align: center; padding: 24px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 0.65rem; color: var(--text-muted);
      border-top: 1px solid var(--border); margin-top: 12px;
    }}
  </style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="header">
    <div class="header-left">
      <h1>A.M.A.R.A. Intelligence Sync</h1>
      <div class="subtitle">Quantum Flex / Ghost Node Telemetry — Rahshaun Chambers</div>
    </div>
    <div class="header-right">
      <div class="last-sync"><span class="live-dot"></span>LIVE</div>
      <div class="last-sync" style="margin-top:4px">Last sync: {ts[:19]}</div>
      <div class="last-sync" style="margin-top:4px">Substrate: Fedora 44 · AMD Ryzen AI 5 340</div>
    </div>
  </div>

  <!-- Status Banner -->
  <div class="status-banner">
    <div class="status-main">
      <div class="status-badge" style="color:{status_color};border-color:{status_color}">
        {status}
      </div>
      <div>
        <div style="font-size:0.8rem;color:var(--text-muted)">System Decision Gate</div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.85rem;margin-top:2px">
          Confidence: <span style="color:{status_color}">{conf:.2f}</span>
        </div>
      </div>
    </div>
    <div class="confidence-bar-wrap">
      <div class="confidence-label">CONFIDENCE SCORE — {conf*100:.0f}%</div>
      <div class="confidence-bar">
        <div class="confidence-fill" style="width:{conf*100:.0f}%"></div>
      </div>
    </div>
  </div>

  <!-- Live Metrics -->
  <p class="section-header">Live Kernel Telemetry</p>
  <div class="metrics-grid">
    <div class="metric-card">
      <div class="metric-label">I/O Wait</div>
      <div class="metric-value">{iowait}</div>
      <div class="metric-unit">% — dissolved oxygen level</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">RAM Pressure</div>
      <div class="metric-value">{ram_pct}</div>
      <div class="metric-unit">% of 14 GiB</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Swap Used</div>
      <div class="metric-value">{swap_mb}</div>
      <div class="metric-unit">MB of 8 GiB</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">CPU Load (1m)</div>
      <div class="metric-value">{load_1m}</div>
      <div class="metric-unit">of 12 logical cores</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Athena Vectors</div>
      <div class="metric-value">{athena_vecs}</div>
      <div class="metric-unit">ChromaDB collection</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Ollama Models</div>
      <div class="metric-value" style="font-size:0.9rem;padding-top:8px">{ollama_models}</div>
      <div class="metric-unit">loaded inference engines</div>
    </div>
  </div>

  <!-- Node Status -->
  <p class="section-header">Node Registry</p>
  <div class="nodes-grid">
    <div class="node-card">
      <div class="node-icon">🔬</div>
      <div class="node-info">
        <div class="node-name">Ghost Node Agent</div>
        <div class="node-detail">decision_gate.py · PID active</div>
      </div>
      <div class="node-status-dot" style="background:var(--green)"></div>
    </div>
    <div class="node-card">
      <div class="node-icon">📊</div>
      <div class="node-info">
        <div class="node-name">A.M.A.R.A. Dashboard</div>
        <div class="node-detail">port 8000 · uvicorn</div>
      </div>
      <div class="node-status-dot" style="background:var(--green)"></div>
    </div>
    <div class="node-card">
      <div class="node-icon">🧠</div>
      <div class="node-info">
        <div class="node-name">A.T.H.E.N.A. RAG Node</div>
        <div class="node-detail">port 8001 · ChromaDB · {athena_status}</div>
      </div>
      <div class="node-status-dot" style="background:{athena_color}"></div>
    </div>
    <div class="node-card">
      <div class="node-icon">🗄️</div>
      <div class="node-info">
        <div class="node-name">amara-matrix</div>
        <div class="node-detail">PostgreSQL 15 · Truth Log</div>
      </div>
      <div class="node-status-dot" style="background:{'var(--green)' if PG_AVAILABLE else 'var(--yellow)'}"></div>
    </div>
    <div class="node-card">
      <div class="node-icon">⚡</div>
      <div class="node-info">
        <div class="node-name">Ollama Inference</div>
        <div class="node-detail">port 11434 · {ollama_status}</div>
      </div>
      <div class="node-status-dot" style="background:{ollama_color}"></div>
    </div>
    <div class="node-card">
      <div class="node-icon">🛡️</div>
      <div class="node-info">
        <div class="node-name">Sentinel Pipeline</div>
        <div class="node-detail">quarantine_chamber.py · podman</div>
      </div>
      <div class="node-status-dot" style="background:var(--green)"></div>
    </div>
  </div>

  <!-- Active Alerts -->
  <p class="section-header">Active Alerts</p>
  <div class="alerts-box">{alerts_html}</div>

  <!-- Athena RAG Query -->
  <div class="query-box">
    <p class="section-header">A.T.H.E.N.A. RAG Query Interface</p>
    <div style="font-size:0.8rem;color:var(--text-muted)">
      Query the Athena cognitive node directly. Searches ChromaDB knowledge base.
    </div>
    <div class="query-input-row">
      <input id="rag-input" type="text"
        placeholder="Ask Athena anything about Quantum Flex..."
        onkeydown="if(event.key==='Enter')submitQuery()"/>
      <button id="rag-btn" onclick="submitQuery()">Query Athena</button>
    </div>
    <pre id="rag-output"></pre>
  </div>

  <!-- Two-column tables -->
  <div class="two-col">
    <div>
      <p class="section-header">Telemetry History (PostgreSQL)</p>
      <div class="card">
        <table>
          <thead>
            <tr>
              <th>Timestamp</th><th>iowait</th><th>RAM</th>
              <th>Swap</th><th>Load</th><th>Status</th>
            </tr>
          </thead>
          <tbody>
            {history_rows if history_rows else '<tr><td colspan="6" style="color:var(--text-muted);text-align:center">No data yet — qf-monitor starting</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
    <div>
      <p class="section-header">Throttle Events (AMARA Reflexes)</p>
      <div class="card">
        <table>
          <thead>
            <tr>
              <th>Time</th><th>Metric</th><th>Value</th>
              <th>Thresh</th><th>Action</th><th>Result</th>
            </tr>
          </thead>
          <tbody>
            {throttle_rows if throttle_rows else '<tr><td colspan="6" style="color:var(--text-muted);text-align:center">No throttle events — environment stable</td></tr>'}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Raw Ledger -->
  <p class="section-header">Raw Ledger State</p>
  <div class="card">
    <pre style="font-family:'JetBrains Mono',monospace;font-size:0.72rem;color:var(--accent);white-space:pre-wrap">{json.dumps(ledger, indent=2, default=str)}</pre>
  </div>

  <div class="footer">
    A.M.A.R.A. Agentic Framework v2.0 · Quantum Flex Infrastructure · Zero-Trust · Rootless Podman · Fedora 44 SELinux
  </div>
</div>

<script>
  // Auto-refresh every 30 seconds
  setTimeout(() => location.reload(), 30000);

  async function submitQuery() {{
    const input = document.getElementById('rag-input');
    const btn   = document.getElementById('rag-btn');
    const out   = document.getElementById('rag-output');
    const q = input.value.trim();
    if (!q) return;

    btn.disabled = true;
    btn.textContent = 'Querying...';
    out.style.display = 'block';
    out.textContent = '[ATHENA] Processing RAG query...';

    try {{
      const res = await fetch('/api/query', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{question: q}})
      }});
      const data = await res.json();
      if (data.error) {{
        out.textContent = '[ERROR] ' + data.error;
      }} else {{
        out.textContent = '[ANSWER]\\n' + data.answer +
          '\\n\\n[SOURCES] ' + (data.sources || []).join(', ') +
          '\\n[MODEL] ' + data.model +
          '\\n[VECTORS] ' + data.vectors;
      }}
    }} catch(e) {{
      out.textContent = '[OFFLINE] Athena node unavailable: ' + e;
    }}

    btn.disabled = false;
    btn.textContent = 'Query Athena';
  }}
</script>
</body>
</html>"""
    return html


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("dashboard:app", host="0.0.0.0", port=8000, reload=True)
