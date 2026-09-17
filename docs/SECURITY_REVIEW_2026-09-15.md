# Security review — 2026-09-15

## Conclusion and scope

The source contains security defects that prevent endorsing the supplied handoff's “airtight, zero-trust” conclusion. This is a repository static review with selected isolated checks, not a penetration test or certification of the running host.

Inventoried 362 tracked files, including 69 Python files, 44 C++ source/header files (including vendored JSON), and 20 shell scripts. Ran repository-wide targeted searches and syntax checks, then manually traced high-risk API, database, quarantine, IPC, signing, replication, UI, and deployment paths. Also inspected the untracked `scripts/hertzbleed-gate.sh` and the user's attached handoff. This does not claim every line or dependency was audited. Generated artifacts, private keys, secret environment values, live database ACLs, installed service units, physical shard custody, and actual network exposure were not verified.

Application files, database permissions, containers, and services were not changed. This report is the only repository addition from the review. The existing untracked script was preserved.

## Findings

### 1. High — dashboard request text reaches a host shell

`amara/dashboard.py:334` interpolates `command` from `/api/mobile/action` into `subprocess.run(..., shell=True)`. An API-key holder can execute shell syntax with the service account's permissions. Lines 268 and 308 also provide a fixed, source-visible fallback API key when configuration is missing.

**Fix:** fail closed when the key is absent, authenticate with a constant-time comparison, and replace the CLI bridge with an explicit allowlist of operations and argument arrays. Removing `shell=True` alone is insufficient if unrestricted CLI subcommands remain dangerous. Verify authenticated requests cannot invoke arbitrary commands.

### 2. High — application database roles are superusers

`setup_databases.sql:14–17` creates `rahshaunchambers`, `ghostnode`, and `amara_admin` as superusers with executable placeholder passwords. Python services default to `ghostnode`, including the controller and Athena API. If deployed as written, a compromised service has privileges across its PostgreSQL cluster. Table-level revocations cannot constrain a superuser. [PostgreSQL role documentation](https://www.postgresql.org/docs/17/role-attributes.html).

**Fix:** provision credentials through deployment secrets, separate migration/administration roles from runtime roles, and remove superuser privileges from application identities after checking their actual workload requirements. Existing deployments need a role migration; editing the template alone does not change existing roles.

### 3. High — schema initialization undoes append-only protection

`setup_quantum_flex_schema.sql:15–18` grants all table privileges and access to every existing sequence in `public`. Running it after `enforce_immutability.sql` restores destructive access for `quantum_sentinel`. The immutability script does not restrict the other named role, and cannot constrain it if it is a superuser.

**Fix:** make the initialization template least-privilege from the start, scope sequence grants to this table, and use a reviewed migration to revoke existing excessive grants. Inspect role memberships, ownership, and column-level grants as well as direct table ACLs.

### 4. High — sensitive HTTP routes have no application authentication

`api_node/main.py:112` accepts a host file path for ingestion without authentication or an allowed-directory boundary. `mcp_layer/athena_api.py:297` accepts knowledge-base writes without authentication. `mcp_layer/qf_bot/bot_server.py:206` accepts approvals without identifying the operator; history is also exposed. Its CORS configuration allows all origins.

Any caller able to reach these services can use those operations. Loopback defaults reduce remote reachability but do not establish operator identity. External proxy/Tailscale authorization was not verified. The current draft implementation marks actions approved and writes an audit entry; it does not actually execute the advertised action, so this finding does not claim that approval directly executes arbitrary code.

**Fix:** authenticate and authorize sensitive routes, constrain ingestion to staged uploads, restrict browser origins, limit payload sizes, and record the authenticated actor.

### 5. High — purge accepts a missing-key signature

`src/crypto/crypto_signer.cpp` returns empty strings on missing signing keys, then combines them into `"|"`. `include/quantum-flex/audit_proof.hpp:19` only checks that the combined string is nonempty. `src/core/bae_node.cpp:81` relies on this structural check before dropping the table.

**Confirmed in an isolated compiled reproduction:** nonexistent key paths produced `Missing-key signature: [|]` and `Structural proof accepted: 1`. No database was accessed.

**Fix:** fail key loading/signing explicitly, verify both signature components against expected public keys before deletion, and test missing keys and signing failures. Structural completeness is not cryptographic verification.

### 6. High — enrollment can deadlock the single-threaded server

`src/core/replication_layer.cpp:35–41` holds `peer_mtx_` while calling `save_peers()`, which acquires the same non-recursive mutex at line 76. If the peers file opens successfully, enrollment blocks indefinitely. The IPC server processes connections serially.

**Fix:** use one clear locking boundary and save a consistent snapshot without recursively locking. Add a bounded completion test.

### 7. High — peer and replication verification remain disabled/stubbed

`src/core/replication_layer.cpp:32` comments out rejection of failed enrollment signatures. Line 152 accepts every nonempty replication message without verifying a signature or chain. `src/core/gossipsub_handler.cpp` explicitly forwards messages without the planned signature/block validation and rewards caller-supplied peer IDs.

These paths are reachable through authenticated IPC commands, so an accepted client certificate is currently a much broader trust boundary than the protocol implies. Enrollment also has the deadlock above; fixing that alone would expose its unchecked key replacement path.

**Fix:** reject or disable unfinished commands until signature, identity, sequence, replay, and chain validation are implemented. Do not represent ACKs as verified replication.

### 8. High — any accepted IPC client can replace the harvester key

`src/core/ipc_server.cpp:97` dispatches `SET_HARVESTER_KEY` without command-specific authorization. `src/core/local_node.cpp` replaces the verification key directly. A CA-trusted client can replace it with its own key and submit evidence signed with that key when the node is active.

**Fix:** separate operator and ingestion identities, bind certificate identity to allowed commands, and require an authorized rotation protocol or locally provisioned key.

### 9. High — an idle TCP connection can stall IPC before authentication

`src/core/ipc_server.cpp:347` performs blocking `SSL_accept` and later `SSL_read` without socket deadlines. `src/main.cpp` handles one connection at a time. A reachable client can stall the service by opening a connection and withholding TLS handshake bytes; a certificate is not needed for that stage.

**Fix:** apply handshake/read/write deadlines and bounded connection handling. Catch malformed share parsing errors inside the per-connection error boundary; `parse_shares()` currently calls throwing `std::stoi` before its caller's try block.

### 10. High — quarantine fallback interpolates filenames into a shell

`run_sentinel.py:92` embeds the payload basename unquoted into an Alpine `sh -c` command. A crafted existing filename can alter commands inside the fallback container. This is container command injection, not a demonstrated host escape. The container also mounts the entire shared airlock, exposing concurrently staged files to that command.

`run_sentinel.py:60–66` stages requests under basename alone, so concurrent files with the same basename overwrite or remove each other's staging data.

**Fix:** use a unique private directory per request, mount only its payload, and pass filenames as positional shell arguments or avoid a shell entirely.

### 11. High — primary quarantine failure is reported as success

`run_sentinel.py` mounts the airlock read-only and passes its file to `sentinel/quarantine_chamber.py`. That script tries to chmod and move the original file, catches errors into a `FAILED` result, prints it, and exits successfully. The orchestrator treats the zero exit code as success.

**Fix:** copy into the writable quarantine before modifying it, and propagate a failed quarantine operation through a nonzero exit status and structured result. Verify both primary-image and fallback-image behavior.

### 12. Medium — route test cleanup can remove unrelated containers

`scripts/run_route_test.sh:19–22` always stops/removes fixed names, including when creation fails because a pre-existing container already owns a name. It also starts package installation asynchronously and immediately attempts ping. Any failure of `touch` is interpreted as proof of a read-only filesystem, including execution/container errors.

**Fix:** allocate unique names, retain IDs only after successful creation, clean up only owned resources, wait for readiness, and distinguish mount enforcement from command failure. The route harness was syntax-checked but not executed against the host.

### 13. Medium — the XDP filter does not cover the stated engine transport

`sentinel/xdp/qf_ingress.c:7` guards UDP port 9443 and explicitly passes non-UDP packets. The C++ engine uses TCP/TLS, and the supplied handoff says its deployed port is 9444. This filter cannot establish protection of that engine's ingress. Plaintext QFXK magic is also not visible inside TLS packets.

**Fix:** document the filter's actual transport scope and test the deployed path. Do not claim generic XDP proves zero socket-buffer allocation or total malformed-frame protection from this source. Kernel attachment and packet layout were not verified.

### 14. Medium — volatile/no-write and verification claims exceed the checks

The handoff claims zero physical writes, but `api_node/main.py:142` stages webhook content in a home-directory path before RAM ingestion. The route test itself installs packages into a writable container. A tmpfs mount alone does not establish host-wide no-write behavior, swap policy, logging behavior, or secure erasure; Podman documents separate tmpfs and swap controls. [Podman runtime documentation](https://docs.podman.io/en/latest/markdown/podman-run.1.html).

`secure_zero_wipe()` opens with `wb`, truncating the file before writing, and writes at most 16 MiB. This is not evidence that all original memory pages were overwritten. Heap-pointer reset in the Wasm wrapper likewise establishes reuse, not secure zeroization.

The handoff's listed test counts sum to 29 passing tests, while its headline claims 27. The untracked Hertzbleed gate can print PASSED when governor reads fail or the bind address is non-loopback; its printed isolation claim therefore does not follow from its own checks.

**Fix:** narrow claims to measured properties, retain reproducible test output, and treat missing measurements as unknown. Live CPU/kernel identity, installed models, device installation, benchmark results, and shard custody remain unverified.

### 15. High — unavailable TPM and ledger can be reported as verified

`sentinel/invariant_gate.py:160–190` defaults both TPM and ledger values to 64 zeroes when their reads fail, then attaches a fresh timestamp. The policy only checks equal 64-character values. Evaluating those exact placeholders against the shipped Wasm returned `(True, 'ADMIT', ...)` in an isolated check.

**Fix:** represent failed measurements explicitly and deny before comparison. Require successful acquisition from both trusted sources, reject placeholder values, and test simultaneous TPM/database failure. Comparing client-supplied hashes is not hardware attestation.

### 16. High — Wasm daemon path omits dynamic compromise flags

`pqc-immune-daemon/immune_daemon.py:534` calls `evaluate_verdict(cbom)` without threat flags. The Wasm wrapper supplies an empty flags dictionary by default, so threat data held by the HTTP OPA sidecar does not automatically reach the in-process evaluation. The daemon can return early with a healthy verdict even when the corresponding compromise flag should force a fallback.

**Confirmed with shipped Wasm:** the same ML-KEM/ML-DSA CBOM returned `COMPLIANT` without flags and `TOXIC` with `ML_KEM_COMPROMISED=true`. This checks policy behavior without changing any live flag.

**Fix:** provide the same authenticated, fresh policy data to both evaluation paths and add integration tests that exercise the daemon adapter, not only the wrapper with flags passed explicitly.

## Additional Phase 1/2 walkthrough assessment

The second attachment is included in this review. Its claims of zero disk writes and zero lingering RAM are not established by the pasted stdout. The route script also leaves its bridge network in place and does not enforce the claimed latency threshold.

The Wasm implementation and its nine current tests are present, but “full OPA ABI” and “constant memory usage” overstate the wrapper: it dispatches only two hard-coded builtin IDs, returns undefined for others, and places no maximum on linear memory. Heap-pointer restoration alone does not shrink a grown memory allocation or establish a memory bound. Resolve builtin IDs from the exported mapping and explicitly reject unsupported builtins; set resource limits and measure sustained use.

The walkthrough's seven Wasm tests differ from the nine currently in the file; the earlier handoff lists nine but retains a 27-pass headline. `--wasm` exists in the daemon, but the claimed `PQC_USE_WASM` environment option is absent from the current source; its HTTP override is `PQC_FORCE_HTTP`. These documents should be tied to exact code revisions and refreshed outputs. The historical 1,000-iteration benchmark was not reproduced.

## Suggested SQL direction — not executed

The pasted text has formatting damage: `REATE` must be `CREATE`; remove literal backslashes before underscores and decode `&#x20;` into spaces. The repository SQL already has valid spelling/formatting.

For an ingestion role that needs append and read access, this is a starting point for a reviewed migration, assuming the table exists in `public` and the role is neither superuser nor owner and has no inherited excess grants:

```sql
BEGIN;
REVOKE ALL PRIVILEGES ON TABLE public.quantum_telemetry_channel
    FROM PUBLIC, quantum_sentinel;
GRANT USAGE ON SCHEMA public TO quantum_sentinel;
GRANT INSERT, SELECT ON TABLE public.quantum_telemetry_channel
    TO quantum_sentinel;
REVOKE ALL PRIVILEGES ON SEQUENCE public.quantum_telemetry_channel_id_seq
    FROM PUBLIC, quantum_sentinel;
GRANT USAGE ON SEQUENCE public.quantum_telemetry_channel_id_seq
    TO quantum_sentinel;
COMMIT;
```

This does not remove prior broad grants on other sequences, inherited privileges, schema CREATE access, column grants, or privileges held by `rahshaunchambers`. Determine whether that role is a human administrator or runtime identity before changing it. Administrators/owners remain able to alter records. Schema-qualified migrations and an explicit deployment order are needed. Consider `TIMESTAMPTZ` for creation time and documented units/validation for the BIGINT timestamp.

## Verification performed

- All 69 tracked Python files parsed successfully without importing application modules.
- All 20 tracked shell scripts and the untracked Hertzbleed script passed `bash -n`.
- `venv/bin/python -m pytest -q -p no:cacheprovider tests/test_privacy_filter.py tests/test_wasm_gatekeeper.py`: **12 passed in 0.21s**, bytecode writes disabled.
- OPA source tests: **10/10** in `sentinel/policies`, **8/8** in `pqc-immune-daemon`.
- Isolated C++ missing-key/proof reproduction compiled and confirmed finding 5; temporary artifacts are under `/tmp/qflex-security-review`.
- Isolated evaluations of shipped Wasm confirmed admission of unavailable TPM/ledger placeholders and the verdict difference caused by missing threat flags (findings 15–16).
- No full-suite, live gateway, route/container, destructive purge, credential rotation, or service-restart tests were run. Existing tests passing does not resolve the findings above.

## Recommended order

1. Remove the host shell bridge/default key and secure sensitive HTTP routes.
2. Migrate application roles and correct schema grants.
3. Make signing, purge, TPM acquisition, and threat-data propagation fail closed; disable unfinished replication commands.
4. Repair IPC authorization/deadlines and quarantine failure handling.
5. Repair test resource ownership and replace unsupported handoff claims with measured evidence.
