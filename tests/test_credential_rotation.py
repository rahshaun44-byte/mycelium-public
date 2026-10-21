"""
Unit and boundary tests for QuantumFlex Credential Rotation & Secret Hygiene.
Tests provider-aware rotation, secret protection, duplicate detection, and Linux safety invariants.
"""

import os
import stat
import pytest
from pathlib import Path

from tools.rotate_credentials_linux import (
    CredentialRotationManager,
    ProviderType,
    CredentialItem,
    SecretLeakageError,
    WindowsPathError,
    DuplicateSecretError,
    MissingProviderCredentialError,
)


@pytest.fixture
def temp_workspace(tmp_path):
    """Creates an isolated temporary test workspace with mock env files."""
    env_dir = tmp_path / "env"
    env_dir.mkdir(mode=0o700)
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir(mode=0o700)
    config_dir = tmp_path / "config"
    config_dir.mkdir(mode=0o700)
    
    main_env = env_dir / ".env"
    main_env.write_text(
        "DB_HOST=127.0.0.1\n"
        "DB_PORT=5432\n"
        "GHOSTNODE_DB_USER=ghostnode\n"
        "GHOSTNODE_DB_PASSWORD=initial_ghostnode_secret_1234567890\n"
        "SENTINEL_DB_USER=sentinel_service\n"
        "SENTINEL_DB_PASSWORD=initial_sentinel_secret_1234567890\n"
        "DASHBOARD_API_KEY=qf_live_dashboard_key_abcdef1234567890\n"
        "ATHENA_API_KEY=qf_live_athena_key_abcdef1234567890\n"
    )
    main_env.chmod(0o600)
    
    return {
        "root": tmp_path,
        "env_file": main_env,
        "secrets_dir": secrets_dir,
        "config_dir": config_dir,
    }


def test_rejects_windows_paths(temp_workspace):
    """Assert that Windows drive letters, backslashes, and Windows path formats are strictly rejected."""
    manager = CredentialRotationManager(
        workspace_root=temp_workspace["root"],
        env_file=temp_workspace["env_file"],
        secrets_dir=temp_workspace["secrets_dir"],
    )
    
    with pytest.raises(WindowsPathError):
        manager.validate_path_safety("C:\\Users\\quant\\AppData\\Local")
        
    with pytest.raises(WindowsPathError):
        manager.validate_path_safety("D:/data/store")
        
    with pytest.raises(WindowsPathError):
        manager.validate_path_safety("relative\\path\\with\\backslashes")


def test_dry_run_does_not_mutate_files(temp_workspace, capsys):
    """Assert that dry-run mode makes zero modifications to any files on disk."""
    manager = CredentialRotationManager(
        workspace_root=temp_workspace["root"],
        env_file=temp_workspace["env_file"],
        secrets_dir=temp_workspace["secrets_dir"],
    )
    
    initial_content = temp_workspace["env_file"].read_text()
    
    report = manager.run(dry_run=True)
    captured = capsys.readouterr()
    
    assert temp_workspace["env_file"].read_text() == initial_content
    assert report["dry_run"] is True
    assert "DRY RUN INVENTORY" in captured.out


def test_never_prints_or_logs_secret_values(temp_workspace, capsys):
    """Assert that neither existing nor newly generated secrets appear in stdout or stderr."""
    manager = CredentialRotationManager(
        workspace_root=temp_workspace["root"],
        env_file=temp_workspace["env_file"],
        secrets_dir=temp_workspace["secrets_dir"],
    )
    
    test_secret = "initial_ghostnode_secret_1234567890"
    manager.run(dry_run=True)
    captured = capsys.readouterr()
    
    assert test_secret not in captured.out
    assert test_secret not in captured.err
    # Also ensure partial masking (e.g. init...7890) doesn't leak prefix/suffix
    assert "initial" not in captured.out
    assert "1234567890" not in captured.out


def test_backup_preservation(temp_workspace):
    """Assert that existing backup files are never overwritten."""
    backup_file = temp_workspace["env_file"].with_name(".env.bak-20261020-001")
    backup_file.write_text("ORIGINAL_BACKUP_DATA")
    backup_file.chmod(0o600)
    
    manager = CredentialRotationManager(
        workspace_root=temp_workspace["root"],
        env_file=temp_workspace["env_file"],
        secrets_dir=temp_workspace["secrets_dir"],
    )
    
    # Attempting to backup to an existing path must raise an error rather than overwrite
    with pytest.raises(FileExistsError):
        manager.create_atomic_backup(target_backup=backup_file)


def test_duplicate_secret_detection(temp_workspace):
    """Assert that secret reuse across different roles or services is detected and rejected."""
    bad_env = temp_workspace["env_file"]
    bad_env.write_text(
        "DB_PASSWORD=reused_secret_1234567890\n"
        "GHOSTNODE_DB_PASSWORD=reused_secret_1234567890\n"
        "DASHBOARD_API_KEY=shared_key_1234567890\n"
        "ATHENA_API_KEY=shared_key_1234567890\n"
    )
    
    manager = CredentialRotationManager(
        workspace_root=temp_workspace["root"],
        env_file=bad_env,
        secrets_dir=temp_workspace["secrets_dir"],
    )
    
    with pytest.raises(DuplicateSecretError) as exc_info:
        manager.audit_uniqueness()
        
    msg = str(exc_info.value)
    assert "Duplicate secret detected" in msg
    # Assert the secret itself is NOT in the error message
    assert "reused_secret_1234567890" not in msg


def test_provider_aware_classification(temp_workspace):
    """Assert that credentials are correctly categorized into provider domains."""
    manager = CredentialRotationManager(
        workspace_root=temp_workspace["root"],
        env_file=temp_workspace["env_file"],
        secrets_dir=temp_workspace["secrets_dir"],
    )
    
    inventory = manager.get_inventory()
    
    # Check that database roles, API keys, and third party keys are categorized
    categories = {item.provider for item in inventory}
    assert ProviderType.LOCAL_POSTGRES in categories
    assert ProviderType.INTERNAL_SERVICE in categories


def test_missing_provider_stops_rotation(temp_workspace):
    """Assert that if third-party provider rotation is required but unconfigured, it fails closed."""
    manager = CredentialRotationManager(
        workspace_root=temp_workspace["root"],
        env_file=temp_workspace["env_file"],
        secrets_dir=temp_workspace["secrets_dir"],
        config_dir=temp_workspace["config_dir"],
        require_third_party=True,
    )
    
    with pytest.raises(MissingProviderCredentialError):
        manager.run(dry_run=False)


def test_file_permissions_enforced(temp_workspace):
    """Assert that any files created or modified by the manager strictly retain 0600 permissions."""
    manager = CredentialRotationManager(
        workspace_root=temp_workspace["root"],
        env_file=temp_workspace["env_file"],
        secrets_dir=temp_workspace["secrets_dir"],
    )
    
    manager.run(dry_run=False)
    
    file_mode = stat.S_IMODE(os.stat(temp_workspace["env_file"]).st_mode)
    assert file_mode == 0o600
