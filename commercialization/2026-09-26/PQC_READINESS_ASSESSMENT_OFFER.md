# Offer draft: Post-Quantum Readiness Snapshot

**Draft, September 26, 2026.** Consulting track that runs in parallel with
[QUANTUMFLEX_PAID_PROOF.md](QUANTUMFLEX_PAID_PROOF.md). It sells operator labor and judgment, not
the QuantumFlex runtime, so it does not wait on the A6 launcher repair. It does not replace the
paid-proof test: a payment here shows demand for PQC assessment work, not for QuantumFlex itself.

## Pre-send gate (do these before any outreach goes out)

1. Deliver the full snapshot on an operator-owned host (the Yoga) and keep a redacted copy as the
   sample report. Record real hours spent; reprice if it takes more than 8.
2. Recheck every regulatory reference below against the primary source on the day of sending.
3. The A6 launcher repair and adversarial matrix rerun passed 11/11 cases (CL-09). The installed
   host trust anchor in `~/.local/libexec/quantumflex` has been updated with the repaired launcher.
   If referencing CL-09, cite the 11/11 verified matrix pass; do not cite older "10/10" notation.
   Do not cite CL-06 test counts; they are dated.
4. Do not use `scripts/generate_cbom.py` output as a deliverable. It contains host-specific
   constants and fallback values. The CBOM in this offer is hand-built and schema-validated.

## One-page offer (customer-facing)

> **Post-Quantum Readiness Snapshot — one Linux host, three business days, fixed price**
>
> Quantum-capable attackers are expected to break the RSA and elliptic-curve key exchange and
> signatures most systems use today. NIST's post-quantum transition guidance (NIST IR 8547 / SP 800-131A)
> outlines the deprecation and transition away from classical public-key cryptography by 2030–2035,
> while NSA's CNSA 2.0 timeline mandates post-quantum capability starting in 2025–2027 and requires
> full deployment for software signing and network protocols by 2030 (complete NSS transition by 2035 per NSM-10).
> Data recorded now can be decrypted later ("Harvest Now, Decrypt Later"). The first step every
> guidance document names is the same: know where your cryptography is.
>
> **What you get**
> - An inventory of the cryptography one Linux host actually uses: TLS endpoints and negotiated
>   groups, SSH key exchange and host keys, certificates and their expiry, and the crypto libraries
>   and versions installed. Every finding comes with the command that produced it, so your team can
>   rerun it.
> - Each item marked **quantum-vulnerable**, **hybrid/post-quantum capable**, or **unknown**, with
>   unknowns listed honestly rather than guessed.
> - A CycloneDX cryptographic bill of materials (CBOM) file for that host.
> - A prioritized migration plan: the three changes that give the most protection first (for
>   example, enabling hybrid ML-KEM key exchange where your OpenSSL/OpenSSH already supports it),
>   each with a rollback note.
> - A 30-minute walkthrough call.
>
> **Scope:** one host, up to three network-facing services, one technical contact, 8 hours of
> work. Read-only collection on the host you designate; no changes are made unless you ask for one
> in writing.
>
> **Not included:** penetration testing, scanning of systems you have not named in writing,
> production changes, FIPS 140-3 or any certification, or legal/regulatory compliance opinions.
>
> **Price:** $1,500. $750 to book, $750 on delivery of the listed items.
>
> **Who does the work:** an operator who runs a post-quantum migration on their own
> infrastructure: an ML-KEM key-exchange runtime, TLS 1.3-only services, and Ed25519-signed
> release manifests checked by an external verifier.

Items in that last line map to ledger entries still standing: CL-15 (TLS 1.3 floor) and CL-08
(external provenance authority). None of it claims certification (CL-14: not claimed).

## Outreach templates

Replace every `[bracket]`. Send only to people with a visible, specific reason to care; one
message, one follow-up, then stop.

**1. Cold email to an MSP owner or engineering lead**

> Subject: Post-quantum inventory for [company]'s Linux hosts
>
> Hi [name],
>
> I saw [specific public fact: their on-prem Linux product / federal customers / security page].
> The first step in every post-quantum migration plan is an inventory of where RSA and
> elliptic-curve crypto is actually in use, and most teams don't have one per host yet.
>
> I do a fixed-price snapshot of one Linux host in three business days: what TLS, SSH,
> certificates, and crypto libraries it really uses, what is quantum-vulnerable, a CycloneDX
> CBOM file, and the three highest-value changes to make first. $1,500, read-only, no
> production changes. A redacted sample is attached.
>
> Worth a 15-minute call to see if it fits [system they mentioned]?
>
> [name] · [company/LLC] · [contact]

**2. Reply to a posted job asking for PQC, crypto inventory, or TLS/SSH review**

> Your post asks for [quote their requirement]. I can deliver that for one Linux host as a
> fixed-scope snapshot: a rerunnable inventory of TLS/SSH/certificate/library crypto, each item
> classed as quantum-vulnerable, hybrid-capable, or unknown, a CycloneDX CBOM, and a prioritized
> migration plan with rollback notes. Three business days after access, 8 hours, $1,500
> (or your posted budget if it's close). I don't do certification or unscoped scanning.
> Redacted sample attached. What OS and services are on the host?

**3. Short LinkedIn / chat message**

> Hi [name], I help teams take the first post-quantum step: a per-host inventory of where
> RSA/ECC is actually used, with a CBOM and the three changes to make first. Fixed price, three
> days, one Linux host. Is PQC on [company]'s list this year? Happy to send a redacted sample.

## Qualifying questions (first call)

1. What is driving this: a customer security questionnaire, a federal contract, or general
   planning? Is there a date attached?
2. Which host and which services? Who can grant read-only access, and how fast?
3. Do you already use an inventory tool (for example IBM Quantum Safe Explorer or CBOMkit)? If
   so, what does it leave unanswered?
4. Who approves a $1,500 purchase, and how do you pay vendors?

Disqualify politely if there is no named host, no one who can grant access within two weeks, or
the need is a certification this offer does not provide.

## Measuring the test

Track: messages sent, replies, calls held, proposals sent, deposits cleared, delivery hours,
and whether each buyer asked for a second host. One cleared deposit within 14 days of the first
send is the pass signal. Zero calls from 20 targeted messages means change the audience or the
message before changing the price.
