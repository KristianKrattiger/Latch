#!/usr/bin/env python3
"""
kappa.py -- Cohen's kappa for the self re-annotation agreement check.

Reads two annotation CSV files (pass1 and pass2), extracts the
'decomposable_yes_no' column from each, and computes Cohen's kappa on that
binary column. Prints the kappa value and a plain-English interpretation.

Usage:
    python kappa.py annotation_sheet_pass1.csv annotation_sheet_pass2.csv

Per ANNOTATION_GUIDE.md: kappa below ~0.6 means the rubric is ambiguous and
needs tightening before trusting the coverage number it produced.

Stdlib only -- no numpy, no scipy, no pandas.
"""

import csv
import sys


def read_column(path: str, column: str = "decomposable_yes_no") -> list:
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if column not in reader.fieldnames:
            print(f"Error: column {column!r} not found in {path}", file=sys.stderr)
            print(f"  Available columns: {reader.fieldnames}", file=sys.stderr)
            sys.exit(1)
        return [row[column].strip().lower() for row in reader]


def cohens_kappa(a: list, b: list) -> float:
    assert len(a) == len(b), f"length mismatch: {len(a)} vs {len(b)}"
    n = len(a)
    if n == 0:
        return 1.0
    agree = sum(1 for x, y in zip(a, b) if x == y) / n
    pa = sum(1 for x in a if x == "yes") / n
    pb = sum(1 for x in b if x == "yes") / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    if expected >= 1.0:
        return 1.0
    return (agree - expected) / (1 - expected)


def interpret(kappa: float) -> str:
    if kappa < 0.0:
        return "Less than chance agreement -- rubric is likely being applied inconsistently."
    if kappa < 0.20:
        return "Slight agreement -- rubric is very ambiguous, needs major revision."
    if kappa < 0.40:
        return "Fair agreement -- rubric has significant ambiguity."
    if kappa < 0.60:
        return "Moderate agreement -- rubric is ambiguous; tighten before trusting coverage numbers."
    if kappa < 0.80:
        return "Substantial agreement -- rubric is reasonably reliable."
    return "Almost perfect agreement -- rubric is clear and stable."


def main():
    if len(sys.argv) != 3:
        print(f"Usage: python {sys.argv[0]} pass1.csv pass2.csv", file=sys.stderr)
        sys.exit(1)

    a = read_column(sys.argv[1])
    b = read_column(sys.argv[2])

    if len(a) != len(b):
        print(f"Error: row count mismatch: {len(a)} in {sys.argv[1]} vs {len(b)} in {sys.argv[2]}", file=sys.stderr)
        sys.exit(1)

    k = cohens_kappa(a, b)
    print(f"Cohen's kappa: {k:.4f}")
    print(f"Interpretation: {interpret(k)}")
    if k < 0.6:
        print("\nWARNING: kappa < 0.6 -- per ANNOTATION_GUIDE.md, the rubric is ambiguous.")
        print("Re-run on a 20-question subset with a revised rubric before trusting")
        print("the coverage number.")


if __name__ == "__main__":
    main()
