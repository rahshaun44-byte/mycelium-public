# Quantum Flex: stress and containment assessment

Date: 2026-09-16. Tested the modified working tree based on commit
`2f559ec69064df5806e0288fef239e1076173227`, not an unchanged release.

## End result

The file ingestion path reached its intended quarantine outcome in all eight
concurrent test requests. The network engine rejected malformed KEM requests,
survived a burst of 100 such requests, timed out an idle unauthenticated connection,
and then successfully served valid cryptographic requests. Rejection itself is
expected defensive behavior and is not counted as a system failure.

These results support bounded claims about these paths. They do not establish an
unconditional security guarantee or certification of the complete deployment.

## Paths actually traced

1. File ingestion: `/ingest` → path containment check → four-slot subprocess
   semaphore → `run_sentinel.py` → request-specific RAM staging directory →
   rootless Podman with no network, read-only root filesystem, dropped
   capabilities and a tmpfs sink → hash/copy/chmod → container removal and staging
   cleanup. The cached Alpine fallback was used; the primary image was absent.
2. Network input: mTLS listener → framing/KEM validation → reject/close and LIF

   anomaly accounting → next connection. The current C++ LIF callback logs an
   alert. It does not invoke the file quarantine chamber. SSH detection likewise
   explicitly runs in alert-only mode. A malformed network input being rejected
   need not produce a quarantined file to be safely handled.
3. Policy: CBOM → OPA/Wasm verdict → daemon decision. The strict daemon path
   stops the configured worker on an unavailable or unhealthy verdict. The
   agility circuit-breaker path has separate quarantine/recovery behavior.
   Neither is the file-copy chamber above.

## Executed workloads and outcomes

| Workload | Result and interpretation |
|---|---|
| Fresh CMake build | Succeeded. |
| Python baseline | 54 tests passed, including strict stop and quarantine/recovery tests. Some dependency boundaries are mocked in these tests. |
| Rego tests | 21 passed across daemon and sentinel policy suites. |
| Native ML-KEM | 1,000 roundtrips and mutated-ciphertext checks completed. |
| Native framing | 20,000 seeded valid/corrupt fragmented frames and 5,000 pending sessions exercised. |
| Sanitizers | The native workload completed under Clang AddressSanitizer and UndefinedBehaviorSanitizer with leak detection, exit 0. This is workload-specific evidence, not proof of memory safety. |
| Wasm sequential policy | 5,000 alternating healthy/compromised evaluations returned expected statuses. Sampled memory stayed at 196,608 bytes for this workload. |
| Larger policy inventories | 1, 100 and 1,000 components evaluated; memory increased with input size. No global resource-bound claim established. |
| Isolated mTLS engine | 250 serial and 200 requests from four concurrent clients succeeded. |
| Malformed network burst | 100 truncated KEM requests rejected; subsequent valid exchange succeeded. Invalid share ID did not terminate the engine. |
| Idle network connection | An authorized request waited behind an idle client. A separate test allowed the socket deadline to expire: idle connection closed and a subsequent valid exchange succeeded. |
| Real quarantine chain | Eight concurrent ASGI ingestion requests ran real subprocesses and real disposable containers. Correct hashes, tmpfs telemetry, unchanged source files, and removal of each staging copy verified for all eight. Harmless shell-looking contents were treated as data; semicolons in filenames did not execute commands. |
| API key configured | 100 requests without the key rejected with HTTP 401. |

The quarantine test relocated the permitted input directory to a temporary
fixture directory and disabled only the unrelated status/TPM import. The ingest
route, subprocess runner, orchestrator and Podman execution were real. It did not
test a deployed HTTP reverse proxy. Retaining the original input file is the
current behavior; this path isolates a copy rather than removing all source data.

## Observations that remain after following the outcome

- **Valid protocol fragmentation:** splitting the initial `QF` magic across TLS
  writes returned a legacy `NODE_UNINITIALIZED` error instead of the requested
  native public key. This is a valid-client correctness issue; no escape from
  quarantine or key disclosure was demonstrated.
- **Availability boundary:** the synchronous listener recovers after the tested
  idle timeout, but one client delays the next. The framing unit accepted a frame
  after its configured 1,200 ms reassembly deadline. Per-read socket timeouts and
  an absolute frame deadline are different protections. Sustained slow-client
  resistance remains unproven.
- **Wasm concurrency boundary:** sharing one evaluator across four threads in a
  separate process aborted with a Wasmtime stack-walker assertion (exit 134).
  Sequential use passed. This does not demonstrate that the deployed daemon uses
  that unsupported concurrent pattern or that an external caller can cause it.
- **Policy input boundary:** empty/malformed inventories were labeled COMPLIANT
  with zero assessed components. Equal non-hex TPM strings and negative resource
  obligations were admitted by the raw reserve policy. These are direct policy
  inputs; bypass of trusted telemetry acquisition was not demonstrated. Any
  assurance claim must identify which upstream validations are required.
- **API configuration boundary:** when both key settings were absent, the ingest
  handler admitted a request in an isolated test with downstream execution mocked.
  Quarantine may be the intended destination for untrusted submissions; that
  outcome does not by itself establish caller authentication. Production exposure
  and intended public-ingest policy were not established here.
- **Primary chamber untested:** only Alpine was cached. Source inspection shows
  the primary script defaults to `/quarantine`, while the orchestrator mounts
  `/opt/sentinel/quarantine`. The successful fallback result cannot establish that
  the primary image works.

## Evidence and limits

Temporary harnesses and results are under
`/tmp/quantumflex-stress-20260916-fzmjWk/`:
`stress_native.cpp`, `stress_policy.py`, `stress_ipc.py`,
`stress_quarantine.py`, `policy-results.txt`, `thread-results.txt`,
`ipc-results.json`, and `quarantine-results.json`. Temporary artifacts may be
removed by host cleanup. Certificates and keys there belong only to test fixtures.

No live service, production database, TPM state, firewall or real suspicious
payload was targeted. The supplied route script was inspected, not executed:
its cleanup uses fixed container names and its ping/rootfs checks cannot establish
zero host storage writes. The separate deployment outside this repository was
not assessed. Container escape, host swap behavior, physical erasure, exhaustive
fuzzing, sustained saturation, production recovery and independent compliance
assessment remain outside this run.

A defensible guarantee needs a named property, covered inputs and attacker model,
deployment assumptions, measurable limits, and evidence that every required
enforcement path reaches its safe outcome. For example, this run supports:
“The eight tested file submissions were copied to an isolated tmpfs chamber and
their staging copies were removed.” It does not support “all hostile traffic is
automatically quarantined” or “the system cannot fail.”
