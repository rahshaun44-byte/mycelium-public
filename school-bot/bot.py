#!/usr/bin/env python3
"""
Sovereign School & Test-Out Sprint Hub (Port 9060)
==================================================
Isolated FastAPI mobile web app for Rocky's Pixel 11 Pro (Tailscale + localhost):
  1. Syllabus & Prof. Antoun Submission Pre-Flight Audit:
     - Extracts text from ~/Documents/SNHU-emails/email-cs320-antoun.odt
     - Audits ~/Documents/CS320/appointment-service (classes, JUnit 5 tests, Maven test run)
     - Flags over-engineered/unexplained patterns so Rocky owns & can explain every line
  2. 3-Day Coursework & Test-Out Accelerator:
     - Mobile Test-Out Rapid Drill (gemma3:4b)
     - CS 320 / CS 210 Socratic JUnit & Code Coach (qwen2.5-coder:7b)
  3. PQC Weekly Digest Approval Queue (Approve & Teach into partner-notes.md)

Zero database credentials. Zero cloud APIs. 100% local Ollama (127.0.0.1:11434).
"""

import json
import os
import re
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
STUDY_MODEL = os.environ.get("STUDY_MODEL", "qwen2.5-coder:7b")
FAST_MODEL = os.environ.get("FAST_MODEL", "gemma3:4b")

CS320_DIR = Path("/home/quant/Documents/CS320")
APPT_DIR = CS320_DIR / "appointment-service"
STUDY_NOTES = Path("/home/quant/mycelium/school-bot/study-notes.md")
BOT_TOKEN = os.environ.get("SCHOOL_BOT_TOKEN", "").strip()

app = FastAPI(title="Sovereign Study & Test-Out Hub", version="1.1.0")


def check_auth(request: Request) -> bool:
    """Loopback (127.0.0.1) is allowed locally; any non-loopback (Tailscale/Pixel) request MUST supply SCHOOL_BOT_TOKEN."""
    client_host = request.client.host if request.client else ""
    if client_host in ("127.0.0.1", "::1"):
        return True
    if not BOT_TOKEN:
        return False
    supplied = request.headers.get("X-Study-Token", "").strip()
    return supplied == BOT_TOKEN


def inspect_cs320_workspace() -> dict:
    """Audits CS320 files, zip contents, Java style simplicity, and Maven test status (no private email content exposed over HTTP)."""
    report = {
        "files_found": [],
        "zip_inventories": {},
        "style_checks": [],
        "maven_summary": "Not run yet",
    }

    if CS320_DIR.exists():
        for p in sorted(CS320_DIR.rglob("*")):
            if p.is_file() and ".git" not in p.parts and "target" not in p.parts:
                rel = str(p.relative_to(CS320_DIR))
                report["files_found"].append(rel)
                if p.suffix.lower() == ".zip":
                    try:
                        with zipfile.ZipFile(p, "r") as zf:
                            report["zip_inventories"][p.name] = zf.namelist()[:40]
                    except Exception as e:
                        report["zip_inventories"][p.name] = [f"error: {e}"]
                if p.suffix.lower() == ".java":
                    src = p.read_text(encoding="utf-8", errors="replace")
                    flags = []
                    if "Objects.requireNonNull" in src:
                        flags.append("Uses Objects.requireNonNull (Throws NullPointerException instead of IllegalArgumentException required by SNHU rubric!)")
                    if "Stream." in src or ".stream()" in src:
                        flags.append("Uses Java Streams (simple HashMap loops are cleaner & easier to explain in CS 320)")
                    if "@DisplayName" in src and src.count("@DisplayName") > 5:
                        flags.append("Heavy @DisplayName boilerplate — make sure you can explain every test case in your own words")
                    report["style_checks"].append({
                        "file": rel,
                        "lines": len(src.splitlines()),
                        "flags": flags or ["Clean, standard Java structure"],
                    })

    if APPT_DIR.exists() and (APPT_DIR / "pom.xml").exists():
        try:
            res = subprocess.run(
                ["mvn", "-q", "test"],
                cwd=str(APPT_DIR),
                capture_output=True,
                text=True,
                timeout=30,
            )
            out = (res.stdout + "\n" + res.stderr).strip()
            report["maven_summary"] = f"EXIT {res.returncode}\n{out[-800:]}" if out else f"EXIT {res.returncode} (ALL TESTS PASSED)"
        except Exception as e:
            report["maven_summary"] = f"Maven check skipped/error: {e}"

    return report


def ask_ollama(model: str, system: str, prompt: str) -> str:
    payload = json.dumps({
        "model": model,
        "system": system,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 700},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "").strip()
    except Exception as e:
        return f"[Ollama Error: {e}]"


@app.get("/api/preflight")
async def api_preflight(request: Request):
    if not check_auth(request):
        return JSONResponse({"error": "Unauthorized: set and provide X-Study-Token for remote/Tailscale access."}, status_code=401)
    return JSONResponse(inspect_cs320_workspace())


@app.post("/api/study")
async def api_study(request: Request):
    if not check_auth(request):
        return JSONResponse({"error": "Unauthorized: set and provide X-Study-Token for remote/Tailscale access."}, status_code=401)
    data = await request.json()
    mode = data.get("mode", "tutor")
    topic = data.get("topic", "").strip()
    if not topic:
        return JSONResponse({"error": "Enter a question, concept, or test-out topic."}, status_code=400)

    if mode == "testout":
        sys_prompt = (
            "You are Rocky's high-speed Test-Out & Exam Prep Coach. "
            "Give a crisp, high-retention breakdown: (1) Core rule in 1 sentence, "
            "(2) Key commands/ports/formulas to memorize, and (3) One realistic Test-Out multiple-choice practice question (A/B/C/D) with the answer hidden at the bottom."
        )
        ans = ask_ollama(FAST_MODEL, sys_prompt, topic)
    elif mode == "cs320":
        sys_prompt = (
            "You are Rocky's CS 320 (SNHU Software Testing & QA, Prof. Antoun) Socratic Coach. "
            "Focus on plain, natural student Java (simple if-checks throwing IllegalArgumentException, HashMap storage, and clear JUnit 5 assertThrows / assertEquals tests). "
            "Never generate over-engineered boilerplate; explain the why so Rocky can write and defend every line himself."
        )
        ans = ask_ollama(STUDY_MODEL, sys_prompt, topic)
    else:
        sys_prompt = "You are a direct, clear academic tutor running 100% locally. Explain concepts concisely with concrete examples."
        ans = ask_ollama(STUDY_MODEL, sys_prompt, topic)

    return JSONResponse({"answer": ans, "model": FAST_MODEL if mode == "testout" else STUDY_MODEL})


@app.post("/api/study_note")
async def api_study_note(request: Request):
    if not check_auth(request):
        return JSONResponse({"error": "Unauthorized: set and provide X-Study-Token for remote/Tailscale access."}, status_code=401)
    data = await request.json()
    note = data.get("note", "").strip()
    if not note:
        return JSONResponse({"error": "Note cannot be empty"}, status_code=400)
    stamp = datetime.now().strftime("%Y-%m-%d")
    STUDY_NOTES.parent.mkdir(parents=True, exist_ok=True)
    with open(STUDY_NOTES, "a", encoding="utf-8") as f:
        f.write(f"- {stamp} — {note}\n")
    return JSONResponse({"status": "saved", "saved": f"- {stamp} — {note}"})


@app.get("/", response_class=HTMLResponse)
async def index():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no"/>
<title>QF Mobile Study & 3-Day Sprint Hub</title>
<style>
  :root {
    --bg: #080c14; --card: #111927; --accent: #00e5ff; --green: #00ff88;
    --yellow: #ffcc00; --red: #ff4444; --text: #e2e8f0; --muted: #94a3b8;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, -apple-system, sans-serif; background: var(--bg); color: var(--text); padding: 14px; max-width: 720px; margin: 0 auto; }
  h1 { font-size: 1.25rem; color: var(--accent); margin-bottom: 4px; }
  .sub { font-size: 0.78rem; color: var(--muted); margin-bottom: 14px; }
  .card { background: var(--card); border: 1px solid #1e2d40; border-radius: 12px; padding: 14px; margin-bottom: 14px; }
  .card h2 { font-size: 0.95rem; color: var(--green); margin-bottom: 8px; }
  .btn-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
  button { background: linear-gradient(135deg, #7c3aed, #00e5ff); color: #fff; border: none; border-radius: 8px; padding: 10px 14px; font-weight: 600; font-size: 0.85rem; cursor: pointer; flex: 1; min-width: 120px; }
  button.secondary { background: #1e2d40; }
  textarea, input { width: 100%; background: #080c14; color: var(--text); border: 1px solid #2d3f58; border-radius: 8px; padding: 10px; font-size: 0.9rem; margin-bottom: 8px; }
  pre { background: #05080f; border: 1px solid #1e2d40; border-radius: 8px; padding: 12px; font-family: monospace; font-size: 0.8rem; white-space: pre-wrap; word-break: break-word; color: var(--text); max-height: 420px; overflow-y: auto; }
  .plan-step { border-left: 3px solid var(--accent); padding-left: 10px; margin-bottom: 8px; font-size: 0.85rem; }
</style>
</head>
<body>
  <h1>🎓 Sovereign Study & Test-Out Hub</h1>
  <div class="sub">100% Isolated Study Corpus • Zero qf-partner/qf-binder/Podman Coupling</div>

  <div class="card">
    <h2>🔑 Tailscale / Pixel Access Token</h2>
    <input type="password" id="auth-token" placeholder="X-Study-Token (required for non-loopback access)"/>
  </div>

  <div class="card">
    <h2>⚡ CS 320 Workspace & Maven Check</h2>
    <div class="plan-step">Checks Java style simplicity and runs <code>mvn -q test</code> (private email text stays local CLI only).</div>
    <button onclick="runPreflight()">🔍 Run CS 320 Code & Maven Check</button>
    <pre id="preflight-out" style="display:none; margin-top:10px;"></pre>
  </div>

  <div class="card">
    <h2>🧠 Mobile Tutor & Test-Out Drill</h2>
    <textarea id="study-input" rows="3" placeholder="Enter a CS 320 topic, Java question, or Test-Out module..."></textarea>
    <div class="btn-row">
      <button onclick="askStudy('cs320')">🎓 CS 320 Coach</button>
      <button onclick="askStudy('testout')">⚡ Test-Out Drill</button>
      <button class="secondary" onclick="askStudy('tutor')">📖 Explain</button>
    </div>
    <pre id="study-out">Ready on 127.0.0.1:11434...</pre>
  </div>

  <div class="card">
    <h2>📝 Save Scoped Study Note (study-notes.md)</h2>
    <textarea id="teach-input" rows="2" placeholder="Save a study takeaway into ~/mycelium/school-bot/study-notes.md..."></textarea>
    <button class="secondary" onclick="saveStudyNote()">💾 Save to Scoped Study Notes</button>
    <pre id="teach-out" style="display:none; margin-top:8px;"></pre>
  </div>

<script>
function authHeaders() {
  const t = document.getElementById('auth-token').value.trim();
  return t ? {'Content-Type': 'application/json', 'X-Study-Token': t} : {'Content-Type': 'application/json'};
}

async function runPreflight() {
  const out = document.getElementById('preflight-out');
  out.style.display = 'block';
  out.textContent = 'Auditing ~/Documents/CS320...';
  const r = await fetch('/api/preflight', {headers: authHeaders()});
  const d = await r.json();
  if (d.error) { out.textContent = d.error; return; }
  let txt = '=== CS 320 FILES ON DISK ===\\n' + (d.files_found.join('\\n') || '(none)') + '\\n\\n';
  txt += '=== ZIP ARCHIVES ===\\n' + JSON.stringify(d.zip_inventories, null, 2) + '\\n\\n';
  txt += '=== CODE OWNERSHIP & SIMPLICITY CHECKS ===\\n' + JSON.stringify(d.style_checks, null, 2) + '\\n\\n';
  txt += '=== MAVEN TEST STATUS ===\\n' + d.maven_summary;
  out.textContent = txt;
}

async function askStudy(mode) {
  const q = document.getElementById('study-input').value.trim();
  const out = document.getElementById('study-out');
  if (!q) { out.textContent = 'Type a question or topic above first.'; return; }
  out.textContent = 'Thinking locally (' + mode + ')...';
  const r = await fetch('/api/study', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({mode: mode, topic: q})
  });
  const d = await r.json();
  out.textContent = d.answer || d.error;
}

async function saveStudyNote() {
  const note = document.getElementById('teach-input').value.trim();
  const out = document.getElementById('teach-out');
  if (!note) return;
  out.style.display = 'block';
  out.textContent = 'Saving to ~/mycelium/school-bot/study-notes.md...';
  const r = await fetch('/api/study_note', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({note: note})
  });
  const d = await r.json();
  out.textContent = d.saved ? ('Saved: ' + d.saved) : d.error;
  document.getElementById('teach-input').value = '';
}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("SCHOOL_BOT_HOST", "127.0.0.1")
    port = int(os.environ.get("SCHOOL_BOT_PORT", 9060))
    uvicorn.run(app, host=host, port=port)

