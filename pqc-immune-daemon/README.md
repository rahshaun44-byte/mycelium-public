# PQC Crypto-Agility Immune Daemon

A small supervisor daemon that watches the cryptographic health of a
post-quantum-capable worker process and autonomously renegotiates its
active KEM/signature algorithm — without a restart or rebuild — when an
OPA policy engine flags the current algorithm as compromised.

Built as a personal infrastructure project to explore the mechanics of
crypto-agility described in [NIST FIPS 203/204/205](https://csrc.nist.gov/pubs/fips/203/final)
and, more recently, in [OMB M-26-15](https://postquantum.com/security-pqc/omb-m-26-15-pqc-migration/)
(June 2026), which gives U.S. federal agencies until October 2026 to submit
PQC migration plans covering exactly this pattern: continuous cryptographic
inventory, provider-based algorithm configuration, and config-driven
renegotiation without re-architecting.

**This is a working prototype, not a certified or audited compliance
product.** It has not been reviewed by anyone outside this repository, has
no FIPS validation, and makes no claim to satisfy any federal mandate. What
it does claim, and what you can verify yourself by reading the ~300 lines
of code, is that it implements the specific *mechanisms* those documents
describe — a provider-based config, an automated inventory snapshot, and
signal-driven renegotiation — correctly and in working order.

## How it works

Every `POLL_INTERVAL_MS` (default 500ms), the daemon:

1. Builds a minimal [CycloneDX](https://cyclonedx.org/capabilities/cbom/)-shaped
   Cryptographic Bill of Materials (CBOM) snapshot from the worker's active
   algorithms.
2. POSTs it to a local [Open Policy Agent](https://www.openpolicyagent.org/)
   sidecar running the policy in `membrane_health.rego`.
3. If the verdict comes back `TOXIC` for the active KEM:
   - Rewrites `crypto_provider.conf` in place (`sed`) to the recommended
     fallback algorithm.
   - Sends `SIGHUP` to the worker process. The worker is expected to catch
     the signal and renegotiate its tunnel on the new algorithm — no
     process restart, no redeploy.
4. If OPA itself is unreachable for `FAIL_SECURE_THRESHOLD` consecutive
   polls, the daemon **fails secure**: it treats the current algorithm as
   compromised and triggers the fallback anyway, rather than assuming
   everything is fine.

### Fallback chain

The policy steps a compromised ML-KEM (lattice-based, NIST FIPS 203) down
to FrodoKEM before falling back further to classical X25519. FrodoKEM is
deliberately structured around different hardness assumptions than ML-KEM,
so a break in one is less likely to also compromise the other — the chain
isn't just a priority-ordered list of "safe" algorithms, it's ordered to
avoid a shared point of failure.

## Files

| File | Purpose |
|---|---|
| `immune_daemon.py` | The daemon itself. |
| `membrane_health.rego` | OPA policy: approved-algorithm registry, threat-flag evaluation, fallback recommendation. |
| `crypto_provider.conf.example` | Example of the mutable config the daemon reads and rewrites. |
| `test_immune_daemon.py` | Feeds a synthetic TOXIC verdict through `execute_vein_collapse()` and asserts the config is actually rewritten and state updated correctly. |

## Running it

```bash
# Config the daemon will read/rewrite (copy the example to get started)
cp crypto_provider.conf.example crypto_provider.conf

export PQC_PROVIDER_CONF="$(pwd)/crypto_provider.conf"
export WORKER_CMD="python3 your_worker.py"   # whatever process terminates the PQC tunnel
export OPA_ENDPOINT="http://127.0.0.1:8181"  # your OPA sidecar

python3 immune_daemon.py
```

Optional audit logging (Postgres insert + webhook push) is entirely
opt-in — set `PQC_DB_USER` / `PQC_DB_PASSWORD` and/or
`PQC_DASHBOARD_WEBHOOK` if you want it; the daemon runs fine without
either.

### Running the test

```bash
python3 test_immune_daemon.py
```

## What this is, and isn't

This grew out of a personal, self-hosted security project and is offered
as a demonstration of working crypto-agility mechanics — a piece of
evidence, not a finished product. It is not deployed anywhere, has no
users, and isn't seeking to be a drop-in dependency for production
systems. If you're evaluating it as part of a hiring process or technical
review: read the code, run the test yourself, and judge it on that.

## License

Apache License 2.0 — see [LICENSE](LICENSE). Chosen over MIT for the explicit
patent grant (Section 3), which matters more than usual for cryptographic
code: it gives downstream users an express patent license and a
patent-retaliation clause, not just a copyright permission.
