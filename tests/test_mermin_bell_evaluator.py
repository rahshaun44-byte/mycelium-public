"""
Unit and Invariant Tests for Mermin-Bell Inequality & DIQRNG Evaluation
========================================================================
Validates:
  1. Mermin polynomial calculation M_3 = <XXX> - <XYY> - <YXY> - <YYX>
  2. Device-independent tripartite Svetlichny non-locality certification (M_3 > 2*sqrt(2))
  3. Classical local realism failure modes (M_3 <= 2.0)
  4. NIST SP 800-90B conditional min-entropy monotonicity and bounds
"""

import math
import unittest
import tempfile
import json
from pathlib import Path

from tools.verify_mermin_bell_hardware import evaluate_mermin_bell, SVETLICHNY_THRESHOLD, CLASSICAL_BOUND

class TestMerminBellEvaluator(unittest.TestCase):

    def _create_mock_record(self, xxx: float, xyy: float, yxy: float, yyx: float) -> Path:
        data = {
            "source_raw_acquisition": {
                "job_id": "test_mock_job_123",
                "backend": "ibm_mock_heron"
            },
            "option_b_ghz_complete_witness_analysis": {
                "ghz_state_fidelity": 0.935,
                "witness_expectation": -0.435,
                "measured_expectations": {
                    "x0_x1_x2": xxx,
                    "x0_y1_y2": xyy,
                    "y0_x1_y2": yxy,
                    "y0_y1_x2": yyx
                }
            }
        }
        t = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(data, t)
        t.close()
        return Path(t.name)

    def test_ideal_ghz_mermin_violation(self):
        """Ideal noiseless GHZ state reaches maximal algebraic Tsirelson bound M_3 = 4.0."""
        # For |GHZ> = (|000> + |111>)/sqrt(2):
        # <XXX> = +1, <XYY> = -1, <YXY> = -1, <YYX> = -1
        # M_3 = 1 - (-1) - (-1) - (-1) = 4.0
        p = self._create_mock_record(1.0, -1.0, -1.0, -1.0)
        try:
            res = evaluate_mermin_bell(p)
            self.assertAlmostEqual(res["mermin_m3"], 4.0, places=4)
            self.assertTrue(res["violates_classical_lhv"])
            self.assertTrue(res["violates_svetlichny_tripartite"])
            self.assertGreaterEqual(res["h_min_per_shot"], 0.99)
        finally:
            p.unlink()

    def test_classical_state_rejection(self):
        """Classical separable states satisfy |M_3| <= 2.0 and fail Svetlichny threshold."""
        # E.g., Product state |000> has <XXX>=0, <XYY>=0, <YXY>=0, <YYX>=0 => M_3 = 0
        p = self._create_mock_record(0.0, 0.0, 0.0, 0.0)
        try:
            res = evaluate_mermin_bell(p)
            self.assertAlmostEqual(res["mermin_m3"], 0.0, places=4)
            self.assertFalse(res["violates_classical_lhv"])
            self.assertFalse(res["violates_svetlichny_tripartite"])
            self.assertAlmostEqual(res["h_min_per_shot"], 0.0, places=4)
        finally:
            p.unlink()

    def test_kingston_bulk_layout_empirical_run(self):
        """November 3 Heron r2 physical run (dbl33e56) certifies genuine tripartite non-locality."""
        p = self._create_mock_record(0.9453, -0.9141, -0.9219, -0.9219)
        try:
            res = evaluate_mermin_bell(p)
            self.assertAlmostEqual(res["mermin_m3"], 3.7032, places=4)
            self.assertGreater(res["mermin_95_lcb"], SVETLICHNY_THRESHOLD)
            self.assertTrue(res["violates_svetlichny_tripartite"])
            self.assertGreater(res["h_min_per_shot"], 0.5)
            self.assertGreater(res["total_extractable_bits"], 128.0)
        finally:
            p.unlink()

    def test_min_entropy_monotonicity(self):
        """Device-independent min-entropy increases monotonically with Bell violation."""
        violations = [2.1, 2.5, 2.8284, 3.2, 3.7, 3.99]
        h_mins = []
        for v in violations:
            p = self._create_mock_record(v / 4.0, -v / 4.0, -v / 4.0, -v / 4.0)
            try:
                res = evaluate_mermin_bell(p)
                h_mins.append(res["h_min_per_shot"])
            finally:
                p.unlink()
        
        # Verify strictly increasing
        for i in range(len(h_mins) - 1):
            self.assertLess(h_mins[i], h_mins[i + 1])

if __name__ == "__main__":
    unittest.main()
