# ML-KEM migration and strict policy

## What this change establishes

The daemon defaults to `fips_strict`. This is an algorithm allowlist and stopping policy, **not FIPS 140-3 module validation**. OpenSSL 3.5 provides native ML-KEM, including through its default provider. A successful key exchange proves execution and agreement, not validation of the module or the overall system.

A FIPS 140-3 claim requires an applicable CMVP certificate, the exact validated module and its security policy, approved mode/operations, and approved operating conditions. Loading a provider named `fips`, or setting `fips=yes`, alone does not establish those facts. See [OpenSSL FIPS guidance](https://github.com/openssl/openssl/blob/master/README-FIPS.md) and [NIST FIPS 203](https://csrc.nist.gov/pubs/fips/203/final).

## Policy and daemon

- Select `--profile fips_strict|iso_strict|agility`; CLI overrides `PQC_COMPLIANCE_PROFILE`, which defaults to `fips_strict`. Unknown values fail startup.
- The daemon includes `requested_profile` in every generated CBOM. Raw policy evaluations without a profile retain historical agility behavior; callers outside the daemon must supply their profile explicitly.
- Strict policy rejects algorithms outside its ML-KEM/ML-DSA/SLH-DSA allowlist. Rejections contribute to `node_status=TOXIC`. `recommended_fallback=NONE` is authoritative.
- A family-wide ML-KEM compromise stops affected operations. Moving from ML-KEM-768 to ML-KEM-512 does not escape the shared assumption and reduces parameter strength.
- A strict-mode missing/untrusted policy response stops immediately, including the first outage. The daemon never enters Frodo quarantine or consults the research ladder for strict-mode failure.
- Strict Wasm evaluation requires readable authoritative threat data from `OPA_ENDPOINT` (or the supplied HTTP endpoint). An unavailable threat feed cannot silently become an empty healthy flag set. Wasm policy execution is in-process; threat-data acquisition still has a service dependency.
- Non-dry strict startup requires `WORKER_PID` identifying the supervised data-path worker. On a denied/failed evaluation the Linux daemon uses a pidfd, sends TERM, escalates to KILL after two seconds if needed, and confirms exit. A missing or unkillable worker is an enforcement error. `--dry-run` does not signal or rewrite configuration and returns an unsuccessful status for a denial.
- Deployment must ensure that an independent supervisor cannot restart the worker after a policy stop. This patch does not edit systemd units or enforce a host-wide shutdown. The configured worker must be the process actually controlling affected operations; stopping an unrelated worker provides no protection.
- `agility` and the existing `iso_strict` profile preserve research fallback behavior. The profile name is not an ISO or FIPS certification assertion.

The canonical source is `pqc-immune-daemon/membrane_health.rego`; the source copy under `sentinel/policies` is synchronized. Rebuild with `bash scripts/build_membrane_wasm.sh`. The script checks the source copies match and retains five entrypoints. The wrapper resolves builtin IDs from the compiled module's exported mapping.

## C++ implementation and wire compatibility

`MLKem768Engine` uses OpenSSL EVP key generation, encapsulation and decapsulation. Keys stay in an OpenSSL-owned object; output lengths and API return values are checked. The production IPC handler uses this class. The prior `HybridKemEngine` remains for explicitly labeled legacy research tests; IPC does not select it.

The 16-byte network-order header remains `QF`, version 1, message type, sequence, payload length, flags. New message IDs distinguish ML-KEM from legacy Frodo traffic:

| Type | Direction | Payload |
| --- | --- | --- |
| `0x12` | request | Empty public-key request |
| `0x12` | response | 1,184-byte ML-KEM-768 public key |
| `0x13` | request | 1,088-byte ML-KEM-768 ciphertext |
| `0x14` | response | 32-byte server confirmation tag |
| `0x7f` | response | Empty rejection for unsupported type/invalid length/provider error |

Legacy `0x02`/`0x03` KEM requests are rejected. Existing Frodo clients require migration; there is no automatic downgrade or reinterpretation of their payloads.

Confirmation is `HMAC-SHA256(shared_secret, "QuantumFlex-ML-KEM-768-server-confirm-v1" || ciphertext)`. The shared secret is never returned over the wire and the server wipes its temporary buffer after generating the tag. Clients must verify the tag. Correctly sized invalid ciphertexts use ML-KEM implicit rejection: they may produce a different secret rather than an API error. A returned tag by itself does not prove the client's ciphertext was valid; matching confirmation does.

**Transport limit:** this is a KEM exchange and confirmation over the existing mTLS transport. It does not add ML-KEM-derived application encryption, upgrade the TLS negotiated group, establish a persistent application session, or provide client key confirmation. A PQ-protected application transport needs a separately designed and reviewed session protocol. Do not report this exchange as proof that all traffic is PQ encrypted.

OpenSSL system configuration and optional `QF_KEM_PROPERTIES` govern provider selection. For deployments with an independently verified FIPS module, an appropriate property query can restrict provider selection; an unavailable requested provider fails rather than falling back. This repository does not ship a validated module.

## HUD and documentation

`python3 qflex.py pqc` separates provider availability, configured policy, and C++ source implementation. It reports validation as not established and explicitly says it has not inspected the running daemon/binary or negotiated sessions. It no longer prints fabricated passing test counts, verified repository state, or traffic-stop claims based on an algorithm listing.

Earlier walkthroughs, audit reports, timing output and Frodo protocol descriptions are historical snapshots. They do not attest to this revision or a deployed runtime. In particular, native ML-KEM availability and the profile name must not be used as FIPS 140-3 evidence.

## Verification and deployment

Verification performed for this change:

- Python daemon/Wasm regression tests: strict denials, all three ML-KEM parameter sets under family compromise, unknown profiles, explicit selection, dry-run safety, threat-data failure, and stopping an owned test child.
- OPA source tests and an isolated loopback HTTP OPA process compared with compiled Wasm, covering healthy/compromised ML-KEM and forbidden Frodo/X25519 inputs.
- Full CMake build, native KEM roundtrip/implicit rejection/provider failure/size tests, and wire framing/negative-input tests.
- Temporary mTLS engine with disposable CA/client/server certificates: public-key retrieval, ML-KEM confirmation, rejection of legacy Frodo messages and malformed ciphertext. No PostgreSQL connection or deployed service was used.

Reproduce with a separate build directory:

```sh
cmake -S . -B /tmp/qflex-mlkem-build
cmake --build /tmp/qflex-mlkem-build -j2
/tmp/qflex-mlkem-build/test_mlkem768
/tmp/qflex-mlkem-build/test_wire_framing
/tmp/qflex-mlkem-build/test_wire_fuzz_negative
opa test pqc-immune-daemon/membrane_health.rego pqc-immune-daemon/membrane_health_test.rego
opa test sentinel/policies
PYTHONDONTWRITEBYTECODE=1 venv/bin/python -m pytest -q -p no:cacheprovider tests/test_strict_pqc.py tests/test_wasm_gatekeeper.py pqc-immune-daemon/test_immune_daemon.py
QF_TEST_BUILD_DIR=/tmp/qflex-mlkem-build PYTHONDONTWRITEBYTECODE=1 venv/bin/python -m pytest -q -p no:cacheprovider tests/test_pqc_policy_http.py tests/test_mlkem_ipc.py
```

The final two tests require permission to bind temporary loopback sockets. Policy-source tests alone do not verify rebuilt Wasm, daemon adapters, or IPC. These checks are not ACVP certification, a cryptographic proof, or an audit of all legacy cryptography.

**Deployment is pending:** no live service was restarted, no worker PID was selected, no database grant was changed, and no installed engine was replaced by this change. Before activation, migrate clients, set the intended worker/profile, verify service restart behavior, and independently verify the actual cryptographic module requirements for the deployment.
