# Quantum Flex: SSH, C++ and F* technical briefing

Assessment date: 2026-09-16. Based on the current, modified repository.
Status: architecture and proof plan, not a completed formal verification.

## 1. Recommendation

Retain the C++ engine and introduce a small formally verified core for binary
validation and authorization/state transitions. Treat OpenSSL, sockets, storage,
process management and containers as explicit external dependencies. Begin with
the frame validator because it has a small, concrete input and measurable output.

F* is a language and proof system for expressing and checking program properties.
It does not ingest arbitrary existing C++ and automatically prove it correct.
The practical integration is to implement selected components in the verification
toolchain, generate C, and call that code from C++. Current F* documentation
describes Pulse for imperative/concurrent code and EverParse for parsers. Older
examples often use Low*; select and pin a compatible supported toolchain rather
than combining commands from different generations of documentation.
[F* introduction](https://fstar-lang.org/tutorial/book/intro.html),
[KaRaMeL](https://github.com/FStarLang/karamel).

Neither `fstar`, `fstar.exe` nor `krml` was found on PATH during this assessment.
No F* proof was executed, and no production C++ implementation was replaced.

## 2. What “SSH weirdness” can mean here

The exact warning or failed connection has not been supplied. There is no basis
yet to diagnose a specific SSH fault. The repository contains several independent
boundaries that can produce apparently contradictory outcomes:

| Boundary | Question it answers | What it does not establish |
|---|---|---|
| Network reachability | Can this device reach this listener? | User identity or permission to modify the ledger |
| SSH authentication | Can this identity obtain an OS session? | Engine unseal authority |
| Engine mTLS | Is this client certificate trusted for a connection? | Permission for every application command |
| Command authorization | May this identity perform this operation? | Correctness of supplied shares or ledger contents |
| Engine state | Is the engine initialized, locked or active? | Whether the operating system is trustworthy |
| Cryptographic policy | Is the selected algorithm allowed by this profile? | CMVP validation or correct transport use |

The local SSH client reports OpenSSH 10.2p1 with OpenSSL 3.5.8. This is a local
version observation, not evidence of a remote server's version or a negotiated
session's algorithms.

If the warning concerns a non-post-quantum key exchange, OpenSSH documents that
warning beginning in 10.1. OpenSSH 10.0 made `mlkem768x25519-sha256` its default
key agreement. An older peer or restricted algorithm configuration can prevent
that negotiation. SSH key agreement, host authentication and user authentication
are separate algorithm choices; an Ed25519 login key does not tell us which KEM
protected the session. [OpenSSH PQ guidance](https://www.openssh.org/pq.html).

Repository-specific observations:

- `scripts/restrict_sshd_binds.sh` writes loopback/Tailscale ListenAddress entries
  and reloads sshd. It requires host root because it edits a system service. That
  requirement does not imply that the Ghost Node or a database ingestion role
  should have superuser privileges. The script was not executed here.
- `docs/tailscale_acl_policy.hujson` distinguishes owner devices and a tagged
  worker. Its comments also mention SELinux/Tailscale SSH interoperability.
  These are configuration intentions, not proof of the currently applied policy.
- `sentinel/lif_sentinel.py` detects repeated failed-login events and raises an
  alert. `active_defense.py` consumes that stream in alert-only mode. It does not
  automatically send an SSH source address to the file quarantine container.
- The supplied cold-restart test is an engine mTLS test, not an SSH test.

For a specific incident, collect the exact error, destination/port, whether the
connection is OpenSSH or Tailscale SSH, and the relevant negotiated algorithm or
authentication error. Do not change listener bindings or disable host-key checks
merely to make an unexplained error disappear.

## 3. Connecting the earlier discussions

### Biological strata

Use the metaphor to describe responsibilities: observation, decision,
enforcement and recovery. Formal specifications need the actual events and state
changes. A neuron firing can mean “emit an alert”; a quarantine action can mean
“copy a file into an isolated container”; neither implies the other occurred.

### A guarantee

A useful guarantee has a property, quantified inputs, assumptions and a defined
enforcement boundary. Tests demonstrate particular executions. Proofs establish
a specified property for all cases covered by their model, subject to their
assumptions and trusted tools. A proof of the wrong rule is still the wrong rule.

Example target: every rejected telemetry operation leaves the committed ledger
unchanged. Proving the decision function alone is insufficient: the C++ caller
must obey the result, and the commit path must enforce the same condition.

### Framed messages

The current wire header is 16 bytes: two magic bytes `QF`, version, message type,
and three network-order 32-bit fields: sequence ID, payload length and flags.
The header also contains a separate `QFXK_MAGIC` constant representing four bytes;
the serializer actually emits two. The proof specification must follow the real
wire format and resolve misleading constants before generation.

Current parsing checks version, flags and a 16,384-byte payload ceiling. It
appends input before validation, has a separate timeout sweep, and returns the
same boolean for incomplete and invalid input. The IPC listener also selects
binary versus legacy handling before complete magic bytes are guaranteed.
These are concrete places where a precise parsing contract can help.

### Cold restart

`LocalNode::load_state()` distinguishes missing/genesis state from a saved sealed
ledger. Missing state and the `UNINITIALIZED` marker enter initialization;
a populated sealed envelope enters LOCKED pending secret reconstruction.
Therefore “every startup is LOCKED” is broader than current behavior.

The restart test asserts `STATUS` is denied on the sealed-ledger path. It does
not establish every command's behavior. Native KEM requests take a separate
dispatch path before legacy state checks. Decide explicitly whether public-key
retrieval and key confirmation are permitted while locked, then prove and test
that matrix. A handshake operation need not have the same permission as a ledger
mutation.

### ML-KEM, Frodo and FIPS

FIPS 203 specifies ML-KEM. Formal verification addresses implementation
properties; it does not prove the underlying mathematical assumption will never
be broken. In a declared family-wide compromise scenario, changing from
ML-KEM-768 to ML-KEM-512 does not remove that compromised assumption.
[NIST FIPS 203](https://csrc.nist.gov/pubs/fips/203/final).

The project's strict profile should deny affected operations with fallback NONE.
That is a project policy rule, not a claim that NIST universally mandates that
particular incident response. Frodo agility and an approved-profile boundary are
separate choices. Likewise, SSH's ML-KEM/X25519 hybrid has its own protocol and
policy context; matching the substring “ML-KEM” is not a compliance assessment.

FIPS 140-3 validation applies to a cryptographic module in its documented scope
and operating conditions. Neither F* proofs nor default-provider algorithm
support confer it. For an OpenSSL-based validation claim, verify the exact module,
certificate, security policy, algorithms and operating environment. Loading a
file named `fips.so` alone is insufficient. [NIST CMVP FAQ](https://csrc.nist.gov/Projects/cryptographic-module-validation-program/faqs).

## 4. Proposed verified core

```text
Untrusted bytes / authenticated identity / current engine state
                         |
              C++ transport and bounded buffering
                         |
              Generated C validator and decision core
                         |
          explicit parsed message / permission / next state
                         |
             C++ crypto, ledger and containment actions
                         |
               checked result and recorded outcome
```

EverParse is a strong candidate for the binary validator: its purpose is to
generate verified parsers/validators from format specifications. Evaluate its
3D frontend against this header before committing to a toolchain. The surrounding
socket scheduling and stream reassembly still need their own contracts.
[EverParse project](https://github.com/project-everest/everparse).

### Concrete proof obligations

The statements below are proposed contracts, not already-proved theorems.

| ID | Property | C++ integration point |
|---|---|---|
| F-01 | Never read outside the supplied input or write outside the supplied output buffer | Frame validator |
| F-02 | Acceptance implies valid magic/version/flags/type, bounded length and enough available bytes | Frame validator |
| F-03 | Parsing reports consumed bytes; additional frames remain available | Stream adapter |
| F-04 | Splitting the same valid byte stream at any boundary preserves its decoded messages, absent timeout/resource rejection | Stream reassembly |
| F-05 | Per-session and aggregate buffered bytes remain within configured limits before allocation | Reassembly pool |
| F-06 | No frame completes after its absolute deadline when evaluated with a valid monotonic time input | Reassembly state transition |
| S-01 | A sealed restart never becomes ACTIVE without successful unseal evidence | Load/unlock transition |
| S-02 | Telemetry mutation requires ACTIVE plus an authorized identity and valid payload authentication | Every telemetry entry point |
| S-03 | A denied command changes neither ledger contents nor trusted keys | Dispatcher and commit boundary |
| P-01 | Strict profile plus affected algorithm or invalid policy evidence cannot authorize continued protected work | Policy adapter and worker control |
| P-02 | Empty and malformed inventories cannot become healthy merely because nothing was assessed | Inventory validation |
| Q-01 | Each containment request has an independent identity and cleanup responsibility; success requires action completion | Orchestrator protocol |

Deadlines require a clock and a scheduled caller. A pure theorem cannot make an
unscheduled process wake up. Storage consistency requires assumptions about the
database/filesystem. OS isolation remains a deployment property.

### C ABI design

Use byte pointers with explicit lengths, fixed-width integers, caller-owned
bounded output buffers and a result enum such as NEED_MORE, REJECT, READY.
Return consumed length explicitly. Define borrowing/lifetimes and aliasing rules.
Keep exceptions, STL containers and allocator ownership out of the C interface.
The C++ wrapper validates preconditions and converts results into typed objects.

All paths that mutate protected state must call the authorization core. Include
legacy messages, native frames, internal APIs, recovery and maintenance paths.
The final commit operation should recheck necessary state or hold the required
lock to avoid a decision becoming stale before the action occurs.

## 5. Build and evidence plan

1. Freeze the header layout, legal message types, locked-state command matrix,
   resource limits and restart/genesis distinction in a versioned specification.
2. Pin F*, solver, generator and supporting libraries. Verify a small validator
   and record its assumptions. Reject admitted proofs or unchecked verification
   modes in the release verification job.
3. Generate C and integrate it behind a narrow wrapper. The current CMake project
   declares only CXX; enable C when generated C is actually added. Keep generated
   source hashes and the exact generation commands in build evidence.
4. Differential-test the existing and generated validators. Review every
   disagreement against the specification; existing behavior is not automatically
   the correct oracle. Keep fuzzing and sanitizers on the C++ wrapper.
5. Verify authorization/state transitions next. Test sealed restart, genesis,
   malformed ledgers, duplicate/invalid shares, denied commands and unchanged
   ledger roots through real isolated IPC.
6. In CI, require proof checking, generation consistency, compilation, integration
   tests and containment/recovery tests. Make/Ninja execute this dependency graph;
   successful compilation alone does not imply any proof was checked.
7. Publish a claim-to-evidence table identifying each verified module, property,
   build, assumption, excluded behavior and independent review result.

The current `build_check` directory uses Unix Makefiles. Continue building it
with `cmake --build build_check`. A separate Ninja directory is an optional build
choice and has no bearing on formal assurance.

## 6. Claims that need precision before proof

The security-target document in this worktree is useful input, but several
statements should be treated as objectives pending evidence:

- An ML-KEM handshake or confirmation tag does not establish that later telemetry
  is encrypted/authenticated with the derived secret. Trace actual key usage.
- Erasing a shared-secret buffer does not alone prove forward secrecy; key
  lifetimes, reuse and the surrounding protocol determine that property.
- A secret-dependent hash labeled `LEDGER_SIGNATURE` is not automatically an
  asymmetric signature providing public non-repudiation.
- `OPENSSL_cleanse` at selected sites does not prove every copy of a salt or shard
  is erased. Track ownership and copying, including strings and process exits.
- ML-KEM-768's security category should not be restated as a proved exact number
  of quantum-security bits.
- A tmpfs quarantine copy does not prove zero host writes, no swap, removal of the
  original file, or physical erasure. These require separate operational evidence.

The strongest first deliverable is a verified frame validator connected to the
actual IPC path, with tests showing that rejection, valid traffic and recovery
still reach their intended outcomes. That creates a small, auditable foundation
for progressively stronger claims without changing the system's purpose.
