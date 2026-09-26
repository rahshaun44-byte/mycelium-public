# QuantumFlex local release-admission demonstration

This package contains an exact snapshot of the repository launcher, verifier,
binding/signing helpers, and the existing 11-case adversarial test.
`SOURCE_HASHES.json` records those source bytes. Hashes identify the snapshot;
they are not an independent signature or certification.

## Run

Requirements: Linux with `/proc`, Python 3.10+, GCC, and an OpenSSL CLI with
Ed25519 support. No account, network call, root access, or production key is
required by the demonstration. Python's optional `cryptography` package can
accelerate verifier operations; otherwise the judge uses OpenSSL.

From this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/test_quantumflex_runtime_admission.py
```

Exit code 0 plus eleven `[PASS] Case` lines is a successful run. Any error or
missing case is an incomplete or failed run. Temporary fixtures and disposable
private keys are deleted when the script exits normally. No live service is
replaced or configured.

The fixture compiles a small C executable that reports its arguments and checks
whether `LD_PRELOAD` was passed to it. It signs a separate sample release artifact
and binds the runtime executable to that manifest. This is synthetic test data.
It does not use a customer's binary or start a customer service.

## What the cases exercise

1. Correct signed release and runtime launch.
2. Changed executable rejection.
3. Missing runtime signature rejection.
4. Wrong runtime signing key rejection.
5. Modified runtime binding rejection.
6. Modified runtime signature rejection.
7. Mismatched manifest digest rejection.
8. Changed declared A5 artifact rejection.
9. A pathname replacement just before execution still launches the opened file.
10. The target runtime does not receive the test's `LD_PRELOAD` value.
11. A signed runtime binding cannot substitute for a missing A5 signature.

## What this does not establish

This is a Linux ELF fixture test. It does not establish whole-host security,
in-place mutation resistance, dynamic-library or interpreter integrity, signing
key lifecycle safety, a protected OS trust boundary, or resilience to a privileged
attacker. The pathname replacement case is an injected test event, not a full
concurrent-adversary campaign. The environment case does not prove protection of
the Python interpreter or OpenSSL subprocess against hostile startup environments.
Ed25519 is a classical signature. This demonstration is not PQC certification,
FIPS module validation, a full audit, or evidence of customer demand.

A separate customer pilot must agree a supported environment, establish an
external trust anchor controlled by the customer, use the customer's artifact,
record the exact cases and outputs, and obtain independent acceptance.

This is an internal evaluation handoff. Ownership and distribution terms must
be confirmed before sending the package externally; no new license is granted
by this README.
