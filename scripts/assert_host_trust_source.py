#!/usr/bin/env python3
"""Assert the host-judge *source* before any bytes are written to libexec.

This is not a transformer. Missing evidence means HALT and write nothing.
`scripts/verify_provenance_manifest.py` is a pointer — treating it as the
judge source is a Hard-Stop. The only admitted template is
`host-trust/verify-provenance`, inspected against its exact current text.
"""

from __future__ import annotations

import argparse
import py_compile
import sys
from pathlib import Path

# Exact strings from host-trust/verify-provenance as it exists in this tree.
# If a checkout rewrites the template, this must fail rather than "adapt."
JUDGE_REQUIRED = (
    'TRUST_ANCHOR_DIR = Path(__file__).resolve().parent',
    'DEFAULT_KEY_PATH = TRUST_ANCHOR_DIR / "release_signing_key.pub"',
    'if line.startswith("SIGNATURE_B64="):',
    'value = entry.get("sha256")',
    "path.relative_to(root)",
    "openssl",
    "pkeyutl",
    "-rawin",
)

# Shapes that mean "this is not the host judge."
JUDGE_FORBIDDEN = (
    "In-repo pointer",
    "os.execv",
    "PUB_KEY_PATH = os.path.join(RELEASE_DIR",
    "WORKSPACE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))",
)

POINTER_REQUIRED = (
    "In-repo pointer",
    "os.execv",
    "Host trust anchor missing",
)

POINTER_FORBIDDEN = (
    'TRUST_ANCHOR_DIR = Path(__file__).resolve().parent',
    "SIGNATURE_B64=",
    "VERDICT: TRUSTED",
)


def halt(message: str) -> None:
    print(f"[HARD-STOP] {message}", file=sys.stderr)
    raise SystemExit(1)


def load_text(path: Path) -> str:
    if not path.is_file():
        halt(f"source missing: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        halt(f"unreadable source {path}: {exc}")


def require_needles(text: str, needles: tuple[str, ...], *, label: str) -> None:
    missing = [needle for needle in needles if needle not in text]
    if missing:
        halt(f"{label} missing required evidence {missing!r}")


def forbid_needles(text: str, needles: tuple[str, ...], *, label: str) -> None:
    present = [needle for needle in needles if needle in text]
    if present:
        halt(f"{label} contains forbidden shape {present!r}")


def compile_source(path: Path) -> None:
    try:
        py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError as exc:
        halt(f"syntax compile failed for {path}: {exc}")


def assert_judge(path: Path) -> None:
    text = load_text(path)
    require_needles(text, JUDGE_REQUIRED, label=f"judge {path}")
    forbid_needles(text, JUDGE_FORBIDDEN, label=f"judge {path}")
    compile_source(path)
    print(f"[+] source shape VALID (judge): {path}")


def assert_pointer(path: Path) -> None:
    text = load_text(path)
    require_needles(text, POINTER_REQUIRED, label=f"pointer {path}")
    forbid_needles(text, POINTER_FORBIDDEN, label=f"pointer {path}")
    compile_source(path)
    print(f"[+] source shape VALID (pointer, not a judge): {path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Assert QF-R2 source shape. Writes nothing. Missing evidence HALTs."
    )
    parser.add_argument("path", type=Path, help="File to inspect")
    parser.add_argument(
        "--role",
        choices=("judge", "pointer"),
        required=True,
        help="Expected role of the file",
    )
    args = parser.parse_args()
    if args.role == "judge":
        assert_judge(args.path.resolve())
    else:
        assert_pointer(args.path.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
