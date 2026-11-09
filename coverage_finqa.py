"""
coverage_finqa.py -- automatic coverage estimate of the operator set (OPERATORS.md)
against FinQA's gold annotated reasoning programs.

What this measures: for each FinQA question, does every function name used in its
gold "program" string map onto a supported operator in gate.py/OPERATORS.md? This is
an UPPER BOUND on true expressibility, not a guarantee: it checks the operator
*vocabulary*, not whether every argument would actually resolve to a clean verbatim
span or a correctly-typed prior-step output in practice. Argument-level checking is
what the manual annotation pass in ANNOTATION_GUIDE.md / C3 is for -- this script is
the cheap, automatic first pass that tells you where to spend that manual effort.

Data source: https://github.com/czyssrs/FinQA (MIT license, verified directly:
https://github.com/czyssrs/FinQA/blob/main/LICENSE -- "MIT License, Copyright (c) 2021
Zhiyu Chen"). Paper: Chen et al., "FinQA: A Dataset of Numerical Reasoning over
Financial Data," EMNLP 2021.

Usage:
    python coverage_finqa.py --download   # fetches data/finqa_test.json via urllib
    python coverage_finqa.py               # uses data/finqa_test.json if present
    python coverage_finqa.py --n 200 --seed 42   # subsample for a quick pilot-sized check

If your network cannot reach raw.githubusercontent.com, run this manually instead:
    curl -o data/finqa_test.json https://raw.githubusercontent.com/czyssrs/FinQA/main/dataset/test.json
then re-run this script without --download.
"""

import argparse
import json
import os
import random
import re
import sys
import urllib.request
from collections import Counter

FINQA_URL = "https://raw.githubusercontent.com/czyssrs/FinQA/main/dataset/test.json"
DATA_PATH = os.path.join("data", "finqa_test.json")

FN_PATTERN = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)\(")

# Mapping from FinQA program function name -> (our operator, supported: bool, note)
FN_TO_OPERATOR = {
    "add":           ("arithmetic(add)", True, ""),
    "subtract":      ("arithmetic(sub)", True, ""),
    "multiply":      ("arithmetic(mul)", True, ""),
    "divide":        ("arithmetic(div)", True, ""),
    "greater":       ("numeric_compare(gt)", True, ""),
    "table_average": ("aggregate(avg)", True, "requires the averaged column to be built as a list_number step first"),
    "table_max":     ("aggregate(max)", True, "same caveat as table_average"),
    "table_min":     ("aggregate(min)", True, "same caveat as table_average"),
    "table_sum":     ("aggregate(sum)", True, "same caveat as table_average"),
    "exp":           (None, False, "exponentiation is not in the v1 operator set (OPERATORS.md); "
                                    "would need a new 'power' operator, not shipped in this pilot"),
}


def ensure_data(download: bool):
    if os.path.exists(DATA_PATH):
        return
    if not download:
        print(f"ERROR: {DATA_PATH} not found. Re-run with --download, or fetch it manually:\n"
              f"  mkdir -p data && curl -o {DATA_PATH} {FINQA_URL}", file=sys.stderr)
        sys.exit(1)
    os.makedirs("data", exist_ok=True)
    print(f"Downloading {FINQA_URL} ...")
    urllib.request.urlretrieve(FINQA_URL, DATA_PATH)
    print("Done.")


def classify_program(program: str):
    """Returns (expressible: bool, fn_names: list[str], unsupported: list[str])."""
    fn_names = FN_PATTERN.findall(program)
    unsupported = [fn for fn in fn_names if fn not in FN_TO_OPERATOR or not FN_TO_OPERATOR[fn][1]]
    return (len(unsupported) == 0 and len(fn_names) > 0), fn_names, unsupported


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--n", type=int, default=None, help="subsample size (default: full test set)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=os.path.join("data", "finqa_coverage_results.json"))
    args = ap.parse_args()

    ensure_data(args.download)

    with open(DATA_PATH, encoding="utf-8") as f:
        examples = json.load(f)

    random.seed(args.seed)
    if args.n and args.n < len(examples):
        examples = random.sample(examples, args.n)

    fn_counter = Counter()
    unsupported_fn_counter = Counter()
    results = []
    expressible_count = 0
    for ex in examples:
        qa = ex.get("qa", {})
        program = qa.get("program", "")
        expressible, fn_names, unsupported = classify_program(program)
        for fn in fn_names:
            fn_counter[fn] += 1
        for fn in unsupported:
            unsupported_fn_counter[fn] += 1
        if expressible:
            expressible_count += 1
        results.append({
            "id": ex.get("id"),
            "question": qa.get("question"),
            "program": program,
            "expressible": expressible,
            "functions_used": fn_names,
            "unsupported_functions": unsupported,
        })

    n = len(examples)
    coverage_pct = 100.0 * expressible_count / n if n else 0.0

    print(f"\n=== FinQA operator-vocabulary coverage (n={n}) ===")
    print(f"Expressible (every function in gold program maps to a supported operator): "
          f"{expressible_count}/{n} = {coverage_pct:.1f}%")
    print("\nFunction usage across sampled programs:")
    for fn, c in fn_counter.most_common():
        mapped = FN_TO_OPERATOR.get(fn)
        status = "SUPPORTED -> " + mapped[0] if mapped and mapped[1] else "UNSUPPORTED: " + (mapped[2] if mapped else "unknown function")
        print(f"  {fn:16s} {c:5d}  {status}")

    if unsupported_fn_counter:
        print("\nQuestions blocked, by unsupported function:")
        for fn, c in unsupported_fn_counter.most_common():
            note = FN_TO_OPERATOR.get(fn, (None, False, "unrecognized function name"))[2]
            print(f"  {fn}: blocks {c} program(s). Reason: {note}")
    else:
        print("\nNo unsupported functions encountered in this sample.")

    # CI note, per PREREG.md / round-1 statistics: n=100 gives roughly +/-10pp at p~0.5.
    if n:
        import math
        p = expressible_count / n
        se = math.sqrt(p * (1 - p) / n)
        half_width = 1.96 * se * 100
        print(f"\n95% CI on coverage (Wald approx, n={n}): {coverage_pct:.1f}% +/- {half_width:.1f}pp")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"n": n, "expressible_count": expressible_count, "coverage_pct": coverage_pct,
                   "function_usage": dict(fn_counter), "unsupported_functions": dict(unsupported_fn_counter),
                   "results": results}, f, indent=2)
    print(f"\nFull per-question results written to {args.out}")
    print("\nREMINDER: this is operator-VOCABULARY coverage (does a supported function exist for "
          "every op name in the gold program), not a guarantee that arguments will resolve to "
          "clean verbatim spans in practice. Treat this as an upper bound; the manual pass in "
          "ANNOTATION_GUIDE.md checks the part this script cannot.")


if __name__ == "__main__":
    main()
