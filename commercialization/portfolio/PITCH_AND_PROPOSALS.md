# Commercial Pitch Deck & Freelance Proposal Toolkit
**Authority:** Rahshaun Chambers // Post-Quantum Security & Cryptographic Systems  
**Target Channels:** Upwork, Contra, LinkedIn Direct, MSP/Enterprise Outreach  

---

## 1. Tiered Service Offerings & Pricing Matrix

| Tier | Package Name | Scope | Deliverables | Turnaround | Price |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier 1** | **Codebase CBOM Scan** | 1 GitHub repository or application source tree | • CycloneDX v1.5 CBOM JSON<br>• Discovered Cryptographic Asset Table<br>• Quantum-Vulnerability Classification | 24–48 hours | **$350** |
| **Tier 2** | **Host Readiness Assessment** | 1 Linux host + up to 3 network services (TLS/SSH) | • Full Host Cryptographic Inventory<br>• Buffer Elasticity / Truncation Check<br>• Top 3 Prioritized Remediation Steps<br>• 30-min Technical Walkthrough Call | 3 business days | **$750** |
| **Tier 3** | **PQC Agility & Policy Integration** | Host + CI/CD pipeline or custom service boundary | • Automated CBOM in CI/CD (GitHub Actions)<br>• Open Policy Agent (OPA) Crypto-Agility Gate<br>• OpenSSL 3.5 ML-KEM Hybrid Configuration | 5 business days | **$1,500** |

---

## 2. Upwork Proposal Templates

### Template A: General Cryptography / OpenSSL / Security Audit Jobs
*Use when job descriptions mention "OpenSSL", "TLS configuration", "cryptography review", "security assessment", or "FIPS".*

> **Proposal Subject:** Cryptographic Inventory & Readiness Assessment
>
> Hi there,
>
> I saw your posting regarding [mention specific project requirement, e.g., reviewing cryptographic implementations / TLS configuration / library dependencies].
>
> Many engineering teams are beginning to inventory their cryptographic footprint ahead of new post-quantum mandates (NIST FIPS 203/204). The critical first step is establishing an exact, rerunnable Cryptographic Bill of Materials (CBOM) so you know exactly which ciphers, key exchanges, and signature schemes are active across your code and network endpoints.
>
> What I deliver:
> 1. A complete inventory of active cryptographic primitives (ciphers, hashes, signatures, key exchange).
> 2. CycloneDX v1.5 CBOM file ready for your compliance records.
> 3. Quantum-vulnerability classification (identifying legacy RSA/ECC vs. post-quantum/hybrid schemes).
> 4. Buffer elasticity check (ensuring network framing can handle larger post-quantum keys without memory truncation).
> 5. A prioritized, actionable remediation memo with exact rollback notes.
>
> I maintain a working post-quantum Linux pipeline on my own infrastructure (OpenSSL 3.5, ML-KEM-768, and declarative OPA policy gates). A sanitized sample report is available for review.
>
> Would you like to review the sample report to see if this fits your current codebase?
>
> Best regards,  
> Rahshaun Chambers

---

### Template B: Specifically for PQC / Post-Quantum Cryptography Jobs
*Use when job descriptions specifically mention "Post-Quantum", "PQC", "ML-KEM", "Kyber", "Dilithium", or "CNSA 2.0".*

> **Proposal Subject:** Practical PQC Assessment & ML-KEM/ML-DSA Implementation
>
> Hi there,
>
> I specialize in practical post-quantum cryptography migration, focusing on the newly standardized NIST algorithms (FIPS 203 ML-KEM, FIPS 204 ML-DSA) and hybrid transitional deployment.
>
> Rather than theoretical advice, I focus on operational readiness:
> - Mapping your current classical public-key dependencies (ECDH/RSA).
> - Generating an official CycloneDX CBOM (Cryptographic Bill of Materials).
> - Configuring hybrid key encapsulation (e.g., X25519 + ML-KEM-768 via OpenSSL 3.5) so you maintain backward compatibility while achieving forward secrecy against Harvest-Now-Decrypt-Later threats.
> - Verifying signature verification boundaries and buffer sizes.
>
> Fixed-price deliverables start with a 48-hour codebase inventory ($350) or a full host assessment ($750). I can share a sanitized sample report showing the exact tables, CBOM schema, and remediation roadmap.
>
> What language and crypto libraries does your stack currently rely on?
>
> Best regards,  
> Rahshaun Chambers

---

## 3. Direct Message / LinkedIn Template (1-on-1 Outreach)

*Target: CTOs, VP of Engineering, or Security Leads at SaaS/Fintech companies or Web3 infra protocols.*

> Hi [First Name],
>
> I saw [specific observation about their company, e.g., your on-prem Linux architecture / focus on infrastructure security].
>
> With NIST finalizing FIPS 203/204, the first step in any post-quantum transition plan is establishing where classical RSA and elliptic-curve cryptography are actually active across services.
>
> I provide a fixed-scope, read-only **Post-Quantum Cryptographic Readiness Snapshot** for Linux codebases and hosts: an automated CycloneDX CBOM inventory, vulnerability classification, and the top 3 highest-impact configuration updates to make first.
>
> Fast turnaround (3 business days), fixed price, zero production disruption. A sanitized sample deliverable is available if you're exploring PQC planning this quarter.
>
> Worth sending over a copy?
>
> Rahshaun Chambers · FinallyFungus LLC

---

## 4. Client Qualification Checklist (Before Accepting a Contract)

Before taking a deposit or beginning work with a client:
1. **Target Environment**: Confirm the operating system (e.g., Ubuntu/Debian/RHEL x86_64 or a standard Git repository).
2. **Access Method**: Read-only repository access or non-production test host access. Never accept production root credentials.
3. **Deliverable Scope**: Agree on the exact package (Tier 1, 2, or 3) and provide the sample deliverable so expectations are 100% aligned.
4. **Deposit / Escrow**: Upwork milestone escrow funded upfront, or direct 50% deposit before analysis begins.
