# Proposed pilot scope — for review, not a signed agreement

**Service:** QuantumFlex Release Admission Challenge.

**Customer / supplier / authorized contacts:** to be supplied before acceptance.

**Outcome:** determine whether the agreed QuantumFlex signed-release launch path
admits the customer's valid Linux executable and rejects the six agreed invalid
cases in one nonproduction environment. Record failed and inconclusive outcomes
as clearly as successful ones. This engagement is a scoped demonstration and
integration test, not a whole-system security audit or certification.

**Preflight before booking:** identify a native Linux ELF executable and supported
Linux host; run the synthetic demonstration there; confirm a customer-controlled
test signing key and verifier location; agree artifact access, distribution terms,
test permissions, rollback and exact cases. Private production signing keys are
not needed. An unsupported environment is not booked under this scope.

**Delivery:** one valid-launch case, changed runtime bytes, missing runtime
signature, wrong runtime signer, altered binding, changed declared release
artifact, and missing release signature. The customer chooses the mutation
locations within these cases. Additional race-condition or platform scenarios
are separately scoped. The customer observes whether the target executes and
retains exit codes, artifact hashes, commands, and source-version identifiers.

**Acceptance:** the valid artifact launches; all six agreed invalid cases deny
launch; the customer can reproduce the results from the provided instructions.
Unexpected allow, unexpected deny, or an unreproducible result prevents acceptance
until fixed and rerun. The buyer supplies written acceptance or lists the failed
criteria. Evidence delivery by itself is not successful technical acceptance.

**Time and fee:** proposed $1,500; $750 after written scope acceptance, successful
preflight and confirmed start date; $750 after acceptance. Five business days from
that start, up to eight delivery hours. Customer access delays move the timetable.
No subscription or renewal is included. Supplier/customer identity, taxes, payment
processing fees, invoicing details and distribution terms must be agreed before
the scope is executed.

**Failure treatment to agree before payment:** one repair window of up to two
business days and four additional supplier hours, with no additional pilot fee.
If agreed criteria remain unmet, deliver the failure evidence and refund the
pilot payment for this unsuccessful engagement; no final balance is due.
This is a proposed commercial term requiring supplier approval before use.

**Boundaries:** primary executable integrity is tested, not its dynamic libraries,
interpreter, entire machine, all privileged attackers, or signing-key lifecycle.
The demo's signatures are Ed25519; no post-quantum/FIPS validation claim is made.
Production service installation, persistent host policy, fleet rollout and broad
remediation are excluded from this first experiment.

**Customer artifacts:** use only for the agreed pilot, retain evidence in the
customer's approved location, and agree a deletion date before receiving files.
No customer code, identifiers or logs become marketing material without consent.
