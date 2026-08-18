# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Quantum Flex is a personal, self-hosted security/telemetry system for a single Fedora host, modeled
loosely on a biological homeostasis metaphor (docs map components to the life cycle of *Corydalus
cornutus*, the Eastern Dobsonfly — see `quantum_flex_architecture.md`). It has two halves that must
be read as separate systems that happen to share a Postgres instance:

- **Python control plane** (`sentinel/`, `mcp_layer/`, `amara/`, `api_node/`) — the part that
  actually runs day to day: intrusion detection, a dashboard, a RAG assistant, and an LLM task
  swarm. Deployed as systemd **user** services.
- **C++20 evidence/ledger engine** (`src/`, `include/quantum-flex/`) — a from-scratch port of a
  separate, previously-untracked prototype (`~/quantum-flex`, now archived to
  `~/quantum-flex-archive` — not part of this repo). Newer and much less exercised than the Python
  side; most of it compiles and links but is not wired into any running service yet.

## Build & run

**C++ engine:**
```bash
cmake -S . -B build_check -DCMAKE_EXPORT_COMPILE_COMMANDS=ON   # build_check/ is gitignored
cmake --build build_check -j"$(nproc)"
```
No vcpkg, no CMake presets, no test target — this is a plain `pkg-config`-based build
(`libpqxx`, `sqlite3`, `libsystemd`, OpenSSL) producing two binaries: `quantum_flex_engine` and
`sentinel_push`. `CMakeLists.txt` uses `file(GLOB ... CONFIGURE_DEPENDS "src/core/*.cpp")` /
`src/crypto/*.cpp` — new `.cpp` files in those two directories are picked up automatically on
the next `cmake` configure, no `add_executable` edit needed. There is no test suite; "verified"
in this repo currently means compiled clean and exercised manually against a live Postgres
instance (see `src/core/bae_node.cpp` for the pattern: build, then actually run it against
`logistics-pg` and check the resulting row).

Runtime config is entirely env-var driven (see `environment_value()` calls in `src/main.cpp` /
`src/core/local_node.cpp`): `QF_DATA_DIR`, `QF_POSTGRES_CONNINFO`, `QF_ED_PRIVATE_KEY` /
`QF_PQC_PRIVATE_KEY`, `QF_SERVER_CERT` / `QF_SERVER_KEY` / `QF_ROOT_CA`. Without
`QF_POSTGRES_CONNINFO` set, the engine boots with Postgres integration disabled rather than
failing. `QF_DATA_DIR` must exist before running — `LocalNode`'s SQLite state file and the mTLS
listener's cert paths are resolved under it, and neither directory-creates for you.

**Python components** — three independent dependency sets, no lockfile, no shared venv manifest:
`sentinel/requirements.txt`, `mcp_layer/requirements-worker.txt`, `api_node/requirements.txt`. The
working venv used on this host is `~/mycelium/venv` (Python 3.14). No formal test suite or lint
config (no `pytest.ini`, `.clang-tidy`, `.clang-format`) currently exists in this repo — don't
assume one and don't invent CI-style tooling that isn't there.

**How this actually runs**: not via a single entrypoint — each Python component is its own
systemd **user** service (`systemctl --user status <name>`: `amara-dashboard`, `athena-node`,
`qf-monitor`, `sentinel.timer`, `neurogenesis.timer`). `systemd-backup/` in this repo is exactly
what it sounds like — backed-up unit files, not the live ones; the live units are under
`~/.config/systemd/user/`. For local iteration, most Python scripts also run standalone
(`python3 mcp_layer/athena_api.py`, etc.) since they read config from `.env` / env vars, not from
systemd `Environment=` lines.

## Architecture

**Two separate Postgres backends — do not conflate them:**
1. Native Postgres on `127.0.0.1:5432`, db `telemetry`. Dual-role: `ghostnode` (admin — full
   `memory_logs`/`integrity_registry` access) and `sentinel_service` (restricted — insert-only on
   `sentinel_ledger`), so a compromised Sentinel process can't corrupt the swarm's core memory.
   Used by nearly everything under `sentinel/` and `mcp_layer/`. Credentials come from
   `GHOSTNODE_DB_USER`/`PASSWORD` and `SENTINEL_DB_USER`/`PASSWORD` in `.env`.
2. Podman container `logistics-pg` (`postgres:15-alpine`) on `127.0.0.1:5433`, db `amara_matrix`,
   role `amara_admin`. Used only by the C++ engine (`BaeNode`, via `QF_POSTGRES_CONNINFO`).
   Password lives in `.env` as `POSTGRES_PASSWORD` and must match whatever the live container was
   actually initialized with — `podman exec logistics-pg env` is the source of truth if `.env`
   and the container ever drift, which has happened before.

**C++ engine object graph** — `LocalNode` (`local_node.hpp`) is the central object and owns:
- `EvidenceEngine`: hash-chained, write-once `evidence_id -> data` map.
  `register_evidence`/`verify_evidence` re-hash and compare; `get_state_root()` collapses the
  whole ledger to one SHA-256.
- `append_evidence(telemetry_id, raw_payload, signature)` hashes the payload into a `ZkCommitment`
  (id + salt + commitment hash) and registers *that* — the raw payload itself is never persisted.
- `HybridSigner` (`crypto_signer.hpp`): Ed25519 + PQC dual signature, PEM keys from
  `QF_ED_PRIVATE_KEY`/`QF_PQC_PRIVATE_KEY`. `sign_payload` returns `"<ed_sig_hex>|<pqc_sig_hex>"`.
- `BaeNode` (`bae_node.hpp`/`bae_node.cpp`): the one real Postgres-partition-purge implementation.
  Extracts a partition deterministically, hashes it, signs the hash with `HybridSigner`, builds and
  structurally verifies an `AuditProof` (`audit_proof.hpp`), writes it to `akashic_ledger`, and
  drops the partition — all inside one `pqxx::work` transaction, so the ledger can never claim a
  purge that didn't happen. If you ever find a second, parallel implementation of this same idea
  under a different class name (`LedgerNode`, `AkashicNode`, etc.) — this has happened before,
  from other AI sessions working the same repo without visibility into each other's changes — it's
  almost certainly a stale duplicate to delete, not a second thing to merge.
- `StateManager`: SQLite-backed (`brie_state.db`) partition state machine —
  `SHRED_VERIFIED → SIGNING → SIGNED_LOCAL → LEDGER_PENDING → LEDGER_COMMITTED → COMPLETE`, with
  `SIGNING_INTERRUPTED`/`REQUIRES_OPERATOR` failure states and a hash-chained journal table for
  crash recovery (`sweep_boot_recovery`). Also owns an optional Postgres `LISTEN/NOTIFY` thread on
  `quantum_telemetry_channel`.
- `ReplicationLayer` + `GossipSubHandler`: gossip-replicated hash-chain across peer nodes with
  decaying peer-scoring. Compiles and is exercised in isolation but this is a single-node
  deployment right now — there's no second peer to actually replicate to.
- `ForensicLockdown`: incident-response actions (disable network, remount read-only, stop
  containers, flush TPM) behind an injectable `ICommandExecutor`, so it's dry-runnable
  (`LockdownPolicy{.dry_run = true}` is the `LocalNode` default).
- `LocalNode` also tracks a `SystemState`
  (`UNINITIALIZED → LOCKED → ACTIVE`, plus `SUSPECT`/`QUARANTINED`/`LOCKDOWN_PENDING`/
  `LOCKDOWN_ACTIVE`). Unlocking needs a Shamir threshold of key shards (`crypto_shamir.hpp`, GF(256)
  + Lagrange interpolation) via `unlock_node`/`initialize_node`.

**Networking**: `IpcServer` (`ipc_server.hpp`) is a single-threaded mTLS TCP server (TLS 1.3,
client-cert auth), default `9443`, driven one connection at a time by
`process_single_connection()` in `src/main.cpp`'s loop — deliberately synchronous. The
`quantum-flex-sentinel-harvester` systemd service (a separate, root-level deployment outside this
repo, under `/usr/local/libexec/quantum-flex/` — see below) is the client that actually talks to
this socket.

**Crypto-agility / "immune" subsystem** (`mcp_layer/immune_daemon.py`,
`mcp_layer/crypto_provider.conf`, `sentinel/policies/membrane_health.rego`): a decision loop, not a
one-off script. Every 500ms, `immune_daemon.py` generates a CBOM snapshot of the active PQC
algorithm, POSTs it to a co-located OPA sidecar, and if OPA's verdict is `TOXIC`, rewrites
`crypto_provider.conf` (`sed`, in place) and `SIGHUP`s the worker process to force renegotiation
with the fallback algorithm. Fails secure: if OPA is unreachable, treat the current algorithm as
toxic rather than assume it's fine.

**LLM task swarm** (`mcp_layer/controller.py` — "The Claw" — and `mcp_layer/swarm_worker.py`):
`controller.py` breaks one directive into atomic tasks via local Ollama and inserts them into a
Postgres `task_queue`; `swarm_worker.py` polls that queue with `FOR UPDATE SKIP LOCKED` so multiple
workers never double-pick a task, executes, and logs outcome to `memory_logs`. Both hit the
`telemetry` Postgres backend (backend #1 above), not `amara_matrix`.

**Repo-state gotchas:**
- **This host runs a second, entirely separate Quantum Flex deployment outside this repo** — root
  and dedicated-user systemd services under `/usr/local/bin`, `/usr/local/libexec/quantum-flex/`,
  `/etc/quantum-flex/`, `/opt/quantum-flex-ingest/`. It is not git-tracked anywhere in
  `~/mycelium`; treat it as a black box unless you're specifically asked to touch it, and check
  `systemctl list-units | grep quantum` before assuming a given binary/service does or doesn't
  exist.
- `~/quantum-flex-archive` (the retired prototype this engine was ported from) still has a live
  root systemd service (`quantum-flex-harvester.service`) pointing at a path inside it
  (`clients/python/sentinel_harvester.py`) — that service will fail on its next restart since the
  directory moved. Not part of this repo, but worth knowing if you're asked to debug it.
- **Multiple AI coding sessions have edited this repo concurrently** at least once already,
  producing a duplicate/incompatible reimplementation of `BaeNode` and an accidental commit of the
  entire `build_check/` directory (compiler binaries, `.o` files — since reverted and gitignored).
  Run `git status`/`git log --oneline -10` before trusting that the working tree matches what you
  last saw, and don't assume you're the only session touching this repo right now.
- `.env` (repo root, gitignored) holds backend #1's credentials; a separate `.env` inside
  `sentinel/` also exists (`sentinel/.env`, `sentinel/.env.example`) — check which one a given
  script actually loads (`load_dotenv(Path(__file__).resolve().parent.parent / ".env")` vs a local
  one) rather than assuming they're the same file.
- `ghost-node` — an earlier packet-sniffer prototype (`/opt/ghost-node/ghost-agent.py`, outside
  this repo) — is intentionally disabled and not part of the running system. `sentinel/`'s own
  earlier duplicate of the same telemetry idea (`decision_gate.py`) was already removed from this
  repo (see git log: "Retire redundant Ghost Node").
