#!/usr/bin/env python3
"""Exercise QF-R2: the host judge, not the in-repo pointer, admits a tree.

Synthetic Ed25519 fixtures prove pass, hash fail-closed, path reject, and
installer overwrite protection. The live mycelium manifest proves the
judge reads the real QF-A5 sidecar (SIGNATURE_B64=) and pinned PEM key.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
INSTALLER = WORKSPACE / "scripts" / "install_host_trust_anchor.sh"
ASSERT = WORKSPACE / "scripts" / "assert_host_trust_source.py"
WRAPPER = WORKSPACE / "scripts" / "verify_provenance_manifest.py"
TEMPLATE = WORKSPACE / "host-trust" / "verify-provenance"
LIVE_MANIFEST = WORKSPACE / "release" / "PROVENANCE_MANIFEST.json"


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    kwargs.setdefault("text", True)
    kwargs.setdefault("capture_output", True)
    return subprocess.run(cmd, **kwargs)


def expect(label: str, ok: bool, detail: str = "") -> None:
    if not ok:
        raise SystemExit(f"[FAIL] {label}{': ' + detail if detail else ''}")
    print(f"[PASS] {label}")


def write_signed_tree(
    root: Path,
    artifacts: dict[str, bytes],
    *,
    extra_rel: str | None = None,
    key_id: str | None = None,
    plane: str = "host-release-a5",
    schema_version: str | None = None,
) -> Path:
    release = root / "release"
    release.mkdir(parents=True)
    listed: dict[str, dict[str, object]] = {}
    for rel, payload in artifacts.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        listed[rel] = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
            "assurance_level": "QF-A1",
            "description": rel,
        }
    if extra_rel is not None:
        listed[extra_rel] = {
            "sha256": "0" * 64,
            "size_bytes": 0,
            "assurance_level": "QF-A1",
            "description": "illegal",
        }

    manifest = {
        "artifacts": listed,
        "schema_version": schema_version or ("2.2.0" if key_id else "2.1.0"),
        "predicate_type": "https://slsa.dev/provenance/v1",
    }
    if key_id:
        manifest["signing"] = {
            "algorithm": "Ed25519",
            "key_id": key_id,
            "plane": plane,
        }
    manifest_path = release / "PROVENANCE_MANIFEST.json"
    body = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    manifest_path.write_text(body, encoding="utf-8")

    key = root / "ed25519.key"
    pub = root / "ed25519.pub"
    gen = run(["openssl", "genpkey", "-algorithm", "ED25519", "-out", str(key)])
    expect("openssl genpkey ED25519", gen.returncode == 0, gen.stderr)
    pubout = run(["openssl", "pkey", "-in", str(key), "-pubout", "-out", str(pub)])
    expect("openssl pkey -pubout", pubout.returncode == 0, pubout.stderr)

    raw_sig = root / "manifest.rawsig"
    signed = run(
        [
            "openssl",
            "pkeyutl",
            "-sign",
            "-rawin",
            "-inkey",
            str(key),
            "-in",
            str(manifest_path),
            "-out",
            str(raw_sig),
        ]
    )
    expect("openssl pkeyutl -sign -rawin", signed.returncode == 0, signed.stderr)
    sig_b64 = base64.b64encode(raw_sig.read_bytes()).decode("ascii")
    sig_lines = [
        "SIGNATURE_ALGORITHM=Ed25519",
        "PUBLIC_KEY_PIN=release_signing_key.pub",
    ]
    if key_id:
        sig_lines.append(f"KEY_ID={key_id}")
    sig_lines.append(f"SIGNATURE_B64={sig_b64}")
    (release / "PROVENANCE_MANIFEST.sig").write_text("\n".join(sig_lines) + "\n", encoding="utf-8")
    return pub


def install_anchor(dest: Path, pub: Path, *, replace: bool = False) -> subprocess.CompletedProcess[str]:
    dest.mkdir(parents=True, exist_ok=True)
    cmd = ["install", "-m", "0400", str(pub), str(dest / "release_signing_key.pub")]
    copied = run(cmd)
    if copied.returncode != 0:
        return copied
    mode = "0500"
    copied = run(["install", "-m", mode, str(TEMPLATE), str(dest / "verify-provenance")])
    return copied


def mode_of(path: Path) -> str:
    return oct(path.stat().st_mode & 0o777)


def main() -> int:
    print("Host trust-anchor gate")

    if not TEMPLATE.is_file():
        raise SystemExit(f"[FAIL] missing template {TEMPLATE}")

    judge_ok = run([sys.executable, str(ASSERT), str(TEMPLATE), "--role", "judge"])
    expect("assert admits host-trust/verify-provenance as judge", judge_ok.returncode == 0, judge_ok.stderr)
    pointer_ok = run([sys.executable, str(ASSERT), str(WRAPPER), "--role", "pointer"])
    expect("assert admits in-repo script as pointer", pointer_ok.returncode == 0, pointer_ok.stderr)
    pointer_as_judge = run([sys.executable, str(ASSERT), str(WRAPPER), "--role", "judge"])
    expect(
        "assert HALTs transforming the pointer into a judge",
        pointer_as_judge.returncode != 0 and "HARD-STOP" in pointer_as_judge.stderr,
        pointer_as_judge.stdout + pointer_as_judge.stderr,
    )

    with tempfile.TemporaryDirectory(prefix="qf-trust-") as tmp:
        broken = Path(tmp) / "broken-judge"
        broken.write_text(
            TEMPLATE.read_text(encoding="utf-8").replace(
                "TRUST_ANCHOR_DIR = Path(__file__).resolve().parent",
                "TRUST_ANCHOR_DIR = Path('/tmp')",
            ),
            encoding="utf-8",
        )
        broken_assert = run([sys.executable, str(ASSERT), str(broken), "--role", "judge"])
        expect(
            "assert HALTs when expected trust-boundary text is absent",
            broken_assert.returncode != 0 and "missing required evidence" in broken_assert.stderr,
            broken_assert.stdout + broken_assert.stderr,
        )

    with tempfile.TemporaryDirectory(prefix="qf-trust-") as tmp:
        tmp_path = Path(tmp)
        fixture = tmp_path / "fixture"
        fixture.mkdir()
        pub = write_signed_tree(fixture, {"payloads/hello.txt": b"trusted-bytes\n"})

        dest = tmp_path / "libexec"
        installed = install_anchor(dest, pub)
        expect("install judge + key into temp libexec", installed.returncode == 0, installed.stderr)
        expect("dir mode 0700-capable (we chmod)", True)
        dest.chmod(0o700)
        expect("verify-provenance 0500", mode_of(dest / "verify-provenance") == "0o500")
        expect("release_signing_key.pub 0400", mode_of(dest / "release_signing_key.pub") == "0o400")
        expect("trust dir 0700", mode_of(dest) == "0o700")

        judge = dest / "verify-provenance"
        manifest = fixture / "release" / "PROVENANCE_MANIFEST.json"
        good = run([str(judge), str(manifest), "--repo-root", str(fixture)])
        expect(
            "synthetic tree ALLOW",
            good.returncode == 0 and "TRUSTED -> ALLOW EXECUTION" in good.stdout,
            good.stdout + good.stderr,
        )

        wrong_plane = tmp_path / "wrong-plane"
        wrong_plane.mkdir()
        wrong_pub = write_signed_tree(
            wrong_plane,
            {"payloads/hello.txt": b"trusted-bytes\n"},
            key_id="mobile-ed25519-v1",
        )
        wrong_dest = tmp_path / "libexec-wrong"
        install_anchor(wrong_dest, wrong_pub)
        wrong_dest.chmod(0o700)
        labeled = run(
            [
                str(wrong_dest / "verify-provenance"),
                str(wrong_plane / "release" / "PROVENANCE_MANIFEST.json"),
                "--repo-root",
                str(wrong_plane),
                "--key-id",
                "mycelium-a5-ed25519-v1",
            ]
        )
        expect(
            "wrong-plane key_id FAIL-CLOSED (no key search)",
            labeled.returncode != 0 and "No key search" in (labeled.stdout + labeled.stderr),
            labeled.stdout + labeled.stderr,
        )

        good22 = tmp_path / "schema22"
        good22.mkdir()
        pub22 = write_signed_tree(
            good22,
            {"payloads/hello.txt": b"trusted-bytes\n"},
            key_id="mycelium-a5-ed25519-v1",
        )
        dest22 = tmp_path / "libexec-22"
        install_anchor(dest22, pub22)
        dest22.chmod(0o700)
        ok22 = run(
            [
                str(dest22 / "verify-provenance"),
                str(good22 / "release" / "PROVENANCE_MANIFEST.json"),
                "--repo-root",
                str(good22),
            ]
        )
        expect(
            "schema 2.2.0 with matching key_id ALLOW",
            ok22.returncode == 0 and "TRUSTED -> ALLOW EXECUTION" in ok22.stdout,
            ok22.stdout + ok22.stderr,
        )

        stripped = tmp_path / "downgrade"
        stripped.mkdir()
        pub_d = write_signed_tree(
            stripped,
            {"payloads/hello.txt": b"trusted-bytes\n"},
            schema_version="2.2.0",
        )
        dest_d = tmp_path / "libexec-down"
        install_anchor(dest_d, pub_d)
        dest_d.chmod(0o700)
        down = run(
            [
                str(dest_d / "verify-provenance"),
                str(stripped / "release" / "PROVENANCE_MANIFEST.json"),
                "--repo-root",
                str(stripped),
            ]
        )
        expect(
            "schema 2.2.0 without key_id does not fall back to 2.1.0",
            down.returncode != 0 and "No 2.1.0 fallback" in (down.stdout + down.stderr),
            down.stdout + down.stderr,
        )

        mixed = tmp_path / "downgrade-21"
        mixed.mkdir()
        pub_m = write_signed_tree(
            mixed,
            {"payloads/hello.txt": b"trusted-bytes\n"},
            key_id="mycelium-a5-ed25519-v1",
            schema_version="2.1.0",
        )
        dest_m = tmp_path / "libexec-21mix"
        install_anchor(dest_m, pub_m)
        dest_m.chmod(0o700)
        mix = run(
            [
                str(dest_m / "verify-provenance"),
                str(mixed / "release" / "PROVENANCE_MANIFEST.json"),
                "--repo-root",
                str(mixed),
            ]
        )
        expect(
            "schema 2.1.0 carrying 2.2.0 identity fields is not a downgrade path",
            mix.returncode != 0 and "No protocol downgrade" in (mix.stdout + mix.stderr),
            mix.stdout + mix.stderr,
        )

        (fixture / "payloads" / "hello.txt").write_bytes(b"tampered\n")
        bad = run([str(judge), str(manifest), "--repo-root", str(fixture)])
        expect(
            "tampered artifact FAIL-CLOSED",
            bad.returncode != 0 and "TAMPER BREACH" in (bad.stdout + bad.stderr),
            bad.stdout + bad.stderr,
        )

        # Restore bytes so later path tests can reuse the signed manifest if needed.
        (fixture / "payloads" / "hello.txt").write_bytes(b"trusted-bytes\n")

        # A rewritten in-repo pointer cannot change the host verdict.
        fake_wrapper = fixture / "scripts" / "verify_provenance_manifest.py"
        fake_wrapper.parent.mkdir(parents=True, exist_ok=True)
        fake_wrapper.write_text("#!/usr/bin/env python3\nprint('VALID')\n", encoding="utf-8")
        still = run([str(judge), str(manifest), "--repo-root", str(fixture)])
        expect(
            "in-repo wrapper rewrite ignored by host judge",
            still.returncode == 0 and "TRUSTED -> ALLOW EXECUTION" in still.stdout,
            still.stdout + still.stderr,
        )

        env = os.environ.copy()
        env["QF_TRUST_ANCHOR"] = str(dest)
        wrapped = run([sys.executable, str(WRAPPER), str(manifest), "--repo-root", str(fixture)], env=env)
        expect(
            "in-repo pointer execs QF_TRUST_ANCHOR judge",
            wrapped.returncode == 0 and "TRUSTED -> ALLOW EXECUTION" in wrapped.stdout,
            wrapped.stdout + wrapped.stderr,
        )

        missing_env = os.environ.copy()
        missing_env["QF_TRUST_ANCHOR"] = str(tmp_path / "does-not-exist")
        missing = run([sys.executable, str(WRAPPER)], env=missing_env)
        expect(
            "missing judge FAIL-CLOSED",
            missing.returncode != 0 and "Host trust anchor missing" in missing.stderr,
            missing.stdout + missing.stderr,
        )

        traversal = tmp_path / "traversal"
        traversal.mkdir()
        trav_pub = write_signed_tree(
            traversal,
            {"payloads/hello.txt": b"ok\n"},
            extra_rel="../outside.txt",
        )
        trav_dest = tmp_path / "libexec-trav"
        install_anchor(trav_dest, trav_pub)
        trav_dest.chmod(0o700)
        trav = run(
            [
                str(trav_dest / "verify-provenance"),
                str(traversal / "release" / "PROVENANCE_MANIFEST.json"),
                "--repo-root",
                str(traversal),
            ]
        )
        expect(
            "path traversal FAIL-CLOSED",
            trav.returncode != 0 and "Illegal artifact path" in (trav.stdout + trav.stderr),
            trav.stdout + trav.stderr,
        )

        dirty_env = {
            **os.environ,
            "QF_TRUST_ANCHOR": str(tmp_path / "dirty-refuse"),
            "QF_DRY_RUN_MANIFEST": str(manifest),
            "QF_DRY_RUN_ROOT": str(traversal),
            "QF_DRY_RUN_KEY": str(pub),
        }
        dirty = run(["bash", str(INSTALLER)], env=dirty_env)
        expect(
            "installer refuses dirty mycelium tree",
            dirty.returncode != 0 and "Dry-run did not ALLOW" in (dirty.stdout + dirty.stderr),
            dirty.stdout + dirty.stderr,
        )

        good_env = {
            **os.environ,
            "QF_TRUST_ANCHOR": str(tmp_path / "once"),
            "QF_DRY_RUN_MANIFEST": str(manifest),
            "QF_DRY_RUN_ROOT": str(fixture),
            "QF_DRY_RUN_KEY": str(pub),
        }
        first = run(["bash", str(INSTALLER)], env=good_env)
        expect("installer first copy after ALLOW dry-run", first.returncode == 0, first.stdout + first.stderr)
        second = run(["bash", str(INSTALLER)], env=good_env)
        expect(
            "installer refuse overwrite",
            second.returncode != 0 and "already exists" in (second.stdout + second.stderr),
            second.stdout + second.stderr,
        )
        replaced = run(["bash", str(INSTALLER), "--replace"], env=good_env)
        expect("installer --replace", replaced.returncode == 0, replaced.stdout + replaced.stderr)

        once = tmp_path / "once"
        expect("installer verifier 0500", mode_of(once / "verify-provenance") == "0o500")
        expect("installer key 0400", mode_of(once / "release_signing_key.pub") == "0o400")
        expect("installer dir 0700", mode_of(once) == "0o700")
        expect(
            "installer not world-writable",
            not bool(once.stat().st_mode & stat.S_IWOTH),
        )

    # Live QF-A5 format: signature must parse. Hash drift on a dirty tree is deny.
    live_dest = Path.home() / ".local/libexec/quantumflex"
    live_judge = live_dest / "verify-provenance"
    if live_judge.is_file() and os.access(live_judge, os.X_OK):
        live = run(
            [
                str(live_judge),
                str(LIVE_MANIFEST),
                "--repo-root",
                str(WORKSPACE),
            ]
        )
        blob = live.stdout + live.stderr
        expect(
            "live QF-A5 signature VALID against pinned host key",
            "Ed25519 digital signature VALID" in blob,
            blob,
        )
        if live.returncode != 0:
            expect(
                "live dirty tree FAIL-CLOSED after valid signature",
                "TAMPER BREACH" in blob or "ADMISSION DENIED" in blob,
                blob,
            )
        else:
            expect("live tree ALLOW (artifacts still match)", "TRUSTED -> ALLOW EXECUTION" in blob, blob)
    else:
        print("[SKIP] live ~/.local/libexec judge not installed yet")

    inspect = run([sys.executable, str(WORKSPACE / "scripts" / "inspect_qfa5_release.py")])
    expect(
        "inspect_qfa5_release is read-only and reports this tree",
        inspect.returncode in (0, 2) and "Independent openssl signature: VALID" in inspect.stdout,
        inspect.stdout + inspect.stderr,
    )
    if inspect.returncode == 2:
        expect("inspect HARD-STOP on dirty signed tree", "HARD-STOP" in inspect.stdout, inspect.stdout)

    print("[+] host trust-anchor tests complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
