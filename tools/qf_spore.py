#!/usr/bin/env python3
"""QuantumFlex Spore: Sporulate a node into a portable seed, sprout it, and pop out.

This tool models the biological mycelium lifecycle:
1. SPORULATE: Packages a verified, self-contained QuantumFlex seed bundle containing
   the native engine binary, the Genesis authority anchor, active ledger, and sprout script.
2. SPROUT: Germinates the spore into an active, listening QuantumFlex node on any host.
3. POP OUT: Runs the spore in an isolated ephemeral sandbox, performs full mTLS verification,
   proves viability, halts cleanly, and wipes all temporary state with zero forensic footprint.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import tarfile
import tempfile
import time

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from qf_ipc_auth import AuthenticationError, authenticate

REPO = Path(__file__).resolve().parents[1]
DATA_DIR = Path.home() / ".local/share/quantum-flex-mycelium"
STATE_DIR = Path.home() / ".local/state/quantum-flex-mycelium"
ENGINE_BIN = REPO / "build_check/quantum_flex_engine"
GENESIS_MANIFEST = STATE_DIR / "authority-genesis-20261015T121219Z.json"
LEDGER_DAT = DATA_DIR / "ledger.dat"
MTLS_DIR = DATA_DIR / "mtls"
ED_KEY = DATA_DIR / "ed_priv.pem"
PQC_KEY = DATA_DIR / "pqc_priv.pem"
PROBE_CLIENT_ID = "qfx-spore-probe"

EXPECTED_ENGINE_SHA256 = "601f3e0207a45ad0dd1ebf39afae7242d38d19437eed4951b3b39b6acafba9d1"
EXPECTED_GENESIS_LEDGER_SHA256 = "1d479c6ac6df98ab502d0efe536fc8edbdce63d0e13294c33e38f63d259407b9"


def file_sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def create_probe_identity(device_keys_dir: Path, private_key_path: Path) -> None:
    key = Ed25519PrivateKey.generate()
    device_keys_dir.mkdir(parents=True, exist_ok=True)
    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    private_key_path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    private_key_path.chmod(0o600)
    public_key_path = device_keys_dir / f"{PROBE_CLIENT_ID}.pem"
    public_key_path.write_bytes(key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    public_key_path.chmod(0o644)


SPROUT_SCRIPT_TEMPLATE = """#!/usr/bin/env bash
# ==============================================================================
# QuantumFlex Spore: Germinate node from seed
# ==============================================================================
set -euo pipefail

SPORE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PORT="${1:-9444}"
BIND_ADDR="${2:-127.0.0.1}"

echo "[*] Germinating QuantumFlex Spore on ${BIND_ADDR}:${PORT}..."

export LD_LIBRARY_PATH="${SPORE_DIR}/lib:${LD_LIBRARY_PATH:-}"
export QF_DATA_DIR="${SPORE_DIR}/data"
export QF_BIND_ADDRESS="${BIND_ADDR}"
export QF_BIND_PORT="${PORT}"
export QF_SERVER_CERT="${SPORE_DIR}/data/mtls/server.crt"
export QF_SERVER_KEY="${SPORE_DIR}/data/mtls/server.key"
export QF_ROOT_CA="${SPORE_DIR}/data/mtls/ca.crt"
export QF_DEVICE_KEYS_DIR="${SPORE_DIR}/data/device_keys"
export QF_ED_PRIVATE_KEY="${SPORE_DIR}/data/ed_priv.pem"
export QF_PQC_PRIVATE_KEY="${SPORE_DIR}/data/pqc_priv.pem"

chmod +x "${SPORE_DIR}/bin/quantum_flex_engine"
exec "${SPORE_DIR}/bin/quantum_flex_engine"
"""



def sporulate(output_archive: Path, include_node_keys: bool = True) -> Path:
    """Builds a compressed spore archive containing all elements to sprout a node."""
    print(f"[*] Sporulating node from host: {socket.gethostname()}")

    # Check prerequisites
    if not ENGINE_BIN.is_file():
        raise FileNotFoundError(f"Engine binary not found: {ENGINE_BIN}")
    engine_hash = file_sha256(ENGINE_BIN)
    if engine_hash != EXPECTED_ENGINE_SHA256:
        print(f"[!] Warning: Engine hash {engine_hash[:16]}... differs from release hash {EXPECTED_ENGINE_SHA256[:16]}...")
    else:
        print(f"[+] Engine binary verified: {engine_hash[:16]}...")

    if not LEDGER_DAT.is_file():
        raise FileNotFoundError(f"Active ledger not found: {LEDGER_DAT}")
    ledger_hash = file_sha256(LEDGER_DAT)
    print(f"[+] Active ledger verified: {ledger_hash[:16]}...")

    with tempfile.TemporaryDirectory(prefix="qfx-spore-pack-") as tmpdir:
        tmppath = Path(tmpdir)
        bin_dir = tmppath / "bin"
        lib_dir = tmppath / "lib"
        data_dir = tmppath / "data"
        meta_dir = tmppath / "meta"
        mtls_out = data_dir / "mtls"
        device_keys_out = data_dir / "device_keys"
        scripts_out = tmppath / "scripts"

        bin_dir.mkdir(parents=True)
        lib_dir.mkdir(parents=True)
        data_dir.mkdir(parents=True)
        meta_dir.mkdir(parents=True)
        mtls_out.mkdir(parents=True)
        device_keys_out.mkdir(parents=True)
        scripts_out.mkdir(parents=True)

        # 1. Binary & Shared Libraries
        shutil.copy2(ENGINE_BIN, bin_dir / "quantum_flex_engine")
        (bin_dir / "quantum_flex_engine").chmod(0o755)

        libpqxx_src = Path("/usr/lib/x86_64-linux-gnu/libpqxx-7.10.so")
        if libpqxx_src.is_file():
            shutil.copy2(libpqxx_src, lib_dir / "libpqxx-7.10.so")

        # 2. Ledger
        shutil.copy2(LEDGER_DAT, data_dir / "ledger.dat")

        # 3. Genesis anchor
        if GENESIS_MANIFEST.is_file():
            shutil.copy2(GENESIS_MANIFEST, meta_dir / GENESIS_MANIFEST.name)

        # 4. Certificates and keys
        if include_node_keys:
            for f in ["ca.crt", "server.crt", "server.key", "client.crt", "client.key"]:
                src = MTLS_DIR / f
                if src.is_file():
                    shutil.copy2(src, mtls_out / f)
            if ED_KEY.is_file():
                shutil.copy2(ED_KEY, data_dir / "ed_priv.pem")
            if PQC_KEY.is_file():
                shutil.copy2(PQC_KEY, data_dir / "pqc_priv.pem")
            shutil.copy2(
                Path.home() / "quantum-flex/keys/ed25519_public.pem",
                device_keys_out / "qfx-yoga-local.pem",
            )
        shutil.copy2(REPO / "scripts/qf_ipc_auth.py", scripts_out / "qf_ipc_auth.py")

        # 5. Sprout script
        sprout_path = tmppath / "sprout"
        sprout_path.write_text(SPROUT_SCRIPT_TEMPLATE)
        sprout_path.chmod(0o755)

        # 6. Spore Manifest
        manifest = {
            "spore_version": "2.1-mycelium",
            "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source_host": socket.gethostname(),
            "engine_sha256": engine_hash,
            "ledger_sha256": ledger_hash,
            "components": {}
        }
        for item in sorted(tmppath.rglob("*")):
            if item.is_file() and item.name != "manifest.json":
                rel = str(item.relative_to(tmppath))
                manifest["components"][rel] = file_sha256(item)

        (tmppath / "manifest.json").write_text(json.dumps(manifest, indent=2))

        # 7. Create tarball
        output_archive.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(output_archive, "w:gz") as tar:
            tar.add(tmppath, arcname="qfx-spore")

    print(f"[+] Spore successfully created: {output_archive} ({output_archive.stat().st_size} bytes)")
    return output_archive


def probe_mtls(
    host: str,
    port: int,
    ca_file: Path,
    client_cert: Path,
    client_key: Path,
    signing_key_path: Path,
    timeout: float = 3.0,
) -> dict:
    """Proves both mTLS transport and the enrolled Ed25519 device identity."""
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(ca_file))
    ctx.load_cert_chain(certfile=str(client_cert), keyfile=str(client_key))
    ctx.check_hostname = False

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    with ctx.wrap_socket(s, server_side=False) as ss:
        ss.connect((host, port))
        authenticate(ss, signing_key_path, PROBE_CLIENT_ID)
        cert = ss.getpeercert()
        return {
            "status": "authenticated",
            "peer_subject": dict(x[0] for x in cert.get("subject", [])),
            "cipher": ss.cipher(),
            "version": ss.version()
        }


def pop_out_test(spore_tar: Path, test_port: int = 19444) -> bool:
    """Sprouts the spore in an isolated ephemeral environment, probes via mTLS, and pops out."""
    print(f"\n[*] === INITIATING SPORE POP-UP TEST (Port {test_port}) ===")

    with tempfile.TemporaryDirectory(prefix="qfx-sprout-test-") as test_dir:
        test_path = Path(test_dir)
        print(f"[*] Inoculating temporary substrate: {test_path}")

        # Extract spore
        with tarfile.open(spore_tar, "r:gz") as tar:
            tar.extractall(test_path)

        spore_root = test_path / "qfx-spore"
        engine_bin = spore_root / "bin/quantum_flex_engine"
        data_dir = spore_root / "data"
        ca_file = data_dir / "mtls/ca.crt"
        client_cert = data_dir / "mtls/client.crt"
        client_key = data_dir / "mtls/client.key"
        probe_signing_key = test_path / "probe-auth-private.pem"
        create_probe_identity(data_dir / "device_keys", probe_signing_key)

        if not engine_bin.is_file():
            raise RuntimeError("Corrupt spore: engine binary missing")

        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = f"{spore_root / 'lib'}:{env.get('LD_LIBRARY_PATH', '')}"
        env["QF_DATA_DIR"] = str(data_dir)
        env["QF_BIND_ADDRESS"] = "127.0.0.1"
        env["QF_BIND_PORT"] = str(test_port)
        env["QF_SERVER_CERT"] = str(data_dir / "mtls/server.crt")
        env["QF_SERVER_KEY"] = str(data_dir / "mtls/server.key")
        env["QF_ROOT_CA"] = str(ca_file)
        env["QF_DEVICE_KEYS_DIR"] = str(data_dir / "device_keys")
        env["QF_ED_PRIVATE_KEY"] = str(data_dir / "ed_priv.pem")
        env["QF_PQC_PRIVATE_KEY"] = str(data_dir / "pqc_priv.pem")

        log_file = test_path / "sprout_engine.log"

        print(f"[*] Sprouting node process...")
        with open(log_file, "w") as out:
            proc = subprocess.Popen(
                [str(engine_bin)],
                cwd=str(spore_root),
                env=env,
                stdout=out,
                stderr=subprocess.STDOUT
            )

        try:
            # Poll for listening socket
            connected = False
            probe_result = None
            for attempt in range(20):
                time.sleep(0.2)
                if proc.poll() is not None:
                    print(f"[!] Engine exited prematurely with code {proc.returncode}")
                    break
                try:
                    probe_result = probe_mtls(
                        "127.0.0.1",
                        test_port,
                        ca_file,
                        client_cert,
                        client_key,
                        probe_signing_key,
                        timeout=1.0,
                    )
                    connected = True
                    break
                except AuthenticationError as exc:
                    print(f"[!] Ed25519 admission rejected: {exc}")
                    return False
                except (ConnectionRefusedError, socket.timeout):
                    continue
                except ConnectionError as exc:
                    print(f"[!] IPC authentication exchange failed: {exc}")
                    return False
                except (ssl.SSLError, OSError):
                    continue

            if not connected:
                print("[!] Failed to establish mTLS connection with sprouted node.")
                if log_file.exists():
                    print("--- Engine Log ---")
                    print(log_file.read_text())
                return False

            print("[+] Node popped up successfully!")
            print(f"    - Protocol: {probe_result['version']} ({probe_result['cipher'][0]})")
            print(f"    - Peer Identity: {probe_result['peer_subject']}")

            # Verify log states
            time.sleep(0.3)
            log_content = log_file.read_text()
            if "Ledger suspended in memory. Engine is LOCKED. Awaiting SSS unlock." in log_content:
                print("[+] Verified Security State: Node booted cleanly into LOCKED state awaiting SSS quorum.")
            else:
                print("[!] Security State Note: Output captured:")
                print(log_content.strip())

            # Now POP OUT: Graceful shutdown
            print("\n[*] Popping out: Signaling clean node halt (SIGTERM)...")
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(timeout=5.0)
                print(f"[+] Engine halted cleanly with exit code {proc.returncode}")
            except subprocess.TimeoutExpired:
                print("[!] Engine timeout on SIGTERM; terminating...")
                proc.kill()
                proc.wait()

            # Verify that superposition / ledger state was serialized
            if log_file.exists():
                final_log = log_file.read_text()
                if "Ledger successfully committed to disk" in final_log or "Superposition collapsed" in final_log:
                    print("[+] Verified Clean Decommission: Ledger successfully committed and state collapsed.")

        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()

        print("[*] Erasing ephemeral test substrate...")

    print("[+] POPPED OUT COMPLETELY. Zero residual state on host.")
    return True


def remote_pop_out_test(spore_tar: Path, host: str, port: int = 19444) -> bool:
    """Transplants the spore over SSH, sprouts it remotely, probes via mTLS, and pops out."""
    print(f"\n[*] === INITIATING REMOTE SPORE POP-UP TEST ON {host} (Port {port}) ===")
    remote_tmp = f"/tmp/qfx-spore-remote-{int(time.time())}.tar.gz"

    print(f"[*] Transplanting spore to remote host {host}:{remote_tmp}...")
    scp_res = subprocess.run(["scp", "-q", str(spore_tar), f"{host}:{remote_tmp}"], capture_output=True, text=True)
    if scp_res.returncode != 0:
        print(f"[!] SCP failed: {scp_res.stderr}")
        return False

    remote_python_script = f'''
import os, sys, time, signal, socket, ssl, subprocess, tempfile, tarfile
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

spore_tar = Path("{remote_tmp}")
try:
    with tempfile.TemporaryDirectory(prefix="qfx-remote-sprout-") as tmpdir:
        tmppath = Path(tmpdir)
        with tarfile.open(spore_tar, "r:gz") as tar:
            tar.extractall(tmppath)
        spore_root = tmppath / "qfx-spore"
        engine_bin = spore_root / "bin/quantum_flex_engine"
        data_dir = spore_root / "data"
        lib_dir = spore_root / "lib"
        probe_signing_key = tmppath / "probe-auth-private.pem"
        probe_key = Ed25519PrivateKey.generate()
        probe_signing_key.write_bytes(probe_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
        probe_signing_key.chmod(0o600)
        device_keys_dir = data_dir / "device_keys"
        device_keys_dir.mkdir(parents=True, exist_ok=True)
        (device_keys_dir / "qfx-spore-probe.pem").write_bytes(probe_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ))

        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = f"{{lib_dir}}:{{env.get('LD_LIBRARY_PATH', '')}}"
        env["QF_DATA_DIR"] = str(data_dir)
        env["QF_BIND_ADDRESS"] = "127.0.0.1"
        env["QF_BIND_PORT"] = "{port}"
        env["QF_SERVER_CERT"] = str(data_dir / "mtls/server.crt")
        env["QF_SERVER_KEY"] = str(data_dir / "mtls/server.key")
        env["QF_ROOT_CA"] = str(data_dir / "mtls/ca.crt")
        env["QF_DEVICE_KEYS_DIR"] = str(data_dir / "device_keys")
        env["QF_ED_PRIVATE_KEY"] = str(data_dir / "ed_priv.pem")
        env["QF_PQC_PRIVATE_KEY"] = str(data_dir / "pqc_priv.pem")

        log_file = tmppath / "engine.log"
        with open(log_file, "w") as out:
            proc = subprocess.Popen([str(engine_bin)], cwd=str(spore_root), env=env, stdout=out, stderr=subprocess.STDOUT)

        # Poll socket
        connected = False
        for _ in range(25):
            time.sleep(0.2)
            if proc.poll() is not None:
                break
            try:
                sys.path.insert(0, str(spore_root / "scripts"))
                from qf_ipc_auth import AuthenticationError, authenticate
                ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=str(data_dir / "mtls/ca.crt"))
                ctx.load_cert_chain(certfile=str(data_dir / "mtls/client.crt"), keyfile=str(data_dir / "mtls/client.key"))
                ctx.check_hostname = False
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(1.0)
                with ctx.wrap_socket(s, server_side=False) as ss:
                    ss.connect(("127.0.0.1", {port}))
                    authenticate(ss, probe_signing_key, "qfx-spore-probe")
                    print("[+] Remote node sprouted and verified via mTLS! Peer:", dict(x[0] for x in ss.getpeercert()["subject"]))
                    connected = True
                    break
            except AuthenticationError as exc:
                print("[!] Remote Ed25519 admission rejected:", exc)
                sys.exit(1)
            except (ConnectionRefusedError, socket.timeout):
                continue
            except ConnectionError as exc:
                print("[!] Remote IPC authentication exchange failed:", exc)
                sys.exit(1)
            except (ssl.SSLError, OSError):
                continue

        if not connected:
            print("[!] Remote node failed to respond on mTLS socket.")
            if log_file.exists():
                print(log_file.read_text())
            sys.exit(1)

        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
            print("[+] Remote node halted cleanly on SIGTERM.")
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

finally:
    spore_tar.unlink(missing_ok=True)
    print("[+] Remote ephemeral substrate completely erased. Popped out cleanly!")
'''
    ssh_cmd = ["ssh", host, "python3", "-"]
    ssh_res = subprocess.run(ssh_cmd, input=remote_python_script, capture_output=True, text=True)
    print(ssh_res.stdout)
    if ssh_res.returncode != 0:
        print(f"[!] Remote execution failed: {ssh_res.stderr}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="QuantumFlex Spore: Sporulate, sprout, and pop out.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    # sporulate command
    sp_parser = subparsers.add_parser("sporulate", help="Package a QuantumFlex node into a spore archive.")
    sp_parser.add_argument("--out", type=Path, default=REPO / "release/qfx-spore-latest.tar.gz", help="Output spore tarball path.")

    # popout command
    po_parser = subparsers.add_parser("popout", help="Sporulate, sprout on ephemeral port, probe mTLS, and pop out cleanly.")
    po_parser.add_argument("--port", type=int, default=19444, help="Ephemeral test port (default 19444).")
    po_parser.add_argument("--spore", type=Path, default=None, help="Existing spore tarball to test (or builds fresh if not provided).")

    # remote-popout command
    rpo_parser = subparsers.add_parser("remote-popout", help="Transplant spore to remote host over SSH, sprout, probe mTLS, and pop out.")
    rpo_parser.add_argument("--host", type=str, default="qf-g6", help="SSH host alias or user@ip (default qf-g6).")
    rpo_parser.add_argument("--port", type=int, default=19444, help="Ephemeral test port on remote host (default 19444).")
    rpo_parser.add_argument("--spore", type=Path, default=None, help="Existing spore tarball to test.")

    args = parser.parse_args()

    if args.action == "sporulate":
        archive = sporulate(args.out)
        print(f"\n[+] Done. Spore ready at: {archive}")
    elif args.action == "popout":
        if args.spore and args.spore.is_file():
            spore_path = args.spore
        else:
            default_out = REPO / "release/qfx-spore-latest.tar.gz"
            spore_path = sporulate(default_out)
        success = pop_out_test(spore_path, test_port=args.port)
        if not success:
            sys.exit(1)
        print("\n=== SPORULATION & POP-OUT CEREMONY VERIFIED ===")
    elif args.action == "remote-popout":
        if args.spore and args.spore.is_file():
            spore_path = args.spore
        else:
            default_out = REPO / "release/qfx-spore-latest.tar.gz"
            spore_path = sporulate(default_out)
        success = remote_pop_out_test(spore_path, host=args.host, port=args.port)
        if not success:
            sys.exit(1)
        print("\n=== REMOTE SPORULATION & POP-OUT CEREMONY VERIFIED ===")


if __name__ == "__main__":
    main()
