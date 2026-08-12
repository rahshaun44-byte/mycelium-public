#!/usr/bin/env python3
import logging
import sys
import os

import lif_sentinel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [Quantum Flex] - %(levelname)s - %(message)s')

# journalctl unit to watch — no root/file-permission requirements this way
TARGET_UNIT = os.getenv("SENTINEL_TARGET_UNIT", "sshd")

def main():
    logging.info("========================================")
    logging.info("Active Defense Daemon Online (alert-only)")
    logging.info("========================================")

    try:
        # LIFNeuron.fire() already logs each alert; this loop just keeps the
        # generator running. Deliberately alert-only — see CLAUDE.md on why
        # this doesn't auto-quarantine or auto-block anything.
        for _ in lif_sentinel.process_journal(TARGET_UNIT):
            pass

    except KeyboardInterrupt:
        logging.info("Daemon interrupted by operator.")
    except Exception as e:
        logging.error(f"Critical Matrix Failure: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
