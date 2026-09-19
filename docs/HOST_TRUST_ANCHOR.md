# Host trust anchor (QF-R2)

The defendant cannot be the judge.

If `scripts/verify_provenance_manifest.py` and `release/release_signing_key.pub`
live inside the tree they evaluate, a compromised branch can rewrite the
artifact, the manifest, and the verifier in one blast radius and print
`VALID`. The host judge sits outside that domain.

```
TRUST DOMAIN A (host, not git)          TRUST DOMAIN B (mycelium checkout)
--------------------------------        --------------------------------
~/.local/libexec/quantumflex/           runner / engine / policies
  verify-provenance          0500       release/PROVENANCE_MANIFEST.json
  release_signing_key.pub    0400       release/PROVENANCE_MANIFEST.sig
directory                    0700       everything else

systemd ExecStartPre ──evaluates──► Domain B
```

Existence is not authority. A Git commit, a hash on disk, or an in-repo
script saying "VALID" does not admit execution.

## What this is not

- Not a live edit of Yoga `~/.config/systemd/user/` or
  `~/.config/containers/systemd/`. Those units are outside this repo.
  `systemd-backup/` is the template. Copy + `systemctl --user daemon-reload`
  on the operator host.
- Not QF-R1 (SELinux label separation), QF-R3 (image digest pin), or
  QF-R4 (egress deny). Those gates stay open.
- Not a claim that a prompt-supplied `python:3.14-slim@sha256:…` digest
  was audited. Do not paste one into a Quadlet as if it were locked.
- Not QF-A5 signing of this checkout. The release private key stays
  outside the repo (`QF_RELEASE_KEY_PATH`). This change does not mint a
  new `PROVENANCE_MANIFEST.sig`.

## Operator path (Yoga)

Do not start with the installer. Inspect the real QF-A5 objects, dry-run
against a known-good tree, then lock. The step-by-step is
`docs/QF_R2_OPERATOR_RUNBOOK.md`.

```bash
python3 scripts/inspect_qfa5_release.py    # must exit 0
./scripts/install_host_trust_anchor.sh     # refuses unless dry-run ALLOW'd
```

## Install (once, from a tree you already trust)

```bash
./scripts/install_host_trust_anchor.sh
# later, only after you re-verify the checkout:
./scripts/install_host_trust_anchor.sh --replace
```

Override the destination with `QF_TRUST_ANCHOR` (tests and alternate
homes). The installer refuses root and refuses to overwrite an existing
judge or pinned key without `--replace`.

Permission layout after install:

| Path | Mode |
| --- | --- |
| `~/.local/libexec/quantumflex/` | `0700` |
| `verify-provenance` | `0500` |
| `release_signing_key.pub` | `0400` |

`host-trust/verify-provenance` in git is a template. The judge is the
installed 0500 file. It understands the QF-A5 on-disk format this repo
actually signs (`artifacts[path].sha256` objects, `SIGNATURE_B64=`
sidecar). A verifier that treats artifact entries as bare hex, or the
sidecar as raw base64-only, will fail-closed on a real release.

## Evaluate a checkout

```bash
~/.local/libexec/quantumflex/verify-provenance \
  /path/to/mycelium/release/PROVENANCE_MANIFEST.json \
  --repo-root /path/to/mycelium
echo "Verifier Exit Code: $?"
```

Exit 0 means the pinned key accepted the manifest signature **and** every
declared artifact matched. Signature-valid + hash mismatch is deny, not
allow — that is the expected result on a dirty working tree.

`python3 scripts/verify_provenance_manifest.py` only execs the installed
judge (`QF_TRUST_ANCHOR` or `~/.local/libexec/quantumflex/verify-provenance`).
If the judge is missing, it fail-closes. Editing the pointer cannot change
a systemd unit that already calls Domain A.

## Service pre-flight

`systemd-backup/quantum-flex-engine-mycelium.service` and
`systemd-backup/quantumflex-runner.container` set:

```
ExecStartPre=%h/.local/libexec/quantumflex/verify-provenance \
  %h/mycelium/release/PROVENANCE_MANIFEST.json \
  --repo-root %h/mycelium
```

On Yoga that expands to `/home/quant/...`. A failed pre-flight stops
Podman from instantiating. UNKNOWN ≠ ALLOW.
