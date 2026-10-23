"""Browser-side security headers and CSP violation reporting (sentinel.browser_guard)."""

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sentinel import browser_guard


def _client(tmp_path, monkeypatch):
    log = tmp_path / "csp.jsonl"
    monkeypatch.setenv("QF_CSP_LOG", str(log))
    app = FastAPI()

    @app.get("/")
    def root():
        return {"ok": True}

    @app.get("/framed")
    def framed():
        from fastapi.responses import JSONResponse
        return JSONResponse({"ok": True}, headers={"X-Frame-Options": "DENY"})

    browser_guard.install(app, app_name="unit")
    return TestClient(app), log


def test_hardening_headers_on_every_response(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    r = client.get("/")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert "camera=()" in r.headers["permissions-policy"]


def test_csp_is_report_only_and_never_enforced(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    r = client.get("/")
    assert "content-security-policy" not in r.headers
    csp = r.headers["content-security-policy-report-only"]
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "report-uri /__csp-report" in csp


def test_existing_route_headers_are_not_overwritten(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    assert client.get("/framed").headers["x-frame-options"] == "DENY"


def test_violation_report_is_logged_once(tmp_path, monkeypatch):
    client, log = _client(tmp_path, monkeypatch)
    report = {"csp-report": {
        "document-uri": "http://127.0.0.1:8000/",
        "violated-directive": "script-src-elem",
        "blocked-uri": "inline",
        "source-file": "http://127.0.0.1:8000/",
        "line-number": 42,
    }}
    for _ in range(3):
        r = client.post("/__csp-report", content=json.dumps(report),
                        headers={"Content-Type": "application/csp-report"})
        assert r.status_code == 204
    lines = log.read_text().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["app"] == "unit"
    assert entry["violated_directive"] == "script-src-elem"
    assert entry["line_number"] == 42


def test_oversized_or_malformed_reports_are_dropped(tmp_path, monkeypatch):
    client, log = _client(tmp_path, monkeypatch)
    big = b"{" + b" " * (browser_guard.MAX_REPORT_BYTES + 1) + b"}"
    assert client.post("/__csp-report", content=big).status_code == 413
    assert client.post("/__csp-report", content=b"not json").status_code == 400
    assert not log.exists()
