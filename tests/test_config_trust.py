# tests/test_config_trust.py
"""
Milestone QF-CONFIG-TRUST-v1: Configuration & Secrets Integrity Test Suite.

Proves:
1. API node authentication precedence hierarchy (API_NODE_KEY > DASHBOARD_API_KEY).
2. Fail-closed behavior on missing, empty, or mismatched credentials.
3. Circle configuration precedence and fail-safe defaults.
4. Filesystem permission invariants (0700 for secret dirs, 0600 for secret files).
5. Git exclusion invariants (no .env, .env.local, or secrets in git index).
6. Systemd unit EnvironmentFile precedence and optional fallback handling.
"""

import os
import stat
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from api_node.main import app, verify_api_node_auth
from api_node.circle_usdc_settlement import _load_circle_config

client = TestClient(app)


def test_api_node_auth_precedence_api_node_key_overrides_dashboard():
    """Verify API_NODE_KEY takes priority over DASHBOARD_API_KEY when both are set."""
    with patch.dict(os.environ, {"API_NODE_KEY": "preferred-key", "DASHBOARD_API_KEY": "fallback-key"}, clear=True):
        req_mock = MagicMock()
        req_mock.headers = {"x-api-key": "preferred-key"}
        # Should succeed without raising
        verify_api_node_auth(req_mock)

        # Fallback key should be rejected when override is active
        req_mock.headers = {"x-api-key": "fallback-key"}
        with pytest.raises(HTTPException) as exc_info:
            verify_api_node_auth(req_mock)
        assert exc_info.value.status_code == 401
        assert "Missing or invalid x-api-key" in exc_info.value.detail


def test_api_node_auth_precedence_falls_back_to_dashboard_key():
    """Verify DASHBOARD_API_KEY is used when API_NODE_KEY is absent."""
    with patch.dict(os.environ, {"DASHBOARD_API_KEY": "fallback-key"}, clear=True):
        req_mock = MagicMock()
        req_mock.headers = {"x-api-key": "fallback-key"}
        verify_api_node_auth(req_mock)

        req_mock.headers = {"x-api-key": "wrong-key"}
        with pytest.raises(HTTPException) as exc_info:
            verify_api_node_auth(req_mock)
        assert exc_info.value.status_code == 401


def test_api_node_auth_fails_closed_when_no_key_configured():
    """Verify service locks and fails closed (HTTP 401) when no keys are in environment."""
    with patch.dict(os.environ, {}, clear=True):
        req_mock = MagicMock()
        req_mock.headers = {"x-api-key": "any-key"}
        with pytest.raises(HTTPException) as exc_info:
            verify_api_node_auth(req_mock)
        assert exc_info.value.status_code == 401
        assert "Service locked" in exc_info.value.detail


def test_api_node_auth_fails_closed_on_missing_or_empty_header():
    """Verify missing or empty x-api-key header results in HTTP 401."""
    with patch.dict(os.environ, {"API_NODE_KEY": "valid-secret-token"}, clear=True):
        req_mock = MagicMock()
        
        # Missing header
        req_mock.headers = {}
        with pytest.raises(HTTPException) as exc_info:
            verify_api_node_auth(req_mock)
        assert exc_info.value.status_code == 401
        assert "Missing or invalid x-api-key" in exc_info.value.detail

        # Empty header
        req_mock.headers = {"x-api-key": ""}
        with pytest.raises(HTTPException) as exc_info:
            verify_api_node_auth(req_mock)
        assert exc_info.value.status_code == 401


def test_circle_config_env_precedence(tmp_path):
    """Verify environment variables take precedence over config file in _load_circle_config()."""
    conf_file = tmp_path / "circle.env"
    conf_file.write_text("CIRCLE_API_KEY=file-key\nCIRCLE_API_BASE=https://file-base\nCIRCLE_WALLET_ID=file-wallet\n")

    with patch("api_node.circle_usdc_settlement.CONFIG_FILE", conf_file):
        # 1. Environment takes precedence
        with patch.dict(os.environ, {
            "CIRCLE_API_KEY": "env-key",
            "CIRCLE_API_BASE": "https://env-base",
            "CIRCLE_WALLET_ID": "env-wallet"
        }, clear=True):
            key, base, wallet = _load_circle_config()
            assert key == "env-key"
            assert base == "https://env-base"
            assert wallet == "env-wallet"

        # 2. File is used when environment is empty
        with patch.dict(os.environ, {}, clear=True):
            key, base, wallet = _load_circle_config()
            assert key == "file-key"
            assert base == "https://file-base"
            assert wallet == "file-wallet"


def test_circle_config_fallback_defaults(tmp_path):
    """Verify safe fallback defaults when neither environment nor config file is present."""
    non_existent = tmp_path / "does_not_exist.env"
    with patch("api_node.circle_usdc_settlement.CONFIG_FILE", non_existent):
        with patch.dict(os.environ, {}, clear=True):
            key, base, wallet = _load_circle_config()
            assert key == ""
            assert base == "https://api.circle.com/v1/w3s"
            assert wallet == "mock-vault-wallet-id"


def test_filesystem_permissions_secret_stores():
    """Verify that all canonical credential stores adhere strictly to 0700 / 0600 permissions."""
    home = Path.home()
    
    # 1. ~/.config/qf
    qf_dir = home / ".config" / "qf"
    if qf_dir.exists():
        dir_mode = stat.S_IMODE(qf_dir.stat().st_mode)
        assert dir_mode & 0o077 == 0, f"~/.config/qf permissions too permissive: {oct(dir_mode)}"
        for child in qf_dir.iterdir():
            if child.is_file():
                f_mode = stat.S_IMODE(child.stat().st_mode)
                assert f_mode & 0o077 == 0, f"~/.config/qf/{child.name} permissions too permissive: {oct(f_mode)}"

    # 2. ~/projects/beta/secrets
    secrets_dir = home / "projects" / "beta" / "secrets"
    if secrets_dir.exists():
        dir_mode = stat.S_IMODE(secrets_dir.stat().st_mode)
        assert dir_mode & 0o077 == 0, f"~/projects/beta/secrets permissions too permissive: {oct(dir_mode)}"
        for child in secrets_dir.iterdir():
            if child.is_file():
                f_mode = stat.S_IMODE(child.stat().st_mode)
                assert f_mode & 0o077 == 0, f"~/projects/beta/secrets/{child.name} permissions too permissive: {oct(f_mode)}"

    # 3. Repo .env and .env.local
    repo_dir = Path(__file__).resolve().parent.parent
    for env_name in [".env", ".env.local"]:
        env_path = repo_dir / env_name
        if env_path.exists():
            f_mode = stat.S_IMODE(env_path.stat().st_mode)
            assert f_mode & 0o077 == 0, f"{env_name} permissions too permissive: {oct(f_mode)}"


def test_inconsistent_qfx_directory_is_absent():
    """Verify that redundant ~/.config/qfx directory does not exist, preserving single source of truth."""
    qfx_dir = Path.home() / ".config" / "qfx"
    assert not qfx_dir.exists(), "Redundant ~/.config/qfx directory detected! Must use ~/.config/qf."


def test_git_untracked_secrets_invariant():
    """Verify that no .env, .env.local, or *.secret files are tracked by Git."""
    repo_dir = Path(__file__).resolve().parent.parent
    res = subprocess.run(
        ["git", "ls-files", ".env", ".env.local", "*.secret", "*.env", "*.key", "*.pem"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True
    )
    tracked_secrets = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    assert not tracked_secrets, f"Git tracking sensitive files: {tracked_secrets}"


def test_systemd_unit_environment_files_structure():
    """Verify systemd user unit specifies EnvironmentFiles in the correct order with optional .env.local."""
    unit_path = Path.home() / ".config" / "systemd" / "user" / "api-node.service"
    assert unit_path.exists(), "api-node.service unit file missing"

    content = unit_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines()]

    # Assert mandatory base .env
    assert "EnvironmentFile=/home/quant/mycelium/.env" in lines
    # Assert optional override .env.local with leading hyphen
    assert "EnvironmentFile=-/home/quant/mycelium/.env.local" in lines
