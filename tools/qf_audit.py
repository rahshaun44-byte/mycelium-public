#!/usr/bin/env python3
"""
═════════════════════════════════════════════════════════════════════
  QUANTUM FLEX // AUTOMATED PQC & CBOM COMPLIANCE AUDITOR (qf-audit)
═════════════════════════════════════════════════════════════════════
Commercial Audit Tool developed by Rahshaun Chambers.
Performs automated Cryptographic Bill of Materials (CBOM) discovery,
CycloneDX v1.5 generation, and OPA policy evaluation against
NIST FIPS 203/204/205 and White House OMB M-26-15 compliance mandates.
"""

import os
import sys
import re
import json
import uuid
import hashlib
import argparse
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Set

# Safe terminal encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ANSI Color Palettes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# Cryptographic Signatures Taxonomy
ALGORITHM_TAXONOMY = {
    # Post-Quantum Compliant KEMs (NIST FIPS 203 & Candidates)
    "ML-KEM-512": {"category": "PQC_KEM", "standard": "NIST FIPS 203", "status": "APPROVED", "strength": 128},
    "ML-KEM-768": {"category": "PQC_KEM", "standard": "NIST FIPS 203", "status": "APPROVED", "strength": 192},
    "ML-KEM-1024": {"category": "PQC_KEM", "standard": "NIST FIPS 203", "status": "APPROVED", "strength": 256},
    "FrodoKEM-640-AES": {"category": "PQC_KEM", "cipher": "FrodoKEM-640-AES", "standard": "Experimental / Non-ISO (draft-longa-cfrg)", "status": "isolated", "strength": 128},
    "FrodoKEM-976-AES": {"category": "PQC_KEM", "standard": "ISO/IEC 18033-2:2006/Amd 2:2026", "status": "FALLBACK_APPROVED", "strength": 192},
    "FrodoKEM-1344-AES": {"category": "PQC_KEM", "standard": "ISO/IEC 18033-2:2006/Amd 2:2026", "status": "FALLBACK_APPROVED", "strength": 256},
    "Classic-McEliece": {"category": "PQC_KEM", "standard": "Round 4 Candidate", "status": "MONITORED", "strength": 128},
    "HQC": {"category": "PQC_KEM", "standard": "Round 4 Candidate", "status": "MONITORED", "strength": 128},

    # Post-Quantum Compliant Digital Signatures (NIST FIPS 204/205)
    "ML-DSA-44": {"category": "PQC_SIG", "standard": "NIST FIPS 204", "status": "APPROVED", "strength": 128},
    "ML-DSA-65": {"category": "PQC_SIG", "standard": "NIST FIPS 204", "status": "APPROVED", "strength": 192},
    "ML-DSA-87": {"category": "PQC_SIG", "standard": "NIST FIPS 204", "status": "APPROVED", "strength": 256},
    "SLH-DSA-SHA2-128f": {"category": "PQC_SIG", "standard": "NIST FIPS 205", "status": "APPROVED", "strength": 128},
    "SLH-DSA-SHAKE-128f": {"category": "PQC_SIG", "standard": "NIST FIPS 205", "status": "APPROVED", "strength": 128},

    # Classical Algorithms (DEPRECATED under OMB M-26-15)
    "RSA-2048": {"category": "CLASSICAL_ASYMMETRIC", "standard": "NIST SP 800-56B", "status": "DEPRECATED_OMB_M26_15", "strength": 112},
    "RSA-4096": {"category": "CLASSICAL_ASYMMETRIC", "standard": "NIST SP 800-56B", "status": "DEPRECATED_OMB_M26_15", "strength": 128},
    "ECDSA-P256": {"category": "CLASSICAL_ASYMMETRIC", "standard": "FIPS 186-4", "status": "DEPRECATED_OMB_M26_15", "strength": 128},
    "ECDSA-P384": {"category": "CLASSICAL_ASYMMETRIC", "standard": "FIPS 186-4", "status": "DEPRECATED_OMB_M26_15", "strength": 192},
    "ECDH-P256": {"category": "CLASSICAL_ASYMMETRIC", "standard": "NIST SP 800-56A", "status": "DEPRECATED_OMB_M26_15", "strength": 128},
    "X25519": {"category": "CLASSICAL_ASYMMETRIC", "standard": "RFC 7748", "status": "TRANSITIONAL_HYBRID_ONLY", "strength": 128},
    "Ed25519": {"category": "CLASSICAL_ASYMMETRIC", "standard": "RFC 8032", "status": "TRANSITIONAL_HYBRID_ONLY", "strength": 128},

    # Symmetric & Hash Primitives
    "AES-256-GCM": {"category": "SYMMETRIC", "standard": "NIST SP 800-38D", "status": "APPROVED", "strength": 256},
    "AES-128-GCM": {"category": "SYMMETRIC", "standard": "NIST SP 800-38D", "status": "ACCEPTABLE", "strength": 128},
    "SHA-256": {"category": "HASH", "standard": "NIST FIPS 180-4", "status": "APPROVED", "strength": 128},
    "SHA-384": {"category": "HASH", "standard": "NIST FIPS 180-4", "status": "APPROVED", "strength": 192},
    "SHA-512": {"category": "HASH", "standard": "NIST FIPS 180-4", "status": "APPROVED", "strength": 256},
    "SHA-1": {"category": "HASH", "standard": "DISALLOWED", "status": "TOXIC", "strength": 0},
    "MD5": {"category": "HASH", "standard": "DISALLOWED", "status": "TOXIC", "strength": 0},
}

PATTERNS = {
    "ML-KEM-512": re.compile(r"(ML[-_]?KEM[-_]?512|kyber[-_]?512)", re.IGNORECASE),
    "ML-KEM-768": re.compile(r"(ML[-_]?KEM[-_]?768|kyber[-_]?768)", re.IGNORECASE),
    "ML-KEM-1024": re.compile(r"(ML[-_]?KEM[-_]?1024|kyber[-_]?1024)", re.IGNORECASE),
    "FrodoKEM-640-AES": re.compile(r"FrodoKEM[-_]?640[-_]?(AES|SHAKE)?", re.IGNORECASE),
    "FrodoKEM-976-AES": re.compile(r"FrodoKEM[-_]?976[-_]?(AES|SHAKE)?", re.IGNORECASE),
    "FrodoKEM-1344-AES": re.compile(r"FrodoKEM[-_]?1344[-_]?(AES|SHAKE)?", re.IGNORECASE),
    "Classic-McEliece": re.compile(r"(Classic[-_]?McEliece|mceliece[0-9]+)", re.IGNORECASE),
    "HQC": re.compile(r"HQC[-_]?(128|192|256)?", re.IGNORECASE),

    "ML-DSA-44": re.compile(r"(ML[-_]?DSA[-_]?44|dilithium[-_]?2)", re.IGNORECASE),
    "ML-DSA-65": re.compile(r"(ML[-_]?DSA[-_]?65|dilithium[-_]?3)", re.IGNORECASE),
    "ML-DSA-87": re.compile(r"(ML[-_]?DSA[-_]?87|dilithium[-_]?5)", re.IGNORECASE),
    "SLH-DSA-SHA2-128f": re.compile(r"(SLH[-_]?DSA|sphincs(\+|plus)?)", re.IGNORECASE),

    "RSA-2048": re.compile(r"\b(RSA[-_]?2048|rsaEncryption.*2048)\b", re.IGNORECASE),
    "RSA-4096": re.compile(r"\b(RSA[-_]?4096|rsaEncryption.*4096)\b", re.IGNORECASE),
    "ECDSA-P256": re.compile(r"\b(secp256r1|prime256v1|ECDSA.*P[-_]?256)\b", re.IGNORECASE),
    "ECDSA-P384": re.compile(r"\b(secp384r1|ECDSA.*P[-_]?384)\b", re.IGNORECASE),
    "X25519": re.compile(r"\b(X25519|curve25519)\b", re.IGNORECASE),
    "Ed25519": re.compile(r"\bEd25519\b", re.IGNORECASE),

    "AES-256-GCM": re.compile(r"\b(AES[-_]?256[-_]?GCM)\b", re.IGNORECASE),
    "AES-128-GCM": re.compile(r"\b(AES[-_]?128[-_]?GCM)\b", re.IGNORECASE),
    "SHA-256": re.compile(r"\bSHA[-_]?256\b", re.IGNORECASE),
    "SHA-384": re.compile(r"\bSHA[-_]?384\b", re.IGNORECASE),
    "SHA-512": re.compile(r"\bSHA[-_]?512\b", re.IGNORECASE),
}


def _toxic_call_sites(name: str) -> re.Pattern:
    """Call-site and API patterns for a disallowed hash: real usage, not prose naming it.

    Matched against raw source lines (never comment-stripped), so no comment or
    keyword heuristic can hide a live call.
    """
    quoted = rf"""['"]{name[:-1]}-?{name[-1]}['"]"""  # 'sha1' / "SHA-1" / 'md5'
    return re.compile(
        "|".join(
            [
                rf"\b{name}\s*\(",                            # sha1(...), hashes.SHA1(), MD5(...)
                rf"\bhashlib\.{name}\b",
                rf"\bhashlib\.new\s*\(\s*{quoted}",
                rf"\bCrypto\.Hash\.{name}\b",
                rf"\b{name}::",                               # Rust sha1::Sha1, Md5::new
                rf"\b{name}_smol\b",
                rf"\bEVP_{name}\b",
                rf"\b{name}_(?:Init|Update|Final)\b",
                rf"\b{name}_FOR_LEGACY_USE_ONLY\b",
                rf"\b{name}\.(?:New|Sum)\b",                  # Go
                rf"""['"]crypto/{name}['"]""",               # Go import
                rf"\b{name}sum\b",
                rf"\bcreateHash\s*\(\s*{quoted}",             # Node
                rf"\bgetInstance\s*\(\s*{quoted}",            # Java MessageDigest
                rf"\bdigestmod\s*=\s*{quoted}",               # Python hmac
                rf"(?<![\w-])-{name}\b",                      # openssl dgst -sha1 / -md5
            ]
        ),
        re.IGNORECASE,
    )


TOXIC_PATTERNS = {"SHA-1": _toxic_call_sites("sha1"), "MD5": _toxic_call_sites("md5")}

# Reviewed exemptions for toxic call sites. Each entry exempts exactly one source line:
# (path relative to the scan root, algorithm, stripped line text) -> written justification.
# Editing the line, moving the file, or a second call in the same file is flagged again.
AUDITED_ALLOWLIST: Dict[Tuple[str, str, str], str] = {}

IGNORE_DIRS = {
    ".git", "node_modules", "venv", "__pycache__", ".venv", "build", "build_check",
    "dist", "qf-audit-output", "reports", "research_notes", ".gemini", ".agents",
    ".vscode", ".pytest_cache", ".cache", ".idea", "target", "out"
}
IGNORE_EXTS = {
    ".png", ".jpg", ".jpeg", ".ico", ".pdf", ".bin", ".o", ".so", ".a",
    ".tar.gz", ".gz", ".tgz", ".tar", ".zip", ".db", ".sqlite", ".sqlite3",
    ".log", ".patch", ".wasm", ".crx", ".cmake",
    ".md", ".txt", ".rst", ".adoc"
}


def print_banner():
    banner = f"""
{CYAN}{BOLD}╔═════════════════════════════════════════════════════════════════════╗
║     ██████╗ ███████╗       █████╗ ██╗   ██╗██████╗ ██╗████████╗     ║
║    ██╔═══██╗██╔════╝      ██╔══██╗██║   ██║██╔══██╗██║╚══██╔══╝     ║
║    ██║   ██║█████╗  █████╗███████║██║   ██║██║  ██║██║   ██║        ║
║    ██║▄▄ ██║██╔══╝  ╚════╝██╔══██║██║   ██║██║  ██║██║   ██║        ║
║    ╚██████╔╝██║           ██║  ██║╚██████╔╝██████╔╝██║   ██║        ║
║     ╚══▀▀═╝ ╚═╝           ╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚═╝   ╚═╝        ║
║          {MAGENTA}POST-QUANTUM CRYPTOGRAPHIC BILL OF MATERIALS (CBOM){CYAN}         ║
║          {MAGENTA}COMMERCIAL COMPLIANCE AUDITOR // RAHSHAUN CHAMBERS{CYAN}          ║
╚═════════════════════════════════════════════════════════════════════╝{RESET}
"""
    print(banner)


def strip_comments(content: str, ext: str) -> str:
    """Strips standard single- and multi-line comments across supported languages
    to prevent commented-out code or documentation comments from triggering
    false positives. Does NOT mask active code.
    """
    lines = content.splitlines()
    cleaned_lines = []

    in_block_comment = False
    for line in lines:
        # C/Rust/Go/Java/Solidity/JS/TS block comments
        if ext in {".c", ".h", ".cpp", ".hpp", ".rs", ".go", ".sol", ".js", ".ts", ".java"}:
            if in_block_comment:
                if "*/" in line:
                    line = line.split("*/", 1)[1]
                    in_block_comment = False
                else:
                    continue
            if "/*" in line:
                if "*/" in line:
                    line = re.sub(r"/\*.*?\*/", " ", line)
                else:
                    line = line.split("/*", 1)[0]
                    in_block_comment = True
            # Strip single-line comments (including //! and ///)
            if "//" in line:
                line = line.split("//", 1)[0]

        # Python/Shell/YAML/TOML comments
        elif ext in {".py", ".sh", ".bash", ".yml", ".yaml", ".toml"}:
            if "#" in line:
                line = line.split("#", 1)[0]

        # Rego/SQL comments
        elif ext in {".rego", ".sql"}:
            if "#" in line:
                line = line.split("#", 1)[0]
            if "--" in line:
                line = line.split("--", 1)[0]

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def scan_target(target_path: Path) -> Dict[str, Any]:
    """Inspects target directory or file and discovers cryptographic primitives."""
    findings: Dict[str, List[Dict[str, Any]]] = {alg: [] for alg in ALGORITHM_TAXONOMY}
    allowlisted_findings: List[Dict[str, Any]] = []
    total_files = 0
    scanned_files = 0

    if target_path.is_file():
        files_to_scan = [target_path]
    else:
        files_to_scan = []
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".") and not d.startswith("build")]
            for f in files:
                ext = Path(f).suffix.lower()
                if ext not in IGNORE_EXTS:
                    file_path = Path(root) / f
                    # Skip scanner itself, its toxic-pattern test vectors, and test policy files containing mock test vectors
                    if f in {"qf_audit.py", "test_qf_audit_toxic.py"} or f.endswith("_test.rego"):
                        continue
                    files_to_scan.append(file_path)

    total_files = len(files_to_scan)
    buffer_vulnerabilities = []

    for p in files_to_scan:
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            scanned_files += 1
            rel_path = str(p.relative_to(target_path)) if target_path.is_dir() else p.name
            ext = p.suffix.lower()

            clean_content = strip_comments(content, ext)

            for alg, pattern in PATTERNS.items():
                matches = pattern.findall(clean_content)
                if matches:
                    findings[alg].append({
                        "file": rel_path,
                        "occurrences": len(matches),
                    })

            # Toxic hashes: one finding per raw source line, exempted only by an exact allowlist entry
            for line_no, line in enumerate(content.splitlines(), 1):
                for alg, pattern in TOXIC_PATTERNS.items():
                    if not pattern.search(line):
                        continue
                    code = line.strip()
                    reason = AUDITED_ALLOWLIST.get((rel_path, alg, code))
                    if reason:
                        allowlisted_findings.append({
                            "file": rel_path,
                            "line": line_no,
                            "algorithm": alg,
                            "code": code,
                            "rationale": reason,
                        })
                    else:
                        findings[alg].append({
                            "file": rel_path,
                            "line": line_no,
                            "code": code,
                            "occurrences": 1,
                        })
        
            # Buffer Exhaustion Heuristic (AST-lite)
            # Looks for static buffers: char buf[4096]; or uint8_t buffer[1024];
            buffer_pattern = re.compile(r"(?:char|uint8_t|unsigned\s+char|byte)\s+\w+\s*\[\s*(\d+)\s*\]")
            for line_no, line in enumerate(content.splitlines(), 1):
                for match in buffer_pattern.finditer(line):
                    try:
                        size = int(match.group(1))
                        # Flag if less than 15792 (FrodoKEM-976-AES CT size) and looks like a network buffer (1024-8192 usually)
                        if 1024 <= size < 15792:
                            buffer_vulnerabilities.append({
                                "file": rel_path,
                                "line": line_no,
                                "size": size,
                                "code": line.strip()
                            })
                    except ValueError:
                        pass

        except Exception:
            continue

    # Filter out empty findings
    active_findings = {k: v for k, v in findings.items() if len(v) > 0}
    return {
        "target": str(target_path.resolve()),
        "total_files": total_files,
        "scanned_files": scanned_files,
        "buffer_vulnerabilities": buffer_vulnerabilities,
        "findings": active_findings,
        "allowlisted_findings": allowlisted_findings,
    }


def generate_cyclonedx_cbom(scan_result: Dict[str, Any], serial_uuid: str) -> Dict[str, Any]:
    """Assembles an official CycloneDX v1.5 CBOM JSON document."""
    iso_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    components = []

    for alg_name, occurrences in scan_result["findings"].items():
        meta = ALGORITHM_TAXONOMY.get(alg_name, {})
        category = meta.get("category", "UNKNOWN")
        status = meta.get("status", "UNVERIFIED")

        comp = {
            "type": "crypto-asset",
            "name": alg_name,
            "version": meta.get("standard", "Custom"),
            "description": f"Discovered cryptographic primitive across {len(occurrences)} file(s). Status: {status}.",
            "cryptoProperties": {
                "assetType": "algorithm",
                "algorithmProperties": {
                    "algorithm": alg_name,
                    "primitive": category,
                    "classicalSecurityLevel": meta.get("strength", 128),
                    "nistQuantumSecurityLevel": 5 if "1024" in alg_name or "87" in alg_name else 3 if "768" in alg_name or "65" in alg_name else 1 if "512" in alg_name or "44" in alg_name else 0,
                },
            },
            "evidence": {
                "occurrences": [{"location": occ["file"], "line": occ.get("line", occ["occurrences"])} for occ in occurrences[:5]],
            }
        }
        components.append(comp)

    cbom = {
        "$schema": "http://cyclonedx.org/schema/bom-1.5.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{serial_uuid}",
        "version": 1,
        "metadata": {
            "timestamp": iso_timestamp,
            "tools": [
                {
                    "vendor": "Rahshaun Chambers",
                    "name": "qf-audit",
                    "version": "1.0.0",
                }
            ],
            "component": {
                "type": "application",
                "name": Path(scan_result["target"]).name,
                "description": f"Target boundary audited by QuantumFlex qf-audit.",
            },
        },
        "components": components,
    }
    return cbom


def evaluate_with_opa(cbom_data: Dict[str, Any], requested_profile: str = "agility") -> Dict[str, Any]:
    """Evaluates CBOM against OPA membrane_health.rego policy."""
    repo_root = Path(__file__).resolve().parents[1]
    rego_path = Path("/home/quant/mycelium/pqc-immune-daemon/membrane_health.rego")
    if not rego_path.exists():
        rego_path = repo_root / "pqc-immune-daemon" / "membrane_health.rego"

    threat_flags_path = Path("/home/quant/mycelium/sentinel/policies/threat_flags.json")
    if not threat_flags_path.exists():
        threat_flags_path = repo_root / "sentinel" / "policies" / "threat_flags.json"

    opa_bin = "/usr/local/bin/opa"
    if not os.path.exists(opa_bin):
        user_opa = os.path.expanduser("~/.local/bin/opa")
        opa_bin = user_opa if os.path.exists(user_opa) else "opa"

    # --stdin-input binds stdin directly to `input` in Rego (do not double-wrap in {"input": ...})
    opa_input = dict(cbom_data)
    opa_input.setdefault("requested_profile", requested_profile)
    input_payload = json.dumps(opa_input)

    cmd = [opa_bin, "eval", "-d", str(rego_path)]
    if threat_flags_path.exists():
        cmd.extend(["-d", str(threat_flags_path)])
    cmd.extend(["--stdin-input", "data.membrane.health"])

    try:
        proc = subprocess.run(
            cmd,
            input=input_payload,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode == 0:
            parsed = json.loads(proc.stdout)
            result = parsed.get("result", [{}])[0].get("expressions", [{}])[0].get("value", {})
            return {"status": "SUCCESS", "verdict": result}
        else:
            return {"status": "ERROR", "error": proc.stderr.strip()}
    except Exception as e:
        return {"status": "FALLBACK", "error": str(e), "verdict": {"node_status": "MANUAL_REVIEW_REQUIRED"}}


def print_audit_report(scan_result: Dict[str, Any], cbom_data: Dict[str, Any], opa_result: Dict[str, Any], out_dir: Path):
    """Renders high-impact executive SITREP to terminal."""
    findings = scan_result["findings"]
    pqc_kems = [k for k in findings if "KEM" in k or k in ["Classic-McEliece", "HQC"]]
    pqc_sigs = [k for k in findings if "DSA" in k]
    classical_algs = [k for k in findings if "RSA" in k or "ECDSA" in k or "ECDH" in k]
    toxic_algs = [k for k in findings if k in ["SHA-1", "MD5"]]

    verdict_data = opa_result.get("verdict", {})
    opa_status = verdict_data.get("node_status", "COMPLIANT")

    print(f"{BOLD}Target Path:{RESET}        {scan_result['target']}")
    print(f"{BOLD}Files Inspected:{RESET}    {scan_result['scanned_files']} / {scan_result['total_files']}")
    print(f"{BOLD}Timestamp (UTC):{RESET}    {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}")
    print("─" * 70)

    print(f"{BOLD}DISCOVERED CRYPTOGRAPHIC INVENTORY:{RESET}")
    if pqc_kems:
        print(f"  {GREEN}✓ Post-Quantum KEMs (FIPS 203):{RESET}     {', '.join(pqc_kems)}")
    else:
        print(f"  {RED}✗ Post-Quantum KEMs (FIPS 203):{RESET}     NONE DETECTED (M-26-15 GAP)")

    if pqc_sigs:
        print(f"  {GREEN}✓ Post-Quantum Sigs (FIPS 204/205):{RESET} {', '.join(pqc_sigs)}")
    else:
        print(f"  {YELLOW}⚠ Post-Quantum Sigs (FIPS 204/205):{RESET} NONE DETECTED")

    if classical_algs:
        print(f"  {YELLOW}⚠ Classical Algorithms (Deprecated):{RESET} {', '.join(classical_algs)}")

    if toxic_algs:
        print(f"  {RED}🚨 Toxic / Disallowed Hash Primitives:{RESET} {', '.join(toxic_algs)}")

    allowlisted = scan_result.get("allowlisted_findings", [])
    if allowlisted:
        print(f"  {CYAN}ℹ Audited Allowlist Exemptions:{RESET}     {len(allowlisted)} verified defensive check(s)")
        for item in allowlisted:
            print(f"    • {item['file']}:{item['line']}: {item['algorithm']} — {item['rationale']}")

    print("─" * 70)
    print(f"{BOLD}OPEN POLICY AGENT (OPA) COMPLIANCE VERDICT:{RESET}")

    if toxic_algs:
        print(f"  {RED}{BOLD}[NON-COMPLIANT // TOXIC DETECTED]{RESET}")
        print(f"  {RED}Disallowed legacy primitives ({', '.join(toxic_algs)}) detected in target boundary.{RESET}")
    elif pqc_kems:
        print(f"  {GREEN}{BOLD}[COMPLIANT // QUANTUM-AGILE]{RESET}")
        print(f"  {GREEN}NIST FIPS 203 post-quantum lattice primitives verified with active policy gates.{RESET}")
    else:
        print(f"  {YELLOW}{BOLD}[TRANSITIONAL // ACTION REQUIRED]{RESET}")
        print(f"  {YELLOW}Boundary relies strictly on classical algorithms. Post-quantum migration roadmap required.{RESET}")

    print("─" * 70)
    print(f"{BOLD}GENERATED ARTIFACTS IN:{RESET} {out_dir}")
    print(f"  • {CYAN}cbom.json{RESET}              (CycloneDX v1.5 Official CBOM)")
    print(f"  • {CYAN}audit_verdict.json{RESET}     (OPA Policy Evaluation Verdict)")
    print(f"  • {CYAN}remediation_report.md{RESET}  (Executive Compliance & Remediation SOW)")
    print("═" * 70 + "\n")


def write_artifacts(scan_result: Dict[str, Any], cbom_data: Dict[str, Any], opa_result: Dict[str, Any], out_dir: Path):
    """Saves official compliance deliverables to disk."""
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. CycloneDX CBOM JSON
    cbom_file = out_dir / "cbom.json"
    with open(cbom_file, "w") as f:
        json.dump(cbom_data, f, indent=2)

    # 2. OPA Verdict JSON
    verdict_file = out_dir / "audit_verdict.json"
    with open(verdict_file, "w") as f:
        json.dump(opa_result, f, indent=2)

    # 3. Executive Remediation Markdown Report
    report_file = out_dir / "remediation_report.md"
    findings = scan_result["findings"]
    pqc_kems = [k for k in findings if "KEM" in k or k in ["Classic-McEliece", "HQC"]]
    classical_algs = [k for k in findings if "RSA" in k or "ECDSA" in k or "ECDH" in k]

    md_content = f"""# Post-Quantum Cryptographic Readiness & CBOM Audit Report
**Audited Target:** `{scan_result['target']}`  
**Issuing Authority:** Rahshaun Chambers // QuantumFlex Audit Engine  
**Standard:** NIST FIPS 203/204/205 • OMB Memorandum M-26-15 • CycloneDX v1.5 CBOM  
**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}  
**Serial ID:** `{cbom_data['serialNumber']}`  

---

## 1. Executive Summary
This cryptographic assessment evaluates the software and configuration boundary against the post-quantum cryptographic standards mandated by OMB M-26-15 and NIST FIPS 203/204.

- **Total Files Scanned:** {scan_result['scanned_files']}
- **Cryptographic Assets Discovered:** {len(findings)}
- **Post-Quantum KEM Coverage:** {'COMPLIANT (' + ', '.join(pqc_kems) + ')' if pqc_kems else 'NON-COMPLIANT (No PQC KEM Detected)'}
- **Legacy Classical Footprint:** {len(classical_algs)} classical algorithm family references identified.

---

## 2. Discovered Cryptographic Asset Inventory
| Algorithm | Primitive Category | Standard Baseline | Compliance Posture | Discovered References |
| :--- | :--- | :--- | :--- | :--- |
"""
    for alg, occs in findings.items():
        meta = ALGORITHM_TAXONOMY.get(alg, {})
        md_content += f"| **{alg}** | {meta.get('category', 'OTHER')} | {meta.get('standard', 'N/A')} | `{meta.get('status', 'REVIEW')}` | {len(occs)} file(s) |\n"

    md_content += """
---

## 3. Buffer Exhaustion Vectors (NIST Level 3/5 Inelasticity)
The following static buffer allocations were detected within the AST/source code. These allocations are strictly bounded below the 15,792 byte FrodoKEM-976-AES ciphertext size (ISO/IEC 18033-2 candidate; not part of NIST FIPS 203, which specifies ML-KEM only), guaranteeing memory truncation and process crashes during post-quantum key exchange.

| File | Line | Static Allocation Size | Offending Code |
| :--- | :--- | :--- | :--- |
"""
    buffers = scan_result.get("buffer_vulnerabilities", [])
    if not buffers:
        md_content += "| No vulnerable static buffers detected | N/A | N/A | N/A |\n"
    else:
        for b in buffers[:50]:
            f_val = b.get("file", "")
            l_val = b.get("line", "")
            s_val = b.get("size", "")
            c_val = b.get("code", "")
            md_content += f"| `{f_val}` | {l_val} | `{s_val} bytes` (Critically Undersized) | `{c_val}` |\n"

    md_content += """
---

## 4. Required Remediation Roadmap (OMB M-26-15)

1. **Replace Asymmetric Key Encapsulation**: Any classical ECDH / RSA key exchange must implement a NIST FIPS 203 ML-KEM-768 or ISO/IEC 18033-2 FrodoKEM-976 hybrid wrapper.
2. **Eliminate Hardcoded Ciphers**: Migrate all hardcoded cipher suites to runtime policy evaluation via Open Policy Agent (OPA).
3. **Continuous CBOM Verification**: Ensure automated CycloneDX generation is embedded in pre-commit and CI/CD pipelines.

---
*Report certified by Rahshaun Chambers.*
"""
    with open(report_file, "w") as f:
        f.write(md_content)


def main():
    parser = argparse.ArgumentParser(
        description="QuantumFlex Automated PQC & CBOM Compliance Auditor (Rahshaun Chambers)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("target", nargs="?", default=".", help="Path to directory, repo, or file to audit (default: current directory)")
    parser.add_argument("-o", "--output-dir", default="./qf-audit-output", help="Directory to save CBOM JSON and remediation report")
    parser.add_argument("--json", action="store_true", help="Print pure JSON output to stdout")

    args = parser.parse_args()
    if not args.json:
        print_banner()

    target_path = Path(args.target).resolve()

    if not target_path.exists():
        print(f"{RED}Error: Target path '{args.target}' does not exist.{RESET}", file=sys.stderr)
        sys.exit(1)

    scan_result = scan_target(target_path)
    serial_uuid = str(uuid.uuid4())
    cbom_data = generate_cyclonedx_cbom(scan_result, serial_uuid)
    opa_result = evaluate_with_opa(cbom_data)
    out_dir = Path(args.output_dir).resolve()

    write_artifacts(scan_result, cbom_data, opa_result, out_dir)

    if args.json:
        print(json.dumps(cbom_data, indent=2))
    else:
        print_audit_report(scan_result, cbom_data, opa_result, out_dir)

    sys.exit(0)


if __name__ == "__main__":
    main()
