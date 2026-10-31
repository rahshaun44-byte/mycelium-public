# Track 0 Financial Reserve Reconciliation Worksheet (`QF-M5.1` — P0)

**Governing Law:** Supreme Alignment Law (`Law 0`) & Golden Financial Invariant (`QF-CAPITAL-01`)  
**Governing Equation:**

$$
R_{\text{verified liquid}} \geq 6O, \qquad O = O_{\text{household living}} + O_{\text{debt service}} + O_{\text{operating}}
$$

> **STRICT PRIVACY INVARIANT (`QF-PRIVACY-01`):**
> Never enter real personal dollar amounts into any Git-tracked file in `/home/quant/mycelium`.
> Copy the JSON worksheet schema below to `~/.config/quantumflex/private/track0_worksheet.json` (`chmod 0600`), populate your verified statement figures offline, and run `scripts/reconcile_track0_reserves.py`. The reconciler outputs **dimensionless coverage ratios only** (`coverage_months`, category share percentages, and pass/fail booleans) so raw household balances never enter Git, stdout logs, or dossier artifacts.

---

## 1. Verified Liquid Account Balances ($R_{\text{verified liquid}}$)

Include **only settled, unconditionally accessible, low-volatility cash equivalents** verified against current bank or brokerage statements:

| Account Category | Eligible? | Example Instruments | Placeholder |
| :--- | :--- | :--- | :--- |
| Primary Checking (FDIC/NCUA insured) | **YES** | Household operating checking | `$0.00` |
| High-Yield Savings / Money Market | **YES** | Insured liquid reserve savings | `$0.00` |
| Settled Short-Term US T-Bills (`<= 3 mo`) | **YES** | TreasuryDirect / `SGOV` settled value | `$0.00` |
| Pending Bug Bounty Awards | **NO (Excluded)** | Unsettled Immunefi / Code4rena triage | `$0.00` *(Excluded)* |
| Anticipated Public-Good Grants | **NO (Excluded)** | Unpaid NLnet milestones | `$0.00` *(Excluded)* |
| Speculative / Illiquid / Retirement Assets | **NO (Excluded)** | Crypto tokens, options, locked 401(k), home equity | `$0.00` *(Excluded)* |

---

## 2. Outstanding Debts & Monthly Debt-Service Obligations ($O_{\text{debt service}}$)

Record every contractual monthly minimum or fixed payment required to remain in good standing:

| Obligation | Principal Balance (Reference) | Required Monthly Payment |
| :--- | :--- | :--- |
| Mortgage / Rent Contractual Lease | `$0.00` | `$0.00` |
| Auto / Student / Personal Loans | `$0.00` | `$0.00` |
| Credit Card Minimum / Statement Payoff | `$0.00` | `$0.00` |
| Tax Installment / Estimated Reserve Obligation | `$0.00` | `$0.00` |

---

## 3. Monthly Household Living Expenses ($O_{\text{household living}}$)

Use a conservative trailing 3-month average (excluding debt payments already counted in Section 2):

| Living Expense Category | Monthly Baseline |
| :--- | :--- |
| Housing (Rent/Property Tax/HOA/Insurance if not in Section 2) | `$0.00` |
| Utilities (Electric, Heating, Water, Trash, Mobile/ISP) | `$0.00` |
| Groceries & Household Essentials | `$0.00` |
| Healthcare, Insurance Premiums & Wellness | `$0.00` |
| Transportation, Fuel & Maintenance | `$0.00` |
| Dependents / Loved Ones / Essential Buffer | `$0.00` |

---

## 4. Committed QuantumFlex Monthly Operating Expenses ($O_{\text{operating}}$)

Verify the sovereign non-corporate operating-cost baseline (`PA-LLC = RETIRED`, `$0.00` cloud LLM spend):

| Operating Line Item | Expected Sovereign Baseline | Monthly Committed Cost |
| :--- | :--- | :--- |
| External Paid Cloud LLM Inference APIs | **Must equal `$0.00`** (`127.0.0.1:11434` only) | `$0.00` |
| Corporate LLC Franchise / Registered Agent Overhead | `$0.00` (`PA-LLC` retired in `QF-SOVEREIGN` mode) | `$0.00` |
| Local Compute Electricity (`qfx-yoga` + `g6pro`, ~65W–95W) | `~$7.50 – $12.00 / mo` @ `$0.16/kWh` | `$0.00` |
| Dedicated Network / Domain / Hardware Replacement Sinking Fund | Committed monthly allocation | `$0.00` |

---

## 5. Six-Month Reserve Calculation

1. **Combined Monthly Obligations ($O$):**
   $$O = O_{\text{household living}} + O_{\text{debt service}} + O_{\text{operating}}$$
2. **Required 6-Month Liquid Reserve Floor ($6O$):**
   $$R_{\text{required}} = 6 \times O$$
3. **Verified Coverage Ratio (Dimensionless Months):**
   $$\text{Coverage Months} = \frac{R_{\text{verified liquid}}}{O}$$
4. **Gate Condition:**
   - `Coverage Months >= 6.0` $\implies$ `TRACK_0 = CLOSED` (eligible for `QF-A5` human signing ceremony).
   - `Coverage Months < 6.0` $\implies$ `TRACK_0 = OPEN` (protect & rebuild Bucket 1 reserves; freeze discretionary capex; `ADMISSION_SIGNED = FALSE`).

---

## 6. Offline Private JSON Schema & Verification Procedure

1. Create the private directory and `0600` file **outside** the Git repository:
   ```bash
   mkdir -p ~/.config/quantumflex/private
   chmod 700 ~/.config/quantumflex/private
   umask 077
   cat <<'EOF' > ~/.config/quantumflex/private/track0_worksheet.json
   {
     "schema": "qf.track0_worksheet.v1",
     "reconciled_at_utc": "2026-10-30T22:30:00Z",
     "operator_attestation": {
       "operator_id": "rahshaun_chambers",
       "operator_attested": true,
       "statements_verified_against_primary_institutions": true,
       "pending_awards_and_speculative_assets_excluded": true
     },
     "verified_liquid_accounts_usd": {
       "checking_fdic": 0.0,
       "savings_or_money_market_fdic": 0.0,
       "settled_short_term_tbills": 0.0
     },
     "excluded_non_reserve_items_usd": {
       "pending_bounties": 0.0,
       "anticipated_grants": 0.0,
       "speculative_or_illiquid_assets": 0.0
     },
     "outstanding_debts": [
       {
         "name": "primary_housing_or_loan",
         "principal_balance_usd": 0.0,
         "monthly_payment_usd": 0.0
       }
     ],
     "monthly_household_living_expenses_usd": {
       "housing_non_debt": 0.0,
       "utilities_and_connectivity": 0.0,
       "groceries_and_essentials": 0.0,
       "healthcare_and_insurance": 0.0,
       "transportation": 0.0,
       "family_and_contingency": 0.0
     },
     "committed_quantumflex_operating_expenses_usd": {
       "external_cloud_llm_spend": 0.0,
       "corporate_llc_overhead": 0.0,
       "local_compute_electricity": 10.0,
       "network_and_hardware_reserve": 15.0
     }
   }
   EOF
   chmod 600 ~/.config/quantumflex/private/track0_worksheet.json
   ```

2. Run the independent local reconciler (emits ratio-only evidence, zero dollar amounts):
   ```bash
   .venv/bin/python scripts/reconcile_track0_reserves.py \
     --input ~/.config/quantumflex/private/track0_worksheet.json \
     --output build_check/track0_reconciliation_receipt.json
   ```

3. Verify `QF-A5` ceremony preflight readiness **without** premature signing:
   ```bash
   .venv/bin/python scripts/prepare_qf_a5_ceremony.py --preflight
   ```
