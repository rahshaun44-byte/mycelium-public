#!/usr/bin/env bash
# ==============================================================================
# QuantumFlex Reproducible Audit Bundle Generator
# ==============================================================================
# Executes all deterministic validation harnesses, checks process and network
# permissions, evaluates adversarial failure modes, and emits an independent
# audit verification report.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
AUDIT_REPORT="$BASE_DIR/AUDIT_BUNDLE_REPORT.txt"

echo "═══════════════════════════════════════════════════════════════════"
echo "         QUANTUMFLEX REPRODUCIBLE AUDIT HARNESS RUNNER             "
echo "═══════════════════════════════════════════════════════════════════"
echo "Execution Timestamp: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "Host Kernel: $(uname -r) | Arch: $(uname -m)"

cat << REPORT_HEADER > "$AUDIT_REPORT"
================================================================================
QUANTUMFLEX INDEPENDENT AUDIT BUNDLE REPORT
Generated: $(date -u '+%Y-%m-%dT%H:%M:%SZ')
Kernel: $(uname -r) | User: $(id -un) (UID: $(id -u))
================================================================================

REPORT_HEADER

# 1. Deployed Permissions & Process Auditor
echo -e "\n[*] Step 1: Auditing Deployed Permissions, Sockets & Roles..."
bash "$SCRIPT_DIR/audit_deployed_permissions.sh" | tee -a "$AUDIT_REPORT"

# 2. C++ Invariant Binaries
echo -e "\n[*] Step 2: Executing C++ Cryptographic & Wire Invariant Binaries..."
{
    echo -e "\n--- C++ INVARIANT BINARIES ---"
    "$BASE_DIR/build_check/test_mlkem768"
    "$BASE_DIR/build_check/test_hybrid_kem"
    "$BASE_DIR/build_check/test_wire_fuzz_negative"
    "$BASE_DIR/build_check/test_zeroization"
} | tee -a "$AUDIT_REPORT"

# 3. OPA Rego Policy Verification
echo -e "\n[*] Step 3: Executing Open Policy Agent (OPA) Formal Tests..."
{
    echo -e "\n--- OPA REGO TESTS ---"
    opa test "$BASE_DIR/pqc-immune-daemon"
    opa test "$BASE_DIR/sentinel/policies"
} | tee -a "$AUDIT_REPORT"

# 4. Adversarial Failure-Mode & Containment Tests
echo -e "\n[*] Step 4: Executing Adversarial Failure-Mode & Containment Suite..."
{
    echo -e "\n--- ADVERSARIAL STRESS & FAILURE-MODE TESTS ---"
    PYTHONPATH="$BASE_DIR" "$BASE_DIR/venv/bin/pytest" \
        "$BASE_DIR/tests/test_adversarial_failure_modes.py" \
        "$BASE_DIR/tests/test_strict_pqc.py" \
        "$BASE_DIR/tests/test_ghost_node_tmpfs.py" \
        -v --tb=short
} | tee -a "$AUDIT_REPORT"

# 5. Checksum Manifest of Critical Artifacts
echo -e "\n[*] Step 5: Generating SHA-256 Checksum Manifest..."
{
    echo -e "\n--- CRYPTOGRAPHIC ARTIFACT CHECKSUMS ---"
    sha256sum "$BASE_DIR/build_check/quantum_flex_engine"
    sha256sum "$BASE_DIR/sentinel/policies/membrane_health.wasm"
    sha256sum "$BASE_DIR/sentinel/policies/reserve_invariant.wasm"
    sha256sum "$BASE_DIR/docs/SECURITY_TARGET_AND_PROMISES.md"
    sha256sum "$BASE_DIR/docs/COMPLIANCE_CONTROL_TRACEABILITY.md"
} | tee -a "$AUDIT_REPORT"

echo -e "\n═══════════════════════════════════════════════════════════════════"
echo "  AUDIT BUNDLE COMPLETE. Report saved to:"
echo "  $AUDIT_REPORT"
echo "═══════════════════════════════════════════════════════════════════"
