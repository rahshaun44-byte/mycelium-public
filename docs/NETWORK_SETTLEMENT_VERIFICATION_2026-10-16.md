# Network and settlement verification — October 16, 2026

Seven deployed HTTP routes returned 200 after correcting the AMARA dashboard's
Python f-string escaping of JavaScript `${wsProto}` and restarting its user service.
The endpoint checker now uses current local routes and Tailscale HTTPS discovery,
rejects HTTP errors, and returns a nonzero exit code on failure. Retired port 9000
and direct Tailnet ports 8000/8080 were not evidence of a current cockpit outage.
HTTP reachability does not imply admission approval or fresh Sentinel evidence.

Authenticated Circle GET requests with an explicit User-Agent confirmed wallet
8c54c4d5-c989-5c61-bd0b-5b5981e8e0d2 is LIVE, developer-controlled, EOA, BASE-SEPOLIA.
Circle balances and independent Base Sepolia RPC confirmed 20 USDC and zero ETH.
The returned transaction history contains one completed INBOUND transfer of 20 USDC:
0xd712c32a084731d37aa350935b56e7062515f6c95e2fd3eff4559aed80ffccb5.
No outgoing settlement was evidenced. Initial requests without an explicit
User-Agent returned 403; changing the Uok so ser-Agent resolved those requests.

Settlement tests exercised offline validation only. The implementation now reports
PROOF_VERIFIED_DRY_RUN with submitted=false and rejects nonfinite metrics,
noncanonical JSON, and mismatched job/correlation fields. This is input validation,
not independent proof of physical execution. Live mode explicitly returns BLOCKED:
authenticated evidence, entity-secret signing, durable idempotency/reconciliation,
and gas funding are required before commissioning live EOA payments.
The incomplete outgoing transfer implementation was removed. No transfer was sent.

The settlement module now exposes an explicit authenticated-evidence verifier and
a conservative transaction reconciler. A detached signature is not trusted merely
because it is present: a commissioned trust-anchor verifier must return `True`.
Reconciliation binds a confirmed response to the expected idempotency key, amount,
and destination; mismatches become `INDETERMINATE`. The supported outcome states
are `PENDING`, `CONFIRMED`, `FAILED`, and `INDETERMINATE`. Live mode remains
fail-closed and returns `INDETERMINATE` without submitting a request until signing,
transport, and reconciliation are commissioned behind an explicit operator gate.

Remaining limitations: TPM PCR15 reads as all-zero; the admission policy rejects
it. check_tpm_attestation currently returns quote_verified=false unconditionally.
Those trust restrictions remain intact. Sentinel's displayed drive row is dated
October 8, although monitor telemetry is current; do not interpret that old row as
current physical verification. All user units had no failed services at inspection.

The Marrakesh ledger records 953/1024 shots in 000 or 111 (93.07%). That computational
basis population alone does not establish GHZ coherence, state fidelity, or
156-qubit entanglement. The recorded circuit used three qubits on a 156-qubit device.
