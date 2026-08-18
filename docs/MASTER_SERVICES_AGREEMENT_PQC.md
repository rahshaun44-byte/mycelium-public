# MASTER SERVICES AGREEMENT (MSA) & STATEMENT OF WORK (SOW)
**Post-Quantum Cryptography (PQC) Architectural Advisory & Engineering Prototyping**

This Master Services Agreement ("Agreement") is entered into as of this _____ day of ____________, 2026 ("Effective Date"), by and between:

**CONSULTANT:** FinallyFungus LLC [⚠ Entity registration must be verified with state before signing] ("Consultant"), a limited liability company, and  
**CLIENT:** ____________________________________________________ ("Client"), a corporation/entity.

---

## 1. SCOPE OF SERVICES & INDEPENDENT ADVISORY NATURE

1.1 **Scope of Work:** Consultant agrees to provide independent architectural advisory, technical analysis, and prototype development related to Post-Quantum Cryptography (PQC) migration, Cryptographic Bill of Materials (CBOM) automation, and policy sidecar deployment as detailed in attached Statements of Work ("SOW").

1.2 **Advisory Classification Disclaimer:** Client explicitly acknowledges that Consultant operates as an independent technical advisory and engineering services provider. Consultant is **not** an accredited Third-Party Assessment Organization (3PAO) or Certified Third-Party Assessment Organization (C3PAO), and does not issue formal third-party regulatory accreditations. Consultant's deliverables are engineered to provide technical architecture, evidence artifacts, and compliance readiness for Client's internal governance and subsequent third-party audits.

---

## 2. STATEMENT OF WORK (SOW) #1 — OMB M-26-15 COMPLIANCE PROTOTYPING

### A. Deliverables & Milestones
- **Milestone 1: Cryptographic Discovery & CBOM Baseline ($2,500)**
  - Delivery of automated CycloneDX v1.5 CBOM scanning workflow.
  - Inventory report mapping active algorithms against NIST FIPS 203/204/205 standards.
- **Milestone 2: OPA Policy Engine & Fallback Architecture ($3,500)**
  - Deployment of Open Policy Agent (OPA) sidecar with custom `membrane_health.rego` policy rules.
  - Configuration of multi-tier fallback routing (`ML-KEM-512/768/1024` $\rightarrow$ `FrodoKEM` $\rightarrow$ `X25519`).
- **Milestone 3: Live-Fire Fallback Verification & Executive Brief ($1,500)**
  - Execution of simulated compromise test demonstrating zero-downtime atomic vein collapse.
  - Delivery of final Executive Cryptographic Architecture & Migration Document.

**Total Fixed Engagement Fee:** **$7,500 USD** (50% deposit upon signing, 50% upon milestone completion).

---

## 3. COMPENSATION & PAYMENT TERMS

3.1 **Invoicing:** Invoices shall be issued upon execution of this Agreement and completion of deliverables. Payment is due within fifteen (15) days of invoice date ("Net 15").  
3.2 **Late Payments:** Overdue amounts shall accrue interest at 1.5% per month or the maximum rate permitted by law.

---

## 4. INTELLECTUAL PROPERTY & WORK PRODUCT

4.1 **Client Deliverables:** Upon full payment of all fees, Client shall own all custom documentation, architectural reports, and client-specific configuration scripts created under this Agreement.  
4.2 **Pre-Existing IP & Tooling:** Consultant retains all right, title, and interest in its pre-existing tools, core libraries, algorithms, biological daemon blueprints, and general methodologies (including QuantumFlex / Sentinel frameworks). Consultant grants Client a perpetual, non-exclusive, royalty-free license to utilize such components integrated into Client's environment.

---

## 5. CONFIDENTIALITY & NON-DISCLOSURE

Each party agrees to preserve the confidentiality of all proprietary and non-public technical, business, and cryptographic information disclosed by the other party with the same degree of care it exercises with its own sensitive data, but not less than reasonable care.

---

## 6. LIMITATION OF LIABILITY & E&O SHIELD

6.1 **Liability Cap:** IN NO EVENT SHALL CONSULTANT’S TOTAL AGGREGATE LIABILITY ARISING OUT OF OR RELATED TO THIS AGREEMENT, WHETHER IN CONTRACT, TORT (INCLUDING NEGLIGENCE), OR OTHERWISE, EXCEED THE TOTAL FEES ACTUALLY PAID BY CLIENT TO CONSULTANT UNDER THE APPLICABLE STATEMENT OF WORK IN THE PRECEDING TWELVE (12) MONTHS.

6.2 **Consequential Damages:** IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR ANY INDIRECT, SPECIAL, INCIDENTAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES (INCLUDING LOSS OF PROFITS OR DATA), EVEN IF ADVISED OF THE POSSIBILITY THEREOF.

9.3 **Insurance:** [⚠ STRICKEN UNLESS POLICY IS ACTIVELY BOUND] Consultant maintains Technology Errors & Omissions (E&O) and Cyber Liability insurance with standard coverage limits of not less than $1,000,000.

---

## 7. GOVERNING LAW & JURISDICTION

This Agreement shall be governed by and construed in accordance with the laws of the State of Delaware / Pennsylvania, without regard to its conflict of law principles.

---

**IN WITNESS WHEREOF**, the parties have executed this Master Services Agreement as of the Effective Date.

**FINALLYFUNGUS LLC (Consultant)**  
Signature: _________________________________________  
Name: Rahshaun Chambers  
Title: Principal Security Architect / Managing Member  
Date: ________________________  

**CLIENT NAME (Client)**  
Signature: _________________________________________  
Name: _____________________________________________  
Title: ______________________________________________  
Date: ________________________  
