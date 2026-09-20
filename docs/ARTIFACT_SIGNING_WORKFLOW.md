# Artifact signing workflow

One ceremony shape, multiple artifact classes. Not a different crypto
story per file.

```
hash → (manifest) → authority signature → pinned verify → gate
```

Signing without a gate is documentation. A gate without a stable pin is
theater.

Philosophy of the rest of the architecture is `docs/LIVING_COMPUTATION_CYCLE.md`.
This file is only the signing plane.

## Ceremony (all three workflows)

1. **BUILD** — record commit and toolchain.
2. **COLLECT** — the path list that *is* the release.
3. **HASH** — SHA-256 of file bytes into a manifest.
4. **CANONICALIZE** — `json.dumps(..., indent=2, sort_keys=True) + "\n"`
   (`scripts/qf_signing_ceremony.py`). Encode once, then sign those bytes.
   Sidecar `TIMESTAMP=` is unsigned.
5. **SIGN** — offline Ed25519 (`openssl pkeyutl -sign -rawin`). Private
   key never in git or GitHub Actions.
6. **PUBLISH** — artifacts + manifest + detached `.sig` (`SIGNATURE_B64=`,
   optional `KEY_ID=`).
7. **VERIFY** — one pinned pubkey, one `key_id`. No keyring search.
8. **ADMIT** — start/link/install only on exit 0.

Roles: builder produces bytes (untrusted). Signer holds the key.
Publisher moves files. Verifier has only the public pin. Runtime
fail-closes.

## Planes (blast radius)

| Plane | `key_id` | Signed object | Pin | Gate |
| --- | --- | --- | --- | --- |
| Host release (A5) | `mycelium-a5-ed25519-v1` | `release/PROVENANCE_MANIFEST.json` | `release/release_signing_key.pub` → libexec | `verify-provenance` / ExecStartPre |
| Mobile OTA | `mobile-ed25519-v1` | per-file or small manifest | **not the A5 key** | `mobile/setup-mobile.sh` today: **hash only** |
| Runtime package | `quantumflex-admission-ed25519-v1` | `QuantumFlexAdmission.json` | sign only when the prefix is exported | `AdmitQuantumFlex.cmake` today: **hash binding**, `signed: false` |

One monetization vector → one repository or published package boundary →
one `key_id` namespace. Do not share A5 and mobile keys.

## What exists vs the gap

**Workflow 1 — Host A5 (primary).** Generator writes schema **2.2.0**
with `signing.key_id`. The live `release/PROVENANCE_MANIFEST.json` is
still **2.1.0** (no `key_id`); the judge accepts that historical shape
and pins the pubkey file. Next operator ceremony (offline key) produces
2.2.0. External judge: `host-trust/verify-provenance`. Do not regex
the in-repo pointer into that judge.

**Workflow 2 — Mobile.** `setup-mobile.sh` checks a baked SHA-256 of
`qflex_cli.py`. That answers “same bytes?”, not “this authority”.
Detached sig + `mobile-ed25519-v1` is the next step on that plane, not
a fourth workflow.

**Workflow 3 — Admission.** `cmake --install` writes an unsigned
receipt. Mycelium verifies hashes. Origin signature is for a *foreign
or aged prefix*, using the A5 ceremony over the receipt bytes — later,
when you actually export. Unsigned receipt is self-consistency only.

Do not invent Workflow 4 until one of these is boring.

## CI

Default: **verify only**. `QF_RELEASE_KEY_PATH` must not enter Actions.
The `bind-and-sign` job’s Cosign/OIDC path is a **different** plane
(transparency), not `mycelium-a5-ed25519-v1`. Sigstore is additive, not
a replacement for the offline pin.

## Failure modes this shape is built against

- Verifier inside the judged tree → host trust anchor (QF-R2).
- Non-canonical JSON → one encoder, sign those bytes.
- Unsigned admission for a remote prefix → keep `signed: false` until
  the export ceremony exists.
- Same key for mobile and A5 → separate `key_id`s.
- “Try all keys” → `enforce_single_pin`; mismatch is deny.

## Operator commands (Workflow 1)

```bash
# Offline, after inspect_qfa5_release.py would be the *new* known-good set:
python3 scripts/generate_provenance_manifest.py \
  --key ~/.config/quantumflex/vault/release_ed25519.key \
  --key-id mycelium-a5-ed25519-v1

python3 host-trust/verify-provenance \
  release/PROVENANCE_MANIFEST.json --repo-root . \
  --key-id mycelium-a5-ed25519-v1
```

This checkout is not a newly signed 2.2.0 release. Do not mint a
signature without the offline key.
