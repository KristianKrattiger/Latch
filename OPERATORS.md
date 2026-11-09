# Operator Specification v1

Status: draft for pilot use. Scope: compositional/factual multi-hop QA (2WikiMultihopQA-shaped)
and numeric financial QA (FinQA-shaped). Not a general reasoning calculus.

## Design rule

Every operator is a **pure, deterministic function over already-admitted typed values**.
No operator ever reads free text or searches the context. Finding a value in the context
is a **retrieval** action (a verbatim span, admitted the same way a premise is), never an
operator. This is the answer to round 1's open question about bridge-entity resolution:
it is a retrieval step, not an operator (see "Exclusions" below).

Every step is `ADMIT`, `REJECT(reason_code)`, or `ABSTAIN(reason_code)`. ADMIT means
"well-typed, provenance-clean, operator evaluated" — **it does not mean "correct."**
See "Known false-pass class" at the end of this file; do not mistake the gate for a
truth checker.

## Starting set (the user's original 7) — kept, with precise semantics

### 1. `numeric_compare`
- Signature: `(a: Number, b: Number, op: {lt, le, gt, ge, eq, neq}) -> Bool`
- Preconditions: `a`, `b` resolve to numeric leaves.
- Semantics: standard comparison.
- Abstain: never (total function over numbers); REJECT on type mismatch instead.
- Examples:
  - `numeric_compare(1963, 1955, gt)` -> `True`
  - `numeric_compare(age(A), age(B), lt)` -> depends on resolved values; if either isn't numeric, REJECT(TYPE_MISMATCH).

### 2. `count`
- Signature: `(items: Set[Entity]) -> Number`
- Preconditions: `items` must be a previously-admitted step whose result type is `Set`.
- Semantics: cardinality of the set.
- Abstain: never.
- Examples:
  - `count({A, B, C})` -> `3`
  - `count(member_filter_result)` -> cardinality of whatever the prior step produced.

### 3. `negate`
- Signature: `(x: Bool) -> Bool`
- Semantics: logical NOT.
- Examples: `negate(True) -> False`.

### 4. `conjoin`
- Signature: `(xs: List[Bool]) -> Bool`
- Semantics: logical AND over the list (generalizes "pairwise AND" to n-ary; this is a
  deliberate widening from a literal reading of "conjoin" to cover 2Wiki's
  bridge_comparison questions, which combine more than two facts).
- Added for completeness: `disjoin(xs: List[Bool]) -> Bool`, logical OR. Justification:
  2Wiki's "which of the following must be true" / "may be true" question shapes need OR,
  not just AND; omitting it would silently misclassify a real share of compositional
  questions as "not expressible" when the only missing piece is a connective.

### 5. `temporal_order`
- Signature: `(date_a: Date, date_b: Date, op: {before, after, same}) -> Bool`
- Preconditions: both leaves parse as dates under a single declared format
  (`ISO 8601` preferred; partial dates — year-only — are a separate `Date` subtype,
  see below).
- Semantics: standard date ordering.
- Abstain: `ABSTAIN(AMBIGUOUS_DATE_PRECISION)` if the two dates have incompatible precision
  (e.g., one is year-only, the other is full date, and the comparison's outcome would
  change depending on the unresolved day/month) — this is a real abstain condition, not
  a cop-out; most date-ordering errors in multi-hop QA come from exactly this case.

### 6. `set_membership`
- Signature: `(x: Entity, items: Set[Entity]) -> Bool`
- Semantics: `x in items`.

### 7. `transitive_chain`
- Signature: `(rel_ab: Relation, rel_bc: Relation) -> Relation | ABSTAIN`
- This is the trickiest operator to keep mechanical, and round 1 was right to flag it.
  **Composition is only ever attempted for relations on a small, explicit, pre-declared
  transitive-relation whitelist** (e.g., `located_in`, `part_of`, `subclass_of`).
  `parent_of`, `director_of`, `founder_of` etc. are explicitly **not** transitive
  (grandparent != parent) and the gate must `REJECT(NON_TRANSITIVE_RELATION)` if asked
  to chain them. For non-transitive relation chains (which is most of what 2Wiki's
  "bridge" questions actually need — e.g., "father's father"), the correct operator is
  **not** `transitive_chain` at all; it's a `relation_compose` lookup against an explicit,
  tiny table of known composite-relation names (e.g., `parent_of ∘ parent_of = grandparent_of`
  only if that composite relation is itself in the whitelist with its own semantics).
  This pilot ships `transitive_chain` for the genuinely-transitive case only and treats
  composed-but-non-transitive relation chains as **out of scope for v1** — flagged
  explicitly in the coverage rubric, not silently misclassified as expressible.

## Additions (justified against W3's named gaps)

### 8. `arithmetic`
- Signature: `(a: Number, b: Number, op: {add, sub, mul, div}) -> Number`
- Justification: required for any FinQA-style question ("what is the difference between
  revenue in 2015 and 2016"); `numeric_compare` alone cannot produce a number, only a bool.
- Abstain: `ABSTAIN(DIVISION_BY_ZERO)` on `div` with `b == 0`, not a crash and not a silent 0.

### 9. `date_diff`
- Signature: `(date_a: Date, date_b: Date, unit: {days, months, years}) -> Number`
- Justification: distinct from `temporal_order` — many 2Wiki/FinQA questions ask
  "how many years between X and Y," which needs a magnitude, not just an ordering.
  Separating it from `temporal_order` keeps each operator's semantics simple and keeps
  the abstain condition (precision mismatch) local to one operator instead of baked into two.

### 10. `arg_extreme`
- Signature: `(items: List[Tuple[Entity, Number]], mode: {max, min}) -> Entity`
- Justification: required for any superlative question ("who is the oldest," "which
  product had the highest revenue") — a large share of 2Wiki's comparison type and
  FinQA's ranking-style questions need this and it was a real, named gap in round 1.
- Abstain: `ABSTAIN(TIE)` if more than one item shares the extreme value and the question
  has no tie-breaking rule stated in context — this is a genuine ambiguity, not a gate bug.

### 11. `aggregate`
- Signature: `(items: List[Number], op: {sum, avg, min, max}) -> Number`
- Justification: FinQA's multi-row table questions ("total revenue across three years")
  need aggregation over more than two values; `arithmetic` is binary only.

### 12. `entity_equal`
- Signature: `(a: Entity, b: Entity) -> Bool`
- Justification: required for any "same nationality/birthplace/occupation" comparison
  question — a real, documented gap found during the annotation guide's worked-example
  exercise (see `ANNOTATION_GUIDE.md`'s "Comparison — near-miss" example). Without this
  operator, questions like "Are X and Y of the same nationality?" are unexpressible even
  though both entity values can be cleanly retrieved from context. `numeric_compare`'s
  `eq` is typed to numbers only; this operator fills the entity-equality gap without
  widening `numeric_compare`'s contract.
- Preconditions: `a`, `b` resolve to entity-typed leaves.
- Semantics: exact string equality after whitespace stripping (the gate's standard entity
  coercion). This is deliberately strict — "USA" != "United States" — because the gate
  is a type-checker, not a knowledge base. If the model retrieved two different surface
  forms for the same real-world entity, the gate cannot and should not silently resolve
  that; the model's job is to retrieve the canonical form from the context for both.
- Abstain: never (total function over entity strings); REJECT on type mismatch.
- Examples:
  - `entity_equal("American", "American")` -> `True`
  - `entity_equal("American", "British")` -> `False`
  - `entity_equal("042", "42")` -> `False` (string identity, not numeric — "042" and "42"
    are different entity strings even though they'd be the same number)

## Exclusions, argued explicitly

**Bridge-entity resolution is not an operator.** It is the act of finding, in the context,
the entity that satisfies a stated property (e.g., "the director of the film mentioned in
step 1"). That is a text-search/retrieval action, not a function over typed values — making
it an operator would require the gate to judge whether a candidate span *correctly*
identifies the right entity, which is exactly the open-ended, non-mechanical judgment this
whole design exists to avoid (see round 1, W2). **Decision: bridge resolution is a retrieval
step**, admitted through the same verbatim-span-provenance mechanism as a grounded premise,
never through an operator call. The model proposes "the entity named in span [x:y] of
document d satisfies the bridge property"; the gate can mechanically verify the span exists
and the text matches, but it cannot and does not verify that the span actually satisfies the
stated property — that residual judgment call is disclosed, not hidden, in the false-pass
class below.

**Composed non-transitive relation chains** (W3's open item) — out of scope for v1, as
argued under operator 7. Flag these questions as "requires `relation_compose`, not shipped,"
not as silently unexpressible or silently expressible.

## What this set cannot express

Open-ended entailment ("X implies Y" from general world knowledge, not from a declared
relation or arithmetic fact), analogy, causal reasoning not reducible to a stated relation,
multi-key ranking (ranking by two criteria at once), and anything requiring commonsense
not present in the provided context. This matches round 1's "entailment-shaped questions"
gap — it is not fixed by this operator set, it is fenced off from it so coverage numbers are
honest about where the fence is.

## JSON step schema

```json
{
  "step_id": "s3",
  "operator": "numeric_compare",
  "args": [
    {"ref_type": "span", "doc_id": "p1", "start": 120, "end": 134},
    {"ref_type": "step", "step_id": "s1"}
  ],
  "params": {"op": "gt"},
  "result_type": "bool"
}
```

Rules:
- Every `arg` is either `{"ref_type": "span", "doc_id", "start", "end"}` (must match
  verbatim text present in the supplied context at those exact offsets) or
  `{"ref_type": "step", "step_id"}` (must reference a step that has already been `ADMIT`ed
  in this same trace — referencing a rejected, abstained, or not-yet-seen step is always
  `REJECT(UNADMITTED_STEP_REF)`).
- No field anywhere in a step carries free-text content except the span's `doc_id` (an
  opaque context-document identifier) and the fixed enum values for `operator`/`op`/`unit`/`mode`.
- The final step in a trace additionally declares the question's `result_type` for the
  gate to check against (`bool`, `number`, `entity`, `date`, `set`).

## Reason codes (stable list)

`SCHEMA_INVALID`, `UNKNOWN_OPERATOR`, `ARITY_MISMATCH`, `TYPE_MISMATCH`,
`PROVENANCE_SPAN_NOT_FOUND`, `PROVENANCE_SPAN_TEXT_MISMATCH`, `UNADMITTED_STEP_REF`,
`CYCLE_DETECTED`, `RESULT_TYPE_MISMATCH`, `NON_TRANSITIVE_RELATION`, `DIVISION_BY_ZERO`,
`AMBIGUOUS_DATE_PRECISION`, `TIE`, `EVAL_ERROR`.

## Known false-pass class (read this before trusting a green run)

An `ADMIT` verdict means: the step is syntactically valid, every argument traces to a real
span or an already-admitted step, types line up, and the operator evaluated without error.
It does **not** mean the operator or operands were the *right* ones for the question, and it
does **not** mean a bridge-resolution span actually satisfies the property it claims to. A
model can emit `numeric_compare(span_A, span_B, gt)` where `span_A` and `span_B` are both
real, well-typed numbers that have nothing to do with the question, and the gate will admit
it. This is W2 from round 1, operationalized: the gate is a type-checker, not an oracle. The
harness's manual scoring sheet (Task C4) exists specifically to measure how often this
happens; do not report gate-admission rate as if it were accuracy.
