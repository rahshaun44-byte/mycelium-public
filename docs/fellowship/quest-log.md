# Quest Log

**Last updated:** 2026-10-08

## Open

Decisions and commitments that survive across sessions. One line per entry, dated.

- 2026-10-08 — DECIDED (Rock): admission requires attestation. `evaluate_all_invariants()` must not ADMIT unless a TPM quote is cryptographically verified; until quote verification exists, every composite verdict is DENY.
- 2026-10-08 — DECIDED (Rock): Option A — no push. Patches + encrypted backup only. Option B (empty private repo, new passphrase-protected SSH key, push cleaned history from Yoga, then layer branches if ancestors match) is revisited only after sort + credential rotation, not before.
