from types import SimpleNamespace
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization

from tools import qf_spore


def test_spore_probe_identity_matches_enrolled_public_key_and_is_private(tmp_path):
    private_key_path = tmp_path / "probe-private.pem"
    device_keys_dir = tmp_path / "device_keys"

    qf_spore.create_probe_identity(device_keys_dir, private_key_path)

    private_key = serialization.load_pem_private_key(private_key_path.read_bytes(), None)
    public_key = serialization.load_pem_public_key(
        (device_keys_dir / f"{qf_spore.PROBE_CLIENT_ID}.pem").read_bytes()
    )
    private_public_bytes = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    public_bytes = public_key.public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )

    assert private_public_bytes == public_bytes
    assert private_key_path.stat().st_mode & 0o777 == 0o600


def test_remote_spore_probe_script_is_valid_without_running_ssh(tmp_path):
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[0] == "ssh":
            compile(kwargs["input"], "<remote-spore-probe>", "exec")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    with patch.object(qf_spore.subprocess, "run", side_effect=fake_run):
        assert qf_spore.remote_pop_out_test(tmp_path / "unused-spore.tar.gz", "unused-host")

    assert commands[0][0] == "scp"
    assert commands[1][:3] == ["ssh", "unused-host", "python3"]
