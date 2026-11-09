# PREREG.md — Pre-registration for the hard-gated single-model pilot (Arm 2 vs. Arm 0/4)

Commit this file before running anything downstream of it. If you change a threshold
after seeing data, that's a different, unregistered experiment — log it as such in
`LOG.md`, don't silently edit this file.

## Scope correction, carried forward from VERIFICATION.md — read this first

This pilot tests the **single-model** mechanism only (Arm 2 vs. Arm 0 vs. Arm 4/4b
stub). It does **not** test the multi-SLM/gate-between-models claim — that's out of
scope for this round by instruction (no multi-agent code). Consequently, references
below to the Nature MI 2026 "capability-saturation threshold" are an **open analogy**,
not a direct extension: that paper's finding is about *agentic* tasks (tool use,
multi-turn, partial observability) and this pilot's tasks (2WikiMultihopQA, FinQA) are
static single-shot QA. Treat any framing sentence that invokes that paper as "a
plausible stretch worth checking later, once/if a multi-model arm is ever built," not
as "this experiment is a direct test of that paper's threshold."

## 1. Hypotheses and per-category predictions

**H1 (primary):** A hard mechanical admission gate over typed operators (Arm 2) produces
a better risk-coverage tradeoff than free-form CoT at matched compute (Arm 0), on
questions pre-annotated as decomposable, for a 1B-4B model.

**H2 (mechanism, not just outcome):** The advantage, where it exists, should be
concentrated in operator-shaped question types — numeric/count/temporal/set-membership
comparisons — and should be weak-to-absent on types that are mostly bridge-retrieval
(`compositional`, k=0 per `ANNOTATION_GUIDE.md`) or require relations the operator set
doesn't have (`inference`, many of which need `relation_compose`, not in v1). Predicted
ranking, strongest to weakest advantage: `comparison` and `bridge_comparison`
(temporal_order, numeric_compare — directly supported) > `compositional` (gate adds
little beyond provenance-checking two retrieval leaves) > `inference` (operator gap,
see `ANNOTATION_GUIDE.md`'s `relation_compose` near-miss).

**What would falsify "hard vs. soft" in favor of "anchored vs. unanchored":** if Arm 2's
advantage over Arm 0 (if any) disappears or reverses when Arm 0 is given the SAME
verbatim-span-grounded context presentation (i.e., the prompt explicitly marks out
spans) but NOT the operator/gate structure, that means grounding/anchoring was doing
the work, not the hard-vs-soft gating choice per se. This pilot does not build that
exact control arm (it would be a 5th prompt variant on Arm 0, in scope to add cheaply —
flagged as a recommended addition, not required for G1/G2).

## 2. Arms (this pilot; multi-model arms 1/3 excluded by scope)

- **Arm 0:** free-form CoT, same model, no schema, no gate. (`harness.py` mode C)
- **Arm 2:** formalize to typed steps -> gate -> evaluate -> answer or abstain.
  (`harness.py` mode B)
- **Arm 4 (stub only, not run this round):** self-consistency at matched compute.
- **Arm 4b (stub only, not run this round):** PAL/PoT-style code-offload, no gate.

## 3. Matched-compute definition

Per question, compute = (forward passes) + (total input+output tokens, including the
gate-time wall clock logged separately and NOT counted as "compute" since the gate is a
few milliseconds of pure Python, not a model call). Arm 0 is one forward pass. Arm 2 is
one forward pass (the formalization call) UNLESS a step is rejected and the design calls
for a retry — this pilot's Arm 2 as built does **not** retry on rejection (it abstains
immediately per `harness.py`'s `run_mode_b`), so Arm 2 and Arm 0 are naturally matched at
exactly one forward pass each. If you add a retry-on-rejection variant, that arm's
compute total must include every retry call, and the comparison against Arm 0 needs an
equivalent-budget multi-sample Arm 0 (e.g. best-of-2 CoT) to stay matched — don't compare
a 2-try Arm 2 against a 1-try Arm 0.

## 4. Paired design and analysis

Both arms run on the SAME question set (every question gets both an Arm 0 attempt and an
Arm 2 attempt), so the natural analysis is **paired**, not two independent samples.
Use **McNemar's test** on the 2x2 table of (Arm 0 correct/incorrect) x (Arm 2
correct/incorrect) for the primary significance check on accuracy. For the abstention-
aware comparison, use risk-coverage curves (Section 5) as the primary metric, with
McNemar's test as a secondary confirmatory check restricted to the subset where Arm 2
did not abstain (since McNemar's test has no native way to handle a three-way
correct/incorrect/abstain outcome cleanly — do not force abstentions into "incorrect"
without saying so explicitly in any report, that silently penalizes exactly the
behavior this architecture is supposed to reward).

**Promotion bar (default, from round 1's power calculation — challenge if you disagree):**
Arm 2 must beat Arm 0 by >= 15 percentage points on accuracy-at-full-coverage (or show a
clearly dominant risk-coverage curve, Section 5) on the decomposable subset, AND the
McNemar p-value must be < 0.05. **Below 15 points but still positive: inconclusive, do
not promote, do not kill** — this band exists because round 1's own power calculation
showed n=100 has a minimum detectable difference around 27.7pp at 80% power; a 15-point
bar is already an aggressive compromise between "sensitive enough to notice something
real" and "achievable without an infeasible sample size," and a result sitting
underneath it is genuinely uninformative, not a soft "no."

## 5. Risk-coverage curves (primary metric)

For each arm, sort predictions by a confidence/admission signal (Arm 2: ADMIT vs.
ABSTAIN is binary, so its curve has only two points — plot accuracy at ABSTAIN-excluded
coverage vs. accuracy at full coverage, treating every abstention as "not answered,"
never as "wrong"; Arm 0 has no native abstention signal, so build its curve using
self-reported confidence if the model gives one, otherwise plot it as a single point at
100% coverage, which is itself an important visual — it shows Arm 0 has no mechanism to
trade coverage for risk at all, which is the whole point of comparing against a gate).
Plot risk (1 - accuracy) on the y-axis, coverage (fraction answered) on the x-axis, for
both arms on the same figure, one line per arm, matplotlib is fine (stdlib `csv` +
`matplotlib` only, no pandas required for a plot this simple).

## 6. Stage gates

**G1 — Coverage gate (no model, already partially run this round):**
FinQA operator-vocabulary coverage: 99.7% (1144/1147, full test set; 99.5%, 199/200,
seeded subsample) — see `coverage_finqa.py` output. This number is an upper bound (see
its own caveat) and does NOT by itself clear G1, because G1's actual criterion is about
2WikiMultihopQA's manually-annotated "cleanly decomposable" rate (`ANNOTATION_GUIDE.md`),
which still needs the human annotation pass this kit could not do. **G1 promote:
overall 2Wiki coverage >= 60%, or >= 80% on >=1 type. G1 kill: < 35%. 35-60%: restrict to
best type(s), re-sample, re-annotate before deciding.** Budget: ~2 hours (you doing the
annotation pass yourself, per `ANNOTATION_GUIDE.md`'s protocol).

**G2 — Formalization gate (needs a model; the W1 test):**
Run `harness.py` mode A on the subset of your annotated-decomposable 2Wiki questions
(target 20-30 for manual review via `failure_taxonomy.md`, more if G1's coverage rate
means you have a large decomposable pool). **G2 promote: correct-formalization rate
>= 50%. G2 kill: < 30%. 30-50%: try one 8B or API model on the same 20-30 traces before
deciding** (per `failure_taxonomy.md`'s W1 thresholds — unchanged from the brief, no
evidence found this round to recalibrate them; they are a reasonable, if somewhat
arbitrary, split and should be treated as provisional until you have real distribution
data to compare against). Budget: ~4-6 hours (running the model, manually scoring 20-30
traces against `failure_taxonomy.md`).

**G3 — Full arm comparison (needs a model; only if G1 and G2 both promote):**
Run Arm 0 and Arm 2 on the full decomposable set (harness.py modes B and C), apply
Section 4's analysis. **G3 promote: clears the 15-point/p<0.05 bar above. G3 kill:
Arm 2 loses to Arm 0, or wins by <15 points with p>=0.05 twice in a row on independent
samples** (one failed attempt at the bar is the inconclusive band, not a kill — two
independent failed attempts is a real negative result). Budget: ~6-8 hours.

**Time box: approximately 20 hours through G2**, matching the "about 10-12 hours of my
time" weekend budget if split across two weekends, or roughly one long weekend plus a
few weekday evenings. G3 is explicitly NOT part of the weekend-sized commitment — see
`README.md`'s time table.

## 7. What would make me stop entirely, not just fail one gate

- G1 kills AND the 2Wiki "near-miss" categories found during annotation
  (`relation_compose`, `entity_equality` — see `ANNOTATION_GUIDE.md`'s worked examples)
  turn out to need more than 2-3 new operators to close, i.e. the operator set would
  need to grow substantially to ever clear 35%, not just get a couple of additions.
- G2 kills AND trying a bigger model (8B/API) in the 30-50% ambiguous band ALSO fails to
  clear 50% — that's evidence the bottleneck is the task/schema, not model scale, which
  undercuts the entire "give small models a mechanical crutch" premise.
- Any sign, during manual trace review, that `STRUCTURALLY_VALID_SEMANTICALLY_WRONG`
  (the false-pass class) is the DOMINANT failure mode even among ADMITted traces — that
  would mean the gate is manufacturing false confidence rather than adding real
  reliability, which is worse than doing nothing.
- You personally stop being interested, or Track A/B job search and graduation need the
  hours more — this is sprawl material per `sprawl/README.md`'s own rules, not a
  commitment, and nothing in this file overrides that.
