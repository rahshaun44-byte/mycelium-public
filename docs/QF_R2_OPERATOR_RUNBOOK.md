# QF-R2 operator runbook — inspect, then lock

You are the only person who can finish this. The cloud agent is not Yoga.
It cannot see `/home/quant`, cannot edit live systemd/Quadlet units, and
cannot mint a new QF-A5 signature (the private key is not in this repo).

**Rule:** the judge lives outside the repo, speaks the real QF-A5 contract,
and is locked only after *you* have inspected the signed objects and a
dry-run against a **known-good** tree exits 0.

UNKNOWN ≠ ALLOW. Signature-valid + hash mismatch = DENY. A dirty tree is
not a verified baseline.

```
YOU inspect signed artifacts + units
        │
        ▼
independent openssl + sha256 (not the in-repo pointer)
        │
   ┌────┴────┐
 FAIL       PASS every artifact
   │           │
   X           ▼
 HARD-STOP   dry-run host-trust/verify-provenance
             (template, still in git — evaluation only)
                │
           ┌────┴────┐
          DENY      ALLOW
           │           │
           X           ▼
        HARD-STOP   ./scripts/install_host_trust_anchor.sh
                    lock ~/.local/libexec/quantumflex  0700/0500/0400
                       │
                       ▼
                    re-run the *installed* judge — must still be 0
                       │
                       ▼
                    copy ExecStartPre into live units
                    systemctl --user daemon-reload
                       │
                       ▼
                    negative test (tamper → service must not start)
```

`scripts/verify_provenance_manifest.py` is an exec-only pointer. Do not
treat it as the judge. Do not run `install_host_trust_anchor.sh` first
and “inspect later.”

---

## 0. What QF-A5 actually is

Authoritative files (this is the contract, not a sketch):

| File | Role |
| --- | --- |
| `release/PROVENANCE_MANIFEST.json` | Schema **2.1.0**, SLSA-style predicate, artifact map |
| `release/PROVENANCE_MANIFEST.sig` | Detached Ed25519 sidecar, `SIGNATURE_B64=` |
| `release/release_signing_key.pub` | Bootstrap PEM (Ed25519). Copied to libexec at lock time |
| `scripts/generate_provenance_manifest.py` | Signer. Private key via `--key` / `QF_RELEASE_KEY_PATH` (default `~/.config/quantumflex/vault/release_ed25519.key`) |
| `host-trust/verify-provenance` | Judge *template*. Installed copy is the judge |

**On-disk format the judge must accept (or it is a sketch):**

```text
PROVENANCE_MANIFEST.json
  schema_version    = "2.1.0"
  predicate_type    = "https://slsa.dev/provenance/v1"
  build_definition  = { source, builder, assurance_status, security_target, timestamp_utc }
  artifacts[rel]    = { sha256, size_bytes, assurance_level, description }

PROVENANCE_MANIFEST.sig
  SIGNATURE_ALGORITHM=Ed25519
  PUBLIC_KEY_PIN=release_signing_key.pub
  SIGNATURE_B64=<base64 of the 64-byte raw signature>
  TIMESTAMP=...

σ = Sign_Ed25519(raw manifest bytes)
openssl pkeyutl -sign -rawin / openssl pkeyutl -verify -rawin -pubin
```

A verifier that treats `artifacts[path]` as a bare hex string, or the
sidecar as raw base64-only, will reject a valid release. That sketch
was not installed.

`release/MANIFEST.json` (schema 1.5.0) is a **different** policy-bundle
file. It is not QF-A5. Do not point the judge at it.

The current signed release (`timestamp_utc` 2026-09-19T13:36:28Z) binds
git commit `8abffc1f1987c33eabd598c092fc241860f0bd88` and records
`dirty_working_tree: true`. The hashes, not the commit string, are the
authority. `build_check/` is gitignored — you cannot restore the signed
binaries with `git checkout`.

---

## 1. Inventory — every signed artifact

Thirteen paths. Nothing else is QF-A5-authenticated today.

| Path | Level | What you are looking at |
| --- | --- | --- |
| `build_check/quantum_flex_engine` | QF-A1 | Production C++ engine. Gitignored. |
| `build_check/test_verified_core` | QF-A1 | Formal invariant test binary. Gitignored. |
| `include/quantum-flex/verified_core.h` | QF-A1 | C ABI header |
| `src/core/verified_core.c` | QF-A1 | Manual C reference (QF-A4 is still NULL) |
| `pqc-immune-daemon/membrane_health_test.rego` | QF-A1 | Rego unit tests |
| `pqc-immune-daemon/membrane_health.rego` | QF-A2 | Source membrane policy |
| `sentinel/policies/membrane_health.wasm` | QF-A2 | Compiled OPA membrane |
| `sentinel/policies/reserve_invariant.wasm` | QF-A2 | Compiled reserve policy |
| `formal/QuantumFlex_Core.fst` | QF-A3 | F* specification |
| `docs/QFXK_WIRE_PROTOCOL_SPEC.md` | SPEC | Wire protocol |
| `docs/INDEPENDENT_ASSESSMENT_GUIDE.md` | DOC | Assessor guide |
| `docs/SECURITY_TARGET_AND_PROMISES.md` | DOC | Security target |
| `docs/ASSURANCE_LEVELS.md` | DOC | Assurance hierarchy |

**Not in the signed set** (inspect by eye; do not call them verified):

- `systemd-backup/quantum-flex-engine-mycelium.service`
- `systemd-backup/quantumflex-runner.container`
- live `~/.config/systemd/user/*` and `~/.config/containers/systemd/*`
- any container image / digest (QF-R3 is OPEN)
- `runner.py` / Quadlet runtime
- `host-trust/verify-provenance` itself (template; trust is your reading of it)

Expected SHA-256 values are in `release/PROVENANCE_MANIFEST.json`. Do
not retype them from chat. Read the file.

---

## 2. Hard-Stop snapshot of *this* collapse branch

Measured against the signed manifest on the agent that cut this branch
(signature **VALID** via `openssl pkeyutl -verify -rawin`):

| Path | Result |
| --- | --- |
| `docs/INDEPENDENT_ASSESSMENT_GUIDE.md` | MATCH |
| `docs/QFXK_WIRE_PROTOCOL_SPEC.md` | MATCH |
| `docs/SECURITY_TARGET_AND_PROMISES.md` | MATCH |
| `formal/QuantumFlex_Core.fst` | MATCH |
| `pqc-immune-daemon/membrane_health.rego` | MATCH |
| `pqc-immune-daemon/membrane_health_test.rego` | MATCH |
| `sentinel/policies/membrane_health.wasm` | MATCH |
| `sentinel/policies/reserve_invariant.wasm` | MATCH |
| `src/core/verified_core.c` | MATCH |
| `build_check/quantum_flex_engine` | **MISMATCH** (rebuilt; gitignored) |
| `build_check/test_verified_core` | **MISMATCH** (rebuilt; gitignored) |
| `docs/ASSURANCE_LEVELS.md` | **MISMATCH** (QF-R2 doc edit) |
| `include/quantum-flex/verified_core.h` | **MISMATCH** (earlier collapse) |

**This branch is not a known-good tree.** A dry-run MUST exit non-zero.
`./scripts/install_host_trust_anchor.sh` will refuse. That is correct.

Do not lock an anchor from this tree and then tell yourself the
deployment is verified.

---

## 3. On Yoga — step by step

Work as `quant`, never as root. Repo assumed at `/home/quant/mycelium`.
If your checkout path differs, substitute it everywhere.

### 3.1 Confirm you are looking at the real contract

```bash
cd /home/quant/mycelium
git fetch origin mushtrust-anchor-3fbc
git checkout mushtrust-anchor-3fbc   # or merge it; your call
git rev-parse HEAD
git status --porcelain

python3 -m json.tool release/PROVENANCE_MANIFEST.json | less
cat release/PROVENANCE_MANIFEST.sig
cat release/release_signing_key.pub
less host-trust/verify-provenance
less scripts/install_host_trust_anchor.sh
less systemd-backup/quantum-flex-engine-mycelium.service
less systemd-backup/quantumflex-runner.container
```

You are checking, with your own eyes:

1. Manifest schema is `2.1.0` and `artifacts` values are **objects**
   with `sha256`, not bare hex.
2. Sidecar has `SIGNATURE_B64=`.
3. Public key is a PEM `BEGIN PUBLIC KEY` Ed25519 pin you already
   recognize (compare the PEM body to whatever you stored when you
   generated `release_ed25519.key` — if you do not recognize it,
   **HARD-STOP**).
4. The judge template reads `sha256` from objects and `SIGNATURE_B64`
   from the sidecar. If it does not, it is a sketch. Stop.
5. `ExecStartPre=` points at `%h/.local/libexec/quantumflex/verify-provenance`,
   not `scripts/verify_provenance_manifest.py`.

### 3.2 Independent cryptographic inspection (no installer, no libexec write)

```bash
python3 scripts/inspect_qfa5_release.py
echo "inspect exit: $?"
```

Exit **0** = known-good. You may continue to 3.4.

Exit **2** = signature valid, artifacts drifted. **HARD-STOP.** Go to 3.3.

Exit **1** = signature or schema failed. **HARD-STOP.** Do not install.
The tree is not the signed release, or the bootstrap key is wrong.

Optional, fully manual (same checks the inspector runs):

```bash
# 1. Signature over raw manifest bytes
python3 - <<'PY'
import base64, pathlib, subprocess, tempfile
sig = pathlib.Path("release/PROVENANCE_MANIFEST.sig").read_text()
b64 = [l.split("=",1)[1].strip() for l in sig.splitlines() if l.startswith("SIGNATURE_B64=")][0]
raw = tempfile.NamedTemporaryFile(delete=False)
raw.write(base64.b64decode(b64)); raw.close()
raise SystemExit(subprocess.call([
    "openssl","pkeyutl","-verify","-rawin","-pubin",
    "-inkey","release/release_signing_key.pub",
    "-in","release/PROVENANCE_MANIFEST.json",
    "-sigfile", raw.name,
]))
PY

# 2. Per-artifact sha256
python3 - <<'PY'
import hashlib, json
from pathlib import Path
man = json.loads(Path("release/PROVENANCE_MANIFEST.json").read_text())
for rel, meta in man["artifacts"].items():
    p = Path(rel)
    if not p.is_file():
        print("MISSING", rel); continue
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    print("MATCH" if h == meta["sha256"] else "MISMATCH", rel)
PY
```

`openssl` must print `Signature Verified Successfully`. If it does not,
stop. Do not “fix” this by editing the in-repo pointer.

### 3.3 If inspection is not exit 0 — collapse the tree first

You have exactly two honest moves. There is no third.

**Move A — restore the signed bytes, then re-inspect.**

```bash
# Source files that drifted on this branch (binaries cannot come from git):
git show 8abffc1f1987c33eabd598c092fc241860f0bd88:docs/ASSURANCE_LEVELS.md \
  > /tmp/ASSURANCE_LEVELS.signed.md
git show 8abffc1f1987c33eabd598c092fc241860f0bd88:include/quantum-flex/verified_core.h \
  > /tmp/verified_core.signed.h
# Compare, then replace only if you accept those exact bytes as the release.
# Restore quantum_flex_engine and test_verified_core from the machine that
# signed at 2026-09-19T13:36:28Z. git cannot help; build_check/ is ignored.
# A new cmake build will not reproduce the pinned hashes.
```

**Move B — mint a new signed release after you accept the new bytes.**

Only if the offline private key is in *your* custody, not in the repo:

```bash
# Confirm the key is outside mycelium
ls -l ~/.config/quantumflex/vault/release_ed25519.key
# 0400, your uid, not under /home/quant/mycelium

python3 scripts/generate_provenance_manifest.py \
  --key ~/.config/quantumflex/vault/release_ed25519.key

python3 scripts/inspect_qfa5_release.py
# must now be exit 0
```

If the private key is missing, **HARD-STOP.** Do not generate a new
keypair and call it the old pin. That would be a different root of
trust, and every previously signed release becomes unverifiable.

Do not proceed to 3.4 until `inspect_qfa5_release.py` exits 0.

### 3.4 Dry-run the template judge (still not locked)

```bash
python3 host-trust/verify-provenance \
  /home/quant/mycelium/release/PROVENANCE_MANIFEST.json \
  --repo-root /home/quant/mycelium \
  --key /home/quant/mycelium/release/release_signing_key.pub
echo "dry-run exit: $?"
```

Required output:

```
[+] PROVENANCE: Ed25519 digital signature VALID
[+] PROVENANCE: All 13/13 artifacts byte-accurate.
[+] VERDICT: TRUSTED -> ALLOW EXECUTION
```

Exit must be **0**. Anything else is HARD-STOP. Do not install.

This dry-run uses the in-repo template *as an evaluation tool*. It is
not yet the host judge. Admission starts only after step 3.5.

### 3.5 Lock the trust anchor

```bash
./scripts/install_host_trust_anchor.sh
# The installer re-runs the same dry-run and refuses unless it ALLOW'd.

stat -c '%a %n %U' \
  ~/.local/libexec/quantumflex \
  ~/.local/libexec/quantumflex/verify-provenance \
  ~/.local/libexec/quantumflex/release_signing_key.pub
```

Required modes:

| Path | Mode |
| --- | --- |
| `/home/quant/.local/libexec/quantumflex` | `0700` |
| `verify-provenance` | `0500` |
| `release_signing_key.pub` | `0400` |

Owner must be `quant`, not root. If you already have a copy from an
earlier experiment, re-lock only after a passing dry-run:

```bash
./scripts/install_host_trust_anchor.sh --replace
```

`--force-unverified` exists so a denier can be installed from a dirty
tree. Using it means QF-R2 is **not** complete. Do not use it.

### 3.6 Re-run the *installed* judge

```bash
/home/quant/.local/libexec/quantumflex/verify-provenance \
  /home/quant/mycelium/release/PROVENANCE_MANIFEST.json \
  --repo-root /home/quant/mycelium
echo "Verifier Exit Code: $?"
```

Must be exit 0, key path printed as
`/home/quant/.local/libexec/quantumflex/release_signing_key.pub`.

Prove the defendant is not the judge:

```bash
printf '%s\n' '#!/usr/bin/env python3' 'print("VALID")' \
  > /tmp/fake-judge.py
# Do not overwrite scripts/verify_provenance_manifest.py unless you
# immediately restore it. The live unit must not call that file.
/home/quant/.local/libexec/quantumflex/verify-provenance \
  /home/quant/mycelium/release/PROVENANCE_MANIFEST.json \
  --repo-root /home/quant/mycelium
# still exit 0 — the libexec copy did the work
```

### 3.7 Inspect live units, then wire ExecStartPre

The backup files are templates. Live units are under
`~/.config/systemd/user/` and `~/.config/containers/systemd/`.

```bash
# See what is actually enabled today
systemctl --user list-units 'quantumflex*' 'quantum-flex*' --all
ls -l ~/.config/systemd/user/ ~/.config/containers/systemd/ 2>/dev/null

# Diff the backup against whatever is live (paths vary on your host)
diff -u ~/.config/systemd/user/quantum-flex-engine-mycelium.service \
        systemd-backup/quantum-flex-engine-mycelium.service || true
```

Add **exactly** this pre-flight, after you have read the rest of the
unit and confirmed it is the engine you intend to start:

```ini
ExecStartPre=/home/quant/.local/libexec/quantumflex/verify-provenance /home/quant/mycelium/release/PROVENANCE_MANIFEST.json --repo-root /home/quant/mycelium
```

Do **not**:

- point `ExecStartPre` at `scripts/verify_provenance_manifest.py`
- paste a prompt-supplied `python:3.14-slim@sha256:…` as if it were audited
- set `SecurityLabelDisable=true` and call SELinux an enforcing boundary
- uncomment `Network=none` unless you have proven the runner needs no egress
- copy the Quadlet template onto a host that does not yet have `runner.py`

QF-R1 (SELinux), QF-R3 (image digest), QF-R4 (egress) stay OPEN. This
runbook closes QF-R2 only.

```bash
systemctl --user daemon-reload
```

### 3.8 Negative test — the X that defines the architecture

```bash
# Service must start only while the tree is known-good
systemctl --user start quantum-flex-engine-mycelium.service
systemctl --user is-active quantum-flex-engine-mycelium.service

# Tamper one signed artifact
cp docs/ASSURANCE_LEVELS.md /tmp/ASSURANCE_LEVELS.md.bak
echo 'tamper' >> docs/ASSURANCE_LEVELS.md

systemctl --user restart quantum-flex-engine-mycelium.service
systemctl --user is-active quantum-flex-engine-mycelium.service
# must be failed / inactive — journal should show TAMPER BREACH

# Restore
mv /tmp/ASSURANCE_LEVELS.md.bak docs/ASSURANCE_LEVELS.md
systemctl --user reset-failed quantum-flex-engine-mycelium.service
systemctl --user start quantum-flex-engine-mycelium.service
```

If the service starts while the file is tampered, the live unit is not
calling the host judge. **HARD-STOP** and re-read the unit file.

---

## 4. What you do *not* do

- Do not install first and inspect after.
- Do not treat `python3 scripts/verify_provenance_manifest.py` as admission.
- Do not generate a new Ed25519 key to “make inspect pass.”
- Do not re-sign from a key that lives inside `~/mycelium`.
- Do not claim QF-R3/R4 closed because this runbook exists.
- Do not run `systemctl --user daemon-reload` from this cloud agent and
  call Yoga updated.

---

## 5. Done when

- [ ] You recognized the PEM pin as *your* release public key
- [ ] `python3 scripts/inspect_qfa5_release.py` exited 0 on Yoga
- [ ] Template dry-run exited 0 (13/13)
- [ ] `~/.local/libexec/quantumflex` is `0700/0500/0400`, owner `quant`
- [ ] Installed judge exited 0 against the same tree
- [ ] Live `ExecStartPre` points at libexec, not `scripts/`
- [ ] Tamper test kept the service from starting
- [ ] Restore returned the service to active *only* after hashes matched again
