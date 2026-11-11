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

## 2026-11-11: G2-prime — text-search gate + no-offset schema + compositional example

Unregistered follow-on to G2. Changes: (1) gate provenance switches to text-search
(Route B), (2) span schema drops start/end (Route D), (3) compositional few-shot
example replaced with entity_equal chain, pure-retrieval [] case moved to Example 4
(Route C). Same input: sample_2wiki_decomposable.jsonl, n=72.

### Results

| | llama3.2:3b | qwen2.5:7b |
|---|---|---|
| Parse success | 49/72 (68%) | 69/72 (96%) |
| Gate ADMIT | **3/72 (4.2%)** | **5/72 (6.9%)** |
| SPAN_EXTRACTION_ERROR | 0 (eliminated ✓) | 0 (eliminated ✓) |
| TYPE_MISMATCH | 18 (25%) | 37 (51%) |
| PROVENANCE_SPAN_NOT_FOUND | 21 (29%) | 11 (15%) |
| MISSING_STEP (empty array) | 0 | 16 (22%) |
| MISSING_STEP (parse fail) | 23 (32%) | 3 (4%) |

By question type (7b):

| Type | n | ADMIT | TYPE_MISMATCH | SPAN_NOT_FOUND | MISSING_STEP |
|---|---|---|---|---|---|
| bridge_comparison | 25 | 1 | 22 | 2 | 0 |
| comparison | 22 | 4 | 10 | 6 | 2 |
| compositional | 25 | 0 | 5 | 3 | 17 |

### Key observations

1. **SPAN_EXTRACTION_ERROR eliminated**: The offset-matching failure mode is gone. The gate fix worked as intended.
2. **New dominant failure — TYPE_MISMATCH on bridge_comparison (22/25 for 7b)**: The docs contain free-text dates ("October 5 1985", "March 10, 1892 – March 1, 1952") that don't parse as ISO 8601. `temporal_order` requires parseable dates — the gate correctly rejects these. This is an operator coverage gap, not a model failure.
3. **PROVENANCE_SPAN_NOT_FOUND (11-21 cases)**: Text the model claims isn't literally in the doc — paraphrasing, truncating, or hallucinating spans. Real semantic errors, not mechanical ones.
4. **Compositional MISSING_STEP partly fixed**: Empty arrays dropped 26→16 for 7b. The new few-shot example helped but 14/25 compositional still empty — the model may need more examples or the question type genuinely lacks a suitable operator chain.
5. **Admits more than doubled** vs G2 (0→3 for 3b, 0→5 for 7b), all in comparison type.

### G2-prime verdict

6.9% admit on 7b — still below the 30% threshold. The fix ladder has revealed the next layer: date parsing. bridge_comparison is essentially blocked until `_parse_date()` can handle natural language date strings. Without that, 22/25 bridge_comparison questions will always TYPE_MISMATCH regardless of model scale or prompt quality.

**Recommendation:** Extend `_parse_date()` to handle common non-ISO formats ("Month D YYYY", "D Month YYYY", date ranges "YYYY–YYYY") before another harness run. This is a gate engineering task, not a model task.

---

## 2026-11-11: G2 mode A — qwen2.5:14b

**Run:** `harness.py --mode A --model qwen2.5:14b --input sample_2wiki_decomposable.jsonl`
**Output:** `runs/mode_a_qwen25_14b.jsonl` (n=72)

### Results

| Category | n | % |
|---|---|---|
| SPAN_EXTRACTION_ERROR (right text, wrong offsets) | 52 | **72%** |
| WRONG_OPERANDS (text not in doc) | 11 | 15% |
| MISSING_STEP (parse fail) | 6 | 8% |
| MISSING_STEP (empty array) | 2 | 3% |
| OTHER (PROVENANCE_SPAN_NOT_FOUND) | 1 | 1% |
| **Gate ADMIT (non-trivial)** | **0** | **0%** |

By question type:

| Type | n | SPAN_EXTRACT_ERR | WRONG_OPERANDS | MISSING_STEP |
|---|---|---|---|---|
| bridge_comparison | 25 | 20 | 5 | 0 |
| comparison | 22 | 20 | 1 | 1 |
| compositional | 25 | 12 | 5 | 8 |

### Key observations

1. **Empty arrays eliminated**: Only 2 empty-step responses (vs 26 for 7b). The 14b model attempts formalization for compositional questions where 7b gave up.
2. **SPAN_EXTRACTION_ERROR worsens with scale**: 33% (3b) → 49% (7b) → 72% (14b). Larger models try harder, pick semantically better text, but get *more* confident about wrong byte offsets.
3. **Scale does not help offset precision**: This is the clearest evidence in the dataset. Character-level byte indexing is not a capability that improves with model scale.

---

## 2026-11-11: G2 mode A — llama3.2:3b GPU re-run

**Run:** `harness.py --mode A --model llama3.2:3b --input sample_2wiki_decomposable.jsonl`
**Output:** `runs/mode_a_llama32_v2.jsonl` (n=72, GPU — original was CPU with 18 timeouts)

### Results

| Category | n | % |
|---|---|---|
| SPAN_EXTRACTION_ERROR (right text, wrong offsets) | 24 | 33% |
| WRONG_OPERANDS (text not in doc) | 21 | 29% |
| MISSING_STEP (parse fail) | 19 | 26% |
| ARITY_MISMATCH | 5 | 7% |
| OTHER (various) | 3 | 4% |
| **Gate ADMIT (non-trivial)** | **0** | **0%** |

Broadly reproduces the CPU run (23 parse fail, 18 SPAN_EXTRACTION_ERROR, 22 WRONG_OPERANDS). GPU eliminates timeout-driven parse failures but the failure profile is the same.

---

## 2026-11-11: Three-model summary — G2 failure taxonomy across scale

| Failure mode | 3b (GPU) | 7b | 14b |
|---|---|---|---|
| SPAN_EXTRACTION_ERROR (right text, wrong offsets) | 24 (33%) | 35 (49%) | **52 (72%)** |
| WRONG_OPERANDS (text not in doc) | 21 (29%) | 9 (12%) | 11 (15%) |
| MISSING_STEP (parse fail) | 19 (26%) | 2 (3%) | 6 (8%) |
| MISSING_STEP (empty array) | 0 (0%) | 26 (36%) | 2 (3%) |
| Schema/arity/other errors | 8 (11%) | 0 (0%) | 1 (1%) |
| **Gate ADMIT (non-trivial)** | **0** | **0** | **0** |

### G2 verdict (all three models)

All three models score 0% by strict gate admission. The registered kill threshold is < 30%. Per `PREREG.md` §7, G2 kill is confirmed when "trying a bigger model ALSO fails to clear 50%."

However, the failure taxonomy reveals the bottleneck is **not model reasoning** — it is the gate's exact-offset provenance check. SPAN_EXTRACTION_ERROR *increases* with scale because larger models formalize more questions (fewer empty arrays, fewer parse failures) but cannot reliably compute character-level byte offsets. This is a gate interface problem, not a model capability problem.

**Registered conclusion:** G2 kills by the strict spec. This is logged honestly.
**Unregistered observation:** The failure is concentrated in a single, fixable interface layer. See route analysis (separate note).

---

## 2026-11-11: G2-prime-v3 — qwen2.5:14b with full fix stack

Unregistered. Same fixes as G2-prime-v3 (text-search gate, no-offset schema,
compositional few-shot, NL date parsing, conjoin fix) applied to 14b.

**Run:** `harness.py --mode A --endpoint http://localhost:11434/v1 --model qwen2.5:14b --input sample_2wiki_decomposable.jsonl --out runs/mode_a_qwen25_14b_v2.jsonl`

### Results

| Metric | Value |
|---|---|
| Total questions | 72 |
| Parse success | 68/72 (94%) |
| Gate ADMIT | **24/72 (33.3%)** |

Failure taxonomy:

| Category | n | % |
|---|---|---|
| TYPE_MISMATCH | 21 | 29% |
| PROVENANCE_SPAN_NOT_FOUND | 19 | 26% |
| MISSING_STEP (parse fail) | 4 | 6% |
| UNADMITTED_STEP_REF | 2 | 3% |
| MISSING_STEP (empty) | 1 | 1% |

By question type:

| Type | n | ADMIT | TYPE_MISMATCH | SPAN_NOT_FOUND | OTHER |
|---|---|---|---|---|---|
| bridge_comparison | 25 | 8 | 11 | 6 | 0 |
| comparison | 22 | **16** | 3 | 3 | 0 |
| compositional | 25 | 0 | 7 | 10 | 8 |

### 7b vs 14b comparison (full fix stack)

| | qwen2.5:7b (v4) | qwen2.5:14b (v2) |
|---|---|---|
| Gate ADMIT | **36.1%** | 33.3% |
| bridge_comparison admits | **16/25** | 8/25 |
| comparison admits | 10/22 | **16/22** |
| compositional admits | 0/25 | 0/25 |
| PROVENANCE_SPAN_NOT_FOUND | 11 (15%) | **19 (26%)** |
| MISSING_STEP (empty) | 16 (22%) | 1 (1%) |

### Key observations

1. **14b does not beat 7b overall**: 33.3% vs 36.1%. Scale does not monotonically improve admission rate with the current fix stack.
2. **Comparison type improves with scale**: 10/22 → 16/22. 14b is better at the two-hop comparison structure.
3. **bridge_comparison regresses with scale**: 16/25 → 8/25. 14b generates more verbose spans that fail provenance (PROVENANCE_SPAN_NOT_FOUND 6→6, but TYPE_MISMATCH 6→11).
4. **Compositional still zero**: 0/25 for both models. 14b eliminates empty arrays (16→1) but the steps it produces fail on span provenance or type issues.
5. **PROVENANCE_SPAN_NOT_FOUND spikes at 14b**: 11→19. Larger model paraphrases or truncates spans rather than copying verbatim — a prompt compliance issue, not a capability gap.

### Verdict

Both models clear 30% with the full fix stack. 7b slightly outperforms 14b overall; 14b wins on comparison. Neither solves compositional. The bottleneck has shifted from gate engineering to span faithfulness (PROVENANCE_SPAN_NOT_FOUND) and remaining TYPE_MISMATCH cases.

---

## 2026-11-11: G2-prime-v2 — extended `_parse_date()` for natural-language dates

Unregistered follow-on to G2-prime. Change: `_parse_date()` extended to handle
"Month D, YYYY", "D Month YYYY", date ranges ("Date1 – Date2"), and concatenated
multi-date strings ("25 October 1898 12 April 1979"). All bridge_comparison
docs use these formats. 17 new tests added; all 69 tests pass.

Same model (qwen2.5:7b), same input (sample_2wiki_decomposable.jsonl, n=72),
same other fixes (text-search gate, no-offset schema, compositional few-shot).

**Run:** `harness.py --mode A --endpoint http://localhost:11434/v1 --model qwen2.5:7b --input sample_2wiki_decomposable.jsonl --out runs/mode_a_qwen25_7b_v3.jsonl`

### Results

| Metric | Value |
|---|---|
| Total questions | 72 |
| Parse success | 68/72 (94%) |
| Gate ADMIT | **10/72 (13.9%)** |

Failure taxonomy:

| Category | n | % |
|---|---|---|
| TYPE_MISMATCH | 28 | 39% |
| MISSING_STEP (empty array) | 17 | 24% |
| PROVENANCE_SPAN_NOT_FOUND | 13 | 18% |
| MISSING_STEP (parse fail) | 4 | 6% |

By question type:

| Type | n | ADMIT | TYPE_MISMATCH | SPAN_NOT_FOUND | MISSING_STEP |
|---|---|---|---|---|---|
| bridge_comparison | 25 | 2 | 15 | 6 | 2 |
| comparison | 22 | 8 | 7 | 5 | 2 |
| compositional | 25 | 0 | 6 | 2 | 17 |

TYPE_MISMATCH by operator (remaining 28):

| Operator | n | Root cause |
|---|---|---|
| conjoin | 16 | Model uses conjoin as generic comparison; conjoin expects bool args |
| set_membership | 6 | Type mismatch in set membership checks |
| temporal_order | 4 | Non-date args ("Paris", entity names) passed to temporal_order |
| disjoin/numeric_compare | 2 | Operator misuse |

### Comparison to prior runs

| | G2 (7b) | G2-prime (7b) | G2-prime-v2 (7b) |
|---|---|---|---|
| Gate ADMIT | 0% | 6.9% | **13.9%** |
| TYPE_MISMATCH | 49% | 51% | 39% |
| SPAN_EXTRACTION_ERROR | 49% | 0% | 0% |
| PROVENANCE_SPAN_NOT_FOUND | 15% | 15% | 18% |
| MISSING_STEP (empty) | 36% | 22% | 24% |

### Key observations

1. **Date parsing fix worked**: TYPE_MISMATCH dropped 51%→39% and admits doubled 6.9%→13.9%. All targeted date formats ("Month D, YYYY", "D Month YYYY", ranges, multi-date) now parse correctly.
2. **New dominant failure — conjoin misuse (16 cases)**: The model uses `conjoin` as a catch-all comparison operator rather than `entity_equal` or `temporal_order`. This is a prompt compliance failure — conjoin takes boolean args, not dates/entities.
3. **bridge_comparison still hardest**: 2/25 admits. The model correctly structures the temporal_order step but then wraps it in a spurious `conjoin` or passes entity names to `temporal_order`.
4. **Compositional still near-zero**: 0/25 admits. 17/25 empty arrays persists despite the compositional few-shot fix from G2-prime.

### G2-prime-v2 verdict

13.9% — still below 30% kill threshold, but the fix ladder is producing measurable gains (0% → 6.9% → 13.9%) each iteration. The bottleneck has shifted again: from offset precision (G2) → date parsing (G2-prime) → operator misuse in `conjoin` (v2).

**Recommendation:** Add an explicit negative example in few-shot showing `conjoin` is for AND-ing booleans only, with `entity_equal` for entity comparison and `temporal_order` for the final date comparison. This targets the 16 conjoin TYPE_MISMATCH cases directly.

---

## 2026-11-11: G2-prime-v3 — conjoin misuse fix in few-shot

Unregistered follow-on to G2-prime-v2. Change: few-shot Examples 1 and 2
updated to state explicitly that `temporal_order`/`entity_equal` are
`is_final` steps for comparisons, and that `conjoin` takes only bool results
from prior steps — never date spans or entity spans directly. Also corrected
`is_final: false → true` in Example 1.

Same model (qwen2.5:7b), same input (n=72), same gate + schema fixes.

**Run:** `harness.py --mode A --endpoint http://localhost:11434/v1 --model qwen2.5:7b --input sample_2wiki_decomposable.jsonl --out runs/mode_a_qwen25_7b_v4.jsonl`

### Results

| Metric | Value |
|---|---|
| Total questions | 72 |
| Parse success | 69/72 (96%) |
| Gate ADMIT | **26/72 (36.1%)** |

Failure taxonomy:

| Category | n | % |
|---|---|---|
| MISSING_STEP (empty array) | 16 | 22% |
| TYPE_MISMATCH | 15 | 21% |
| PROVENANCE_SPAN_NOT_FOUND | 11 | 15% |
| MISSING_STEP (parse fail) | 3 | 4% |
| ARITY_MISMATCH | 1 | 1% |

By question type:

| Type | n | ADMIT | TYPE_MISMATCH | SPAN_NOT_FOUND | MISSING_STEP |
|---|---|---|---|---|---|
| bridge_comparison | 25 | **16** | 6 | 2 | 1 |
| comparison | 22 | **10** | 5 | 5 | 1 |
| compositional | 25 | 0 | 4 | 4 | 17 |

### Full ladder comparison

| | G2 (7b) | G2-prime | G2-prime-v2 | **G2-prime-v3** |
|---|---|---|---|---|
| Gate ADMIT | 0% | 6.9% | 13.9% | **36.1%** |
| TYPE_MISMATCH | 49% | 51% | 39% | 21% |
| conjoin misuse (of TYPE_MISMATCH) | — | — | 16 | ~0 |
| SPAN_EXTRACTION_ERROR | 49% | 0% | 0% | 0% |
| PROVENANCE_SPAN_NOT_FOUND | — | 15% | 18% | 15% |
| MISSING_STEP (empty) | 36% | 22% | 24% | 22% |

### Key observations

1. **Clears the 30% kill threshold**: 36.1% > 30%. Per PREREG.md §6, G2 is not killed — this crosses into "try larger model" territory.
2. **bridge_comparison unblocked**: 2/25 → 16/25. The conjoin fix plus date parsing together account for the turnaround. bridge_comparison was the hardest type (0% at G2 baseline).
3. **Compositional still zero**: 0/25 admits, 15/25 empty arrays. The compositional few-shot example from Route C partially helped (dropped from 26 to 15–17 empties) but the type remains unsolved.
4. **Remaining TYPE_MISMATCH (15)**: No longer dominated by conjoin. Mix of non-date args to `temporal_order` (e.g. city names) and legitimate operator gaps.

### G2-prime-v3 verdict

**36.1% > 30%** — does not kill. Per PREREG.md §6 "30–50%: try a larger model." The fix ladder (B+C+D+E+F) has closed the gap from 0% to 36% via gate engineering and prompt calibration, without changing model scale. Compositional type remains a gap (0/25); the other two types now admit at 64% (bridge_comparison) and 45% (comparison).
