# QuantumFlex QPU entropy alignment review

Reviewed 2026-10-11. Scope: supplied guidance, `/home/quant/quantumflex/qf` entropy bridge, and the existing native ML-KEM test in `/home/quant/mycelium`. This is a source review and a prebuilt-binary functional check, not certification or verification of live deployment.

## Verdict

The guidance has a sound direction: separate entropy collection, conditioning, random generation, and key use. The current QPU bridge is not ready to supply trusted cryptographic entropy. Keep production key generation on its existing OS/provider randomness path while addressing the findings below. Do not reuse any seed disclosed in documentation, console output, or evidence records for new secrets.

## Findings and required changes

1. **Seed disclosure and retention — high priority.** `qf/ledger.py:142` stores the entire conditioned seed. `qf/qflex_quantum.py:247` prints its first 128 bits; subsequent code saves hex and binary copies. `qf/HANDOFF.md` also publishes a seed. Replace secret fields with evidence digests for future records, stop console disclosure, and avoid default seed persistence. Preserve historical ledger integrity; do not silently rewrite its hash chain. Identify and retire any keys actually derived from disclosed material, if such derivation occurred. Source searches did not establish that these seeds feed the engine.

2. **Entropy credit is unsupported.** `qf/quantum_worker.py:23` computes only marginal bit frequencies and multiplies the resulting estimate by length. A fixed alternating sequence receives a perfect score despite being predictable. Correlations between qubits/shots, IID assumptions, confidence bounds, restart behavior, and a source threat model are unaddressed. Label these values bias diagnostics and credit zero validated entropy until assessment establishes a defensible lower bound.

3. **Missing admission tests for entropy.** Both worker paths condition immediately without startup/continuous source health checks or a minimum assessed entropy gate. Implement repetition-count and adaptive-proportion tests with thresholds derived from an assessed source model and chosen false-alarm probability. Health tests detect failures; passing them does not independently validate entropy.

4. **Shot order can be fabricated.** Both worker paths fall back to concatenating outcome labels multiplied by histogram counts. Counts cannot recover chronological measurements. Reject unavailable ordered samples; validate sample width, binary alphabet, shot count, and complete data before hashing or conditioning.

5. **Conditioning assurance is overstated.** The HMAC key is public metadata (`salt:backend:job_id`). Domain separation is useful but contributes no secret entropy. HMAC-SHA-256 is a vetted conditioning primitive under SP 800-90B requirements; this implementation alone does not prove uniform output or a leftover-hash-lemma guarantee. Remove those claims pending source assessment and a complete conditioning argument.

6. **One-time consumption and RBG integration are absent from the reviewed bridge.** The output is saved and attested; no engine consumer or consumed-event guard was found in the searched Python/C++ source. Specify a native provider boundary and an atomic event-consumption record before integrating. Do not replace provider randomness with a homegrown generator or claim entropy for unassessed QPU input. An optional experiment may mix it as additional input with zero entropy credit while preserving trusted OS seeding; verify the selected OpenSSL provider's behavior.

7. **Secret destruction is unproven.** Raw samples, HMAC output, and hex representations use Python immutable objects and SDK-managed copies. Deleting references cannot demonstrate zeroization. Use a native secret-handling boundary with explicit cleanup on success and failure; document SDK/cloud retention limits. Secure deletion of files cannot be promised merely by unlinking them.

8. **PCR binding needs a public receipt.** The CLI passes the seed to `tpm2_pcrextend` in process arguments. Extend a digest of nonsecret canonical evidence instead. PCR extension binds local supplied data; it does not independently establish source unpredictability or QPU execution. Record extension outcome separately from the already-written collection receipt.

## Corrections to the supplied text

- 8,192 times 0.8009 is approximately 6,561, but that arithmetic only yields a valid total entropy bound under justified source assumptions. The current frequency estimator supplies no such justification.
- Bell outcomes are correlated: two measured Bell bits must not be counted as two independent random bits. The actual entropy worker builds a separate Hadamard circuit; assess that circuit and its hardware correlations directly.
- SP 800-90B formal validation calls for at least 1,000,000 raw sample values plus restart assessment. An 8,192-bit prototype run does not establish compliance.
- DRBG instantiation includes mechanism-specific entropy/nonce requirements. A 32-byte value is not a universal complete instantiation recipe, and KDF expansion cannot increase input entropy or replace the approved RBG required for ML-KEM.
- ML-KEM-768 requires fresh randomness from an approved RBG of at least 192-bit strength for key generation and encapsulation. A successful roundtrip establishes functionality, not randomness quality or module validation.
- Long-term private keys may be retained under a deliberate secure-storage lifecycle. Destruction after a disposable test is appropriate; it is not a universal key-storage rule.
- Remote IBM service results require trust in provider handling and confidentiality. A job ID, hash, or local TPM extension is not device-independent randomness certification.

## Verification performed

`/home/quant/mycelium/build_check/test_mlkem768` exited 0 and reported native ML-KEM-768 roundtrip, implicit rejection, confirmation, provider failure, lengths, and wire framing checks passing. The source test cleanses its shared-secret buffers. This prebuilt binary was not rebuilt or matched to current source, and this test does not consume the QPU seed. No QPU job, TPM extension, key rotation, ledger alteration, or live service change was performed.

## Acceptance criteria for alignment

First close disclosures and incorrect assurance claims. Then verify negative cases for missing/reordered samples, predictable sequences, insufficient entropy, simulator input to a production consumer, duplicate/concurrent consumption, and provider errors. Verify that receipts/logs contain no secret bytes, that failures do not produce usable keys, and that native cleanup runs on every path. Finally demonstrate the selected RBG/provider integration and fresh ML-KEM randomness without weakening OS entropy. Formal compliance remains a separate assessment.

## Primary references

- NIST SP 800-90B: https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-90B.pdf
- FIPS 203, section 3.3: https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.203.pdf
- OpenSSL 3.5 EVP_RAND, entropy input versus additional data and FIPS-mode limitations: https://docs.openssl.org/3.5/man7/EVP_RAND/
