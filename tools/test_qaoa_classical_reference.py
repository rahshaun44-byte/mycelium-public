#!/usr/bin/env python3
"""
Classical reference solver for 3-asset Markowitz Mean-Variance Portfolio.
Enumerates all 2^3 = 8 portfolios and finds the exact optimal feasible portfolio.
"""

import itertools
import numpy as np

mu = np.array([0.15, 0.10, 0.05], dtype=float)

cov = np.array([
    [0.08,  0.02, -0.01],
    [0.02,  0.06,  0.00],
    [-0.01, 0.00,  0.01],
], dtype=float)

risk_weight = 0.5
budget = 2
penalty = 1.0


def portfolio_cost(x):
    x = np.asarray(x, dtype=float)
    return float(
        -mu @ x
        + risk_weight * (x @ cov @ x)
        + penalty * (x.sum() - budget) ** 2
    )


def main():
    results = []
    for bits in itertools.product([0, 1], repeat=3):
        x = np.array(bits, dtype=float)
        results.append({
            "bits": bits,
            "assets_selected": int(x.sum()),
            "cost": portfolio_cost(x),
        })

    print("=" * 60)
    print(" ALL 8 PORTFOLIOS SORTED BY CLASSICAL OBJECTIVE COST:")
    print(" Asset 0: Tech_Growth (15% ret, 8% var)")
    print(" Asset 1: Energy_Dividend (10% ret, 6% var)")
    print(" Asset 2: Treasury_Bond (5% ret, 1% var)")
    print(" Budget : Exactly 2 assets")
    print("=" * 60)

    for row in sorted(results, key=lambda r: r["cost"]):
        feasible_tag = "[FEASIBLE]" if row["assets_selected"] == budget else "[PENALIZED]"
        print(
            f" bits={row['bits']} "
            f" selected={row['assets_selected']} "
            f" cost={row['cost']:+.6f}  {feasible_tag}"
        )

    feasible = [row for row in results if row["assets_selected"] == budget]
    best = min(feasible, key=lambda r: r["cost"])

    print("\n" + "=" * 60)
    print(" BEST FEASIBLE PORTFOLIO:")
    print(f" Bits     : {best['bits']} -> Asset 0 (Tech) + Asset 2 (Treasury)")
    print(f" Cost     : {best['cost']:+.6f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
