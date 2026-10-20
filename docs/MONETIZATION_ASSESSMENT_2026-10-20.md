# QuantumFlex Monetization Assessment (2026-10-20)

Honest 90-day view. Sources: web research on 2026-10-20 plus a local read of `qf-public/docs/COMMERCIAL_OFFERINGS_SOW.md` and `quantumflex/mycelium/commercialization/2026-09-26/`.

## Bottom line

The skills sell now; the product does not. QuantumFlex has no external users, so selling audits of "QuantumFlex deployments" has no buyer. The portfolio covers OpenSSL 3.5 ML-KEM/ML-DSA, mTLS, Shamir custody, CBOM/OPA crypto-agility and a Solidity escrow, and that is marketable today.

## What will not make money

- **Testnet settlement:** 20 Base Sepolia USDC is worth $0.
- **IBM QPU runs:** results fall below a random baseline (TRUTH_LOG §17.3). Any "quantum" marketing that implies an advantage invites credibility damage and FTC risk.
- **Agent Execution Credit ($250 prepaid) and Settlement Bridge ($1,500):** accepting and transmitting customer value likely makes you a money-services business, requiring FinCEN registration plus a license in each state. See [FinCEN FIN-2019-G001](https://www.fincen.gov/sites/default/files/2019-05/FinCEN%20Guidance%20CVC%20FINAL%20508.pdf). **Pull both tiers, or get counsel first.**
- **Invariant Audit ($750):** it audits a system nobody else runs.
- **PQC assurance claims:** without independent review or FIPS 140-3 / CMVP validation, they are not sellable as assurance.

## Ranked actions (expected $ within 90 days × probability)

| # | Action | First step | Effort | Realistic $ | P |
|---|---|---|---|---|---|
| 1 | **Paid part-time role**: campus security/crypto RA or TA, or a part-time PQC contract through a staffing firm | Write a one-page portfolio; send it to 5 faculty and to Apex/Eliassen-type recruiters | 5–10 h | $1.5k–4k campus; more on contract | ~30% |
| 2 | **Freelance C++/OpenSSL/PQC integration** (Upwork, Contra, LinkedIn) | Profile with 2 small open-source demos; bid on 20 jobs | 10 h setup | $1k–5k at $30–75/h | 25–35% |
| 3 | **Fixed-price "PQC Readiness Sprint"**: CBOM (CBOMkit + your generator), TLS/ML-KEM readiness, CNSA 2.0 / FIPS 203/204 remediation memo | Run it free on 2 public OSS repos and publish the reports, then email 30 small SaaS companies and federal subcontractors facing the 1 Jan 2027 CNSA 2.0 gate | ~20 h build, then 8–15 h per client | $500–2,500 per engagement | 20–25% |
| 4 | **Base Builder Grant** (retroactive, no application) | Ship a non-custodial Base mainnet tool that anchors ledger state roots or CBOM hashes; never hold anyone else's USDC | 15–25 h | 1–5 ETH or $0 | 5–10% |
| 5 | **Audit contests** (Code4rena, Sherlock, Cantina) | Enter one Solidity contest | 20–40 h per contest | $0–1k | ~20% |
| 6 | **NLnet proposal**: deadline 3 Nov 2026, 12:00 CET | Hand-written proposal for the ML-KEM gateway plus the CBOM/OPA gate. A "European dimension" is required, and AI-written proposals are refused | 10 h | $0 within 90 days (paid on milestones); €5k–50k eventually | ~10% |
| 7 | **Open-source the OPA + CBOM crypto-agility gate**, with GitHub Sponsors | Make it a standalone repo with CI and a demo | 10–15 h | $0–200 directly; supports actions 1–3 | — |

## Grants that don't fit right now

- **Circle grants:** milestone-based, aimed at teams moving to production on Arc, which pushes you toward mainnet and the transmitter risk above.
- **IBM Quantum Credits:** only for permanent researchers, and they give hardware time, not cash.
- **Sovereign Tech Fund:** the 2026 rounds have closed.
- **Ethereum Foundation ESP:** open applications are paused.
- **Optimism Retro Funding, Gitcoin:** no 2026 rounds confirmed.
- **Alpha-Omega:** funds established critical projects.
- **NSF SBIR:** needs an incorporated small business with a PI employed mainly by it, so it doesn't fit a full-time student.

## Market context

- PQC demand is real but goes mostly to large firms (the 8 NCSC-assured consultancies).
- Posted PQC contracts pay $60–95/h W2 and usually ask for 5+ years' experience.
- CBOMkit is free (PQCA/Linux Foundation), so a CBOM tool alone won't sell; the expert labour around it will.

Caveats: rate figures come from vendor blogs and job posts, which are small samples. Grant-program status changes often, so re-check before applying.

## Addendum: higher-leverage plays (research 2026-10-20, second pass)

1. **ML-DSA/ML-KEM implementation bug hunt.** Bernstein's June 2026 paper "Exploiting ML-DSA bugs" shows two bug classes that recover an equivalent secret key in under 1 s ([postquantum.com](https://postquantum.com/security-pqc/bernstein-exploiting-mldsa-bugs/)). Turn the KAT, negative-fuzz and dudect harnesses into an open differential tester and run it against open-source ML-DSA/ML-KEM libraries (Rust, Go, JS, embedded). Pay comes from bounties where a library is in scope (check each program; unverified) plus CVE credit, which converts into contracts. liboqs has had real CVEs of exactly this kind ([releasealert](https://releasealert.dev/github/open-quantum-safe/liboqs/cves)).
2. **Post-quantum-signed receipts for AI agents.** Competitors sign with Ed25519 only:
   - protect-mcp: free up to 20k receipts, then $0.50/1k
   - Provenant: $99 per anchored bundle
   - Asqav: $79/mo
   - Apify agent-audit-ledger: pay per event
   
   Pricing sources: [GitHub map](https://github.com/JaredKlopstein/provenant/issues/12), [Apify](https://apify.com/apricot_blackberry/agent-audit-ledger). The QuantumFlex hybrid Ed25519+ML-DSA evidence ledger plus the MCP gate is the differentiator. Fastest billing route: publish as an Apify actor (the marketplace handles payment, so there's no money-transmitter issue). Note: the EU AI Act high-risk logging deadline moved to 2 Dec 2027 (Reg. 2026/1744) ([CSA](https://labs.cloudsecurityalliance.org/research/csa-research-note-eu-ai-act-omnibus-vii-deadline-delay-20260/)), so urgency is lower than vendors claim.
3. **Deltakit Community Fund:** $2k–4k quarterly microgrants for open-source QEC tooling (error budgets, thresholds, ZX benchmarks); the first cohort was reviewed 17 Aug 2026 ([QCR](https://quantumcomputingreport.com/riverlane-and-unitary-foundation-launch-deltakit-community-fund-for-open-source-qec/)). The next cohort's date is unconfirmed; check the official page.
4. **Free PQC TLS/SSH scan → paid report.** The free single-domain checkers are taken (DigiCert, ImmuniWeb, Axiad). The gap is bulk attack-surface scans plus a CNSA 2.0 memo, which feeds the Readiness Sprint.
5. **Wallet quantum-exposure checker.** Ethereum has made PQ a top priority, with a $1M Poseidon prize, a planned move to hash-based leanXMSS, and a stated goal of deploying PQ cryptography by 2029 ([The Block](https://www.theblock.co/post/386938/ethereum-foundation-forms-post-quantum-security-team-adds-1-million-research-prize)). A free "is this address's public key exposed?" tool on Base suits the Base Builder Grant route. Revenue is uncertain; attention is likely.

Missed this cycle: Xanadu QHack (16–23 Oct, $67k pool). The Q-Day Prize was already awarded (Apr 2026).
