# Independent Hardware Run Validation: `db8nsvob3g5c73egl760` (`ibm_kingston`)

## 1. Executive Summary & Epistemic Boundaries

This document certifies the independent statistical verification and raw data validation of physical quantum computing execution **`db8nsvob3g5c73egl760`**, performed on the IBM Quantum **`ibm_kingston`** processor (156 Physical Transmon Qubits, Heron r2 Architecture).

- **Execution Mode**: Physical Cryogenic Hardware Execution (`mode=ibm_kingston`).
- **Workload**: 6-circuit batched PUB execution (1 QAOA 3-qubit portfolio optimization circuit + 5 complete GHZ multi-basis witness circuits).
- **Total Acquisition**: 256 shots per circuit $\times$ 6 circuits = **1,536 physical shots** (QPU charge time: 3.0s, circuit execution time: 401.44 ms).
- **Cryptographic Provenance Location**: `/home/quant/qf-research/ibm-qaoa-ghz-kingston-20261016T013409Z/`
- **Zero-Trust Posture**: The QuantumFlex native daemon (`build_c`) remained **`LOCKED`** throughout execution and post-processing on `127.0.0.1:9444`.
- **Entropy Credit**: Exactly **`0.0 bits`**. Per NIST SP 800-90B, physical quantum hardware results are treated strictly as external experimental physics datasets and are never credited as secret cryptographic entropy.

---

## 2. Cryptographic Provenance & Manifest Integrity

All files on disk were independently verified using direct byte-level SHA-256 digests matching `checksums.sha256`:

| File | Exact SHA-256 Digest | Status |
| :--- | :--- | :--- |
| `raw_acquisition.json` | `be8024f4ae88f692f6de413389a0b5d53d67782d890500929e2c5cc8ba12b1d8` | **VERIFIED MATCH** |
| `analysis_record.json` | `2c2f12fc0f23e13a7863a2cea60a5be76b27179b865295d039fdd4b1984f60a0` | **VERIFIED MATCH** |
| Internal Reference | `source_raw_acquisition.sha256` in `analysis_record.json` matches `raw_acquisition.json` | **VERIFIED MATCH** |

Permissions on all archive files are locked to `0600`.

---

## 3. QAOA Portfolio Optimization Results & Distribution Comparison

### Problem Formulation
- **Objective Function**: $C(x) = -\mu^\mathsf{T} x + \lambda x^\mathsf{T} \Sigma x + A \left(\sum_i x_i - B\right)^2$
  - Assets: Asset 0 (Tech Growth, $\mu_0=0.15, \sigma_0^2=0.08$), Asset 1 (Dividend Energy, $\mu_1=0.10, \sigma_1^2=0.06$), Asset 2 (Treasury Bond, $\mu_2=0.05, \sigma_2^2=0.01$).
  - Covariance: $\Sigma_{01}=0.02, \Sigma_{02}=-0.01, \Sigma_{12}=0.00$.
  - Budget: $B = 2$ assets; Penalty parameter: $A = 1.0$; Risk tolerance: $\lambda = 0.5$.
- **Ground Truth**: The unique global minimum is $x = (1, 0, 1)$ (`101` in Qiskit little-endian `|q2 q1 q0>`), selecting **Tech Growth + Treasury Bond** with optimal cost:
  $$C(1, 0, 1) = -0.15 - 0.05 + 0.5(0.08 + 0.01 - 0.02) + 1.0(2 - 2)^2 = \mathbf{-0.165000}$$

### Comparative Distribution Benchmark
Measured over 256 physical shots on `ibm_kingston`, compared against local ideal statevector simulation ($\gamma = \pi/8, \beta = \pi/4$) and the uniform random classical baseline ($P(s) = 1/8$):

| State $|q_2 q_1 q_0\rangle$ | Portfolio $x=(x_0, x_1, x_2)$ | Classical Cost $C(x)$ | Feasible? | Hardware QPU (256 shots) | Ideal Statevector Sim | Uniform Classical Baseline |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `|000>` | $(0, 0, 0)$ | $+4.0000$ | NO | **118** (46.09%) | 36.35% | 12.50% |
| `|001>` | $(1, 0, 0)$ | $+0.8900$ | NO | **28** (10.94%) | 12.36% | 12.50% |
| `|010>` | $(0, 1, 0)$ | $+0.9300$ | NO | **25** (9.77%) | 12.84% | 12.50% |
| `|011>` | $(1, 1, 0)$ | $-0.1600$ | **YES** | **8** (3.12%) | 5.57% | 12.50% |
| `|100>` | $(0, 0, 1)$ | $+0.9550$ | NO | **35** (13.67%) | 12.89% | 12.50% |
| `|101>` | $(1, 0, 1)$ | **$-0.1650$** | **YES (OPTIMAL)** | **11** (4.30%) | 5.63% | 12.50% |
| `|110>` | $(0, 1, 1)$ | $-0.1150$ | **YES** | **11** (4.30%) | 5.86% | 12.50% |
| `|111>` | $(1, 1, 1)$ | $+0.7850$ | NO | **20** (7.81%) | 8.51% | 12.50% |

### Statistical Metrics & Distance Measures
- **Feasible Subspace Probability ($B=2$)**:
  - Hardware QPU: **11.72%** (30 / 256 shots)
  - Ideal Simulation: **17.06%**
  - Uniform Baseline: **37.50%**
- **Optimal Feasible State Detection**: The globally optimal portfolio `|101>` was observed **11 times** on physical silicon.
- **Mean Conditional Feasible Cost**:
  - Hardware QPU: **$-0.145333$**
  - Ideal Simulation: **$-0.146199$**
  - Uniform Baseline: **$-0.146667$**
  - Ground Truth Minimum: **$-0.165000$**
- **Total Distribution Mean Objective**:
  - Hardware QPU: **$+2.206777$** (heavily dominated by `|000>` penalty)
  - Ideal Simulation: **$+1.848191$**
  - Uniform Baseline: **$+0.890000$**
- **Total Variation Distance (TVD)**:
  - $\mathrm{TVD}(\text{Hardware}, \text{Ideal Sim}) = \mathbf{0.1053}$
  - $\mathrm{TVD}(\text{Hardware}, \text{Uniform Baseline}) = \mathbf{0.3477}$
  - $\mathrm{TVD}(\text{Ideal Sim}, \text{Uniform Baseline}) = \mathbf{0.2457}$

**Finding**: The hardware distribution aligns closely with the ideal quantum unitary statevector ($\mathrm{TVD} = 0.1053$, consistent with $\sqrt{1/N} \approx 0.0625$ finite-sample shot noise and SPAM errors), while diverging substantially from uniform classical noise ($\mathrm{TVD} = 0.3477$).

---

## 4. Complete GHZ Witness & Statistical Uncertainty Framework

### Theoretical Operator & Observable Expansion
For a 3-qubit GHZ state $|\mathrm{GHZ}_3\rangle = \frac{1}{\sqrt{2}}(|000\rangle + |111\rangle)$, the state fidelity $\mathcal{F} = \langle\mathrm{GHZ}_3|\rho|\mathrm{GHZ}_3\rangle$ is evaluated via 5 physical measurement settings:
$$\mathcal{F} = \frac{1}{8}\left[ 1 + \langle Z_0 Z_1 \rangle + \langle Z_1 Z_2 \rangle + \langle Z_0 Z_2 \rangle + \langle X_0 X_1 X_2 \rangle - \langle X_0 Y_1 Y_2 \rangle - \langle Y_0 X_1 Y_2 \rangle - \langle Y_0 Y_1 X_2 \rangle \right]$$

The witness operator for genuine tripartite entanglement is:
$$\mathcal{W} = \frac{1}{2}I - |\mathrm{GHZ}_3\rangle\langle\mathrm{GHZ}_3| \implies \langle \mathcal{W} \rangle = \frac{1}{2} - \mathcal{F}$$
For all biseparable states, $\mathcal{F} \le \frac{1}{2}$, so $\langle \mathcal{W} \rangle \ge 0$. Genuine tripartite entanglement is certified **if and only if** $\langle \mathcal{W} \rangle < 0$ at the specified confidence level (i.e., its upper confidence bound must be strictly negative).

### Physical Hardware Observations across 5 Settings
Each setting acquired $N = 256$ physical shots:
1. **Setting 1 (ZZZ)**:
   - Target basis population ($|000\rangle + |111\rangle$): **72.27%** (185 / 256 shots)
   - Other basis population: **27.73%** (71 / 256 shots)
   - Correlators: $\langle Z_0 Z_1 \rangle = +0.5312$, $\langle Z_1 Z_2 \rangle = +0.8438$, $\langle Z_0 Z_2 \rangle = +0.5156$
   - Joint observable $U = Z_0 Z_1 + Z_1 Z_2 + Z_0 Z_2$:
     $$\bar{U} = +1.890625, \quad \mathrm{Var}_N(\bar{U}) = 0.01252651, \quad \mathrm{Var}_{N-1}(\bar{U}) = 0.01257564$$
2. **Setting 2 (XXX)**: $\langle X_0 X_1 X_2 \rangle = \mathbf{+0.421875}$
3. **Setting 3 (XYY)**: $\langle X_0 Y_1 Y_2 \rangle = \mathbf{-0.375000}$
4. **Setting 4 (YXY)**: $\langle Y_0 X_1 Y_2 \rangle = \mathbf{-0.1953125}$
5. **Setting 5 (YYX)**: $\langle Y_0 Y_1 X_2 \rangle = \mathbf{-0.1796875}$

### Derived Expectation Values
- **GHZ State Fidelity**:
  $$\mathcal{F} = \frac{1 + 1.890625 + 0.421875 - (-0.375000) - (-0.1953125) - (-0.1796875)}{8} = \mathbf{0.5078125} \approx 0.5078$$
- **Witness Expectation**:
  $$\langle \mathcal{W} \rangle = 0.5 - 0.5078125 = \mathbf{-0.0078125} \approx -0.0078$$

### Multi-Method Statistical Uncertainty & Confidence Bound Comparison

| Method | Variance Estimator | Standard Error $\sigma_{\mathcal{W}}$ | 95% Confidence Upper Bound on $\langle \mathcal{W} \rangle$ | Threshold for Entanglement | Scientific Conclusion |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Normal Approx (2-Sided 95%, $z=1.96$)** | $N$ (Sample) | $0.020399$ | $\mathbf{+0.032169}$ | $< 0$ | **NOT CERTIFIED** |
| **Normal Approx (1-Sided 95%, $z=1.645$)** | $N$ (Sample) | $0.020399$ | $\mathbf{+0.025741}$ | $< 0$ | **NOT CERTIFIED** |
| **Bessel Corrected (2-Sided 95%, $z=1.96$)** | $N - 1$ (Unbiased) | $0.020439$ | $\mathbf{+0.032247}$ | $< 0$ | **NOT CERTIFIED** |
| **Bessel Corrected (1-Sided 95%, $z=1.645$)** | $N - 1$ (Unbiased) | $0.020439$ | $\mathbf{+0.025807}$ | $< 0$ | **NOT CERTIFIED** |
| **Empirical Bootstrap (100k Resamples, P97.5)** | Resampled empirical | $0.020385$ | $\mathbf{+0.032227}$ | $< 0$ | **NOT CERTIFIED** |
| **Empirical Bootstrap (100k Resamples, P95)** | Resampled empirical | $0.020385$ | $\mathbf{+0.026367}$ | $< 0$ | **NOT CERTIFIED** |
| **Hoeffding Finite-Sample Bound** | Distribution-free | $\delta = 0.054088$ | $\mathbf{+0.046276}$ | $< 0$ | **NOT CERTIFIED** |

### Empirical Bootstrap Details (100,000 Resamples, Seed 42)
- Mean resampled fidelity: $\bar{\mathcal{F}}^* = 0.507744$
- Standard deviation of resampled fidelity: $\sigma_{\mathcal{F}}^* = 0.020385$ (agrees with analytical $0.020399$ to within 0.07%)
- **Fraction of bootstrap samples with $\mathcal{W} < 0$**: **64.02%**
  - **35.98% of bootstrap resamples remain in the classical/biseparable domain ($\mathcal{W} \ge 0$)**.
  - A valid 95% confidence certification requires $\ge 95.00\%$ of resamples in the entangled domain.

---

## 5. Formal Scientific Verdict

$$\boxed{\textbf{entanglement\_certified : FALSE}}$$

**Scientific Reason**: Although the point estimate of state fidelity slightly exceeds the classical threshold ($\mathcal{F} = 0.5078 > 0.5000$), the statistical uncertainty across all 256-shot measurement settings yields a 95% upper confidence bound strictly greater than zero ($\mathcal{W}_{\text{upper}} = +0.0322 \ge 0$). Approximately 36% of the posterior/bootstrap probability mass resides in the separable/biseparable domain. Genuine tripartite entanglement cannot be asserted at standard scientific confidence intervals.

---

## 6. Verification Tooling & Reproducibility

The entire verification pipeline is encapsulated in a standalone script:
```bash
/home/quant/.venv/bin/python3 /home/quant/mycelium/tools/verify_hardware_run_db8nsvob.py
```
This script reads exclusively from `raw_acquisition.json`, recomputes all mathematical steps, checks SHA-256 hashes against `checksums.sha256`, and validates all criteria without connecting to IBM Quantum or modifying any files.
