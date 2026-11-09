LATCH

A hard, mechanical, per-step admission gate for small-model reasoning — the single-model
pilot kit. See docs/HISTORY.md for how this idea developed and why it's still a pilot,
not a project.

## What Latch is

The idea: instead of letting a small language model (SLM) reason in free text, make it
emit each reasoning step as an instantiation of a small closed set of typed operators
(numeric_compare, count, temporal_order, arithmetic, etc. — see OPERATORS.md). A
mechanical gate ("Latch") checks each step: is it a well-typed application of a real
operator to arguments that trace to a verbatim span in the provided context or to a
prior admitted step? ADMIT, REJECT(reason), or ABSTAIN(reason) — never "probably right."

This is explicitly **not** a truth-checker. It catches malformed, ungrounded, or
mistyped reasoning. It does **not** catch well-typed-but-wrong reasoning (see
OPERATORS.md's "Known false-pass class"). The open research question — does this
actually help a small model, and does it help more when paired with a second small
model instead of one — is untested. This kit exists to test the testable parts cheaply,
without requiring anyone to train or run a model to find out whether the scaffolding
itself holds together.

## Status: pilot, not promoted

This started as sprawl (raw, unscheduled research material — see `sprawl/README.md` in
the main vault/workspace for what that means) and is being filed here, as a named
project folder, at Kristian's explicit instruction. **That is a filing decision, not a
priority decision.** Latch sits behind Track A/B job search, graduation, and attest.
Nothing in this repo should be read as "in progress toward a deliverable" — it's a
tested, honest scaffold that's ready to pick up IF and WHEN there's spare high-energy
time for it, per PREREG.md's time-boxed stage gates.

## What's actually been tested vs. what hasn't

**Tested, with real passing tests, no model required:**
- `gate.py` + `test_gate.py` — 43 unit tests, the mechanical gate itself.
- `harness.py` + `test_harness_mock.py` — 17 unit tests, the model-calling scaffold,
  tested against a mock endpoint (malformed outputs, adversarial span mismatches, etc.).
- `coverage_finqa.py` — run against the real FinQA test set (1,147 examples): 99.7%
  operator-vocabulary coverage. This is a real number from real data, not a projection.
- `sample_2wiki.py` — ran against the real, live 2WikiMultihopQA validation split via
  HuggingFace's datasets-server API: a real, reproducible 100-question stratified sample
  exists in `sample_2wiki.csv`/`.jsonl`.

**Not tested — needs a model, which this kit deliberately does not run:**
- Whether a 1-4B model can actually formalize questions into valid steps at a useful
  rate (the W1 risk — see `failure_taxonomy.md`'s decision thresholds).
- Whether Arm 2 (gated) beats Arm 0 (free-form CoT) at matched compute (see
  `PREREG.md`'s G3 stage gate).
- The human annotation pass on `annotation_sheet.csv` that would produce a real 2Wiki
  "cleanly decomposable" coverage number (G1) — this needs Kristian's own judgment calls,
  not a script.

## File map

| File | What it is |
|---|---|
| `docs/HISTORY.md` | The full narrative: how this idea came out of GIN/SEAR, two literature-digging rounds, a red-team, and this construction round. Read this for "why does this exist." |
| `docs/RUNBOOK.md` | The pilot kit's own run order, time budget per step, and local-model-endpoint start commands. |
| `CITATIONS.md` | Every citation used anywhere in this project, with a URL, a one-line description, and a verification status tag. |
| `VERIFICATION.md` | The specific round-2 task of closing open citation questions from the red-team — overlaps with CITATIONS.md but keeps the original per-item verification writeups. |
| `OPERATORS.md` | The closed operator set specification — the actual design document for what Latch can and cannot express. |
| `gate.py` / `test_gate.py` | The reference mechanical gate, pure Python, 43 tests. |
| `coverage_finqa.py` | FinQA gold-program coverage scanner; real run results in `data/`. |
| `sample_2wiki.py` / `sample_2wiki.csv` / `.jsonl` | 2WikiMultihopQA sampler and its real output. |
| `ANNOTATION_GUIDE.md` / `annotation_sheet.csv` | Manual decomposability-annotation protocol and template. |
| `harness.py` / `prompts/` / `test_harness_mock.py` | Model-agnostic formalization harness + its tests. |
| `failure_taxonomy.md` / `scoring_sheet.csv` | Manual trace-review categories and template. |
| `PREREG.md` | Pre-registration: hypotheses, arms, stage gates, kill/promote criteria. |

## Running it

See `docs/RUNBOOK.md` for the exact command sequence, time budget per step, and how to
point the harness at a local model (ollama/llama.cpp/vLLM) or an API.
