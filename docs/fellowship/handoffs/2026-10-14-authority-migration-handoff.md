# Handoff — Authority migration (2026-10-14)

**From:** Claude session 68509e1f (ended mid-task; the user is restarting with Claude only)
**Repo:** `~/mycelium`, branch `fix/w1-w4` @ `1a596b9`, dirty tree. Nothing committed this session.
**Protocol:** QF-ALIGN. Rock runs every live command. Never echo passwords, shares or secrets.

## Decision in force

The legacy 3-of-5 authority is **retired, not recovered**:
- Shards 1, 4 and 5 were readable on this host. The shard-1 password is in agent transcripts; shards 4 and 5 are in an unencrypted stego PNG in the Gemini cache.
- Treat the secret itself as exposed. Do not unlock with it and do not re-split it.
- Path: archive the legacy ledger, then genesis a fresh authority with sealed shares.
- The legacy ledger has the empty state root, so no evidence is lost. Live `ledger.dat` sha256 is `d366f9c50a693c79dca3c6e1fdb203ab052b2ad6ecc631ed5e947ceddef87f6a`.

## Verified this session (by Rock's output or agent read-only checks)

- **USB vault:** `QFX_BACKUP/quantumflex_vault.enc` opens with Rock's password.
  - It contains one file, `quantumflex_watermark.png` (1,537,296 B).
  - That PNG's sha256 `ac1ea25f…045cf` equals the Gemini cache copy.
- **Shard 1:** `~/qfx-shards-genesis/shard_1.enc` opens with the 38-char transcript password (sha256 prefix `fe91bd0b0ff05ead`).
- **Checker:** rebuilt 13:10 from reviewed source, binary sha256 `0a7016c5…af2107`; `tests/test_legacy_recovery_check.py` reported 37 passed.
- **Engine:** `quantum-flex-engine-mycelium.service` is active and LOCKED, PID 34046 at the time.
- **No share values** appear in either Gemini session's files; a regex search over them found none.

## Built this session — written but NOT yet compiled or run

Auto mode began blocking shell commands, so none of this has run.

| File | Purpose |
|---|---|
| `tools/qf_authority_split.cpp` | Native: RAND_bytes 32-byte secret, 3-of-5 split, verifies all 10 subsets, emits 5 `id:hex` lines only to a pipe (refuses a TTY). An earlier version of this file compiled and smoke-tested OK (5×64-hex lines, TTY refusal). |
| `tools/qf_authority_ceremony.py` | `archive-legacy --expect-sha256 <hex>`: engine must be stopped; link+unlink to read-only `ledger.dat.archive-legacy-authority-<UTC>`; writes a manifest. `genesis --dest D1,…,D5`: engine running UNINITIALIZED; 5 distinct hidden passphrases (≥12 B) taken before the secret exists; gpg AES256 seal from memory; reopen-and-compare; INIT; all 10 subsets checked against the new ledger; manifest in `~/.local/state/quantum-flex-mycelium/`. Refuses agent, repo, engine and temp dirs; refuses ≥3 shares on one filesystem and >1 share on the home filesystem. |
| `tools/qf_recovery.py` (edited) | Added a throwaway GNUPGHOME, `gpg_open`, and the `--sealed-shares a,b,c` unlock/check mode. Passphrase goes via fd 3, never argv. |
| `tests/test_authority_ceremony.py` | Synthetic end to end against an isolated engine: genesis → seal → all subsets MATCH → restart LOCKED → UNLOCK with sealed shares. Also covers refusal paths, destination and passphrase rules, and archive. |

**Concurrent edit warning.** Another agent, probably the Codex session that wrote the G6 handoff, edited `tools/qf_recovery.py` during this session. It added `HOLD_FILE = ~/.local/state/quantum-flex-mycelium/unlock.hold`, and `enforce_unlock_hold()` blocks `--unlock`. Kept on purpose. Remove the hold file **only after** a successful genesis.

## Next steps, in order

1. **Make sure the other agent is stopped.** Then run `git status` and `git diff --stat`, and confirm nothing else moved.
2. **Review and build.** Review `tools/qf_authority_ceremony.py` and the `qf_recovery.py` additions; this is the first time anyone has read them. Then build the natives:
   ```bash
   cd ~/mycelium && for t in qf_authority_split qf_legacy_recovery_check; do s=tools/$t.cpp; g++ -std=c++20 -O2 -Wall -Wextra -Werror -I quantumflex/include $s quantumflex/src/crypto/crypto_shamir.cpp -lcrypto -o build_recovery_check/$t || break; done; sha256sum build_recovery_check/*
   ./venv/bin/python3 -m pytest -q tests/test_authority_ceremony.py tests/test_legacy_recovery_check.py
   ```
   Fix until green. Get a Legolas review, then a Boromir review, since this is custody code.
3. **Prepare custody media (physical, Rock).**
   - Unplug the shard-2 USB from G6. The Codex handoff claims it is mounted at `/mnt/qfx_shard`; this is unverified.
   - Choose 5 destination directories: at most 1 on the home filesystem, and no single device holding 3 or more shares.
4. **Live ceremony (Rock runs, one step at a time, output pasted back):**
   1. `systemctl --user stop quantum-flex-engine-mycelium.service`. Expected: exits non-zero (a LOCKED state is not serialized) and `ledger.dat` is unchanged. Re-check the sha256 equals `d366f9c5…`.
   2. `./venv/bin/python3 tools/qf_authority_ceremony.py archive-legacy --expect-sha256 d366f9c50a693c79dca3c6e1fdb203ab052b2ad6ecc631ed5e947ceddef87f6a`
   3. `systemctl --user start quantum-flex-engine-mycelium.service`. The engine writes the UNINITIALIZED envelope.
   4. `./venv/bin/python3 tools/qf_authority_ceremony.py genesis --dest <D1>,<D2>,<D3>,<D4>,<D5>`. Expected: `GENESIS SEALED`.
   5. Restart the engine to confirm it comes up LOCKED. Then `tools/qf_recovery.py --check --sealed-shares a,b,c`; expected `MATCH`.
5. **Retire the legacy material.** Only after step 4 passes, and only by Rock's order:
   - stego PNG in `~/.gemini/antigravity/brain/a7be76e2…/`
   - `~/qfx-shards-genesis/shard_1.enc`
   - the USB vault
   - leaked-password transcripts in `~/.gemini` and `~/.codex`
   Remove `unlock.hold` at the same time.
6. **Follow-ups.**
   - `ledger.dat` mode is 0664; make it 0600.
   - The mTLS CA private key (`mtls/ca.key`) sits beside the engine, so mTLS is not a same-user boundary.
   - `tools/genesis_tool.cpp` writes plaintext shard files and `recover` prints the secret. Retire it or gate it.
   - Update `scripts/unlock_engine.sh` to point at `--sealed-shares`.

## Other open items

- **Codebase map:** updated this session (`docs/fellowship/codebase-map.md`).
- **`specs/pytest_run_2026-10-08.log`:** misfiled log; Rock to decide.
- **G6 handoff (Codex, 2026-10-14):** treat as CLAIMED. It tells agents to bypass the paste-guard with `ssh BatchMode` and run on G6; do not. It mislabels `json.dumps(sort_keys)` as RFC 8785, uses unpinned `kafka-ui:latest`, and gives `qfx` passwordless sudo.
- **qf-public:** private. Two specific tailnet IPs are in `sentinel/policies/trusted_ips.json` on `origin/main`. `.gitignore` gaps: `.gemini/`, `*.dat`, `evidence_ledger.jsonl`, `quantum_entropy.{hex,bin}`.
