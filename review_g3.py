"""
review_g3.py — G3 manual scoring aid.

Usage:
  python review_g3.py arm2   # print Arm 2 admit traces for manual scoring
  python review_g3.py arm0   # print Arm 0 answers for manual scoring
  python review_g3.py score  # after both score files exist, run McNemar + risk-coverage

Score files (edit these after review):
  scores/arm2_scores.jsonl  — {question_id, verdict: "correct"|"wrong"|"abstain"}
  scores/arm0_scores.jsonl  — {question_id, verdict: "correct"|"wrong"}
"""

import sys, json, os, collections
from pathlib import Path

ARM2_RUN  = "runs/arm2_14b_v4.jsonl"
ARM0_RUN  = "runs/arm0_14b_v4.jsonl"
DATA      = "sample_2wiki_decomposable.jsonl"
SCORES_DIR = Path("scores")

def load_samples():
    m = {}
    with open(DATA, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            m[r["id"]] = r
    return m

def load_run(path):
    records = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                r = json.loads(line)
                records[r["question_id"]] = r
            except:
                pass
    return records

# ---------------------------------------------------------------------------
# arm2 — print admit traces
# ---------------------------------------------------------------------------

def cmd_arm2():
    samples = load_samples()
    records = load_run(ARM2_RUN)
    admits = [(qid, r) for qid, r in records.items() if r.get("final_status") == "ADMIT"]
    abstains = [(qid, r) for qid, r in records.items() if r.get("final_status", "").startswith("ABSTAIN")]
    print(f"Arm 2 results: {len(admits)} ADMIT, {len(abstains)} ABSTAIN  (of {len(records)} total)\n")
    print("=" * 80)
    for i, (qid, r) in enumerate(admits, 1):
        s = samples.get(qid, {})
        qtype = s.get("type", "?")
        q = s.get("question", "?")
        gold = s.get("answer", "?")
        steps = r.get("parsed_steps") or []
        gate_verdicts = r.get("gate_verdicts") or []
        gate_value = gate_verdicts[-1]["value"] if gate_verdicts else None

        print(f"[{i:02d}] [{qtype}] {q}")
        print(f"      Gold answer : {gold}")
        print(f"      Gate value  : {gate_value}")
        # Show steps
        for step in steps:
            op = step.get("operator", "?")
            args = step.get("args", [])
            pairs = [(a.get("doc_id","?"), a.get("text","?")) if isinstance(a,dict) else str(a) for a in args]
            params = step.get("params", {})
            print(f"      step: {op}({pairs}) params={params}")
        print(f"      VERDICT: [ correct / wrong ]   <- fill in scores/arm2_scores.jsonl")
        print()
    print("=" * 80)
    print(f"\nAbstains ({len(abstains)}):")
    for qid, r in abstains:
        s = samples.get(qid, {})
        print(f"  [{s.get('type','?')}] {s.get('question','?')[:70]}  status={r.get('final_status')}")

# ---------------------------------------------------------------------------
# arm0 — print CoT answers
# ---------------------------------------------------------------------------

def cmd_arm0():
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    samples = load_samples()
    records = load_run(ARM0_RUN)
    print(f"Arm 0 results: {len(records)} records\n")
    print("=" * 80)
    for i, (qid, r) in enumerate(sorted(records.items()), 1):
        s = samples.get(qid, {})
        qtype = s.get("type", "?")
        q = s.get("question", "?")
        gold = s.get("answer", "?")
        model_answer = r.get("answer", "(no answer extracted)")
        # Simple normalization for quick visual check
        def norm(x): return str(x).lower().strip().rstrip('.').strip("'\"") if x else ""
        match = "OK" if norm(gold) in norm(model_answer) or norm(model_answer) in norm(gold) else "??"
        print(f"[{i:02d}] {match} [{qtype}] {q[:70]}")
        print(f"      Gold  : {gold}")
        print(f"      Model : {model_answer}")
        print()

# ---------------------------------------------------------------------------
# score — McNemar + risk-coverage (run after scoring)
# ---------------------------------------------------------------------------

def cmd_score():
    SCORES_DIR.mkdir(exist_ok=True)
    arm2_path = SCORES_DIR / "arm2_scores.jsonl"
    arm0_path = SCORES_DIR / "arm0_scores.jsonl"
    if not arm2_path.exists() or not arm0_path.exists():
        print("Score files not found. Create scores/arm2_scores.jsonl and scores/arm0_scores.jsonl first.")
        print("Format: one JSON per line: {\"question_id\": \"...\", \"verdict\": \"correct\"|\"wrong\"|\"abstain\"}")
        return

    arm2 = {}
    for line in arm2_path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line); arm2[r["question_id"]] = r["verdict"]
    arm0 = {}
    for line in arm0_path.read_text(encoding="utf-8").splitlines():
        r = json.loads(line); arm0[r["question_id"]] = r["verdict"]

    samples = load_samples()
    all_qids = list(samples.keys())

    # Fill abstains for Arm 2 questions not in score file (they were gate-abstained)
    arm2_records = load_run(ARM2_RUN)
    for qid, r in arm2_records.items():
        if qid not in arm2:
            status = r.get("final_status","")
            arm2[qid] = "abstain" if status.startswith("ABSTAIN") else "wrong"

    # 2x2 table: treat abstain as "not answered" (not incorrect per PREREG §4)
    # For McNemar: restrict to subset where BOTH arms gave an answer
    a0c_a2c = a0c_a2w = a0w_a2c = a0w_a2w = 0
    correct_arm0 = correct_arm2 = abstain_arm2 = 0
    for qid in all_qids:
        v0 = arm0.get(qid, "wrong")
        v2 = arm2.get(qid, "abstain")
        if v0 == "correct": correct_arm0 += 1
        if v2 == "correct": correct_arm2 += 1
        if v2 == "abstain": abstain_arm2 += 1
        if v2 != "abstain" and v0 != "abstain":
            if v0 == "correct" and v2 == "correct":   a0c_a2c += 1
            elif v0 == "correct" and v2 != "correct": a0c_a2w += 1
            elif v0 != "correct" and v2 == "correct": a0w_a2c += 1
            else:                                       a0w_a2w += 1

    n = len(all_qids)
    print(f"\n=== G3 Results (n={n}) ===\n")
    print(f"Arm 0 accuracy (full coverage): {correct_arm0}/{n} = {100*correct_arm0/n:.1f}%")
    print(f"Arm 2 accuracy (admitted only): {correct_arm2}/{n-abstain_arm2} admitted = {100*correct_arm2/max(1,n-abstain_arm2):.1f}%")
    print(f"Arm 2 accuracy (full coverage, abstain=wrong): {correct_arm2}/{n} = {100*correct_arm2/n:.1f}%")
    print(f"Arm 2 abstain rate: {abstain_arm2}/{n} = {100*abstain_arm2/n:.1f}%")
    print()
    print(f"McNemar 2x2 (answered questions only, n={a0c_a2c+a0c_a2w+a0w_a2c+a0w_a2w}):")
    print(f"              Arm2 correct  Arm2 wrong")
    print(f"  Arm0 correct    {a0c_a2c:4d}          {a0c_a2w:4d}")
    print(f"  Arm0 wrong      {a0w_a2c:4d}          {a0w_a2w:4d}")
    b, c = a0c_a2w, a0w_a2c
    if b + c > 0:
        try:
            from scipy.stats import mcnemar as _mc
            result = _mc([[a0c_a2c, b], [c, a0w_a2w]], exact=(b+c < 25), correction=False)
            print(f"\nMcNemar statistic={result.statistic:.3f}, p={result.pvalue:.4f}")
        except ImportError:
            # Manual McNemar
            import math
            chi2 = (abs(b - c) - 1)**2 / (b + c) if b + c > 0 else 0
            # p-value from chi2 df=1 (approximation)
            print(f"\nMcNemar chi2 (manual, continuity corrected) = {chi2:.3f}")
            print("(install scipy for exact p-value)")
    diff = correct_arm2/n - correct_arm0/n
    print(f"\nAccuracy difference (Arm2 - Arm0, full coverage): {100*diff:+.1f}pp")
    if diff >= 0.15:
        print("→ Clears +15pp promotion bar ✓")
    else:
        print(f"→ Does NOT clear +15pp promotion bar (need +15pp, got {100*diff:+.1f}pp)")

    # Risk-coverage curve data
    print(f"\nRisk-coverage curve:")
    print(f"  Arm 0: single point (1.00 coverage, {1-correct_arm0/n:.3f} risk)")
    cov2_admitted = (n - abstain_arm2) / n
    risk2_admitted = 1 - correct_arm2 / max(1, n - abstain_arm2)
    risk2_full = 1 - correct_arm2 / n
    print(f"  Arm 2 at admitted coverage ({cov2_admitted:.2f}): risk={risk2_admitted:.3f}")
    print(f"  Arm 2 at full coverage (abstain=wrong): risk={risk2_full:.3f}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "arm2": cmd_arm2()
    elif cmd == "arm0": cmd_arm0()
    elif cmd == "score": cmd_score()
    else:
        print(__doc__)
