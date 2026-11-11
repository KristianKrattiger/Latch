# LOG.md — Experiment log for the Latch pilot

Append entries chronologically. Do not silently edit a prior entry if you change a threshold
or methodology after seeing data — add a new entry and cross-reference.

---

## 2026-11-11: G2 mode A — llama3.2:3b (prior machine, reproduced locally)

**Run:** `harness.py --mode A --model llama3.2:3b --input sample_2wiki_decomposable.jsonl`
**Output:** `runs/mode_a_llama32.jsonl` (n=72)

### Results

| Metric | Value |
|---|---|
| Total questions | 72 |
| Parse success | 49/72 (68%) |
| Gate ADMIT (non-trivial) | 0/72 (0%) |
| Correct (manual review) | 5/49 (10.2%) |

Failure taxonomy:

| Category | n | % |
|---|---|---|
| MISSING_STEP (parse fail) | 23 | 32% |
| WRONG_OPERANDS (text not in doc) | 22 | 31% |
| SPAN_EXTRACTION_ERROR (right text, wrong offsets) | 18 | 25% |
| UNADMITTED_STEP_REF | 5 | 7% |
| SCHEMA_INVALID | 2 | 3% |
| ARITY_MISMATCH | 2 | 3% |

**G2 verdict:** 10.2% < 30% kill threshold. Per `failure_taxonomy.md` W1: try one 8B model before deciding.

---

## 2026-11-11: G2 mode A — qwen2.5:7b

**Run:** `harness.py --mode A --model qwen2.5:7b --input sample_2wiki_decomposable.jsonl`
**Output:** `runs/mode_a_qwen25_7b.jsonl` (n=72)
**Compute:** 72 forward passes, 149332 input tokens, 14740 output tokens (164072 total)

### Results

| Metric | Value |
|---|---|
| Total questions | 72 |
| Parse success | 70/72 (97%) |
| Gate ADMIT (non-trivial, non-empty steps) | 0/72 (0%) |
| Trivial admits (empty step array) | 26/72 (36%) |

Failure taxonomy (automated, using gate + text-in-doc check):

| Category | n | % |
|---|---|---|
| SPAN_EXTRACTION_ERROR (right text, wrong offsets) | 35 | 49% |
| MISSING_STEP (empty array) | 26 | 36% |
| WRONG_OPERANDS (text not in doc) | 9 | 12% |
| MISSING_STEP (parse fail) | 2 | 3% |

By question type:

| Type | n | SPAN_EXTRACT_ERR | MISSING_STEP (empty) | WRONG_OPERANDS |
|---|---|---|---|---|
| bridge_comparison | 25 | 19 | 0 | 6 |
| comparison | 22 | 14 | 5 | 2 |
| compositional | 25 | 2 | 21 | 1 |

### Key observations

1. **Schema competence**: 97% parse rate, zero schema/arity errors. The 7b model fully understands the operator vocabulary.
2. **Dominant failure — SPAN_EXTRACTION_ERROR**: In 35/44 rejected cases, the claimed span text *does* exist in the referenced document — the model just got the byte offsets wrong. These are mechanical index errors, not reasoning failures.
3. **Compositional MISSING_STEP**: 21/25 compositional questions received empty `[]` arrays. The model appears to decide "no formalization needed" for multi-hop entity retrieval — a prompt compliance failure, not a capability gap.
4. **WRONG_OPERANDS halved** vs 3b (31% → 12%): Better span selection at 7b scale.

### Comparison to 3b

| | llama3.2:3b | qwen2.5:7b |
|---|---|---|
| Parse rate | 68% | 97% |
| Schema errors | 9 (12%) | 0 (0%) |
| WRONG_OPERANDS | 22 (31%) | 9 (12%) |
| SPAN_EXTRACTION_ERROR | 18 (25%) | 35 (49%) |
| MISSING_STEP (empty) | 0 | 26 (36%) |

The failure mode has qualitatively shifted: 3b couldn't form valid JSON or pick correct spans; 7b understands the schema and mostly picks correct text, but fails on byte offsets and sometimes emits empty arrays.

### G2 verdict

Strict gate: 0% for both. But the failure taxonomy shift indicates **the bottleneck is not model reasoning or schema understanding — it is (a) the gate's exact-offset provenance check and (b) the few-shot prompt not enforcing non-empty steps for compositional questions.**

Per `PREREG.md` §6: "G2 kill: < 30%" — both models technically kill. However, the `failure_taxonomy.md` W1 note says the 8B test is to determine *whether the problem is model scale specifically*. The 7b evidence says **it is not** — the failure mode is offset precision + prompt compliance, both of which are fixable at the gate/prompt layer without changing model scale.

**Recommendation (not a registered decision):** Before calling G2 killed, consider:
- Relaxing gate provenance from exact-offset to text-search-within-doc (fixes ~49% of 7b failures)
- Adding explicit few-shot example for compositional type with non-empty steps (fixes ~36% of 7b failures)
- If either fix clears 30%+ on a re-run, that is a gate/prompt calibration issue, not a model failure

This would be a **new, unregistered experiment** — log it separately if run.

---

## 2026-11-11: G2 mode A — qwen2.5:14b (pending)

Run in progress. See `runs/mode_a_qwen25_14b.jsonl`.

---

## 2026-11-11: G2 mode A — llama3.2:3b local re-run (pending)

Re-running to confirm reproducibility on this GPU machine. See `runs/mode_a_llama32_v2.jsonl`.
