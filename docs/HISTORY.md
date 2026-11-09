# HISTORY — how Latch happened

This is the full narrative, in order. It exists so that "why does this folder have an
operator spec, a red-team report, and a pre-registration in it" has an answer, and so
nobody mistakes any of this for a scheduled project. See the top-level `README.md` for
current status; this file is the story of how it got there.

## Origin (2026-11-06): a thought train, logged as raw sprawl material

The question that started it: what if there were a chain of reasoning between small
language models (SLMs), a bit like Mixture-of-Experts but aimed at making small models
stronger at reasoning instead of just routing capacity? The starting guess was that SLM
weaknesses would be *amplified* by multi-model communication — each model understands
less of what the others are doing, so the reasoning trace each one works on gets weaker.

Working through that guess surfaced a sharper diagnosis:
- **Lossy handoffs.** Inside one model, hidden state carries the reasoning. Between
  models, everything is squeezed through text, which drops implicit context.
- **Error compounding.** Five steps at 90% each is about 59% overall; SLMs have lower
  per-step reliability, so they take a bigger hit from this than large models would.
- **Narrow context.** Each SLM sees only its own slice, so it can't notice an upstream
  step quietly going wrong.
- **MoE is a weak analogy.** MoE experts share one residual stream and train jointly —
  routing is learned along with the reasoning. Separate SLMs share no representation.
- It tends to work when a task splits by *role* with verifiable interfaces
  (planner/solver, propose/check) and fail when it splits by *reasoning type*.

The idea that followed: point the GIN/SEAR pattern (grounding every claim to a
verbatim-span-provenanced corpus, admitted through a sole-writer gate) *inward*, at the
generative process itself. SLMs read a shared, provenance-tracked state and only
*propose* to it; a sole-writer gate ("Bookkeeper"-style) admits or rejects each step
before the next model builds on it. "Zero cursors" — an abstain signal — replaces
confabulation when the gate rejects.

What this was flagged as NOT fixing, from the start: inference steps ("therefore X")
have no verbatim anchor to check against, unlike premises; whatever the gate rejects or
the proposer never proposes is just gone (context loss moves to the admission layer,
it doesn't disappear); and a *learned* gate for this would hit the same known failure
modes as other learned relatedness/relevance signals.

This was logged to the sprawl `LOG.md` as raw, untested material — explicitly not
promoted, not scheduled, and flagged as sitting behind Track A/B job search, graduation,
and attest.

## First critique (same session): does the mechanism actually transfer?

Unprompted deeper discussion surfaced three problems with "point SEAR's gate inward" as
stated: (1) SEAR's gate works because it does mechanical verbatim-substring matching —
there is no equivalent mechanical anchor for an *inference* step, so "point it inward"
doesn't survive contact with what the gate actually is; (2) the nearest non-neural
inference checker in the broader project family (Receipts' quantity/stance channel)
only covers a minority of step types (numeric/factual-stance), leaving entailment and
comparison — the bulk of real multi-hop reasoning — unguarded; (3) stripped of verbatim
provenance, what's left reduces to "typed shared state + sole-writer consistency gate,"
which is not obviously distinguishable from decades of blackboard architectures or
multi-agent debate with a judge. The one genuinely salvaged finding: task splits by
*role with verifiable interfaces* working better than splits by *reasoning type* — that
observation held up.

## The upgrade attempt: "anchor structure, not content"

Pushed to actually try to solve the SLM-reasoning problem rather than just diagnose it,
the idea was reworked: ground premises via SEAR as before, but constrain reasoning
*steps* to a small closed set of typed combinators (transitive-chain, numeric-compare,
count, negate, conjoin, temporal-order, set-membership). The gate checks well-typedness
and arity — not truth. Rejection triggers the zero-cursor abstain. This reframes the
contribution as a generalization of the PAL/Program-of-Thought "give SLMs a calculator"
result to a bigger, closed combinator set, with specialization-by-operator-family
(checkable, unlike "by reasoning type," which the earlier critique found fails) and
cross-model agreement as a proposed second gate layer on ambiguous steps.

This produced a 5-arm experiment design: (0) single-SLM free CoT floor; (1) free-form
multi-SLM; (2) single-SLM + typed-combinator-gate; (3) multi-SLM + gate + cross-model
agreement + escalation; (4) single-SLM self-consistency at matched compute. This also
named the mechanism a third thing, distinct from GIN's decode-time constraint and
SEAR's verify-after stage: a decode-time constraint applied to *inter-model reasoning
handoffs*, not corpus grounding.

## Two rounds of literature digging

**Round one** searched Logic-LM, Selection-Inference, process reward models ("let's
verify step by step"), multi-agent debate, SLM multi-agent gating, and neurosymbolic
DSL verifiers. Found that Logic-LM and Proof of Thought already do essentially the
proposed single-model mechanism; Selection-Inference (Creswell et al., DeepMind-adjacent,
ICLR 2023) is the closest two-model prior art (a 7B two-model system beating a 280B
single model); two independent papers ("If MAD is the Answer, What is the Question?"
and "Should we be going MAD?") show multi-agent debate failing to reliably beat
single-agent CoT/self-consistency even at higher compute, validating the arm-3 risk as
a documented field-wide finding, not a hypothetical; DebateCoder (Pangu-1B) was the
closest SLM-specific framing found, but using a soft confidence gate, not a mechanical
one. This reframed the core throughline as "hard vs. soft gating," the same bet already
made in GIN and SEAR, now tested in a third domain.

**Round two** dug deeper and found the "hard vs. soft gate" axis is not original —
two 2026 surveys ("Trust but Verify," "Generate, Filter, Control, Replay") already
name it directly inside RLVR literature. More importantly, it surfaced the Nature
Machine Intelligence 2026 paper ("Capable language models can outgrow the benefits of
collaboration") as a rigorous, already-published, matched-compute answer to the general
"does coordination help" question — 260 configurations, 6 benchmarks, a documented
capability-saturation threshold. This narrowed the one still-open, citable question to:
does a hard symbolic per-step admission gate move that capability-saturation threshold —
i.e., let small/weak models benefit from coordination in the regime where that paper
shows they currently don't.

Both rounds were logged to sprawl `LOG.md`, with the user asking at several points
whether this "feeds into attest" or could support a future PhD application — both
connections were explicitly rejected as thesis-level adjacency at best, not deliverable-
level, and named directly as justification-seeking rather than acted on.

## The red-team (Hermes Prompt 1)

A fully self-contained adversarial-review prompt, run as a standalone pass against this
restated idea, prior art to verify, and seven named weak points (W1-W7: SLM
formalization capacity, well-typed-but-wrong steps, operator-set coverage gaps,
cross-model agreement reliability, statistical power at n=100, among others).

Verdict: **CONTINUE NARROWED, medium confidence.** Confirmed directly via primary
sources: Logic-LM/LINC/SatLM/Faithful CoT/Proof of Thought/PAL/PoT heavily prior-art the
single-model mechanism; cross-model error correlation runs ρ≈0.47-0.68 (worse for
similar/accurate models), undercutting the cross-model-agreement gate layer; n=100 gives
roughly ±9.8pp 95% CI and ~27.7pp minimum detectable difference at 80% power, badly
underpowered for arm-vs-arm comparisons. One citation from round one ("Ling et al.,
Deductive Verification of Chain-of-Thought") could not be located and was flagged
rather than guessed at.

## Round 2 (Hermes Prompt 2): construction and verification — this pilot kit

A second self-contained prompt, shifting role from adversarial review to actually
building a testable kit, with explicit constraints: no model inference performed by the
builder, no multi-agent/training/fine-tuning code, everything model-dependent left for
Kristian to run himself against an OpenAI-compatible endpoint.

This produced, in order:
1. **VERIFICATION.md** — closed every open citation item from the red-team against
   primary sources, including locating the previously-not-found Ling et al. paper, and
   one real correction: the Nature MI 2026 paper's finding is about *agentic* tasks
   specifically, which this pilot's static-QA benchmarks are not — demoting that
   citation from "direct extension" to "open analogy."
2. **OPERATORS.md / gate.py / test_gate.py** — a 12-operator closed spec (the original 7
   plus disjoin/arithmetic/date_diff/arg_extreme/aggregate), a pure-Python mechanical
   gate, 43 passing tests including adversarial cases.
3. **coverage_finqa.py** — run against the real FinQA test set: 99.7% operator-
   vocabulary coverage (only exponentiation unsupported).
4. **sample_2wiki.py / sample_2wiki.csv** — a real, reproducible 100-question stratified
   sample pulled live from 2WikiMultihopQA's validation split.
5. **ANNOTATION_GUIDE.md / annotation_sheet.csv** — a decomposability rubric with worked
   examples pulled from the actual sampled questions, which surfaced two real, previously
   undocumented gaps: no operator for entity-equality ("same nationality" questions),
   and "paternal grandmother"-shaped questions needing a `relation_compose` lookup not
   in v1.
6. **harness.py / prompts/ / failure_taxonomy.md / scoring_sheet.csv /
   test_harness_mock.py** — a model-agnostic formalization harness (3 modes), a
   matched-compute ledger, stubs for self-consistency/PAL-style single-model arms, and
   17 passing mock-endpoint tests.
7. **PREREG.md** — hypotheses, matched-compute definition, paired McNemar design,
   risk-coverage curves, and G1-G3 stage gates with explicit promote/kill/inconclusive
   bands.

Total: 60 passing automated tests, real coverage numbers from real downloaded data,
nothing fabricated anywhere in the kit.

## Filing as a named project (2026-11-09)

Kristian named the idea **Latch** (a sole-writer admission gate that only ever moves
forward on ADMIT, never un-admits — the most literal description of the mechanism, and
one that doesn't overclaim anything about intelligence or reasoning quality) and asked
for the pilot kit to be filed into `projects/Latch` with every citation documented and
linked. That's this folder. **Filing it here is organizational, not a priority change**
— see the top-level README's "Status" section.
