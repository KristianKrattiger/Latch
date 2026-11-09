# Annotation Guide: "Is this question cleanly decomposable?"

This guide is for the manual pass that the automatic coverage scripts (`coverage_finqa.py`)
cannot do: checking whether a question's gold answer can actually be reached by composing
the operators in `OPERATORS.md`, with every leaf a verbatim span or a prior step's output.
Automatic coverage (FinQA) checks operator *vocabulary*; this checks real *expressibility*
on 2WikiMultihopQA, which has no gold program to scan mechanically.

## Rubric (default, from round 1, unchanged)

A question is **decomposable** if its gold answer is derivable by at most **k = 4**
applications of the closed operator set (`OPERATORS.md`), where every leaf is either a
verbatim span from the provided context or a prior step's output. A **bridge-resolution
step** (finding the entity that satisfies a stated property) counts as a retrieval leaf,
not one of the k operator applications — see `OPERATORS.md`'s exclusion section. This
matters for counting: a question answered by two bridge-retrievals and one `temporal_order`
call is "k=1," not "k=3."

## Decision tree

1. Read the question and gold answer. Identify every fact the chain actually needs.
2. For each fact: is it a direct span in the context (a retrieval leaf), or does it require
   combining two or more facts (needs an operator)?
3. For each combination: does it match one of the 11 operators in `OPERATORS.md` exactly —
   same arity, same kind of inputs? If yes, name it. If it's close but not quite (e.g., it
   needs an operator this set doesn't have), mark it a **near-miss** and name the missing
   operator. If it needs open-ended judgment (commonsense, unstated relation, subjective
   ranking), mark it **out of scope**.
4. Count operator applications (excluding bridge-retrieval leaves). If ≤4 and every leaf and
   operator resolved in step 3, mark **decomposable: yes**. Otherwise **no**, with a reason
   code.

## Worked examples, pulled from the actual pilot sample (`sample_2wiki.csv`)

**Comparison — decomposable, k=1.**
Q: "Which film was released first, Heaven Help Us or Ghar Ki Rani?"
Chain: bridge-retrieve release_date(Heaven Help Us) -> leaf A; bridge-retrieve
release_date(Ghar Ki Rani) -> leaf B; `temporal_order(A, B, before)` -> answer. k=1.
**Decomposable: yes.** Operator chain: `temporal_order`.

**Comparison — near-miss, found during this exercise, not in `OPERATORS.md` v1.**
Q: "Are Frederick Joseph Kinsman and Cassius Gaius Foster of the same nationality?"
Chain needs: bridge-retrieve nationality(A); bridge-retrieve nationality(B); then an
**entity equality test** — and there is no such operator in v1. `numeric_compare`'s `eq`
is typed to numbers only; nothing in the current set compares two entities for equality.
**Decomposable: no.** Blocking reason code: `operator_gap:entity_equality`. This is the
single most actionable finding from building this guide: adding a generic `entity_equal`
(or widening `numeric_compare`'s `eq`/`neq` to accept entity-typed args) is the most
obvious v1.1 addition if the full annotation pass turns up many of these — track the rate.

**Comparison — out of scope, genuinely open-ended.**
Q: "Who has a wider scope of profession, Anne Castles or Colin Will?"
"Wider scope of profession" is not a declared relation or a number; judging it requires
open-ended world knowledge about what counts as a "wider" profession. No operator
combination reaches this. **Decomposable: no.** Blocking reason code: `out_of_scope:subjective_judgment`.

**Compositional — decomposable, k=0 (pure bridge chain, no operator needed at all).**
Q: "What is the place of birth of Empress Xu (Ming Dynasty)'s husband?"
Chain: bridge-retrieve husband(Empress Xu) -> entity Y; bridge-retrieve
place_of_birth(Y) -> answer. No comparison, no arithmetic, nothing to type-check beyond
the two retrieval leaves. **Decomposable: yes, k=0.** This is an important category to
track separately in your tally: some "compositional" questions need zero operator calls,
only correct bridge retrieval — for these, the gate's only job is checking the two spans
exist, and the real difficulty lives entirely in retrieval accuracy, which this pilot's
gate does not and cannot improve.

**Inference — near-miss, explicitly fenced off in `OPERATORS.md` #7.**
Q: "Who is the paternal grandmother of Renaud III, Count of Soissons?"
"Paternal grandmother" = father's mother = composing `parent_of` with itself, but
`parent_of` is explicitly NOT on the transitive-relation whitelist (grandparent != parent),
so `transitive_chain` correctly `REJECT`s this. The right operator would be a
`relation_compose` lookup against a tiny table of named composite relations
(`parent_of ∘ parent_of = grandparent_of`), which v1 does not ship.
**Decomposable: no.** Blocking reason code: `operator_gap:relation_compose`. Note how
common this shape is in the "inference" type bucket before concluding anything about
overall 2Wiki coverage — if most of "inference" is this exact shape, it's a one-operator
fix, not a fundamental dead end, and worth knowing before shelving the whole type.

**Inference — out of scope, no declared relation at all.**
A hypothetical (construct your own if your sample doesn't have one): "Why did the founder
of Versus die?" requires an unstated causal/biographical inference, not a declared relation
in context. **Decomposable: no.** Blocking reason code: `out_of_scope:implicit_causal`.

## Borderline cases worth flagging explicitly, not silently resolving

- **Count vs. aggregate confusion:** "how many X are there" is `count`; "what is the total
  X" is `aggregate(sum)`. Don't conflate them in your operator-chain column — they have
  different type signatures and this distinction is exactly what a future gate-quality
  audit needs to be able to check.
- **Tie-prone superlatives:** if `arg_extreme` would hit a real tie in the context (two
  entities share the extreme value and the question doesn't disambiguate), that's a correct
  `ABSTAIN(TIE)` case per `OPERATORS.md` — mark it decomposable but note "abstain-expected"
  in a free-text comment, don't mark it "no."
- **Mixed-precision dates:** if the chain needs `temporal_order` or `date_diff` and the two
  dates in context have different stated precision (one a full date, one year-only), check
  by hand whether the coarser precision actually creates ambiguity (see `OPERATORS.md`'s
  worked logic) before marking it a blocker — many of these resolve fine.

## CSV annotation sheet

See `annotation_sheet.csv`, pre-populated with the 100 sampled questions
(`id`, `type`, `question`, `answer`) and five blank columns for you to fill in per the
rubric above: `decomposable (yes/no)`, `k (operator count, excluding bridge retrievals)`,
`operator_chain (comma-separated operator names, or "bridge_only" if k=0)`,
`blocking_reason_code`, `notes`.

## Self re-annotation protocol (48-hour agreement check)

1. Annotate all 100 rows in one sitting, saving as `annotation_sheet_pass1.csv`.
2. Wait at least 48 hours — don't do it the next morning, the point is to lose your own
   short-term memory of specific judgment calls.
3. Re-annotate the same 100 rows from a fresh copy of `annotation_sheet.csv`, saving as
   `annotation_sheet_pass2.csv`, without looking at pass 1.
4. Compute Cohen's kappa on the binary `decomposable` column between the two passes:

```python
# pip-free; stdlib only
def cohens_kappa(a, b):
    assert len(a) == len(b)
    n = len(a)
    agree = sum(1 for x, y in zip(a, b) if x == y) / n
    pa = sum(1 for x in a if x == "yes") / n
    pb = sum(1 for x in b if x == "yes") / n
    expected = pa * pb + (1 - pa) * (1 - pb)
    return (agree - expected) / (1 - expected) if expected < 1 else 1.0
```
A kappa below ~0.6 means the rubric itself is ambiguous and needs tightening before you
trust the coverage number it produced — rerun on a 20-question subset with a revised
rubric rather than trusting a noisy first pass.

## Decision thresholds (default, from round 1, unchanged — challenge if you disagree)

- Overall coverage ≥ 60%, **or** ≥ 80% on at least one question type: **promote to G2.**
- Overall coverage < 35%: **shelve.**
- 35–60%: restrict to the best-covered type(s) and re-run the annotation pass on a fresh
  sample of just those types before deciding.

**Reminder, carried forward from round 1's power calculation:** a 100-question coverage
estimate has a 95% CI of roughly ±9.8 percentage points at p≈0.5 (tighter near 0% or 100%).
This pilot can tell you "coverage is probably somewhere in a ~20-point band," which is
enough to clear or fail the 35%/60%/80% thresholds above in most realistic outcomes, but
it **cannot** support a claim like "coverage is 61% vs. a 60% bar" — that distinction is
inside the noise. If your result lands within ~10 points of a threshold, treat it as
inconclusive and annotate 100 more questions before deciding, don't round in whichever
direction you were hoping for.
