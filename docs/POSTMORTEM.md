# POSTMORTEM — Latch pilot, killed at G3 (2026-11-11)

**Verdict.** A mechanical admission gate over typed operators did not beat free-form
chain-of-thought on 2WikiMultihopQA with qwen2.5:14b. Arm 2 (formalize, gate, evaluate)
scored 37.5% at full coverage against 80.6% for Arm 0 (CoT), on the same 72 questions.
The pilot is closed. Source of record: `LOG.md` and commit `4adbb01`.

## What was tested

Hypothesis (`PREREG.md`): a small model that only *proposes* typed reasoning steps, with
a deterministic gate admitting or rejecting each step, is more reliable than the same
model reasoning freely. The gate stages were:

- **G1** — can the questions be expressed in the operator set at all? Promote at >= 60%.
- **G2** — can a model formalize them into gate-valid steps? Promote at >= 50%
  correct-formalization, kill below 30%.
- **G3** — does Arm 2 beat Arm 0 by >= 15pp with p < 0.05 (McNemar)? Kill if Arm 2
  loses to Arm 0.

## What happened

| Stage | Result | Outcome |
|---|---|---|
| G1 | 74/100 decomposable (bridge_comparison 25/25, comparison 24/25, compositional 25/25, inference 0/25) | Promote |
| G2, strict gate | 0% admit on 3b, 7b and 14b. Failures were mostly span-offset errors, which grew with model size (33% on 3b, 49% on 7b, 72% on 14b) | Kill by the registered spec |
| G2-prime v1 to v3 | Gate redesigned (text-search provenance, no-offset schema, date parsing, conjoin fix): 0% to 6.9% to 13.9% to 36.1% admit on 7b | Cleared the 30% kill line |
| G2 manual review | 16 of 26 non-trivial admits were STRUCTURALLY_VALID_SEMANTICALLY_WRONG (62%); corrected correct-formalization 36.1% | Kill again (PREREG section 7) |
| G2-prime v4 | Example 5 added for bridge_comparison. 14b: 58.3% admit, SVSS about 15%, correct-formalization about 50-53% | Promote, borderline |
| G3 | Arm 0 58/72 (80.6%); Arm 2 27/72 (37.5%), abstaining on 40/72 (55.6%) | **Kill** |

## What the result shows

1. **Coverage killed it, not safety.** The gate stayed fairly safe: 27 of 32 admits were
   correct (84.4%). But it admitted only 44% of questions. Formalization into valid step
   JSON is the bottleneck, and neither a bigger model nor better few-shot examples moved
   it enough.
2. **The gate added no measurable precision on matched questions.** The log's "+4pp on
   admitted" compares Arm 2's 32 admits (84.4%) with Arm 0 on all 72 (80.6%). On the same
   32 questions Arm 0 got 29 right (90.6%) and Arm 2 got 27 (84.4%); the McNemar
   discordant cells are b=4 and c=2. The admitted questions were simply easier.
3. **Abstention carries weak signal.** Arm 0 was wrong on 3 of the 32 admitted questions
   (9%) and 11 of the 40 abstained ones (27.5%). Most abstained questions were ones CoT
   answered correctly.
4. **A gate that checks provenance cannot check meaning.** The G2 review found the gate
   admitting film release years as director birth or death dates: the span existed in the
   document, but the gate cannot tell which attribute it represents. A few-shot example
   fixed the specific pattern (SVSS from about 69% to 17% on bridge_comparison), but the
   hole is structural.

## Caveats on the evidence

- **The gate and prompts changed after G2 failed.** G2 promoted only on a redesigned gate
  and a prompt tuned on the failures. That is legitimate iteration, but G2's 50% was
  reached by fitting to the review set.
- **Example 5 was written from SVSS cases in the same 72 questions G3 then ran on.**
  Arm 2's number is therefore optimistic, which strengthens the kill.
- **Scoring was manual, with a heuristic auto-match assist, and not blinded.**
- **McNemar ran on n=32** (the jointly answered questions), which is underpowered. The
  -43pp full-coverage gap does not depend on that test.
- **PREREG section 5 says abstentions are "not answered, never wrong."** The G3 headline
  scores abstentions as wrong at full coverage. The kill clause "Arm 2 loses to Arm 0"
  holds under either reading, but the framing should be stated openly.
- **Some admits counted as correct were trivial** (empty-array and pure-retrieval
  compositional cases). They inflate the correct-formalization rate to a degree this
  review did not quantify.
- **Prior art.** The red-team found the single-model mechanism heavily prior-arted
  (Logic-LM, LINC, SatLM, PAL/PoT). This pilot produced a negative result in that space,
  not a novel one.

## What it does and does not say about GIN's other pieces

It tests one thing: a model translating a free-form question into a formal schema, with a
mechanical gate downstream. It does not test gates that anchor to a literal artifact.

- **receipts** has a model-to-schema step (a Zod proposal schema), but a lost proposal
  costs a missing ledger row, and the ledger reports what went unchecked. It already shows
  Latch-like low yield (for example "proposed 99, admitted 8").
- **attest** has no model in its verdict path. A model-suggested tagger is planned but
  unbuilt; if built, measure coverage first, since that is what failed here.

## Lessons

- Gate the experiment, not just the system: the prereg with kill thresholds made this a
  clean negative result instead of an open-ended project.
- Measure coverage and precision on matched question sets before claiming a precision
  benefit.
- A manual review of admitted items caught a false-pass class (62% SVSS) that the
  admit-rate metric alone hid.
- Do not tune prompts on the evaluation set; hold out a fresh sample for G3.

## Status

**Killed.** Not recommended: a larger model, a second G3 sample, or more operators.
The only open thread is whether mechanical admission pays off when a claim can be
anchored to a literal artifact, which is what receipts and attest test.
