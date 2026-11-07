#!/usr/bin/env python3
"""Command-line entry point for AMARA/ATHENA task checkpoint recovery."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_layer.task_checkpoint import main

if __name__ == "__main__":
    raise SystemExit(main())
