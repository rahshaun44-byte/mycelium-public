# Codebase Map

**Project:** QuantumFlex / Mycelium
**Generated:** 2026-10-08 (branch `wip-2026-09-30` @ `06c0829`, dirty working tree)
**Stack:** Python 3.14 control plane / OPA Rego (+ Wasm) policy / C++20 engine (CMake, libpqxx, SQLite, OpenSSL 3.5) / Rust + Go admission & telemetry crates / PostgreSQL

Evidence note: everything below was read by the agent from the working tree on 2026-10-08.
Runtime observations (unit lists) are agent-observed, not operator-verified.

---

## Stack

- **Python runtime:** 3.14, venv `~/mycelium/venv` → `~/.venv`. No lockfile; three separate requirement sets: `sentinel/requirements.txt`, `mcp_layer/requirements-worker.txt`, `api_node/requirements.txt`.
- **Policy:** OPA Rego under `sentinel/policies/*.rego` (package per file, `import rego.v1`), compiled to Wasm (`*.wasm`, built by `scripts/build_membrane_wasm.sh`) and evaluated in-process by `sentinel/policies/wasm_gatekeeper.py` (wasmtime), or over HTTP to `opa-immune` at `127.0.0.1:8181`.
- **C++ engine:** C++20, `CMakeLists.txt`, pkg-config deps, crypto/wire package in `quantumflex/` admitted via `cmake/AdmitQuantumFlex.cmake`. Build dir `build_check/` (gitignored).
- **Rust:** `quantumflex-telemetry/` (PCR 10 IMA replay, Gatekeeper OPA input, Ghost dispatcher), `quantumflex-ghost-sink/` (zero-authority anomaly sink, axum), `quantum-flex-sdk/`.
- **Go:** `quantumflex-admission/` (Go 1.27 gatekeeper, verifier, OPA parity).
- **Database:** native Postgres `127.0.0.1:5432` db `telemetry` (roles `ghostnode` admin, `sentinel_service` insert-only). Schema SQL at repo root (`setup_databases.sql`, `setup_quantum_flex_schema.sql`, `enforce_immutability.sql`) and `sentinel/swarm_schema.sql`.
- **Testing:**
  - Python: pytest, `pytest.ini` → `testpaths = tests pqc-immune-daemon`, `pythonpath = .`. Run `~/mycelium/venv/bin/python3 -m pytest -q`.
  - Rego: `opa test sentinel/policies/`.
  - Go: `go test ./...` in `quantumflex-admission/`.
  - Rust: `cargo test` per crate.
  - C++ crypto: `quantumflex/tests/`. The engine itself has no test suite.
- **Package managers:** pip (no lock), cargo, go modules. Do not introduce a new one.

## Architecture

The live path for admission decisions is Python + OPA. Measurements are taken, turned into a typed payload, evaluated by policy, and audited to Postgres:

`sentinel/invariant_gate.py` `check_*()` (reads `/proc/meminfo`, `tpm2_nvread 0x1c00010`, `tpm2_pcrread`, `sentinel_ledger` tip) → `query_opa_invariant()` (Wasm first via `get_reserve_wasm_gatekeeper()`, else HTTP `OPA_INVARIANT_URL`, else DENY) → `sentinel/policies/reserve_invariant.rego` (`package quantumflex.invariant`: `allow`, `verdict`, `domain_verdict`, `reason`) → `log_invariant_audit()` → `invariant_audit_ledger` table.

`evaluate_all_invariants()` composes the result. It ADMITs when solvency, anchor and PCR15 are all `allow`. Attestation is evaluated but excluded from the admission decision.

Parallel decision surfaces:
- `pqc-immune-daemon/immune_daemon.py` + `sentinel/policies/membrane_health.rego`: CBOM crypto-agility loop. It rewrites `mcp_layer/crypto_provider.conf`.
- `sentinel/policies/gatekeeper_attestation.rego` + `quantumflex-telemetry/src/telemetry/pcr10_replay.rs`: PCR 10 IMA replay attestation.
- `quantumflex-admission/gatekeeper.go`: Go admission with fixed reason codes, routes anomalies to the Ghost sink.
- `sentinel/decision_log_daemon.py`: receives OPA decision logs on `:9090`, observes only (dry-run "WOULD CONTAIN" default).
- `sentinel/policies/bootgate.rego`: boot gate.

The C++ engine (`src/main.cpp` → `LocalNode` in `src/core/local_node.cpp`) is the evidence/ledger plane. It is separate from the Python gate.

Key files:
- `sentinel/invariant_gate.py`: measurement and composite admission. This is the center of the verification-state work.
- `sentinel/policies/reserve_invariant.rego`: the invariant policy. Its `.wasm` must be rebuilt whenever the `.rego` changes.
- `sentinel/policies/wasm_gatekeeper.py`: in-process OPA Wasm host. Supported builtins: `sprintf`, `time.now_ns` only.
- `include/quantum-flex/*.hpp` + `src/core/*.cpp`: engine object graph (see CLAUDE.md).

## Structure

    sentinel/            Python IDS + gates; policies/ (Rego, Wasm, Wasm host); xdp/ (eBPF ingress)
    pqc-immune-daemon/   crypto-agility decision loop + its own Rego copy and tests
    mcp_layer/           LLM swarm (controller.py, swarm_worker.py), Athena API, crypto_provider.conf
    amara/ api_node/     dashboard / monitor; API gateway + Kafka consumer
    src/ include/        C++20 engine (src/core/*.cpp, include/quantum-flex/*.hpp)
    quantumflex/         C++ crypto + QFXK wire package with its own tests
    quantumflex-*/       Rust (telemetry, ghost-sink) and Go (admission) components
    qfx-provenance-seal/ provenance seal tooling (untracked)
    scripts/             operator scripts, signing ceremony, provenance, some test_*.py
    tools/               C++ tool mains + Python operator tools
    tests/               pytest suite (integration + unit)
    systemd-backup/      BACKUP unit files, not live (live: ~/.config/systemd/user/)
    docs/                runbooks, snapshots; docs/fellowship/ for Fellowship state

**Where to add new code:**
- New invariant / measurement: a `check_<name>()` function in `sentinel/invariant_gate.py` returning a payload dict with `domain`, `resource_type`, `telemetry_timestamp`, `max_staleness_seconds`. Add the matching `is_<x>_resource` / `<x>_valid` / `domain_verdict` / `reason` arms to `sentinel/policies/reserve_invariant.rego`.
- New Rego rule: `sentinel/policies/<name>.rego` with a sibling `<name>_test.rego`. If the rule is evaluated in-process, rebuild `<name>.wasm` and keep `tests/test_wasm_parity.py` green.
- New Python test: `tests/test_<module>.py` (pytest, flat, no fixtures dir).
- New engine class: header `include/quantum-flex/<snake_name>.hpp`, impl `src/core/<snake_name>.cpp` (picked up by the GLOB; re-run cmake).
- New crypto/wire primitive: `quantumflex/src/{crypto,wire}/` with a test in `quantumflex/tests/`. Never put one in `src/core/`.
- Operator script: `scripts/<verb>_<noun>.{sh,py}`.

## Conventions

**Naming:**
- Python: snake_case functions/modules, PascalCase classes, SCREAMING_SNAKE module constants (`OPA_ENDPOINT`, `MAX_PAYLOAD_BYTES`).
- Rego: snake_case rules; boolean predicates read as `is_<x>_resource`, `<x>_valid`; verdict strings SCREAMING_SNAKE (`ADMIT`, `DENY`, `ANCHOR_DESYNC`, `NOT_ATTESTED`).
- C++: snake_case files and methods, PascalCase types, `[[nodiscard]]` + trailing return types.
- Go: fixed enumerated reason codes (`ERR_*`), no free-text parser strings in outputs.

**Error handling (current rule for new and touched code):**
- Fail closed. Any unreachable evaluator, DB, TPM or module must produce DENY, never ADMIT.
- Do not write `except Exception: pass`. If a failure must be tolerated, record it as an explicit state in the payload (e.g. `UNAVAILABLE_*`, `ERROR_*`) and make sure the policy denies on it.
- Raise typed errors (e.g. `DatabaseUnavailableError`) at boundaries where the caller must decide.
- Never derive "verified" from the absence of a value, a default, or a fallback branch.
- Audit writes must report their own failure; never print "committed" without a successful commit.

**Imports:** stdlib, then third-party, then local. Optional deps are guarded (`try: import wasmtime except ImportError: wasmtime = None`) and must degrade to DENY, not to a different evaluator silently.

**Patterns in use:**
- Policy decides, Python measures. Python never computes `allow` itself.
- Freshness is enforced in policy via `telemetry_timestamp` + `max_staleness_seconds`.
- Payloads carry "backward-compatibility" duplicate fields (`reserve_measured`, `units_claimed`). Keep both until the tests are migrated.
- Commit messages: `type(scope): summary` (`fix(gate):`, `sec(sentinel):`, `refactor(sentinel):`).

## Concerns

Verification-state findings (agent-read, unverified by operator):

- **Solvency invariant is tautological.** In `sentinel/invariant_gate.py` `check_system_solvency()`, `available` is set to MemTotal and `obligated` to MemTotal − MemAvailable, so `available >= obligated` always holds and SYSTEM_SOLVENCY can never deny. Fix: decide what the invariant means (e.g. MemAvailable vs a declared obligation) and add a test that it can fail.
- **"Observed" counts toward ADMIT.** In `evaluate_all_invariants()`, PCR15 only needs to be read successfully (`pcr_observation_valid`), which is not verification. Attestation is hardcoded `quote_verified: False` (`check_tpm_attestation()`) and excluded from `all_allowed`. So ADMIT today means "anchor matches and the PCR is readable." Fix: name the admission level honestly, or gate it on attestation.
- **Silent evaluator substitution.** In `query_opa_invariant()`, `except Exception: pass` on the Wasm path falls through to HTTP OPA with no record of which evaluator decided. A broken or stale `.wasm` becomes invisible. Fix: record the evaluator in the result and audit.
- **Audit failure is swallowed and misreported.** `log_invariant_audit()` returns False on any failure and `evaluate_invariant()` ignores it, while the CLI prints "Committed to PostgreSQL" unconditionally.
- **NVRAM / PCR read exceptions swallowed.** `check_tpm_anchor()` and `check_tpm_pcr()` use `except Exception: pass`. The policy does deny on the sentinel strings, but the cause (absent TPM vs timeout vs permission) is lost. There are 27 `except Exception … pass` sites across the Python components.
- **Wasm/Rego drift risk.** `reserve_invariant.rego` and `.wasm` are both modified in the working tree. There is no check in place that the Wasm was rebuilt from the current Rego, apart from `tests/test_wasm_parity.py`.
- **Ghost sink address.** `quantumflex-admission/gatekeeper.go` hardcodes `http://10.88.0.50:19443`, while CLAUDE.md says the Ghost sink is loopback `:19443`.

Repo/runtime drift:
- **Runtime contradicts CLAUDE.md** (agent-observed 2026-10-08). There is no `quantum-flex-engine-mycelium` unit file in `~/.config/systemd/user/`. `immune-daemon`, `swarm-worker`, `amara-dashboard` and `sentinel-drive` unit files exist but are not loaded or active. Loaded and running: `api-node`, `athena-node`, `opa-immune`, `qf-monitor`, `qflex-mcp`.
- **Stray files at repo root.** Three files with names made from agent prose pasted into the shell, plus empty `Local`, `Shamir`, `mTLS`. Remove them by operator order only.
- **Secrets backup at repo root.** `.env.bak-rotate-20261007T230711` contains secrets. It is gitignored (`.gitignore:29 .env.*`), so it will not be committed, but it still sits in plaintext inside the repo tree. Decide its custody.
- **Duplicated policies.** Two copies of `membrane_health.rego` exist (`sentinel/policies/` and `pqc-immune-daemon/`), and both are modified. Pick one source of truth.
- **Malformed header.** `sentinel/policies/wasm_gatekeeper.py` line 1 is `import threading`, which sits above the shebang.
- **Hardcoded node ID.** `include/quantum-flex/replication_layer.hpp:38` hardcodes `get_node_id()` (TODO).
- **Unsafe tool.** `tools/rotate_credentials.py` rewrites `.env` with Windows paths. Do not run it (see memory).
- **Off-topic code.** Windows `.ps1` launchers and off-topic dirs (`school-bot/`, `commercialization/`, `mobile/`) add noise. Treat them as out of scope for gate work.
