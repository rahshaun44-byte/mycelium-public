import os
from pathlib import Path

ui_dir = Path(__file__).resolve().parent / "ui"

with open(ui_dir / "index.html", "r", encoding="utf-8") as f:
    html = f.read()

with open(ui_dir / "style.css", "r", encoding="utf-8") as f:
    css = f.read()

with open(ui_dir / "app.js", "r", encoding="utf-8") as f:
    js = f.read()

# Inline CSS
html = html.replace('<link rel="stylesheet" href="style.css">', f'<style>\n{css}\n</style>')

# Adapter logic for standalone file vs web origin
adapter_js = """
// ── Standalone Host Auto-Configuration ─────────────────────────────
let hostNode = (window.location.protocol === 'file:' || !window.location.host)
  ? (localStorage.getItem('qf_mobile_host') || 'http://192.168.100.11:9050')
  : window.location.origin;

function setHostNode(url) {
  hostNode = url;
  localStorage.setItem('qf_mobile_host', url);
  const statusEl = document.getElementById('activeHostDisplay');
  if (statusEl) statusEl.textContent = url.replace('http://', '');
  if (typeof hapticFeedback === 'function') hapticFeedback('medium');
  if (typeof refreshMeshTelemetry === 'function') refreshMeshTelemetry();
  if (typeof refreshAlertsTelemetry === 'function') refreshAlertsTelemetry();
  console.log('Switched host to:', hostNode);
}

document.addEventListener('DOMContentLoaded', () => {
  const statusEl = document.getElementById('activeHostDisplay');
  if (statusEl) statusEl.textContent = hostNode.replace('http://', '');
});
"""

# Adapt all fetch calls
js_adapted = js.replace("fetch('/api/", "fetch(hostNode + '/api/")
js_adapted = js_adapted.replace("fetch(`/api/", "fetch(`${hostNode}/api/")

# Add top node connection bar
host_bar = """
    <div id="hostBar" style="background:rgba(0,0,0,0.65); padding:6px 14px; font-size:0.72rem; display:flex; align-items:center; justify-content:space-between; border-bottom:1px solid rgba(255,255,255,0.08); font-family:var(--font-mono); z-index:100;">
      <div style="display:flex; align-items:center; gap:6px;">
        <span style="color:var(--muted);">NODE:</span>
        <span id="activeHostDisplay" style="color:var(--teal); font-weight:600;">192.168.100.11:9050</span>
      </div>
      <div style="display:flex; gap:6px;">
        <button onclick="setHostNode('http://192.168.100.11:9050')" style="background:rgba(0,245,212,0.15); border:1px solid rgba(0,245,212,0.35); color:var(--teal); font-size:0.68rem; padding:3px 8px; border-radius:6px; cursor:pointer;">Wi-Fi</button>
        <button onclick="setHostNode('http://100.64.1.31:9050')" style="background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.12); color:var(--text); font-size:0.68rem; padding:3px 8px; border-radius:6px; cursor:pointer;">Tailscale</button>
      </div>
    </div>
"""

html = html.replace('</header>', '</header>' + host_bar)
html = html.replace('<script src="app.js"></script>', f'<script>\n{adapter_js}\n{js_adapted}\n</script>')

target_file = ui_dir / "QuantumFlex-Mobile.html"
with open(target_file, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Successfully generated standalone {target_file} ({os.path.getsize(target_file)} bytes)")
