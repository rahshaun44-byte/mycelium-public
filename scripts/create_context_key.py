#!/usr/bin/env python3
"""Create a one-time owner-only encryption key for the QF Context API."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

from cryptography.fernet import Fernet

KEY_PATH = Path(
    os.environ.get(
        "QF_CONTEXT_ENCRYPTION_KEY_FILE",
        str(Path.home() / ".config" / "quantumflex" / "context.key"),
    )
)


def main() -> int:
    parent = KEY_PATH.parent
    try:
        info = parent.lstat()
    except OSError as exc:
        print(f"context key directory is unavailable: {exc}", file=sys.stderr)
        return 1
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) & 0o077
    ):
        print("context key directory must be owned and private (mode 0700)", file=sys.stderr)
        return 1

    try:
        fd = os.open(
            KEY_PATH,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
    except FileExistsError:
        print(f"refusing to overwrite existing context key: {KEY_PATH}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"cannot create context key: {exc}", file=sys.stderr)
        return 1

    try:
        with os.fdopen(fd, "wb") as key_file:
            key_file.write(Fernet.generate_key() + b"\n")
            key_file.flush()
            os.fsync(key_file.fileno())
        dir_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError as exc:
        try:
            KEY_PATH.unlink()
        except OSError:
            pass
        print(f"cannot persist context key: {exc}", file=sys.stderr)
        return 1

    print(f"created owner-only context key: {KEY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
