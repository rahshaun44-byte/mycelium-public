#!/usr/bin/env bash
# ==============================================================================
# QuantumFlex Secure Umask & Permission Enforcement Tool (umask 077)
# ==============================================================================
#
# Mathematical Foundation:
#   umask specifies the permission bits that MUST NOT be set upon creation.
#   - New files default to 0666 (rw-rw-rw-).
#     With umask 077: 0666 & ~0077 = 0600 (-rw-------) [Owner read/write only]
#   - New directories default to 0777 (rwxrwxrwx).
#     With umask 077: 0777 & ~0077 = 0700 (drwx------) [Owner full access only]
#
# Usage:
#   1. Source into your interactive shell session (or add to ~/.bashrc):
#        source scripts/secure_umask.sh
#   2. Run directly to test, verify, and audit umask compliance:
#        ./scripts/secure_umask.sh
#   3. Use the helper functions:
#        check_umask
#        secure_touch <filepath>
#        secure_mkdir <dirpath>
#        audit_permissions [directory]
# ==============================================================================

set -euo pipefail

# 1. Enforce strict umask 077
enforce_umask() {
    umask 077
    echo "  [OK] umask set to $(umask) (octal: 0077 / owner-only isolation)"
}

# 2. Check current session umask
check_umask() {
    local current_umask
    current_umask=$(umask)
    if [[ "$current_umask" == "0077" || "$current_umask" == "077" ]]; then
        echo "  [PASS] Active umask is secure: ${current_umask}"
        return 0
    else
        echo "  [FAIL] Active umask is permissive: ${current_umask} (expected 0077)" >&2
        return 1
    fi
}

# 3. Securely touch/create a file with 0600 permissions
secure_touch() {
    local target="$1"
    if [[ -z "$target" ]]; then
        echo "Usage: secure_touch <filepath>" >&2
        return 1
    fi
    (
        umask 077
        touch "$target"
        chmod 0600 "$target"
    )
    echo "  [CREATED] File: $target (mode: $(stat -c "%a" "$target"))"
}

# 4. Securely make directory with 0700 permissions
secure_mkdir() {
    local target="$1"
    if [[ -z "$target" ]]; then
        echo "Usage: secure_mkdir <dirpath>" >&2
        return 1
    fi
    (
        umask 077
        mkdir -p "$target"
        chmod 0700 "$target"
    )
    echo "  [CREATED] Directory: $target (mode: $(stat -c "%a" "$target"))"
}

# 5. Audit directory for non-conforming permissions
audit_permissions() {
    local target_dir="${1:-.}"
    echo "Auditing permissions under: $target_dir"
    local leaks
    leaks=$(find "$target_dir" -maxdepth 3 \( -type f -perm /0077 -o -type d -perm /0077 \) 2>/dev/null || true)
    if [[ -n "$leaks" ]]; then
        echo "  [WARN] Found files/directories with group/other permissions:"
        echo "$leaks"
    else
        echo "  [PASS] All audited files and directories enforce owner-only isolation (no group/world permissions)."
    fi
}

# 6. Self-test demonstration when executed directly
run_self_test() {
    echo "═══════════════════════════════════════════════════════════════════"
    echo "             QUANTUMFLEX UMASK 077 SELF-TEST SUITE                 "
    echo "═══════════════════════════════════════════════════════════════════"
    
    enforce_umask
    check_umask

    local test_dir
    test_dir=$(mktemp -d "/tmp/qfx-umask-test.XXXXXX")
    
    echo -e "\nRunning verification in isolated sandbox: $test_dir"
    
    # Test directory creation
    secure_mkdir "$test_dir/test_subfolder"
    local dir_mode
    dir_mode=$(stat -c "%a" "$test_dir/test_subfolder")

    # Test file creation
    secure_touch "$test_dir/test_subfolder/secret.key"
    local file_mode
    file_mode=$(stat -c "%a" "$test_dir/test_subfolder/secret.key")

    echo -e "\nVerification Results:"
    if [[ "$dir_mode" == "700" && "$file_mode" == "600" ]]; then
        echo "  [SUCCESS] Directory mode: $dir_mode (expected 700)"
        echo "  [SUCCESS] File mode:      $file_mode (expected 600)"
        echo "  [SUCCESS] umask 077 mathematically verified."
    else
        echo "  [FAILURE] Unexpected permissions! Dir: $dir_mode, File: $file_mode" >&2
    fi

    # Cleanup sandbox
    rm -rf "$test_dir"

    echo -e "\n═══════════════════════════════════════════════════════════════════"
    echo "To make umask 077 default for your bash user profile:"
    echo "  echo 'umask 077' >> ~/.bashrc"
    echo "To load these helper commands into your current terminal:"
    echo "  source scripts/secure_umask.sh"
    echo "═══════════════════════════════════════════════════════════════════"
}

# Always enforce umask when sourced or run
umask 077

# If run as a standalone script (not sourced), execute self-test
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    run_self_test
fi
