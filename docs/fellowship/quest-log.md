# Quest Log

**Last updated:** 2026-10-15

## Open

Decisions and commitments that survive across sessions. One line per entry, dated.

- 2026-10-08 — DECIDED (Rock): admission requires attestation. `evaluate_all_invariants()` must not ADMIT unless a TPM quote is cryptographically verified; until quote verification exists, every composite verdict is DENY.
- 2026-10-08 — DECIDED (Rock): Option A — no push. Patches + encrypted backup only. Option B (empty private repo, new passphrase-protected SSH key, push cleaned history from Yoga, then layer branches if ancestors match) is revisited only after sort + credential rotation, not before.
- 2026-10-14 — FINDING: legacy 3-of-5 exposed on-host (shard 1 password in agent transcripts; shards 4–5 in an unencrypted stego PNG). Path chosen: offline authority migration to a new root, preserving the historical ledger. Only Claude sessions from here on.
- 2026-10-15 — DONE (CLAIMED by ceremony output; ledger/engine/tool hashes agent-checked): authority genesis sealed, manifest `~/.local/state/quantum-flex-mycelium/authority-genesis-20261015T121219Z.json`.
- 2026-10-15 — DONE: genesis topology disk-separation invariant verified. Share 2 moved off-host to `qf-g6:~/qfx-authority-share2/` (SHA-256: `811b157f...` matching manifest). Local `~/qfx-authority-share2/` removed from Yoga. Custody topology: Yoga: Share 1; G6: Share 2; USB QFX_SHARD_B: Shares 3 & 4; Pixel 11 Pro: Share 5.
- 2026-10-15 — DONE: Ollama GPU acceleration enabled on AMD Radeon 840M (Krackan Point `gfx1152` mapped to `gfx1150` via ROCm override in `/etc/systemd/system/ollama.service.d/override.conf`), verified 100% GPU offload under systemd override without CPU lockups.
- 2026-10-15 — DONE: Physical IBM Quantum experiments executed on real silicon (`ibm_fez`, Heron r2 156-qubit; Job `db8lbbtckpjs73b17plg` QRNG 3.9831 bits entropy; Job `db8lc6694fic73etkmt0` Bell state 68.95% correlation). Kept strictly isolated as research with zero engine entropy credit per NIST SP 800-90B.
- 2026-10-15 — DONE: Tailscale ACL policy updated and verified isolating Pixel 11 Pro (`100.64.1.22`) strictly to Yoga Ollama (`100.64.1.31:11434`), denying all sensitive services and node-to-node reachability.
- 2026-10-15 — OPEN: destroy pre-genesis shard material (`~/qfx-shards-genesis/`, stego PNG) only after confirming the old shares no longer authenticate the ledger.
