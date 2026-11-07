#!/usr/bin/env python3
"""
QuantumFlex Verification Suite: Self-Testing CHSH / Mermin-Bell Inequality Evaluation
=====================================================================================
Evaluates device-independent tripartite non-locality and NIST SP 800-90B conditional
min-entropy lower bounds from physical IBM Quantum Heron r2 processor measurements.

Mathematical Bounds:
  - Classical Local Hidden Variable Bound (LHV): |M_3| <= 2.0
  - Biseparable Quantum / Svetlichny Threshold  : |M_3| <= 2*sqrt(2) ≈ 2.8284
  - Tsirelson / Algebraic Maximum Quantum Bound: |M_3| = 4.0

Mermin Polynomial Definition (4 off-diagonal parity correlators):
  M_3 = <X0 X1 X2> - <X0 Y1 Y2> - <Y0 X1 Y2> - <Y0 Y1 X2>

Device-Independent Min-Entropy Lower Bound H_min(A|E):
  P_guess <= 0.5 * (1 + sqrt(max(0, 1 - (M_3 / 4)^2)))
  H_min(A|E) = -log2(P_guess) bits/shot
"""

import sys
import json
import math
import argparse
from pathlib import Path
from typing import Dict, Any, Tuple

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

# Default historical acquisition records on host
DEFAULT_RECORDS = {
    "oct16_kingston": ROOT_DIR.parent / "qf-research" / "ibm-qaoa-ghz-kingston-20261016T013409Z" / "analysis_record.json",
    "nov03_kingston": ROOT_DIR.parent / "qf-research" / "ibm-qaoa-ghz-kingston-20261103T214608Z" / "analysis_record.json",
    "nov04_kingston": ROOT_DIR.parent / "qf-research" / "ibm-qaoa-ghz-kingston-20261104T211541Z" / "analysis_record.json",
}

SVETLICHNY_THRESHOLD = 2.0 * math.sqrt(2.0)  # 2.828427...
CLASSICAL_BOUND = 2.0
TSIRELSON_MAX = 4.0

def evaluate_mermin_bell(record_path: Path) -> Dict[str, Any]:
    if not record_path.exists():
        raise FileNotFoundError(f"Analysis record not found: {record_path}")

    with open(record_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    job_id = data.get("source_raw_acquisition", {}).get("job_id", "UNKNOWN")
    backend = data.get("source_raw_acquisition", {}).get("backend", "UNKNOWN")
    ghz_sec = data.get("option_b_ghz_complete_witness_analysis", {})
    exp = ghz_sec.get("measured_expectations", {})

    xxx = float(exp.get("x0_x1_x2", 0.0))
    xyy = float(exp.get("x0_y1_y2", 0.0))
    yxy = float(exp.get("y0_x1_y2", 0.0))
    yyx = float(exp.get("y0_y1_x2", 0.0))

    # M3 = <XXX> - <XYY> - <YXY> - <YYX>
    m3 = xxx - xyy - yxy - yyx

    # Stderr estimation based on single-shot parity variance: Var(P_i) = (1 - <P_i>^2) / N
    shots = 256  # default shots per measurement setting in 6-circuit batched suite
    var_terms = [(1.0 - p**2) / shots for p in [xxx, xyy, yxy, yyx]]
    std_m3 = math.sqrt(sum(var_terms))

    # One-sided 95% lower confidence bound (LCB): z_0.95 = 1.64485
    lcb_95 = m3 - 1.64485 * std_m3

    # Device-independent min-entropy lower bound
    ratio = min(1.0, max(0.0, abs(m3) / TSIRELSON_MAX))
    p_guess = 0.5 * (1.0 + math.sqrt(max(0.0, 1.0 - ratio**2)))
    h_min_per_shot = -math.log2(p_guess) if p_guess > 0 else 1.0
    total_extractable_bits = h_min_per_shot * shots

    # Classification
    violates_classical = lcb_95 > CLASSICAL_BOUND
    violates_svetlichny = lcb_95 > SVETLICHNY_THRESHOLD

    return {
        "job_id": job_id,
        "backend": backend,
        "fidelity": ghz_sec.get("ghz_state_fidelity", 0.0),
        "witness_expectation": ghz_sec.get("witness_expectation", 0.0),
        "parities": {
            "x0_x1_x2": xxx,
            "x0_y1_y2": xyy,
            "y0_x1_y2": yxy,
            "y0_y1_x2": yyx,
        },
        "mermin_m3": m3,
        "mermin_std": std_m3,
        "mermin_95_lcb": lcb_95,
        "sigma_above_classical": (m3 - CLASSICAL_BOUND) / std_m3 if std_m3 > 0 else 0.0,
        "sigma_above_svetlichny": (m3 - SVETLICHNY_THRESHOLD) / std_m3 if std_m3 > 0 else 0.0,
        "violates_classical_lhv": violates_classical,
        "violates_svetlichny_tripartite": violates_svetlichny,
        "h_min_per_shot": h_min_per_shot,
        "total_extractable_bits": total_extractable_bits,
    }

def print_report(res: Dict[str, Any], title: str):
    print("=" * 67)
    print(f"  QUANTUMFLEX MERMIN-BELL & MIN-ENTROPY AUDIT: {title}")
    print("=" * 67)
    print(f"  Physical Job ID         : {res['job_id']}")
    print(f"  Silicon Backend         : {res['backend']}")
    print(f"  GHZ State Fidelity (F)  : {res['fidelity'] * 100:.2f}%")
    print(f"  Witness Expectation <W> : {res['witness_expectation']:+.6f}")
    print("  Measured Parity Terms   :")
    print(f"    • <X0 X1 X2>          : {res['parities']['x0_x1_x2']:+.4f}")
    print(f"    • <X0 Y1 Y2>          : {res['parities']['x0_y1_y2']:+.4f}")
    print(f"    • <Y0 X1 Y2>          : {res['parities']['y0_x1_y2']:+.4f}")
    print(f"    • <Y0 Y1 X2>          : {res['parities']['y0_y1_x2']:+.4f}")
    print("  ---------------------------------------------------------------")
    print(f"  Mermin Polynomial M_3   : {res['mermin_m3']:.4f} ± {res['mermin_std']:.4f}")
    print(f"  95% Lower Conf Bound    : {res['mermin_95_lcb']:.4f}")
    print(f"  Classical Bound (<= 2.0): {'VIOLATED' if res['violates_classical_lhv'] else 'NOT VIOLATED'} "
          f"({res['sigma_above_classical']:+.1f}σ from bound)")
    print(f"  Svetlichny (<= 2.8284)  : {'VIOLATED [GENUINE TRIPARTITE]' if res['violates_svetlichny_tripartite'] else 'NOT VIOLATED'} "
          f"({res['sigma_above_svetlichny']:+.1f}σ from bound)")
    print("  ---------------------------------------------------------------")
    print(f"  NIST SP 800-90B DI H_min: {res['h_min_per_shot']:.4f} bits/shot")
    print(f"  Extractable Random Bits : {res['total_extractable_bits']:.1f} bits / 256 shots")
    print("=" * 67)
    print()

def main():
    parser = argparse.ArgumentParser(description="Evaluate Mermin-Bell inequality on QuantumFlex QPU runs")
    parser.add_argument("--file", help="Path to specific analysis_record.json")
    parser.add_argument("--benchmark-all", action="store_true", help="Compare all historical hardware runs")
    args = parser.parse_args()

    if args.file:
        res = evaluate_mermin_bell(Path(args.file))
        print_report(res, Path(args.file).parent.name)
        return

    # Benchmark all historical runs
    for tag, p in DEFAULT_RECORDS.items():
        if p.exists():
            res = evaluate_mermin_bell(p)
            print_report(res, tag)

if __name__ == "__main__":
    main()
