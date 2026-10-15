#!/usr/bin/env bash
# The previous implementation removed ledger.dat and performed fresh genesis.
# It did not migrate/reseal existing state, and could strand a running node.
set -euo pipefail

echo '[!] Shard rotation is unavailable: authenticated ledger resealing is not implemented.' >&2
echo '[!] No state or recovery files were changed.' >&2
echo '[!] Preserve existing shares and backups. Verify the original threshold against the saved ledger before recovery.' >&2
exit 2
