"""
test_gate.py -- >=30 unit tests for gate.py, including adversarial cases.

Run with: python -m unittest test_gate.py -v
"""

import unittest
from gate import Context, Gate, Status, ReasonCode, run_trace


def ctx(**docs):
    return Context(docs=docs)


def span(doc_id, start, end, text=None):
    d = {"ref_type": "span", "doc_id": doc_id, "start": start, "end": end}
    if text is not None:
        d["text"] = text
    return d


def stepref(step_id):
    return {"ref_type": "step", "step_id": step_id}


class TestSchemaAndArity(unittest.TestCase):
    def test_missing_field_rejected(self):
        g = Gate(ctx(p1="hello"))
        v = g.step({"step_id": "s1", "operator": "negate"})  # missing args
        self.assertEqual(v.status, Status.REJECT)
        self.assertEqual(v.reason_code, ReasonCode.SCHEMA_INVALID)

    def test_unknown_operator_rejected(self):
        g = Gate(ctx(p1="hello"))
        v = g.step({"step_id": "s1", "operator": "frobnicate", "args": []})
        self.assertEqual(v.reason_code, ReasonCode.UNKNOWN_OPERATOR)

    def test_arity_mismatch(self):
        g = Gate(ctx(p1="5 10"))
        v = g.step({"step_id": "s1", "operator": "numeric_compare",
                    "args": [span("p1", 0, 1)], "params": {"op": "gt"}})
        self.assertEqual(v.reason_code, ReasonCode.ARITY_MISMATCH)

    def test_duplicate_step_id_rejected(self):
        g = Gate(ctx(p1="5 10"))
        step = {"step_id": "s1", "operator": "numeric_compare",
                "args": [span("p1", 0, 1), span("p1", 2, 4)], "params": {"op": "gt"}}
        v1 = g.step(step)
        self.assertEqual(v1.status, Status.ADMIT)
        v2 = g.step(step)
        self.assertEqual(v2.reason_code, ReasonCode.SCHEMA_INVALID)

    def test_args_not_a_list(self):
        g = Gate(ctx(p1="hello"))
        v = g.step({"step_id": "s1", "operator": "negate", "args": "not a list"})
        self.assertEqual(v.reason_code, ReasonCode.SCHEMA_INVALID)


class TestProvenance(unittest.TestCase):
    def test_span_out_of_bounds(self):
        g = Gate(ctx(p1="5 hi"))
        v = g.step({"step_id": "s1", "operator": "numeric_compare",
                    "args": [span("p1", 0, 1), span("p1", 50, 60)], "params": {"op": "gt"}})
        self.assertEqual(v.reason_code, ReasonCode.PROVENANCE_SPAN_NOT_FOUND)

    def test_span_wrong_doc(self):
        g = Gate(ctx(p1="hi"))
        v = g.step({"step_id": "s1", "operator": "negate",
                    "args": [span("p999", 0, 1)]})
        self.assertEqual(v.reason_code, ReasonCode.PROVENANCE_SPAN_NOT_FOUND)

    def test_span_text_mismatch(self):
        """Adversarial: the step claims text that doesn't match the actual context
        at those offsets -- a model trying to assert a span says something it
        doesn't."""
        g = Gate(ctx(p1="revenue was 42"))
        v = g.step({"step_id": "s1", "operator": "negate",
                    "args": [span("p1", 12, 14, text="99")]})  # actual text is "42"
        self.assertEqual(v.reason_code, ReasonCode.PROVENANCE_SPAN_TEXT_MISMATCH)

    def test_span_text_match_ok(self):
        g = Gate(ctx(p1="true"))
        v = g.step({"step_id": "s1", "operator": "negate",
                    "args": [span("p1", 0, 4, text="true")]})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertEqual(v.value, False)

    def test_unadmitted_step_ref(self):
        """Adversarial: referencing a step that was never admitted (typo'd id,
        or a step that hasn't happened yet)."""
        g = Gate(ctx(p1="5"))
        v = g.step({"step_id": "s2", "operator": "negate", "args": [stepref("s1")]})
        self.assertEqual(v.reason_code, ReasonCode.UNADMITTED_STEP_REF)

    def test_reference_to_rejected_step_stays_unadmitted(self):
        g = Gate(ctx(p1="hi"))
        bad = g.step({"step_id": "s1", "operator": "frobnicate", "args": []})
        self.assertEqual(bad.status, Status.REJECT)
        v = g.step({"step_id": "s2", "operator": "negate", "args": [stepref("s1")]})
        self.assertEqual(v.reason_code, ReasonCode.UNADMITTED_STEP_REF)

    def test_self_reference_is_cycle(self):
        g = Gate(ctx(p1="hi"))
        v = g.step({"step_id": "s1", "operator": "negate", "args": [stepref("s1")]})
        self.assertEqual(v.reason_code, ReasonCode.CYCLE_DETECTED)

    def test_chained_step_refs_work(self):
        g = Gate(ctx(p1="true"))
        v1 = g.step({"step_id": "s1", "operator": "negate",
                     "args": [span("p1", 0, 4)]})
        self.assertEqual(v1.status, Status.ADMIT)
        self.assertEqual(v1.value, False)
        v2 = g.step({"step_id": "s2", "operator": "negate", "args": [stepref("s1")]})
        self.assertEqual(v2.status, Status.ADMIT)
        self.assertEqual(v2.value, True)


class TestTypeChecking(unittest.TestCase):
    def test_well_typed_but_irrelevant_operands_still_admits(self):
        """This is the documented false-pass class from OPERATORS.md: two real
        numbers that have nothing to do with each other still admit. The gate
        is a type-checker, not a truth-checker -- this test documents that
        fact so nobody mistakes an ADMIT for 'correct'."""
        g = Gate(ctx(p1="The sky is blue. 42 apples and 7 oranges."))
        v = g.step({"step_id": "s1", "operator": "numeric_compare",
                    "args": [span("p1", 17, 19), span("p1", 31, 32)],
                    "params": {"op": "gt"}})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertTrue(v.value)  # 42 > 7, mechanically true, semantically meaningless here

    def test_type_mismatch_text_not_number(self):
        g = Gate(ctx(p1="hello world"))
        v = g.step({"step_id": "s1", "operator": "numeric_compare",
                    "args": [span("p1", 0, 5), span("p1", 6, 11)], "params": {"op": "gt"}})
        self.assertEqual(v.reason_code, ReasonCode.TYPE_MISMATCH)

    def test_count_requires_set_type(self):
        g = Gate(ctx(p1="42"))
        v = g.step({"step_id": "s1", "operator": "count", "args": [span("p1", 0, 2)]})
        self.assertEqual(v.reason_code, ReasonCode.TYPE_MISMATCH)

    def test_bad_enum_op_rejected(self):
        g = Gate(ctx(p1="5 10"))
        v = g.step({"step_id": "s1", "operator": "numeric_compare",
                    "args": [span("p1", 0, 1), span("p1", 2, 4)], "params": {"op": "frobnicate"}})
        self.assertEqual(v.reason_code, ReasonCode.TYPE_MISMATCH)

    def test_result_type_mismatch_on_final_step(self):
        g = Gate(ctx(p1="5 10"), expected_result_type="number")
        v = g.step({"step_id": "s1", "operator": "numeric_compare",
                    "args": [span("p1", 0, 1), span("p1", 2, 4)],
                    "params": {"op": "gt"}, "is_final": True})
        self.assertEqual(v.reason_code, ReasonCode.RESULT_TYPE_MISMATCH)

    def test_result_type_match_on_final_step(self):
        g = Gate(ctx(p1="5 10"), expected_result_type="bool")
        v = g.step({"step_id": "s1", "operator": "numeric_compare",
                    "args": [span("p1", 0, 1), span("p1", 2, 4)],
                    "params": {"op": "gt"}, "is_final": True})
        self.assertEqual(v.status, Status.ADMIT)


class TestOperatorSemantics(unittest.TestCase):
    def test_numeric_compare_all_ops(self):
        g = Gate(ctx(p1="5 10"))
        for op, expected in [("lt", True), ("le", True), ("gt", False), ("ge", False),
                              ("eq", False), ("neq", True)]:
            gg = Gate(ctx(p1="5 10"))
            v = gg.step({"step_id": "s1", "operator": "numeric_compare",
                         "args": [span("p1", 0, 1), span("p1", 2, 4)], "params": {"op": op}})
            self.assertEqual(v.value, expected, msg=f"op={op}")

    def test_arithmetic_div_by_zero_abstains(self):
        g = Gate(ctx(p1="5 0"))
        v = g.step({"step_id": "s1", "operator": "arithmetic",
                    "args": [span("p1", 0, 1), span("p1", 2, 3)], "params": {"op": "div"}})
        self.assertEqual(v.status, Status.ABSTAIN)
        self.assertEqual(v.reason_code, ReasonCode.DIVISION_BY_ZERO)

    def test_arithmetic_add(self):
        g = Gate(ctx(p1="5 10"))
        v = g.step({"step_id": "s1", "operator": "arithmetic",
                    "args": [span("p1", 0, 1), span("p1", 2, 4)], "params": {"op": "add"}})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertEqual(v.value, 15.0)

    def test_temporal_order_same_precision(self):
        g = Gate(ctx(p1="2001-01-01 2002-01-01"))
        v = g.step({"step_id": "s1", "operator": "temporal_order",
                    "args": [span("p1", 0, 10), span("p1", 11, 21)], "params": {"op": "before"}})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertTrue(v.value)

    def test_temporal_order_mismatched_precision_abstains_when_ambiguous(self):
        """2001 vs 2001-06-15 -- year precision collapses to the same year, so the
        before/after ordering genuinely cannot be determined without more info."""
        g = Gate(ctx(p1="2001 2001-06-15"))
        v = g.step({"step_id": "s1", "operator": "temporal_order",
                    "args": [span("p1", 0, 4), span("p1", 5, 15)], "params": {"op": "before"}})
        self.assertEqual(v.status, Status.ABSTAIN)
        self.assertEqual(v.reason_code, ReasonCode.AMBIGUOUS_DATE_PRECISION)

    def test_temporal_order_mismatched_precision_resolves_when_unambiguous(self):
        """2001 vs 2005-06-15 -- different years, so precision mismatch doesn't
        actually create ambiguity. Should ADMIT, not ABSTAIN."""
        g = Gate(ctx(p1="2001 2005-06-15"))
        v = g.step({"step_id": "s1", "operator": "temporal_order",
                    "args": [span("p1", 0, 4), span("p1", 5, 15)], "params": {"op": "before"}})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertTrue(v.value)

    def test_date_diff_years(self):
        g = Gate(ctx(p1="2001-01-01 2010-01-01"))
        v = g.step({"step_id": "s1", "operator": "date_diff",
                    "args": [span("p1", 11, 21), span("p1", 0, 10)], "params": {"unit": "years"}})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertEqual(v.value, 9)

    def test_date_diff_mismatched_precision_abstains(self):
        g = Gate(ctx(p1="2001 2001-01-01"))
        v = g.step({"step_id": "s1", "operator": "date_diff",
                    "args": [span("p1", 0, 4), span("p1", 5, 15)], "params": {"unit": "years"}})
        self.assertEqual(v.status, Status.ABSTAIN)

    def test_transitive_chain_whitelisted_relation_admits(self):
        g = Gate(ctx(p1="located_in located_in"))
        v = g.step({"step_id": "s1", "operator": "transitive_chain",
                    "args": [span("p1", 0, 10), span("p1", 11, 21)]})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertEqual(v.value, "located_in")

    def test_transitive_chain_non_transitive_relation_rejected(self):
        """Adversarial: a model tries to chain 'parent_of' transitively, which
        would silently produce a wrong grandparent-as-parent claim if allowed."""
        g = Gate(ctx(p1="parent_of parent_of"))
        v = g.step({"step_id": "s1", "operator": "transitive_chain",
                    "args": [span("p1", 0, 9), span("p1", 10, 19)]})
        self.assertEqual(v.reason_code, ReasonCode.NON_TRANSITIVE_RELATION)

    def test_transitive_chain_mismatched_relations_rejected(self):
        g = Gate(ctx(p1="located_in part_of"))
        v = g.step({"step_id": "s1", "operator": "transitive_chain",
                    "args": [span("p1", 0, 10), span("p1", 11, 18)]})
        self.assertEqual(v.reason_code, ReasonCode.NON_TRANSITIVE_RELATION)

    def test_arg_extreme_simple(self):
        g = Gate(ctx(p1="x"))
        # build a prior step producing a list_entity_number via a stub operator
        # path: we inject it directly as an admitted step for this unit test.
        g.admitted["s0"] = (__import__("gate").TVal("list_entity_number", [("A", 10.0), ("B", 20.0)]), None)
        v = g.step({"step_id": "s1", "operator": "arg_extreme",
                    "args": [stepref("s0")], "params": {"mode": "max"}})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertEqual(v.value, "B")

    def test_arg_extreme_tie_abstains(self):
        g = Gate(ctx(p1="x"))
        g.admitted["s0"] = (__import__("gate").TVal("list_entity_number", [("A", 10.0), ("B", 10.0)]), None)
        v = g.step({"step_id": "s1", "operator": "arg_extreme",
                    "args": [stepref("s0")], "params": {"mode": "max"}})
        self.assertEqual(v.status, Status.ABSTAIN)
        self.assertEqual(v.reason_code, ReasonCode.TIE)

    def test_aggregate_sum(self):
        g = Gate(ctx(p1="x"))
        g.admitted["s0"] = (__import__("gate").TVal("list_number", [1.0, 2.0, 3.0]), None)
        v = g.step({"step_id": "s1", "operator": "aggregate",
                    "args": [stepref("s0")], "params": {"op": "sum"}})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertEqual(v.value, 6.0)

    def test_conjoin_variadic_bools(self):
        g = Gate(ctx(p1="true true false"))
        v = g.step({"step_id": "s1", "operator": "conjoin",
                    "args": [span("p1", 0, 4), span("p1", 5, 9), span("p1", 10, 15)]})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertFalse(v.value)

    def test_disjoin_variadic_bools(self):
        g = Gate(ctx(p1="false false true"))
        v = g.step({"step_id": "s1", "operator": "disjoin",
                    "args": [span("p1", 0, 5), span("p1", 6, 11), span("p1", 12, 16)]})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertTrue(v.value)

    def test_set_membership(self):
        g = Gate(ctx(p1="A"))
        g.admitted["s0"] = (__import__("gate").TVal("set", {"A", "B", "C"}), None)
        v = g.step({"step_id": "s1", "operator": "set_membership",
                    "args": [span("p1", 0, 1), stepref("s0")]})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertTrue(v.value)


class TestEntityEqual(unittest.TestCase):
    def test_entity_equal_same_nationality(self):
        """The motivating case from ANNOTATION_GUIDE.md: 'same nationality' questions
        need an entity equality test between two resolved entity-typed values."""
        g = Gate(ctx(p1="American American"))
        v = g.step({"step_id": "s1", "operator": "entity_equal",
                    "args": [span("p1", 0, 8), span("p1", 9, 17)]})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertTrue(v.value)

    def test_entity_equal_different_entities(self):
        g = Gate(ctx(p1="American British"))
        v = g.step({"step_id": "s1", "operator": "entity_equal",
                    "args": [span("p1", 0, 8), span("p1", 9, 16)]})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertFalse(v.value)

    def test_entity_equal_from_prior_steps(self):
        """Equality test where both entities come from prior admitted steps,
        not raw spans -- the typical pipeline shape."""
        g = Gate(ctx(p1="French French"))
        g.step({"step_id": "s1", "operator": "entity_equal",
                "args": [span("p1", 0, 6), span("p1", 7, 13)]})
        # Use step refs via a chain: first admit two steps that produce entities
        # (we use a direct injection for clean test isolation)
        g2 = Gate(ctx(p1="x"))
        import gate as _g
        g2.admitted["s0a"] = (_g.TVal("entity", "French"), None)
        g2.admitted["s0b"] = (_g.TVal("entity", "French"), None)
        v = g2.step({"step_id": "s1", "operator": "entity_equal",
                     "args": [stepref("s0a"), stepref("s0b")]})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertTrue(v.value)

    def test_entity_equal_adversarial_number_as_entity_rejected(self):
        """Adversarial: trying to pass number-typed spans through entity_equal
        should fail because the span text is coerced as entity (string), not number.
        This tests that entity_equal uses string identity, not numeric comparison --
        '042' != '42' as entities even though they're the same number."""
        g = Gate(ctx(p1="042 42"))
        v = g.step({"step_id": "s1", "operator": "entity_equal",
                    "args": [span("p1", 0, 3), span("p1", 4, 6)]})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertFalse(v.value)  # "042" != "42" as entity strings


class TestRunTrace(unittest.TestCase):
    def test_full_chain_halts_on_rejection(self):
        """A 3-step trace where step 2 is malformed: the trace must halt there
        and not attempt step 3, matching the 'rejection halts the chain' design."""
        c = ctx(p1="5 10 true")
        steps = [
            {"step_id": "s1", "operator": "numeric_compare",
             "args": [span("p1", 0, 1), span("p1", 2, 4)], "params": {"op": "lt"}},
            {"step_id": "s2", "operator": "frobnicate", "args": []},  # bad
            {"step_id": "s3", "operator": "negate", "args": [stepref("s1")]},
        ]
        verdicts, gate = run_trace(c, steps)
        self.assertEqual(len(verdicts), 2)  # stopped after the bad step
        self.assertEqual(verdicts[0].status, Status.ADMIT)
        self.assertEqual(verdicts[1].status, Status.REJECT)

    def test_full_chain_all_admit(self):
        c = ctx(p1="5 10")
        steps = [
            {"step_id": "s1", "operator": "numeric_compare",
             "args": [span("p1", 0, 1), span("p1", 2, 4)], "params": {"op": "lt"}},
            {"step_id": "s2", "operator": "negate", "args": [stepref("s1")]},
        ]
        verdicts, gate = run_trace(c, steps, expected_result_type=None)
        self.assertTrue(all(v.status == Status.ADMIT for v in verdicts))
        self.assertEqual(verdicts[0].value, True)   # 5 < 10
        self.assertEqual(verdicts[1].value, False)  # not True


class TestAdversarialEdgeCases(unittest.TestCase):
    def test_empty_args_for_fixed_arity_op(self):
        g = Gate(ctx(p1="x"))
        v = g.step({"step_id": "s1", "operator": "negate", "args": []})
        self.assertEqual(v.reason_code, ReasonCode.ARITY_MISMATCH)

    def test_too_many_args_for_fixed_arity_op(self):
        g = Gate(ctx(p1="true true"))
        v = g.step({"step_id": "s1", "operator": "negate",
                    "args": [span("p1", 0, 4), span("p1", 5, 9)]})
        self.assertEqual(v.reason_code, ReasonCode.ARITY_MISMATCH)

    def test_leaf_missing_ref_type(self):
        g = Gate(ctx(p1="true"))
        v = g.step({"step_id": "s1", "operator": "negate", "args": [{"doc_id": "p1"}]})
        self.assertEqual(v.reason_code, ReasonCode.SCHEMA_INVALID)

    def test_negative_span_offsets_rejected(self):
        g = Gate(ctx(p1="true"))
        v = g.step({"step_id": "s1", "operator": "negate",
                    "args": [span("p1", -1, 4)]})
        self.assertEqual(v.reason_code, ReasonCode.PROVENANCE_SPAN_NOT_FOUND)

    def test_start_greater_than_end_rejected(self):
        g = Gate(ctx(p1="true"))
        v = g.step({"step_id": "s1", "operator": "negate",
                    "args": [span("p1", 4, 1)]})
        self.assertEqual(v.reason_code, ReasonCode.PROVENANCE_SPAN_NOT_FOUND)


if __name__ == "__main__":
    unittest.main(verbosity=2)
