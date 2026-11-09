"""
test_plot_risk_coverage.py -- tests for plot_risk_coverage.py using synthetic fixtures.

Tests the computation logic (not the matplotlib plot itself). Run with:
    python -m unittest test_plot_risk_coverage.py -v
"""

import json
import os
import tempfile
import unittest

from plot_risk_coverage import (
    compute_risk_coverage_arm0,
    compute_risk_coverage_arm2,
    load_gold,
    load_jsonl,
    normalize_answer,
)


def _write_jsonl(path, records):
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


class TestNormalizeAnswer(unittest.TestCase):
    def test_none(self):
        self.assertIsNone(normalize_answer(None))

    def test_string_lowered_and_stripped(self):
        self.assertEqual(normalize_answer("  Doc A  "), "doc a")

    def test_bool_converted(self):
        self.assertEqual(normalize_answer(True), "true")


class TestLoadGold(unittest.TestCase):
    def test_loads_id_answer_map(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False,
                                          encoding="utf-8") as f:
            _write_jsonl(f.name, [
                {"id": "q1", "answer": "Doc A", "question": "x", "docs": {}},
                {"id": "q2", "answer": "Doc B", "question": "y", "docs": {}},
            ])
            path = f.name
        try:
            gold = load_gold(path)
            self.assertEqual(gold["q1"], "doc a")
            self.assertEqual(gold["q2"], "doc b")
        finally:
            os.unlink(path)


class TestComputeArm2(unittest.TestCase):
    def _make_gold(self):
        return {"q1": "true", "q2": "false", "q3": "true", "q4": "false"}

    def test_all_admit_all_correct(self):
        results = [
            {"question_id": "q1", "final_status": "ADMIT", "answer": True},
            {"question_id": "q2", "final_status": "ADMIT", "answer": False},
        ]
        gold = {"q1": "true", "q2": "false"}
        points = compute_risk_coverage_arm2(results, gold)
        # Two points: ADMIT-only and full, both at coverage=1.0, risk=0.0
        coverages = [c for c, r in points]
        risks = [r for c, r in points]
        self.assertIn(1.0, coverages)
        self.assertAlmostEqual(min(risks), 0.0)

    def test_mixed_admit_and_abstain(self):
        results = [
            {"question_id": "q1", "final_status": "ADMIT", "answer": True},
            {"question_id": "q2", "final_status": "ADMIT", "answer": True},  # wrong
            {"question_id": "q3", "final_status": "ABSTAIN_PARSE_FAILURE", "answer": None},
            {"question_id": "q4", "final_status": "ABSTAIN_GATE_REJECTION", "answer": None},
        ]
        gold = self._make_gold()
        points = compute_risk_coverage_arm2(results, gold)
        # Should have 2 points
        self.assertEqual(len(points), 2)
        # ADMIT-only: 2 admitted, 1 correct (q1) -> coverage=0.5, accuracy=0.5, risk=0.5
        admit_point = min(points, key=lambda p: p[0])
        self.assertAlmostEqual(admit_point[0], 0.5)   # coverage
        self.assertAlmostEqual(admit_point[1], 0.5)    # risk
        # Full: 4 total, 1 correct -> coverage=1.0, risk=0.75
        full_point = max(points, key=lambda p: p[0])
        self.assertAlmostEqual(full_point[0], 1.0)
        self.assertAlmostEqual(full_point[1], 0.75)

    def test_empty_results(self):
        self.assertEqual(compute_risk_coverage_arm2([], {}), [])

    def test_all_abstained(self):
        results = [
            {"question_id": "q1", "final_status": "ABSTAIN_PARSE_FAILURE", "answer": None},
        ]
        gold = {"q1": "true"}
        points = compute_risk_coverage_arm2(results, gold)
        # Only the full-coverage point (all wrong since abstained)
        self.assertEqual(len(points), 1)
        self.assertAlmostEqual(points[0][0], 1.0)  # coverage
        self.assertAlmostEqual(points[0][1], 1.0)  # risk (0% accuracy)


class TestComputeArm0(unittest.TestCase):
    def test_single_point_at_full_coverage(self):
        results = [
            {"question_id": "q1", "answer": "doc a"},
            {"question_id": "q2", "answer": "wrong"},
        ]
        gold = {"q1": "doc a", "q2": "doc b"}
        points = compute_risk_coverage_arm0(results, gold)
        self.assertEqual(len(points), 1)
        self.assertAlmostEqual(points[0][0], 1.0)   # coverage
        self.assertAlmostEqual(points[0][1], 0.5)    # risk (50% accuracy)

    def test_empty_results(self):
        self.assertEqual(compute_risk_coverage_arm0([], {}), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
