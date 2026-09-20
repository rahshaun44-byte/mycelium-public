#!/usr/bin/env python3
"""In-repo pointer — not the judge.

The defendant cannot evaluate itself. This script only execs the host trust
anchor at ~/.local/libexec/quantumflex/verify-provenance. Editing this file
cannot change the verdict of a service that already points at the libexec copy.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def judge_path() -> Path:
    override = os.environ.get("QF_TRUST_ANCHOR")
    root = Path(override).expanduser() if override else Path.home() / ".local/libexec/quantumflex"
    return root / "verify-provenance"


def main() -> int:
    judge = judge_path()
    if not judge.is_file() or not os.access(judge, os.X_OK):
        print(
            "[FAIL-CLOSED] Host trust anchor missing or not executable:\n"
            f"  {judge}\n"
            "Install once from a trusted checkout:\n"
            "  ./scripts/install_host_trust_anchor.sh",
            file=sys.stderr,
        )
        return 1

    repo_root = Path(__file__).resolve().parent.parent
    args = [str(judge)]
    if len(sys.argv) == 1:
        args.append(str(repo_root))
    else:
        args.extend(sys.argv[1:])

    os.execv(str(judge), args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
