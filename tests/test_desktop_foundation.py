#!/usr/bin/env python3
"""
QuantumFlex Command: Phase 1 Desktop Foundation Test Suite
===========================================================
Validates:
  1. Curated visual identity assets (3K wallpaper, watermark, seals)
  2. Standalone launcher script (~/.local/bin/quantumflex)
  3. Desktop entry (~/.local/share/applications/quantumflex.desktop)
  4. Autostart entry (~/.config/autostart/quantumflex.desktop)
  5. Systemd user service (~/.config/systemd/user/quantumflex-desktop.service)
  6. Desktop HTTP endpoint (http://127.0.0.1:9001/desktop) and 13 modules
  7. Visual identity asset HTTP serving (/assets/...)
  8. Live telemetry & subsystem API proxies (Athena, Amara, Vault, Mesh)
"""

import os
import subprocess
import urllib.request
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT_DIR / "assets" / "visual_identity"
DESKTOP_HTML = ROOT_DIR / "mcp_layer" / "qf_bot" / "ui" / "desktop_command.html"
LAUNCHER = Path.home() / ".local" / "bin" / "quantumflex"
DESKTOP_ENTRY = Path.home() / ".local" / "share" / "applications" / "quantumflex.desktop"
AUTOSTART_ENTRY = Path.home() / ".config" / "autostart" / "quantumflex.desktop"
SYSTEMD_SERVICE = Path.home() / ".config" / "systemd" / "user" / "quantumflex-desktop.service"


def test_visual_identity_assets_staged():
    assert ASSETS_DIR.exists(), f"Assets directory not found: {ASSETS_DIR}"
    required = [
        ASSETS_DIR / "Wallpapers" / "quantumflex_yoga_3k.jpg",
        ASSETS_DIR / "Wallpapers" / "quantumflex_pixel_5d.jpg",
        ASSETS_DIR / "quantumflex_extraterrestrial_symbol_watermark_1791745907383.jpg",
        ASSETS_DIR / "quantumflex_mint_agility_seal_1791746560812.jpg",
        ASSETS_DIR / "quantum_lighthouse_subtle_observer_1791745747760.jpg",
        ASSETS_DIR / "anu_ra_temple_macro_1791744784906.jpg",
    ]
    for r in required:
        assert r.exists(), f"Missing required asset: {r}"
        assert r.stat().st_size > 0, f"Asset is empty: {r}"


def test_desktop_html_contains_13_modules_and_visual_identity():
    assert DESKTOP_HTML.exists(), f"Missing desktop command HTML: {DESKTOP_HTML}"
    content = DESKTOP_HTML.read_text(encoding="utf-8")
    
    # Check visual identity references
    assert "quantumflex_yoga_3k.jpg" in content
    assert "quantumflex_extraterrestrial_symbol_watermark_1791745907383.jpg" in content
    assert "#060911" in content
    assert "#00f5d4" in content
    
    # Check 13 navigation module tags
    modules = [
        "overview", "infrastructure", "cockpit", "athena", "amara",
        "research", "quantum", "communications", "vault", "tasks",
        "security", "wealth", "config"
    ]
    for m in modules:
        assert f'data-view="{m}"' in content, f"Missing nav item for module: {m}"
        assert f'id="view-{m}"' in content, f"Missing view section for module: {m}"
    
    # Check persistent elements
    assert "top-bar" in content
    assert "nav-rail" in content
    assert "workspace" in content
    assert "context-panel" in content
    assert "status-bar" in content
    assert "EMERGENCY HOLD" in content


def test_launcher_script_and_status():
    assert LAUNCHER.exists(), f"Missing launcher script: {LAUNCHER}"
    assert os.access(LAUNCHER, os.X_OK), "Launcher script is not executable"
    
    res = subprocess.run([str(LAUNCHER), "--status"], capture_output=True, text=True)
    assert res.returncode == 0
    assert "SUBSYSTEM SERVICE STATUS" in res.stdout
    assert "Port 9001" in res.stdout


def test_desktop_entry_validation():
    assert DESKTOP_ENTRY.exists(), f"Missing desktop entry: {DESKTOP_ENTRY}"
    assert AUTOSTART_ENTRY.exists(), f"Missing autostart entry: {AUTOSTART_ENTRY}"
    assert SYSTEMD_SERVICE.exists(), f"Missing systemd service: {SYSTEMD_SERVICE}"
    
    res = subprocess.run(["desktop-file-validate", str(DESKTOP_ENTRY)], capture_output=True, text=True)
    assert res.returncode == 0, f"Validation failed: {res.stderr}"


def test_http_desktop_endpoint():
    req = urllib.request.Request("http://127.0.0.1:9001/desktop")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        body = resp.read().decode("utf-8")
        assert "QUANTUMFLEX COMMAND" in body
        assert "Pluton TPM 2.0" in body


def test_http_asset_serving():
    req = urllib.request.Request("http://127.0.0.1:9001/assets/visual_identity/Wallpapers/quantumflex_yoga_3k.jpg")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200
        assert resp.headers.get("content-type") == "image/jpeg"
        assert int(resp.headers.get("content-length", 0)) > 100000


def test_live_subsystem_proxies():
    # 1. Athena Health
    req_athena = urllib.request.Request("http://127.0.0.1:9001/api/athena/health")
    with urllib.request.urlopen(req_athena, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("status") == "ONLINE"
        assert data.get("vector_count", 0) >= 121
    
    # 2. Amara Telemetry
    req_amara = urllib.request.Request("http://127.0.0.1:9001/api/amara/telemetry")
    with urllib.request.urlopen(req_amara, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert "drive" in data
        assert "status" in data["drive"]
    
    # 3. Knowledge Vault List (25 Domains)
    req_vault = urllib.request.Request("http://127.0.0.1:9001/api/vault/list")
    with urllib.request.urlopen(req_vault, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        doc_names = [d["name"] for d in data.get("documents", [])]
        assert len(doc_names) >= 43
        for i in range(1, 26):
            expected = f"athena_domain_{i:02d}_"
            assert any(d.startswith(expected) for d in doc_names), f"Missing domain {i} in vault list"
    
    # 4. Real-Node Mesh
    req_mesh = urllib.request.Request("http://127.0.0.1:9001/api/mesh/nodes")
    with urllib.request.urlopen(req_mesh, timeout=5) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        nodes = data.get("nodes", [])
        node_ids = [n["id"] for n in nodes]
        assert "qfx-yoga" in node_ids
        assert "qfx-pixel" in node_ids
