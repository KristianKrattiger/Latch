# Failure Taxonomy for Manual Trace Review

Use this when hand-scoring 20-30 traces from `harness.py` mode A or B output (per
round-2 Task C4). For each step in a trace, pick exactly one category. Report the rate
of each category **per question type** (comparison/inference/compositional/bridge_comparison),
not just overall -- round 1's W3 finding is that difficulty varies enormously by type, and a
flat average will hide that.

| Code | Category | Definition | Distinguish from |
|---|---|---|---|
| `WRONG_OPERATOR` | Wrong operator | The model picked an operator that doesn't match what the question needs (e.g. `numeric_compare` where `arg_extreme` was needed), even though the chosen operator is internally well-typed. | `GATE_BUG` (not a model error) |
| `WRONG_OPERANDS` | Wrong operands | The model picked the right operator but the wrong spans/steps as inputs (grabbed the wrong number from the context). | `SPAN_EXTRACTION_ERROR` (offsets vs. content) |
| `SPAN_EXTRACTION_ERROR` | Span-extraction error | The model's claimed offsets don't match the text it intended to reference, or it miscounted characters -- a mechanical slip, not a reasoning error. Gate should catch this as `PROVENANCE_SPAN_TEXT_MISMATCH` or `PROVENANCE_SPAN_NOT_FOUND`; if it admitted anyway, that IS a `GATE_BUG`. | `WRONG_OPERANDS` (right idea, wrong execution vs. wrong idea) |
| `TYPE_ERROR` | Type error | The model tried to use a value of the wrong type (e.g., treating a free-text span as a number when it isn't one). Gate should reject with `TYPE_MISMATCH`. | n/a |
| `MISSING_STEP` | Missing step | The chain is incomplete -- stops short of actually answering, or skips a necessary intermediate fact. | `WRONG_OPERATOR` (chain is complete but wrong, vs. chain is just absent) |
| `STRUCTURALLY_VALID_SEMANTICALLY_WRONG` | Well-typed but wrong (the documented false-pass class) | Every step ADMITs -- correct schema, real spans, right types -- but the final answer is still wrong because the WRONG real facts were chosen. This is round 1's W2, operationalized as a count you can actually report. | This is the category the gate is explicitly incapable of catching; see `OPERATORS.md`'s "Known false-pass class." |
| `GATE_BUG` | Gate bug | The reference `gate.py` produced a verdict that's wrong given its own spec (e.g., admitted something `OPERATORS.md` says should be rejected, or rejected something that should pass). This is a bug report against this pilot kit, not a model-quality finding -- file it separately. | Everything else (those are model failures, this is a code failure) |
| `CORRECT` | Correct | Right operator, right operands, right final answer. | n/a |

## Reporting template

For a batch of N manually-reviewed traces, report a table:

| Question type | N reviewed | CORRECT | STRUCTURALLY_VALID_SEMANTICALLY_WRONG | WRONG_OPERATOR | WRONG_OPERANDS | SPAN_EXTRACTION_ERROR | TYPE_ERROR | MISSING_STEP | GATE_BUG |
|---|---|---|---|---|---|---|---|---|---|
| comparison | | | | | | | | | |
| inference | | | | | | | | | |
| compositional | | | | | | | | | |
| bridge_comparison | | | | | | | | | |

The single most important number in this table, per round 1's W1/W2: the rate of
`STRUCTURALLY_VALID_SEMANTICALLY_WRONG` relative to `CORRECT` among all ADMIT verdicts.
A high rate there means the gate is giving false confidence -- ADMIT is being mistaken
for "right" when it only ever meant "well-formed." Report this explicitly, don't bury
it in an aggregate accuracy number.

## W1 decision thresholds (default, from round 2 Task C4 — unchanged, see PREREG.md)

On questions pre-annotated as decomposable (ANNOTATION_GUIDE.md), with few-shot
prompting at 1B-4B scale: correct-formalization rate (`CORRECT` / all attempted) < 30%
means the "SLMs have little left to specialize in" worry looks real and the multi-SLM
story should be shelved. >= 50% proceeds to the staged experiment in PREREG.md. 30-50%
is ambiguous -- try one larger model (e.g. an 8B or API model) on the same 20-30 traces
to see whether the problem is model scale specifically, before concluding anything about
the architecture.
