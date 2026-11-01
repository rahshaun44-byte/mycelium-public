# Contributing to Mycelium & pqc-immune-daemon

Thank you for your interest in contributing to **Mycelium** and **pqc-immune-daemon**. This project is dedicated to building sovereign, formally verified post-quantum security membranes, descriptor-bound execution loaders, and declarative policy engines for the open-source commons, supported by the **NLnet Foundation / NGI Zero Restack Fund** (Grant Application `2026-11-4af`).

We welcome contributions from cryptographers, Linux systems programmers, formal verification researchers, and open-source advocates.

---

## 1. Core Operating Principles

All contributions must adhere to our non-negotiable core invariants:

1. **Zero Cloud Spend Invariant ($0.00)**:
   - All tests, builds, local inference, and formal proofs must execute on local developer hardware without requiring paid third-party cloud APIs, external LLM endpoints, or proprietary software.
2. **Fail-Closed Default**:
   - In any security, cryptographic, or state admission evaluation, default strictly to failure (`REJECT` / `0x7F` / quarantine) if invariants or conditions cannot be mathematically proven.
3. **Zero Cryptographic Theater**:
   - Never claim FIPS certifications, end-to-end post-quantum wire security, or audit seals without independently validated evidence. Distinguish clearly between production-grade implementations and experimental/research prototypes.
4. **Strict Secret Hygiene**:
   - Never commit private keys, `.pem` files, seed phrases, API credentials, or internal environment configurations. Files containing secrets must retain `0600` permissions and remain in `.gitignore`.

---

## 2. Development Setup

### Prerequisites

- **Linux** (Kernel $\ge 5.15$ recommended for `memfd_create` and `fexecve` support)
- **Python 3.12+** (tested on 3.12, 3.13, and 3.14)
- **Open Policy Agent (OPA)** (`v1.0.0` or higher) for Rego policy evaluation
- **GCC / Clang** (C11 and C++20 compliant)
- **OpenSSL 3.5+** (for native ML-KEM-768 support if compiling C++ runtime)

### Installation

```bash
# Clone the repository
git clone https://github.com/rahshaun44-byte/mycelium.git
cd mycelium

# Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install testing and development dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 3. Verification & Testing Standards

Every proposed modification must pass the full test and verification suite locally before submission:

### A. Python Regression Suite (550+ Tests)
```bash
pytest -q
```
*Requirement: 100% pass rate, 0 failures.*

### B. Open Policy Agent (OPA) Policy Verification
```bash
# Verify supervisor and membrane health policies
opa test pqc-immune-daemon/ -v

# Verify kernel gatekeeper, bootgate, and reserve invariant policies
opa test sentinel/policies/ -v
```
*Requirement: All policy tests pass with zero assertion errors.*

### C. Post-Quantum Cryptographic Bill of Materials (CBOM) Audit
```bash
python3 tools/qf_audit.py .
```
*Requirement: Must emit `[COMPLIANT // QUANTUM-AGILE]` without unhandled toxic algorithm regressions.*

---

## 4. Pull Request Workflow

1. **Fork and Branch**:
   - Create a feature branch from `main`: `git checkout -b feat/your-feature-name` or `fix/issue-description`.
2. **Atomic, Descriptive Commits**:
   - Use conventional commit messages:
     - `feat(daemon): add descriptor write-sealing test harness`
     - `fix(policy): resolve OPA membrane evaluation edge case`
     - `docs(readme): clarify NLnet milestone deliverables`
     - `test(cli): expand candidate host priority matrix`
3. **Documentation & Tests**:
   - New functionality must include corresponding unit tests and docstrings.
   - Do not remove or alter existing defensive guards or docstrings unrelated to your change.
4. **Submit PR**:
   - Open a pull request against the `main` branch of `rahshaun44-byte/mycelium`.
   - Provide a clear summary of your changes, the rationale, and the test commands executed.

---

## 5. Security Vulnerabilities

Please **do not report security vulnerabilities via public GitHub issues**. Follow the coordinated disclosure procedure in [SECURITY.md](SECURITY.md) or submit a private security report via [GitHub Security Advisories](https://github.com/rahshaun44-byte/mycelium/security/advisories/new).
