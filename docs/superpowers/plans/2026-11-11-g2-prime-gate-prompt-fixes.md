# G2-Prime: Gate text-search + schema drop-offsets + compositional few-shot

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the three failure modes that caused 0% gate admission across all model scales in G2: exact-offset provenance rejection (Route B), offset fields in the schema that models can't compute (Route D), and empty-array responses to compositional questions (Route C).

**Architecture:** Three independent changes that stack: (1) gate.py switches span resolution from byte-slice-and-compare to text-search-in-doc; (2) the span schema drops required `start`/`end` fields — the gate ignores them if present, the prompts stop teaching them; (3) the compositional few-shot example is replaced with one that emits real steps instead of `[]`. Each change has its own test delta. All three must pass `python -m unittest test_gate.py -v` before a harness run.

**Tech Stack:** Python 3.9+, stdlib only. No new dependencies.

**Spec:** `PREREG.md` §6 (G2 gate), `failure_taxonomy.md` (W1 thresholds), `LOG.md` 2026-11-11 three-model summary.

## Global Constraints

- stdlib only — no new imports anywhere
- All existing `test_gate.py` tests must still pass after each task
- `gate.py` public API (`Context`, `Gate`, `Status`, `ReasonCode`, `Verdict`, `run_trace`) must not change signatures
- `OPERATORS.md` documents the schema: update it in Task 1 (the gate is the ground truth; the doc follows the code)
- Log this run as "G2-prime" in `LOG.md` before running the harness — it is a new, unregistered experiment per `PREREG.md`'s instructions
- Do not change `PREREG.md` thresholds

## Review Focus

1. **Ambiguous text match** — if the same string appears twice in a doc (e.g. a year repeated), `str.find()` returns the first occurrence, which may not be the semantically intended one. The gate should ABSTAIN (not ADMIT or REJECT silently) when `text` matches multiple non-overlapping positions in the doc. Add test `test_span_text_ambiguous_match_abstains` in Task 1.
2. **Fabricated text** — a model claims `"text": "99"` on a doc that contains "99" somewhere but not in the semantically relevant position. Under text-search this would ADMIT; under offset-match it REJECTs. The gate cannot distinguish these — this is the documented tradeoff. The existing `test_span_text_mismatch` test must be updated: after Task 1, the same step now ADMITs (the text "99" does not appear in "revenue was 42"), or REJECTs via PROVENANCE_SPAN_NOT_FOUND if text is not in doc at all. Verify the test expectation is correct for the new semantics.
3. **Empty `text` field** — a model emits `{"ref_type": "span", "doc_id": "p1", "text": ""}`. Under text-search, `"".find(text)` always returns 0 — an empty string trivially matches. The gate should treat an empty `text` field as SCHEMA_INVALID. Add test in Task 1.
4. **`start`/`end` still present** — after Task 2, models trained on old few-shots may still emit `start`/`end`. The gate must silently ignore them (not reject). Existing tests that pass `start`/`end` via the `span()` helper must still pass.
5. **Compositional example with step refs** — the new few-shot example in Task 3 uses a `stepref` to chain two steps. If the model copies the structure but emits a wrong `step_id` reference (e.g. references `s2` from `s1`), it gets UNADMITTED_STEP_REF. The example must use the simplest chain (s1 → s2) and the step_id values must be clear.

---

### Task 1: Gate text-search provenance (Route B + part of D)

**Files:**
- Modify: `gate.py` — `Context.span_text()` and `Gate._resolve_leaf()`
- Modify: `test_gate.py` — update 3 existing tests, add 3 new tests

**Interfaces:**
- Produces: `Context.span_text(doc_id, text) -> Optional[str]` *(new signature — returns `text` if found, `None` if not, raises nothing)*
- `Gate._resolve_leaf()` calls new signature; `start`/`end` in the arg dict are silently ignored

**Schema change:** A span leaf is now `{"ref_type": "span", "doc_id": "<id>", "text": "<substring>"}`. The fields `start` and `end` are accepted but ignored if present (backward compat for any existing test fixtures).

- [ ] **Step 1: Update `Context.span_text()` signature and body in `gate.py`**

  New signature: `span_text(self, doc_id: str, text: str) -> Optional[str]`

  Body:
  ```python
  doc = self.docs.get(doc_id)
  if doc is None or not text:
      return None
  idx = doc.find(text)
  if idx == -1:
      return None
  # Ambiguous: text appears at more than one non-overlapping position
  if doc.find(text, idx + len(text)) != -1:
      return "AMBIGUOUS"   # sentinel; _resolve_leaf turns this into ABSTAIN
  return text
  ```

- [ ] **Step 2: Update `Gate._resolve_leaf()` span branch in `gate.py`**

  Replace the current block at lines ~338–352 with:
  ```python
  if arg["ref_type"] == "span":
      doc_id = arg.get("doc_id")
      text_claimed = arg.get("text")
      if doc_id is None or not text_claimed:
          return None, Verdict(Status.REJECT, ReasonCode.SCHEMA_INVALID,
                               message="span missing doc_id or text")
      result = self.context.span_text(doc_id, text_claimed)
      if result is None:
          return None, Verdict(Status.REJECT, ReasonCode.PROVENANCE_SPAN_NOT_FOUND,
                               message=f"{text_claimed!r} not found in {doc_id!r}")
      if result == "AMBIGUOUS":
          return None, Verdict(Status.ABSTAIN, ReasonCode.PROVENANCE_SPAN_NOT_FOUND,
                               message=f"{text_claimed!r} is ambiguous in {doc_id!r}")
      return self._coerce_span(result, expected_type)
  ```

  Note: reuse `PROVENANCE_SPAN_NOT_FOUND` for the ambiguous case — adding a new reason code would change the public enum. If you prefer a new code (`PROVENANCE_SPAN_AMBIGUOUS`), add it to `ReasonCode` and update `OPERATORS.md`.

- [ ] **Step 3: Update existing tests in `test_gate.py` that use offset-based `span()`**

  The `span()` helper still works — it passes `start`/`end` which are now ignored. Tests that relied on out-of-bounds offsets for PROVENANCE_SPAN_NOT_FOUND need to change their approach: use text that isn't in the doc instead. Specific tests to update:

  - `test_span_out_of_bounds` → change doc to `"5 hi"`, arg to `span("p1", 0, 1, text="999")` (text "999" not in doc) — still expects `PROVENANCE_SPAN_NOT_FOUND`
  - `test_span_text_mismatch` → doc is `"revenue was 42"`, claimed text `"99"` — "99" is NOT in that doc, so still expects `PROVENANCE_SPAN_NOT_FOUND` (was `PROVENANCE_SPAN_TEXT_MISMATCH` — reason code changes, verify the test)
  - `test_negative_span_offsets_rejected` → change to use text not in doc: `span("p1", -1, 4, text="xyz")` on doc `"true"` — still PROVENANCE_SPAN_NOT_FOUND
  - `test_start_greater_than_end_rejected` → same approach

  The helper `span(doc_id, start, end, text=None)` can stay as-is — the gate ignores start/end.

- [ ] **Step 4: Add 3 new tests to `test_gate.py` in `TestProvenance`**

  ```python
  def test_span_text_search_finds_text_at_nonzero_offset(self):
      """Text is not at offset 0 but IS in the doc — must ADMIT."""
      g = Gate(ctx(p1="revenue was 42"))
      v = g.step({"step_id": "s1", "operator": "negate",
                  "args": [{"ref_type": "span", "doc_id": "p1", "text": "42"}]})
      # "42" coerces to number, negate expects bool — TYPE_MISMATCH, NOT provenance error
      self.assertEqual(v.reason_code, ReasonCode.TYPE_MISMATCH)

  def test_span_text_not_in_doc_rejected(self):
      g = Gate(ctx(p1="revenue was 42"))
      v = g.step({"step_id": "s1", "operator": "negate",
                  "args": [{"ref_type": "span", "doc_id": "p1", "text": "999"}]})
      self.assertEqual(v.reason_code, ReasonCode.PROVENANCE_SPAN_NOT_FOUND)

  def test_span_text_ambiguous_match_abstains(self):
      """'1907' appears twice — gate cannot know which occurrence was intended."""
      g = Gate(ctx(p1="born 1907 died 1907"))
      v = g.step({"step_id": "s1", "operator": "temporal_order",
                  "args": [{"ref_type": "span", "doc_id": "p1", "text": "1907"},
                            {"ref_type": "span", "doc_id": "p1", "text": "1907"}],
                  "params": {"op": "before"}})
      self.assertNotEqual(v.status, Status.ADMIT)

  def test_span_empty_text_rejected(self):
      g = Gate(ctx(p1="hello"))
      v = g.step({"step_id": "s1", "operator": "negate",
                  "args": [{"ref_type": "span", "doc_id": "p1", "text": ""}]})
      self.assertEqual(v.reason_code, ReasonCode.SCHEMA_INVALID)
  ```

- [ ] **Step 5: Run tests**

  ```
  python -m unittest test_gate.py -v
  ```
  Expected: all tests pass. If `test_span_text_mismatch` or offset-based tests fail, fix the assertions (the behavior changed intentionally — update the expectation, not the gate).

- [ ] **Step 6: Commit**

  ```
  git add gate.py test_gate.py
  git commit -m "gate: text-search provenance replaces exact-offset matching (Route B+D)"
  ```

---

### Task 2: Drop `start`/`end` from prompts and system description (Route D)

**Files:**
- Modify: `prompts/formalize_system.txt`
- Modify: `prompts/formalize_fewshot.txt` (examples 1 and 3 — remove start/end from all span args)

**Interfaces:**
- Consumes: Task 1's new span schema `{"ref_type": "span", "doc_id": "...", "text": "..."}`
- Produces: updated prompt files consumed by `harness.py run_mode_a`

- [ ] **Step 1: Update `prompts/formalize_system.txt`**

  Change the span leaf definition from:
  ```
  {"ref_type": "span", "doc_id": "<id from the context>", "start": <int>, "end": <int>, "text": "<the exact substring, for your own and the checker's benefit>"}
  ```
  to:
  ```
  {"ref_type": "span", "doc_id": "<id from the context>", "text": "<the exact substring as it appears in that document>"}
  ```

  Remove the rule: *`"start"/"end" are character offsets... Count characters carefully...`*

  Replace with: *`"text" must be an exact substring of the named document as it appears in the context. Copy it verbatim — do not paraphrase, truncate, or normalize.`*

- [ ] **Step 2: Update `prompts/formalize_fewshot.txt` examples 1 and 3**

  Remove `"start"` and `"end"` from every span arg in examples 1 and 3. Example 1 becomes:
  ```json
  [
    {"step_id": "s1", "operator": "temporal_order",
     "args": [
       {"ref_type": "span", "doc_id": "p0", "text": "October 5 1985"},
       {"ref_type": "span", "doc_id": "p1", "text": "1991-03-12"}
     ],
     "params": {"op": "before"}, "result_type": "bool", "is_final": false}
  ]
  ```
  Example 3 similarly — just remove `"start"` and `"end"`.

- [ ] **Step 3: Run tests** (prompt changes don't affect gate tests, but confirm nothing broke)

  ```
  python -m unittest test_gate.py -v
  ```
  Expected: all pass.

- [ ] **Step 4: Commit**

  ```
  git add prompts/formalize_system.txt prompts/formalize_fewshot.txt
  git commit -m "prompts: drop start/end offset fields from span schema (Route D)"
  ```

---

### Task 3: Add compositional few-shot example (Route C)

**Files:**
- Modify: `prompts/formalize_fewshot.txt` — replace example 2 (empty-array compositional) with a two-step chain

**Interfaces:**
- Consumes: Task 2's offset-free span schema
- Produces: updated few-shot that shows the model a real compositional chain

The problem: example 2 is a compositional question that correctly emits `[]`, teaching the model that compositional = empty array. 21/25 compositional questions in G2 got `[]`. The model needs to see that compositional questions with a supported operator in the chain DO need steps.

- [ ] **Step 1: Replace example 2 in `prompts/formalize_fewshot.txt`**

  Replace the current example 2 (Empress Xu / empty array) with:

  ```
  EXAMPLE 2

  Context:
  [p0] Empress Xu's husband was the Yongle Emperor.
  [p1] The Yongle Emperor was born in Nanjing.
  [p2] Emperor Hongxi was born in Nanjing.

  Question: Were Empress Xu's husband and Emperor Hongxi born in the same city?
  Expected answer type: bool

  Output:
  [
    {"step_id": "s1", "operator": "entity_equal",
     "args": [
       {"ref_type": "span", "doc_id": "p1", "text": "Nanjing"},
       {"ref_type": "span", "doc_id": "p2", "text": "Nanjing"}
     ],
     "result_type": "bool", "is_final": true}
  ]

  (This question has two retrieval hops — find husband, find birthplace — then one
  operator step: entity_equal on the two birthplaces. Use steps whenever the question
  ends in a comparison, count, or arithmetic, even if the retrieval leading up to it
  is implicit. Only emit [] when the question is PURE retrieval with no operator at the
  end — e.g. "What city was X born in?" has no operator; "Were X and Y born in the same
  city?" ends in entity_equal.)
  ```

  Keep the original Empress Xu / `[]` example as a 4th example (append it after example 3) so the model still sees the pure-retrieval → empty-array case. This teaches the distinction explicitly.

- [ ] **Step 2: Run tests**

  ```
  python -m unittest test_gate.py -v
  ```
  Expected: all pass (prompt change only).

- [ ] **Step 3: Commit**

  ```
  git add prompts/formalize_fewshot.txt
  git commit -m "prompts: add compositional entity_equal example, clarify [] vs step distinction (Route C)"
  ```

---

### Task 4: Log as G2-prime and run harness

**Files:**
- Modify: `LOG.md` — add G2-prime entry before running
- Run: `harness.py --mode A` with qwen2.5:7b (primary) and optionally 14b

- [ ] **Step 1: Add G2-prime entry to `LOG.md`**

  Append before running:
  ```
  ## 2026-11-11: G2-prime — text-search gate + no-offset schema + compositional example
  
  Unregistered follow-on to G2. Changes: (1) gate provenance switches to text-search
  (Route B), (2) span schema drops start/end (Route D), (3) compositional few-shot
  example replaced (Route C). Same input: sample_2wiki_decomposable.jsonl, n=72.
  Primary model: qwen2.5:7b. Hypothesis: SPAN_EXTRACTION_ERROR drops to near-zero;
  MISSING_STEP (empty) drops for compositional. If correct-formalization rate >= 30%,
  G2-prime promotes — this reverses the G2 kill verdict on architectural grounds.
  ```

- [ ] **Step 2: Run harness (GPU)**

  ```
  python harness.py --mode A --endpoint http://localhost:11434/v1 \
      --model qwen2.5:7b \
      --input sample_2wiki_decomposable.jsonl \
      --out runs/mode_a_qwen25_7b_v2.jsonl
  ```

- [ ] **Step 3: Score with failure taxonomy script**

  Run the same classify_run() analysis used in G2. Report:
  - Parse rate
  - Gate ADMIT (non-trivial, non-empty)
  - SPAN_EXTRACTION_ERROR, MISSING_STEP, WRONG_OPERANDS counts
  - Correct-formalization rate (ADMIT / total attempted)

- [ ] **Step 4: Update LOG.md with results, commit, push**
