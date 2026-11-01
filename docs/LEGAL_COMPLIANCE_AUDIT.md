# ⚖️ LEGAL COMPLIANCE AUDIT — QUANTUM FLEX

**Date:** 2026-03-25 (original draft) | **Reviewed:** 2026-09-11  
**Status:** ACTIVE — personal research deployment on Ubuntu (`quant`); **not** a token, marketplace, or paying-customer launch  
**Entity (live docs):** FINALLYFUNGUS LLC (PA Entity ID: 13706513) DBA QuantumFlex — **not** an unincorporated sole proprietorship  
**Root Architect:** Rahshaun Chambers  

> **DISCLAIMER:** This is a structured legal risk analysis, not legal advice. Quantum Flex must retain a crypto-specialized attorney before token launch, data marketplace launch, or onboarding paying customers. This document is a roadmap to get there safely. **As of 2026-09-11, $QFX distribution and the data marketplace are not live** — they remain planned; do not read this audit as evidence they are currently operating.

> **CORRECTIONS 2026-10-23.** An evidence review found several verdicts here
> were stated with more certainty than the sources support. Changes:
> the ✅ CLEAR verdicts are downgraded to "low risk, counsel to confirm"; an
> unverified Street View precedent claim is removed; the "avoid MSB status by
> routing through DEXes" advice is withdrawn; Pennsylvania Act 7 of 2025 is
> added; §7 is relabeled as a self-assessment. Nothing in this file is a legal
> opinion or an exemption. The settlement and prepaid-credit service tiers in
> `qf-public` are suspended in code (`billing/orders.py` `SUSPENDED_TIERS`)
> until counsel reviews them.

---

## 1. WiFi Data Collection
**Verdict:** 🟡 **LEGAL with required privacy controls**

### What We Collect
SSID (network name), anonymized BSSID (last 3 octets zeroed), signal strength (dBm), channel, frequency band. No payload data. No traffic content. Broadcast radio signals only.

### ECPA Analysis
The Electronic Communications Privacy Act (ECPA) explicitly exempts publicly broadcast radio signals. WiFi SSIDs are broadcast beacons — the network announces itself to any device in range. Collecting broadcast SSID/RSSI beacon metadata, without payload, is generally treated as lower risk under ECPA. Payload capture is a different matter: do not cite the Street View WiFi litigation as support, because that case concerned payload data and its outcome has not been verified here.  
**Status:** 🟡 LOW RISK for beacon metadata only. Counsel to confirm. Never capture payloads.

### CFAA Analysis
The Computer Fraud and Abuse Act prohibits accessing computers without authorization. The Quantum Flex node SDK does NOT access any computer — it reads broadcast radio signals in the air. No credentials, no authentication bypass, no network intrusion.  
**Status:** 🟡 LOW RISK as described. This holds only while the SDK never associates with, probes, or sends to networks it does not own.

### GDPR (EU) Risk
BSSIDs are MAC addresses. Under GDPR, MAC addresses are considered personal data because they can identify a specific device and, by extension, a person's home or workplace. Even with last-3-octet anonymization, EU regulators (particularly German DPAs) have ruled that WiFi network identifiers tied to location constitute personal data.  
**Required actions if ANY EU nodes or EU data buyers:**
- Appoint EU Data Protection Representative
- Establish lawful basis (Legitimate Interest or Consent)
- Implement full data subject rights (erasure, access, portability)
- GDPR-compliant privacy notice for node operators  
**Status:** ⚠️ REQUIRES PRIVACY CONTROLS before EU expansion

### CCPA (California)
Precise geolocation data (latitude/longitude + signal readings) triggers CCPA "sensitive personal information" classification when tied to a specific person's device. Since node config files contain lat/lon AND the node has a unique keypair identity, this combination may qualify.  
**Required actions:**
- Privacy Policy disclosing data collection
- Opt-out mechanism for California residents
- Do NOT sell precise geolocation tied to individual identities  
**Status:** ⚠️ REQUIRES PRIVACY POLICY before public launch

### Immediate Actions
- [x] **Add `_optout` SSID filter** (Industry standard — networks broadcasting `_optout` or `_nomap` in SSID are excluded at the edge: implemented in `src/privacy_filter.py`).
- [ ] Draft Privacy Policy disclosing WiFi data collection.
- [ ] Implement BSSID full suppression option (not just anonymization) for GDPR jurisdictions.

---

## 2. $QFX Token (DePIN Rewards)
**Verdict:** 🟠 **LEGALLY VIABLE but requires attorney pre-launch**

### The Howey Test Breakdown
The Supreme Court's *SEC v. W.J. Howey Co. (1946)* defines a security as: (1) investment of money, (2) in a common enterprise, (3) with expectation of profit, (4) from the efforts of others.

* **Prong 1 (Investment of money):** Nodes contribute hardware and electricity — NOT direct cash investment. ✅ *Weaker security argument.*
* **Prong 2 (Common enterprise):** Yes — network value increases with more nodes. ⚠️ *Present.*
* **Prong 3 (Expectation of profit):** CRITICAL. If $QFX is marketed as an investment or nodes are told they will profit from token appreciation, this prong is met. ❌ *DANGER ZONE.*
* **Prong 4 (Efforts of others):** Nodes earn rewards for THEIR OWN labor (WiFi scanning / telemetry verification). ✅ *This is the utility token defense.*

### Recent SEC Developments (2025) — FAVORABLE
The SEC issued a no-action letter to **DoubleZero (Sept 29, 2025)** for DePIN token distributions, stating it would not recommend enforcement if tokens are distributed as rewards for network contributions — NOT as fundraising instruments. This is a major precedent for Quantum Flex.  
*Key quote from SEC guidance:* *"Token distribution is not designed to raise capital or profit from managerial efforts — it rewards labor or services."*

### The Helium Warning
The SEC also sued Nova Labs (Helium's developer) over HNT tokens, claiming they were unregistered securities. The case's current status is not re-verified here; check it before relying on either precedent. A no-action letter covers only the requester's specific facts.

### How to Stay on the Right Side
1. **NEVER market $QFX as an investment.** Not in emails, social media, Discord, nowhere. Token = payment for work, not return on investment.
2. **No presale or ICO** — do not raise money by selling tokens before the network exists.
3. **Token utility first** — $QFX must have real utility (pay for API access, stake to run nodes) before it has tradeable value.
4. **Consult a crypto attorney** — specifically one familiar with SEC no-action letters and Reg D/Reg A+ exemptions (Firms: Cooley LLP, Wilson Sonsini, or specialized crypto boutiques).

### FinCEN / MSB Compliance
If Quantum Flex operates a token exchange or allows users to convert $QFX to USD directly on-platform, it may qualify as a Money Services Business (MSB), requiring FinCEN registration and state money transmission licenses. Routing conversions through third-party DEXes does **not** by itself avoid MSB or money-transmitter status. Under FinCEN FIN-2019-G001, status turns on the operator's actual activities and control, not on whether fiat is touched. Accepting and transmitting convertible virtual currency counts as transmission.

**Pennsylvania:** Act 7 of 2025 (signed 2025-06-27) brought virtual-currency transmission under the Money Transmitter Act. Transmitting virtual currency for a fee on behalf of others requires a DoBS license, with no grace period after the effective date ([DoBS](https://www.pa.gov/agencies/dobs/newsroom/dobs-regulating-virtual-currency-transmitters-thanks-to-new-bipa.html)). This applies directly to any paid settlement, escrow, or prepaid-credit service run from PA.

**Safe today:** paying from project-owned funds for project-internal purposes, and publishing software. **Not without counsel:** holding or releasing customer funds, operating escrow or payouts for clients, or prepaid credits drawn down by USDC release.  
**Status:** 🔴 ATTORNEY REQUIRED before token launch

---

## 3. Data Marketplace
**Verdict:** 🔴 **REQUIRES REGISTRATION before selling data**

### California Data Broker Law (CCPA / Delete Act)
If Quantum Flex sells, licenses, or shares WiFi signal data with third parties — even aggregated — and that data can be linked to individuals or locations, Quantum Flex qualifies as a data broker under California law.
- Annual registration with California Privacy Protection Agency (CPPA): January 1–31 each year.
- Registration fee & disclosure of data collection practices.
- Honor consumer deletion requests via the Data Broker Registry.
- *Fines for non-compliance:* $200/day (Real companies fined $34,000–$35,000 for ~6 months of non-registration).  
**Action:** Register with CPPA before first data sale. Fee is small. Fine is not.

### FTC Enforcement & Sensitive Locations
The FTC took action against *Mobilewalla (Jan 2025)* for selling precise geolocation data revealing visits to sensitive locations (healthcare facilities, religious sites, etc.). The FTC's position: selling precise location data WITHOUT consent is an unfair trade practice.

**Quantum Flex safeguards implemented:**
- Aggregate data before sale (grid-cell level, not individual readings).
- No resale of data that can identify individual device movements.
- No sale of data tied to "sensitive" locations (hospitals, places of worship, etc.).
- Clear data buyer terms prohibiting re-identification.

### GDPR Data Marketplace
If selling data derived from EU residents' networks, data buyers become joint controllers or data processors — requiring Data Processing Agreements (DPAs) with every buyer.  
**Status:** 🔴 Register as CA data broker before Phase 2 marketplace launch.

---

## 4. Node Operators
**Verdict:** 🟡 **CONTRACTOR MODEL is correct**

### IRS Classification & Notice 2024-57
IRS Notice 2024-57 deferred broker reporting for certain transaction types, including some validation activity. It is interim relief, not a ruling that node operators are never brokers. Confirm the current position with a tax professional. However, token rewards ARE taxable income at fair market value on the date received.

**Quantum Flex obligations:**
- Confirm with a tax professional which information return, if any, applies to $QFX rewards paid to operators. Form 1099-DA is a broker form and may not be the right one; 1099-MISC/NEC thresholds also apply.
- Do NOT classify node operators as employees — they are independent contractors.
- No payroll taxes, no benefits, no W-2.
- Node operators are responsible for their own tax reporting on rewards received.

### Independent Contractor vs. Employee Test
- ✅ Nodes control their own hardware and operations.
- ✅ Nodes can run multiple networks simultaneously.
- ✅ No set schedule or hours.
- ✅ Nodes provide their own equipment.
- ✅ Quantum Flex does not supervise the node operator's work process.

### Node Operator Agreement (Required Before Alpha Expansion)
Before distributing the SDK beyond internal testing, every operator must sign a Node Operator Agreement covering:
- Independent contractor status.
- Data collected and how it is used.
- Token reward mechanics and tax responsibility.
- Right to terminate.
- Acceptable use (no fraudulent data submission).  
**Status:** ⚠️ Draft Node Operator Agreement before alpha expansion.

---

## 5. Business Entity
**Verdict:** 🟡 **PA LLC EXISTS — Wyoming DAO is optional, not “incorporate now”**

Due-diligence materials identify **FINALLYFUNGUS LLC (Pennsylvania, Entity ID 13706513) DBA QuantumFlex**. Do not treat the project as a bare sole proprietorship. Confirm with counsel that contracts, banking, and any future token or marketplace activity flow through that LLC (or a successor), not through Rahshaun personally.

A Wyoming DAO LLC remains an **optional** later structure for token governance (W.S. 17-31-101). It is not the current P0 “form an entity from zero” task.

### If counsel later recommends a Wyoming DAO successor
- Limited liability and a recognized contracting entity
- DAO-friendly operating agreement
- All Quantum Flex contracts still must not run in a personal name

---

## 6. Action Priority Matrix

| Priority | Action | Target Milestone | Est. Cost | Status |
|---|---|---|---|---|
| 🔴 **P0** | Confirm PA LLC (FinallyFungus) is the contracting entity; Wyoming DAO only if counsel recommends a successor | Before token / paying customers | Counsel | 🔲 Confirm |
| 🔴 **P0** | Draft Node Operator Agreement | Before 5-node alpha | ~$500 review | 🔲 Target |
| 🔴 **P0** | Add `_optout` SSID filter to SDK | Immediate Sprint | Free | ✅ **BUILT & TESTED** (`src/privacy_filter.py`) |
| 🔴 **P0** | Draft Privacy Policy | Before public-facing release | Template / ~$300 | 🔲 Target |
| 🟠 **P1** | Retain crypto attorney (token counsel) | Before $QFX launch | $5k–$15k | 🔲 Phase 1 |
| 🟠 **P1** | Register CA data broker (CPPA) | Before data marketplace | ~$100/year | 🔲 Phase 2 |
| 🟡 **P2** | GDPR compliance layer | Before EU expansion | Ongoing | 🔲 Phase 2 |
| 🟡 **P2** | 1099-DA issuance system | Before 100+ nodes | Free via on-chain data | 🔲 Phase 2 |

---

## 7. Self-Assessed Baseline (not legal clearance)
- 🟡 WiFi broadcast scanning: low ECPA/CFAA risk as described; not attorney-reviewed.
- ✅ BSSID anonymization already implemented.
- ✅ `127.0.0.1` gateway binding (Zero-trust unexposed).
- ✅ No payload / content interception.
- 🟡 Node operator contractor model proposed (no operators exist; no agreement signed).
- ✅ Token rewards for labor (Proof-of-Telemetry), not passive investment.
- ✅ Zero presale / zero ICO structure.

---
**Sources & Legal Precedents:**  
*Aurum Law — DePIN Legal Risks 2025* · *SEC No-Action Letter for DePIN (DoubleZero, Sept 2025)* · *CA CPPA Data Broker Registry* · *IRS Digital Assets Guidance (Notice 2024-57)* · *FTC v. Mobilewalla (Jan 2025)*
