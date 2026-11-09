#!/usr/bin/env python3
"""
plot_risk_coverage.py -- Risk-coverage curve plotter per PREREG.md Section 5.

Reads harness.py's mode-B output JSONL and gold answers from sample_2wiki.jsonl,
computes accuracy-at-coverage for the ADMIT-only subset vs. full set, and plots
risk (1 - accuracy) on y-axis, coverage (fraction answered) on x-axis.

Usage:
    python plot_risk_coverage.py --mode-b runs/mode_b.jsonl \
        --mode-c runs/mode_c.jsonl --gold sample_2wiki.jsonl \
        --out risk_coverage.png

Stdlib + matplotlib only (no pandas).
"""

import argparse
import json
import sys
from typing import Dict, List, Optional, Tuple


def load_jsonl(path: str) -> List[dict]:
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def load_gold(path: str) -> Dict[str, str]:
    """Returns {question_id: gold_answer}."""
    items = load_jsonl(path)
    return {item["id"]: str(item["answer"]).strip().lower() for item in items}


def normalize_answer(answer) -> Optional[str]:
    if answer is None:
        return None
    return str(answer).strip().lower()


def compute_risk_coverage_arm2(results: List[dict], gold: Dict[str, str]) -> List[Tuple[float, float]]:
    """For Arm 2 (mode B), the curve has two points:
    - Full coverage: all questions, abstentions counted as wrong
    - ADMIT-only coverage: only questions where final_status == 'ADMIT'
    """
    total = len(results)
    if total == 0:
        return []

    # Full coverage point
    full_correct = 0
    for r in results:
        qid = r.get("question_id")
        pred = normalize_answer(r.get("answer"))
        gold_ans = gold.get(qid)
        if pred is not None and gold_ans is not None and pred == gold_ans:
            full_correct += 1
    full_accuracy = full_correct / total
    full_point = (1.0, 1.0 - full_accuracy)  # (coverage, risk)

    # ADMIT-only coverage point
    admitted = [r for r in results if r.get("final_status") == "ADMIT"]
    if not admitted:
        return [full_point]
    admit_correct = 0
    for r in admitted:
        qid = r.get("question_id")
        pred = normalize_answer(r.get("answer"))
        gold_ans = gold.get(qid)
        if pred is not None and gold_ans is not None and pred == gold_ans:
            admit_correct += 1
    admit_coverage = len(admitted) / total
    admit_accuracy = admit_correct / len(admitted)
    admit_point = (admit_coverage, 1.0 - admit_accuracy)

    return [admit_point, full_point]


def compute_risk_coverage_arm0(results: List[dict], gold: Dict[str, str]) -> List[Tuple[float, float]]:
    """For Arm 0 (mode C), a single point at 100% coverage (no abstention mechanism)."""
    total = len(results)
    if total == 0:
        return []
    correct = 0
    for r in results:
        qid = r.get("question_id")
        pred = normalize_answer(r.get("answer"))
        gold_ans = gold.get(qid)
        if pred is not None and gold_ans is not None and pred == gold_ans:
            correct += 1
    accuracy = correct / total
    return [(1.0, 1.0 - accuracy)]


def plot(arm2_points: List[Tuple[float, float]],
         arm0_points: List[Tuple[float, float]],
         out_path: str):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 6))

    if arm2_points:
        cov2, risk2 = zip(*sorted(arm2_points))
        ax.plot(cov2, risk2, "o-", color="tab:blue", label="Arm 2 (gated)", markersize=8)
    if arm0_points:
        cov0, risk0 = zip(*sorted(arm0_points))
        ax.plot(cov0, risk0, "s", color="tab:red", label="Arm 0 (free CoT)", markersize=10)

    ax.set_xlabel("Coverage (fraction answered)")
    ax.set_ylabel("Risk (1 - accuracy)")
    ax.set_xlim(0, 1.05)
    ax.set_ylim(-0.05, 1.05)
    ax.set_title("Risk-Coverage Curve (PREREG.md Section 5)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"Plot saved to {out_path}")


def main():
    ap = argparse.ArgumentParser(description="Risk-coverage curve plotter")
    ap.add_argument("--mode-b", required=True, help="Mode B (Arm 2) JSONL output")
    ap.add_argument("--mode-c", default=None, help="Mode C (Arm 0) JSONL output (optional)")
    ap.add_argument("--gold", required=True, help="Gold answers JSONL (sample_2wiki.jsonl)")
    ap.add_argument("--out", default="risk_coverage.png", help="Output plot path")
    args = ap.parse_args()

    gold = load_gold(args.gold)
    mode_b = load_jsonl(args.mode_b)
    arm2_points = compute_risk_coverage_arm2(mode_b, gold)

    arm0_points = []
    if args.mode_c:
        mode_c = load_jsonl(args.mode_c)
        arm0_points = compute_risk_coverage_arm0(mode_c, gold)

    if not arm2_points and not arm0_points:
        print("No data to plot.", file=sys.stderr)
        sys.exit(1)

    plot(arm2_points, arm0_points, args.out)

    # Print summary
    print("\nArm 2 (gated) risk-coverage points:")
    for cov, risk in sorted(arm2_points):
        print(f"  coverage={cov:.2%}, risk={risk:.2%}, accuracy={1-risk:.2%}")
    if arm0_points:
        print("Arm 0 (free CoT) risk-coverage points:")
        for cov, risk in sorted(arm0_points):
            print(f"  coverage={cov:.2%}, risk={risk:.2%}, accuracy={1-risk:.2%}")


if __name__ == "__main__":
    main()
