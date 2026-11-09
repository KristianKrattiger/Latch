"""
test_kappa.py -- tests for kappa.py's Cohen's kappa calculation.

Run with: python -m unittest test_kappa.py -v
"""

import csv
import os
import tempfile
import unittest

from kappa import cohens_kappa, interpret, read_column


def _write_csv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "decomposable_yes_no"])
        w.writeheader()
        for i, val in enumerate(rows):
            w.writerow({"id": f"q{i}", "decomposable_yes_no": val})


class TestCohensKappa(unittest.TestCase):
    def test_perfect_agreement(self):
        a = ["yes", "no", "yes", "no"]
        b = ["yes", "no", "yes", "no"]
        self.assertAlmostEqual(cohens_kappa(a, b), 1.0)

    def test_no_agreement_beyond_chance(self):
        # Perfectly anti-correlated with balanced marginals -> kappa = -1
        a = ["yes", "yes", "no", "no"]
        b = ["no", "no", "yes", "yes"]
        self.assertAlmostEqual(cohens_kappa(a, b), -1.0)

    def test_partial_agreement(self):
        a = ["yes", "yes", "yes", "no", "no"]
        b = ["yes", "yes", "no", "no", "no"]
        k = cohens_kappa(a, b)
        # Should be moderate agreement, between 0 and 1
        self.assertGreater(k, 0.0)
        self.assertLess(k, 1.0)

    def test_empty_lists(self):
        self.assertEqual(cohens_kappa([], []), 1.0)

    def test_all_same_category_both_raters(self):
        a = ["yes", "yes", "yes"]
        b = ["yes", "yes", "yes"]
        # expected agreement = 1.0, so kappa = 1.0 by convention
        self.assertAlmostEqual(cohens_kappa(a, b), 1.0)


class TestInterpret(unittest.TestCase):
    def test_below_threshold_warns(self):
        self.assertIn("ambiguous", interpret(0.5).lower())

    def test_high_kappa_positive(self):
        self.assertIn("almost perfect", interpret(0.85).lower())


class TestReadColumn(unittest.TestCase):
    def test_reads_csv_correctly(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False,
                                          encoding="utf-8", newline="") as f:
            _write_csv(f.name, ["yes", "no", "yes"])
            path = f.name
        try:
            result = read_column(path)
            self.assertEqual(result, ["yes", "no", "yes"])
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
