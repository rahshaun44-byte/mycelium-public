# Codebase Map

**Project:** QuantumFlex / Mycelium
**Generated:** 2026-10-08 (branch `wip-2026-09-30` @ `06c0829`)
**Updated:** 2026-10-15 (branch `fix/w1-w4` @ `8e26dca`, dirty working tree; 13 commits since generation)
**Stack:** Python 3.14 control plane / OPA Rego (+ Wasm) policy / C++20 engine (CMake, libpqxx, SQLite, OpenSSL 3.5) / Rust + Go admission & telemetry crates / PostgreSQL

Evidence note: read by the agent from the working tree on 2026-10-08, re-checked 2026-10-14 and 2026-10-15.
Runtime observations (unit lists) are agent-observed, not operator-verified.
Sibling repo: `~/qf-public` (GitHub `rahshaun44-byte/quantumflex`, PRIVATE as of 2026-10-14) carries
the newer engine work (W8, evidence persistence, QFXK hardening). This map covers `~/mycelium` only.

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
- **Local LLM:** Ollama 0.35.1, system unit `/etc/systemd/system/ollama.service` (drop-in: 1 loaded model, 1 parallel, ctx 4096), loopback `127.0.0.1:11434` only. Pulled: `qwen2.5-coder:7b`, `quantumflex-partner` (built from `agent/Modelfile` on qwen2.5-coder:7b), `gemma3:4b`, `nomic-embed-text` (768-dim). Consumers read `OLLAMA_HOST`/`OLLAMA_URL`/`OLLAMA_MODEL`/`ATHENA_MODEL`/`EMBED_MODEL` from repo `.env` via `EnvironmentFile=`. New model references must name a pulled model or read one of those env vars.

## Architecture

The live path for admission decisions is Python + OPA. Measurements are taken, turned into a typed payload, evaluated by policy, and audited to Postgres:

`sentinel/invariant_gate.py` `check_*()` (reads `/proc/meminfo`, `tpm2_nvread 0x1c00010`, `tpm2_pcrread`, `sentinel_ledger` tip) → `query_opa_invariant()` (Wasm first via `get_reserve_wasm_gatekeeper()`, else HTTP `OPA_INVARIANT_URL`, else DENY) → `sentinel/policies/reserve_invariant.rego` (`package quantumflex.invariant`: `allow`, `verdict`, `domain_verdict`, `reason`) → `log_invariant_audit()` → `invariant_audit_ledger` table.

`evaluate_all_invariants()` composes the result. It ADMITs only when solvency, anchor, PCR15 **and attestation** are all `allow` (`95f0270`). `check_tpm_attestation()` still hardcodes `quote_verified: False`, so every composite verdict is DENY until quote verification exists — this is the intended state (quest log, 2026-10-08).

Parallel decision surfaces:
- `pqc-immune-daemon/immune_daemon.py` + `sentinel/policies/membrane_health.rego`: CBOM crypto-agility loop. It rewrites `mcp_layer/crypto_provider.conf`.
- `sentinel/policies/gatekeeper_attestation.rego` + `quantumflex-telemetry/src/telemetry/pcr10_replay.rs`: PCR 10 IMA replay attestation.
- `quantumflex-admission/gatekeeper.go`: Go admission with fixed reason codes, routes anomalies to the Ghost sink.
- `sentinel/decision_log_daemon.py`: receives gzip OPA decision logs on `:9090/logs` (config `sentinel/config/opa_decision_logs.yaml`), observes only (dry-run "WOULD CONTAIN" default). Network decisions come from `sentinel/policies/gatekeeper.rego` (`package quantumflex.gatekeeper`, `default allow := false`) against `sentinel/policies/trusted_ips.json`.
- `qfx-provenance-seal/`: provenance seal — `python/qfx_seal.py`, `policy/provenance_seal.rego`, `schema/seal.schema.json`.
- `sentinel/policies/bootgate.rego`: boot gate.

The C++ engine (`src/main.cpp` → `LocalNode` in `src/core/local_node.cpp`) is the evidence/ledger plane. It is separate from the Python gate. Live: `quantum-flex-engine-mycelium.service` runs `build_check/quantum_flex_engine`, mTLS `127.0.0.1:9444`, data `~/.local/share/quantum-flex-mycelium/` (`ledger.dat`, `mtls/`), booted LOCKED.

Recovery path (tracked since `8e26dca`): `tools/qf_recovery.py` (`--check` offline by default; `--unlock` only after MATCH plus runtime binding to the live engine) → native `build_recovery_check/qf_legacy_recovery_check` (built from `tools/qf_legacy_recovery_check.cpp` + `quantumflex/src/crypto/crypto_shamir.cpp`; prints only `MATCH`/`MISMATCH`/fixed error codes) → `scripts/qf_ipc_client.py` for the UNLOCK frame. `scripts/unlock_engine.sh` wraps it for three plaintext share files.

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
    qfx-provenance-seal/ provenance seal: python/, policy/, schema/
    agent/               (untracked) Modelfile for quantumflex-partner + corpus/operator_doctrine.md
    build_recovery_check/ native recovery checker binary (not tracked)
    scripts/             operator scripts, signing ceremony, provenance, some test_*.py
    tools/               C++ tool mains + Python operator tools (incl. qf_recovery.py, qf_legacy_recovery_check.cpp)
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
- Custody/recovery code: `tools/qf_*.py` / `tools/qf_*.cpp`, with a matching `tests/test_*.py` that uses synthetic secrets only. Never print, argv-pass, or write share/secret bytes; emit fixed status strings.
- SQL for roles/schema: `scripts/sql/<name>.sql`.
- Authority/custody ceremony steps: `tools/qf_authority_ceremony.py` (Python orchestration) + `tools/qf_authority_split.cpp` (native split). Ceremony manifests land in `~/.local/state/quantum-flex-mycelium/authority-*.json`, never in the repo.
- Athena knowledge ingestion: `tools/learn_quantumflex.py` (reviewed docs only); query via `tools/ask_quantumflex.py`.

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

Verification-state findings (agent-read 2026-10-14, unverified by operator):

- **Solvency invariant is tautological.** `sentinel/invariant_gate.py` `check_system_solvency()` sets `available` = MemTotal and `obligated` = MemTotal − MemAvailable, so `available >= obligated` always holds. Fix: define a real obligation and add a test that can fail.
- **Silent evaluator substitution.** `query_opa_invariant()` still has `except Exception:` on the Wasm path, falling through to HTTP OPA without recording which evaluator decided. Fix: record the evaluator in result and audit.
- **Audit failure misreported.** The CLI still prints "Committed to PostgreSQL" unconditionally (`sentinel/invariant_gate.py:439`) regardless of `log_invariant_audit()`'s result.
- **Swallowed exceptions.** ~40 multi-line `except …: pass` sites across `sentinel/ mcp_layer/ amara/ api_node/ pqc-immune-daemon/ tools/ scripts/` (2026-10-15 count; wider scope than the 10-14 figure of 23). One was added on 2026-10-15 in `tools/qf_authority_ceremony.py` `seal_share()` around `os.chmod(target, 0o400)`.
- **Embedding model misconfigured.** Repo `.env` sets `EMBED_MODEL=qwen2.5-coder:7b`; `mcp_layer/vector_ingest.py:17` indexes with `nomic-embed-text`. `mcp_layer/athena_api.py:41` would embed queries with a different model and dimension → Athena retrieval breaks on next start. Fix: `EMBED_MODEL=nomic-embed-text`.
- **Code defaults name unpulled models.** `mcp_layer/qf_bot/teammates.py` (`qwen2.5-coder:1.5b`, 5 sites), `mcp_layer/log_analyzer.py:22` (`gemma2:2b`), `mcp_layer/ollama_full_agent.py:23` (`gemma3:12b`), `scripts/ask_athena.py:8` default `gemma2:2b`. Point at env vars / pulled models.
- **Duplicate Ollama unit.** `~/.config/systemd/user/ollama.service` (disabled) would contend for `:11434` with the system unit if enabled. Remove by operator order.
- **Ghost sink address.** `quantumflex-admission/gatekeeper.go:16` hardcodes `http://10.88.0.50:19443`; CLAUDE.md says loopback `:19443`.
- **Wasm/Rego drift risk.** Only `tests/test_wasm_parity.py` checks that `*.wasm` matches its `.rego`.
- **`trusted_ips.json` holds two specific tailnet host addresses**; the same file is on `origin/main` of the qf-public repo, which was public for a period.

Resolved since 2026-10-08: attestation now gates composite ADMIT (`95f0270`); DB-offline vs absence distinguished (`5149f95`); simulated DePIN engine removed (`3a78885`); the two `membrane_health.rego` copies are now byte-identical (still two copies — pick one source).

Custody / recovery (updated 2026-10-15):
- **Authority genesis sealed 2026-10-15T12:12:19Z** (manifest `~/.local/state/quantum-flex-mycelium/authority-genesis-20261015T121219Z.json`, preceded by `authority-legacy-archive-20261015T114424Z.json`). Agent-checked: `ledger_sha256` 1d479c6a… equals current `ledger.dat`; `engine_sha256` 601f3e02… equals `build_check/quantum_flex_engine` and the running engine's exe; `splitter_sha256`/`checker_sha256` equal `build_recovery_check/` binaries; 3-of-5, gpg AES256; shares 1–2 ciphertext hashes match the manifest. The 10-subset authentication is CLAIMED by the ceremony tool's output, not re-run by Claude.
- **Disk-separation check was bypassed.** Committed `validate_destinations()` refuses >1 share on the home filesystem. The genesis ran with an **uncommitted** patch adding `--allow-custom-topology` (disables all separation checks). Resulting topology: shares 1 and 2 both in `~/qfx-authority-share{1,2}/` (this laptop), shares 3 and 4 on one USB (`QFX_SHARD_B`), share 5 on the Pixel via MTP. The laptop holds 2 of 3; laptop + either the USB or the phone rebuilds the secret. Remedy is an operator decision (move one home share off-host, or re-run genesis under the committed checks).
- **Pre-genesis exposed material still on disk:** `~/qfx-shards-genesis/shard_1.enc` and the stego PNG under `~/.gemini/antigravity/brain/`. Inert only if the new authority replaced the old one for this ledger (claimed, not independently tested). Destroy by operator order once that is confirmed.
- **`ledger.dat` is 0664** (group-writable). Tighten to 0600 by operator order.
- **`scripts/qf_ipc_client.py` and `tools/qf_authority_ceremony.py` are modified and unreviewed.**
Repo/runtime drift:
- **Runtime units (agent-observed 2026-10-15):** active — `amara-dashboard`, `amara-matrix`, `quantum-flex-engine-mycelium`. Inactive — `api-node`, `athena-node`, `opa-immune`, `qf-monitor`, `qflex-mcp`. Not loaded: `immune-daemon`, `swarm-worker`, `sentinel-drive`. System: `ollama` active. CLAUDE.md's unit list is stale.
- **Stray files at repo root.** Agent-prose filenames (incl. `n' '--- Historical release commit ---'`) plus empty `Local`, `Shamir`, `mTLS`. Remove by operator order only.
- **Secrets backup at repo root.** `.env.bak-rotate-20261007T230711` (gitignored, plaintext). Decide custody.
- **Malformed header.** `sentinel/policies/wasm_gatekeeper.py` line 1 `import threading` sits above the shebang.
- **Hardcoded node ID.** `include/quantum-flex/replication_layer.hpp:38` (TODO).
- **Unsafe tool.** `tools/rotate_credentials.py` rewrites `.env` with Windows paths. Do not run it.
- **Off-topic code.** Windows `.ps1` launchers, `school-bot/`, `commercialization/`, `mobile/` — out of scope for gate work.
