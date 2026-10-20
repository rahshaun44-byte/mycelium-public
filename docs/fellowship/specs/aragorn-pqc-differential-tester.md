---
status: active
author: aragorn
---

# Requirements: PQC Differential Tester

**Defined:** 2026-10-20
**Locked decisions:** D-01, D-02

## Locked Decisions

- **D-01:** Two separate products. The **home system** (QuantumFlex/Mycelium) v1 is the current re-alignment only: the sentinel realign (done 2026-10-20), the engine `ledger.dat` 0600 deploy, and credential rotation. No new services or features are added there. **Earning** is a separate product, and its v1 is this tester.
- **D-02:** The tester is published as a **new, clean public repository** with no history from `mycelium` or `qf-public`. This is a deliberate exception to the "no push / remotes out of scope" line in `product.md`, and it applies only to that new repo. The `mycelium` push policy (quest log 2026-10-08, Option A) is unchanged.

## Problem Statement

Bernstein's June 2026 paper "Exploiting ML-DSA bugs" describes two bug classes in ML-DSA implementations that let an attacker recover an equivalent secret key in under a second. liboqs has shipped CVEs of the same kind. The newer, less-reviewed ML-DSA and ML-KEM implementations (Rust, Go, JS, embedded C) have no shared, independent harness that tests them against the FIPS 203/204 reference behaviour. Two groups would use such a tool:

- **Maintainers of those libraries**, who want to find these bugs before attackers do.
- **People who hire PQC auditors**, who want evidence that the auditor can find real defects.

Rock already has the core of it in `quantumflex/tests/`:

- `test_known_answer_vectors.cpp`: known-answer (KAT) checks
- `test_wire_fuzz_negative.cpp`: negative fuzzing
- `test_dudect_timing.cpp`: dudect timing checks
- `test_mlkem768.cpp`
- `test_zeroization.cpp`

This product pulls that capability out and points it at other people's code. Its value is credibility: CVE credit and published findings that lead to contract work. It does not take custody of anything and does not move money.

## v1 Requirements

### Harness core

- **[CORE-01]** (P0): For ML-KEM-768 and ML-DSA-65, the tester runs NIST ACVP / FIPS 203/204 known-answer vectors against any implementation reached through a small adapter interface (keygen, encaps/decaps or sign/verify, deterministic seed input).
- **[CORE-02]** (P0): The tester runs differential tests: the same seeds and inputs go to the target and to a reference implementation (OpenSSL 3.5 ≥ 3.5.0), and any byte difference is reported.
- **[CORE-03]** (P0): The tester runs negative tests:
  - Malformed, truncated and out-of-range public keys, ciphertexts and signatures must be rejected.
  - ML-DSA signature malleability, and acceptance of non-canonical encodings, are flagged.
  - The cases cover both bug classes in the Bernstein paper.
- **[CORE-04]** (P1): The tester runs a dudect constant-time check on decapsulation and signing, with a fixed seed and a stated confidence threshold.
- **[CORE-05]** (P1): ML-KEM-1024 and ML-DSA-87 are supported.

### Targets

- **[TGT-01]** (P0): Adapters exist for at least **three outside open-source implementations** in at least two languages. They are chosen from actively used Rust, Go, JS or embedded-C libraries; the list is fixed in Open Questions before the build starts.
- **[TGT-02]** (P1): Each adapter is pinned to an exact upstream version or commit.

### Output

- **[OUT-01]** (P0): One command produces a machine-readable report (JSON) per target. Each case records pass, fail or error, the inputs needed to reproduce it, and the pinned version.
- **[OUT-02]** (P0): Findings are labelled with the truth-log scale. A failing differential case is SUPPORTED until it has been reproduced by hand; nothing counts as VERIFIED until it is reproduced.
- **[OUT-03]** (P1): A findings write-up per target, published only after disclosure (see DISC-01).

### Disclosure & publication

- **[DISC-01]** (P0): Every suspected vulnerability goes through private coordinated disclosure (the maintainer's SECURITY.md, or a GitHub private advisory). The default embargo is 90 days. Nothing reaches the public repo before the fix or the embargo ends.
- **[PUB-01]** (P0): The public repo is created fresh (D-02). It contains no host names, tailnet IPs, keys, tokens, ledger data or files copied from `mycelium` history, and a secret scan (gitleaks or equivalent) passes before the first push.
- **[PUB-02]** (P1): CI runs the KAT and negative suites against the reference on every push.
- **[PUB-03]** (P2): The README includes a one-paragraph contracting note: who built it, and the audit services offered.

## Acceptance Criteria

### CORE-01: KAT vectors
- [ ] The official ACVP ML-KEM-768 and ML-DSA-65 vector sets all pass against the OpenSSL 3.5 reference adapter.
- [ ] One deliberately corrupted vector is detected and reported as a failure.

### CORE-02: Differential
- [ ] At least 10,000 seeded cases per target and algorithm run with no harness crash.
- [ ] A seeded fault in a test adapter (one flipped output byte) is caught and reproduced from the report alone.

### CORE-03: Negative
- [ ] The suite contains named cases for each of the two Bernstein bug classes, and each was shown to fail against a deliberately buggy test double.
- [ ] Rejection of truncated, oversized and non-canonical inputs is checked for every target.

### CORE-04: Timing
- [ ] dudect runs to its stated sample count on decapsulation and signing for the reference and at least one target. The verdict is recorded with its t-statistic.

### TGT-01: Outside targets
- [ ] Three adapters build and run end to end, each pinned to a version.

### OUT-01 / OUT-02: Reports
- [ ] One command produces a JSON report per target. Every failure in it can be reproduced from the report alone.
- [ ] Every finding carries a truth-log label; none is VERIFIED without a manual reproduction note.

### DISC-01: Disclosure
- [ ] For each suspected vulnerability, a dated disclosure record (the channel, the date sent, and the date the embargo ends) exists before any public mention.

### PUB-01: Clean repo
- [ ] `git log` for the new repo starts at its own first commit.
- [ ] The secret scan passes, and a grep finds no `100.`/`fd7a:` tailnet addresses and no `qfx-`/`g6pro` host names.

**v1 is done when** the tester runs against three outside libraries, and each one has a findings write-up: either "no findings at pinned version X", or a disclosed issue.

## v2 (Deferred)

Gimli may not implement these in v1.

- PQ-signed AI agent receipts and an Apify actor listing: a separate product, started only after v1 ships (D-01).
- A bulk PQC TLS/SSH attack-surface scan sold as a paid report: a separate product.
- A wallet quantum-exposure checker on Base: a separate product.
- SLH-DSA, FN-DSA (Falcon), HQC and hybrid-KEM combiners: wait for v1 to show demand.
- A hosted or SaaS version of the tester: needs users first.

## Out of Scope

| Feature | Reason |
|---|---|
| Any change to the home system beyond the D-01 re-alignment | D-01: no new home-system services or features while the earning v1 is built |
| Holding customer USDC, prepaid credit, or any customer funds | FinCEN money-services-business and state money-transmitter risk (MONETIZATION_ASSESSMENT_2026-10-20) |
| Marketing that implies a quantum advantage or "quantum-secured" claims | IBM results fall below a random baseline (TRUTH_LOG §17.3); credibility and FTC risk |
| Claiming FIPS 140-3 / CMVP validation, or "certified" status | No independent validation exists |
| Publishing an exploit before a fix or before the embargo ends | DISC-01; coordinated disclosure only |
| Testing closed-source or production services without permission | Authorisation: open-source libraries run locally only |
| Pushing `mycelium` or `qf-public` history anywhere | D-02 limits the exception to the new clean repo |

## Open Questions

- [ ] Which three outside implementations come first? Research (2026-10-20) proposes the list below. It is not locked; Rock decides.
  - **Prior work:** Symbolic Software's open-source **Crucible** (March 2026) already runs 78 ML-KEM and 51 ML-DSA conformance tests over 15 implementations, through a JSON-line stdin/stdout shim. It published ML-KEM results only: two conformance gaps and no vulnerabilities. Our differentiation has to be ML-DSA signing-side exploitability (the Bernstein bug classes), differential runs against OpenSSL 3.5, dudect timing, and targets Crucible did not cover.
  - **1. RustCrypto `ml-dsa` + `ml-kem` (Rust).** Pure Rust, pre-1.0, no published audit. Two 2026 ML-DSA CVEs: CVE-2026-24850 (duplicate hint indices accepted) and CVE-2026-22705 (Decompose timing). It is the recommended migration target as PQClean is archived (RUSTSEC-2026-0161). Not in Crucible.
  - **2. `@noble/post-quantum` (JS).** Widely used on npm, no ML-DSA audit or advisory found, and JS makes constant-time behaviour hard to guarantee, so dudect has real work to do. Not in Crucible.
  - **3. Go `crypto/mldsa` (Go standard library, new in 1.26).** Young code with a reported verify edge case (golang/go#79959). Hit probability is low, but a finding would carry the most credibility. Not in Crucible (it covered `crypto/mlkem`).
  - **Alternate:** `libcrux-ml-dsa` (Rust; RUSTSEC-2026-0125, AVX2 `use_hint` CVSS 8.2), in place of #3 if Go proves too well reviewed.
  - **Open:** Crucible-compatible adapters (reuse its shim protocol) or our own interface?
- [ ] The repo name and licence: Apache-2.0 or MIT? (Rock)
- [ ] Should the GitHub account be `rahshaun44-byte` or a new one kept separate from the home system? (Rock)
- [ ] Is the default embargo 90 days, or does each upstream's own policy win? (Rock)
