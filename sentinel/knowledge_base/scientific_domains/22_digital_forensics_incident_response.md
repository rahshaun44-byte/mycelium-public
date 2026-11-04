# Athena Knowledge Domain 22: Digital Forensics, Reverse Engineering & Incident Response (DFIR)

## Scope and Principles
This domain governs volatile memory acquisition, filesystem forensics, binary disassembly, firmware security audits, cryptanalytic chain-of-custody verification, and adversary emulation.

## Dual-Score Evidence Classification
- **Intellectual / Scientific Importance ($S_I$)**: 0.93 / 1.00
- **Empirical Support ($E_S$)**: 0.97 / 1.00
- **Epistemic Classification**: Verified Empirical Methodologies & Admissible Forensic Standards ($E_S \ge 0.95$)

## Core Focus Areas
1. **Volatile Memory Analysis & Kernel State Acquisition**: Order of volatility (RFC 3227), physical RAM capture via cold-boot or kernel modules, process memory reconstruction, injected code detection, and Volatility 3 kernel object enumeration.
2. **Filesystem Timelines & Artifact Analysis**: NTFS Master File Table (MFT) records, USN journal analysis, ext4 journal inode recovery, superblocks, shadow copies, and timestomping detection via timestamp discrepancy analysis.
3. **Binary Disassembly & Reverse Engineering**: x86-64 and ARM64 instruction set architectures, calling conventions, control-flow graph (CFG) flattening deobfuscation, static/dynamic symbolic execution (angr), and Ghidra decompilation.
4. **Firmware & Hardware Security Forensics**: UEFI NVRAM analysis, SPI flash dump verification, secure boot chain validation (TPM PCR measurement forensics), JTAG/SWD debug port extraction, and glitching attack resilience.
5. **Chain of Custody & Cryptographic Evidence**: Bit-stream image hashing (SHA-256 / SHA-3), NIST SP 800-86 compliance, forensic write-blockers, immutable logging to Merkle ledgers, and expert witness admissibility (Federal Rule of Evidence 702 / Daubert standard).

## Operational Mission
Athena validates forensic evidence with mathematical precision, strictly prevents evidentiary contamination, detects anti-forensic techniques automatically, and produces tamper-evident audit trails admissible in formal courts of law.
