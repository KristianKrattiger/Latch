"""
test_gate.py -- >=30 unit tests for gate.py, including adversarial cases.

Run with: python -m unittest test_gate.py -v
"""

import unittest
from gate import Context, Gate, Status, ReasonCode, run_trace


def ctx(**docs):
    return Context(docs=docs)


def span(doc_id, text, start=None, end=None):
    """Build a span arg. start/end are accepted but ignored by the gate (kept for
    backward compat with any callers that pass them). text is required."""
    d = {"ref_type": "span", "doc_id": doc_id, "text": text}
    if start is not None:
        d["start"] = start
    if end is not None:
        d["end"] = end
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
                    "args": [span("p1", "5")], "params": {"op": "gt"}})
        self.assertEqual(v.reason_code, ReasonCode.ARITY_MISMATCH)

    def test_duplicate_step_id_rejected(self):
        g = Gate(ctx(p1="5 10"))
        step = {"step_id": "s1", "operator": "numeric_compare",
                "args": [span("p1", "5"), span("p1", "10")], "params": {"op": "gt"}}
        v1 = g.step(step)
        self.assertEqual(v1.status, Status.ADMIT)
        v2 = g.step(step)
        self.assertEqual(v2.reason_code, ReasonCode.SCHEMA_INVALID)

    def test_args_not_a_list(self):
        g = Gate(ctx(p1="hello"))
        v = g.step({"step_id": "s1", "operator": "negate", "args": "not a list"})
        self.assertEqual(v.reason_code, ReasonCode.SCHEMA_INVALID)


class TestProvenance(unittest.TestCase):
    def test_span_text_not_in_doc(self):
        """Text simply doesn't appear in the doc — provenance fails."""
        g = Gate(ctx(p1="5 hi"))
        v = g.step({"step_id": "s1", "operator": "numeric_compare",
                    "args": [span("p1", "5"), span("p1", "999")],
                    "params": {"op": "gt"}})
        self.assertEqual(v.reason_code, ReasonCode.PROVENANCE_SPAN_NOT_FOUND)

    def test_span_wrong_doc(self):
        g = Gate(ctx(p1="hi"))
        v = g.step({"step_id": "s1", "operator": "negate",
                    "args": [span("p999", "hi")]})
        self.assertEqual(v.reason_code, ReasonCode.PROVENANCE_SPAN_NOT_FOUND)

    def test_span_fabricated_text_not_in_doc_rejected(self):
        """Adversarial: claimed text '99' is not in 'revenue was 42' at all —
        provenance correctly fails under text-search."""
        g = Gate(ctx(p1="revenue was 42"))
        v = g.step({"step_id": "s1", "operator": "negate",
                    "args": [span("p1", "99")]})
        self.assertEqual(v.reason_code, ReasonCode.PROVENANCE_SPAN_NOT_FOUND)

    def test_span_text_match_ok(self):
        g = Gate(ctx(p1="true"))
        v = g.step({"step_id": "s1", "operator": "negate",
                    "args": [span("p1", "true")]})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertEqual(v.value, False)

    def test_span_text_search_finds_text_at_nonzero_offset(self):
        """Text is not at offset 0 but IS in the doc — must reach type-check, not provenance error."""
        g = Gate(ctx(p1="revenue was 42"))
        v = g.step({"step_id": "s1", "operator": "negate",
                    "args": [span("p1", "42")]})
        # "42" coerces to number; negate expects bool — TYPE_MISMATCH, not provenance error
        self.assertEqual(v.reason_code, ReasonCode.TYPE_MISMATCH)

    def test_span_text_ambiguous_match_does_not_admit(self):
        """'1907' appears twice in doc — gate must not silently pick one."""
        g = Gate(ctx(p1="born 1907 died 1907"))
        v = g.step({"step_id": "s1", "operator": "temporal_order",
                    "args": [span("p1", "1907"), span("p1", "1907")],
                    "params": {"op": "before"}})
        self.assertNotEqual(v.status, Status.ADMIT)

    def test_span_empty_text_rejected(self):
        g = Gate(ctx(p1="hello"))
        v = g.step({"step_id": "s1", "operator": "negate",
                    "args": [{"ref_type": "span", "doc_id": "p1", "text": ""}]})
        self.assertEqual(v.reason_code, ReasonCode.SCHEMA_INVALID)

    def test_span_missing_text_field_rejected(self):
        g = Gate(ctx(p1="hello"))
        v = g.step({"step_id": "s1", "operator": "negate",
                    "args": [{"ref_type": "span", "doc_id": "p1"}]})
        self.assertEqual(v.reason_code, ReasonCode.SCHEMA_INVALID)

    def test_start_end_fields_ignored_when_present(self):
        """start/end are accepted but ignored — text-search is the provenance check."""
        g = Gate(ctx(p1="true"))
        v = g.step({"step_id": "s1", "operator": "negate",
                    "args": [{"ref_type": "span", "doc_id": "p1",
                               "start": 999, "end": 1000, "text": "true"}]})
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
                     "args": [span("p1", "true")]})
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
                    "args": [span("p1", "42"), span("p1", "7")],
                    "params": {"op": "gt"}})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertTrue(v.value)  # 42 > 7, mechanically true, semantically meaningless here

    def test_type_mismatch_text_not_number(self):
        g = Gate(ctx(p1="hello world"))
        v = g.step({"step_id": "s1", "operator": "numeric_compare",
                    "args": [span("p1", "hello"), span("p1", "world")], "params": {"op": "gt"}})
        self.assertEqual(v.reason_code, ReasonCode.TYPE_MISMATCH)

    def test_count_requires_set_type(self):
        g = Gate(ctx(p1="42"))
        v = g.step({"step_id": "s1", "operator": "count", "args": [span("p1", "42")]})
        self.assertEqual(v.reason_code, ReasonCode.TYPE_MISMATCH)

    def test_bad_enum_op_rejected(self):
        g = Gate(ctx(p1="5 10"))
        v = g.step({"step_id": "s1", "operator": "numeric_compare",
                    "args": [span("p1", "5"), span("p1", "10")], "params": {"op": "frobnicate"}})
        self.assertEqual(v.reason_code, ReasonCode.TYPE_MISMATCH)

    def test_result_type_mismatch_on_final_step(self):
        g = Gate(ctx(p1="5 10"), expected_result_type="number")
        v = g.step({"step_id": "s1", "operator": "numeric_compare",
                    "args": [span("p1", "5"), span("p1", "10")],
                    "params": {"op": "gt"}, "is_final": True})
        self.assertEqual(v.reason_code, ReasonCode.RESULT_TYPE_MISMATCH)

    def test_result_type_match_on_final_step(self):
        g = Gate(ctx(p1="5 10"), expected_result_type="bool")
        v = g.step({"step_id": "s1", "operator": "numeric_compare",
                    "args": [span("p1", "5"), span("p1", "10")],
                    "params": {"op": "gt"}, "is_final": True})
        self.assertEqual(v.status, Status.ADMIT)


class TestOperatorSemantics(unittest.TestCase):
    def test_numeric_compare_all_ops(self):
        for op, expected in [("lt", True), ("le", True), ("gt", False), ("ge", False),
                              ("eq", False), ("neq", True)]:
            gg = Gate(ctx(p1="5 10"))
            v = gg.step({"step_id": "s1", "operator": "numeric_compare",
                         "args": [span("p1", "5"), span("p1", "10")], "params": {"op": op}})
            self.assertEqual(v.value, expected, msg=f"op={op}")

    def test_arithmetic_div_by_zero_abstains(self):
        g = Gate(ctx(p1="5 0"))
        v = g.step({"step_id": "s1", "operator": "arithmetic",
                    "args": [span("p1", "5"), span("p1", "0")], "params": {"op": "div"}})
        self.assertEqual(v.status, Status.ABSTAIN)
        self.assertEqual(v.reason_code, ReasonCode.DIVISION_BY_ZERO)

    def test_arithmetic_add(self):
        g = Gate(ctx(p1="5 10"))
        v = g.step({"step_id": "s1", "operator": "arithmetic",
                    "args": [span("p1", "5"), span("p1", "10")], "params": {"op": "add"}})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertEqual(v.value, 15.0)

    def test_temporal_order_same_precision(self):
        # Use two docs so each date appears only once
        g = Gate(ctx(p1="2001-01-01", p2="2002-01-01"))
        v = g.step({"step_id": "s1", "operator": "temporal_order",
                    "args": [span("p1", "2001-01-01"), span("p2", "2002-01-01")],
                    "params": {"op": "before"}})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertTrue(v.value)

    def test_temporal_order_mismatched_precision_abstains_when_ambiguous(self):
        """2001 vs 2001-06-15 -- year precision collapses to the same year, so the
        before/after ordering genuinely cannot be determined without more info."""
        g = Gate(ctx(p1="2001", p2="2001-06-15"))
        v = g.step({"step_id": "s1", "operator": "temporal_order",
                    "args": [span("p1", "2001"), span("p2", "2001-06-15")],
                    "params": {"op": "before"}})
        self.assertEqual(v.status, Status.ABSTAIN)
        self.assertEqual(v.reason_code, ReasonCode.AMBIGUOUS_DATE_PRECISION)

    def test_temporal_order_mismatched_precision_resolves_when_unambiguous(self):
        """2001 vs 2005-06-15 -- different years, so precision mismatch doesn't
        actually create ambiguity. Should ADMIT, not ABSTAIN."""
        g = Gate(ctx(p1="2001", p2="2005-06-15"))
        v = g.step({"step_id": "s1", "operator": "temporal_order",
                    "args": [span("p1", "2001"), span("p2", "2005-06-15")],
                    "params": {"op": "before"}})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertTrue(v.value)

    def test_date_diff_years(self):
        g = Gate(ctx(p1="2001-01-01", p2="2010-01-01"))
        v = g.step({"step_id": "s1", "operator": "date_diff",
                    "args": [span("p2", "2010-01-01"), span("p1", "2001-01-01")],
                    "params": {"unit": "years"}})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertEqual(v.value, 9)

    def test_date_diff_mismatched_precision_abstains(self):
        g = Gate(ctx(p1="2001", p2="2001-01-01"))
        v = g.step({"step_id": "s1", "operator": "date_diff",
                    "args": [span("p1", "2001"), span("p2", "2001-01-01")],
                    "params": {"unit": "years"}})
        self.assertEqual(v.status, Status.ABSTAIN)

    def test_transitive_chain_whitelisted_relation_admits(self):
        # Use separate docs so each "located_in" appears exactly once
        g = Gate(ctx(p1="located_in", p2="located_in"))
        v = g.step({"step_id": "s1", "operator": "transitive_chain",
                    "args": [span("p1", "located_in"), span("p2", "located_in")]})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertEqual(v.value, "located_in")

    def test_transitive_chain_non_transitive_relation_rejected(self):
        """Adversarial: a model tries to chain 'parent_of' transitively, which
        would silently produce a wrong grandparent-as-parent claim if allowed."""
        g = Gate(ctx(p1="parent_of", p2="parent_of"))
        v = g.step({"step_id": "s1", "operator": "transitive_chain",
                    "args": [span("p1", "parent_of"), span("p2", "parent_of")]})
        self.assertEqual(v.reason_code, ReasonCode.NON_TRANSITIVE_RELATION)

    def test_transitive_chain_mismatched_relations_rejected(self):
        g = Gate(ctx(p1="located_in part_of"))
        v = g.step({"step_id": "s1", "operator": "transitive_chain",
                    "args": [span("p1", "located_in"), span("p1", "part_of")]})
        self.assertEqual(v.reason_code, ReasonCode.NON_TRANSITIVE_RELATION)

    def test_arg_extreme_simple(self):
        g = Gate(ctx(p1="x"))
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
        # Use separate docs so "true"/"false" each appear once per doc
        g = Gate(ctx(p1="true", p2="true", p3="false"))
        v = g.step({"step_id": "s1", "operator": "conjoin",
                    "args": [span("p1", "true"), span("p2", "true"), span("p3", "false")]})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertFalse(v.value)

    def test_disjoin_variadic_bools(self):
        g = Gate(ctx(p1="false", p2="false", p3="true"))
        v = g.step({"step_id": "s1", "operator": "disjoin",
                    "args": [span("p1", "false"), span("p2", "false"), span("p3", "true")]})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertTrue(v.value)

    def test_set_membership(self):
        g = Gate(ctx(p1="A"))
        g.admitted["s0"] = (__import__("gate").TVal("set", {"A", "B", "C"}), None)
        v = g.step({"step_id": "s1", "operator": "set_membership",
                    "args": [span("p1", "A"), stepref("s0")]})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertTrue(v.value)


class TestEntityEqual(unittest.TestCase):
    def test_entity_equal_same_nationality(self):
        """The motivating case from ANNOTATION_GUIDE.md: 'same nationality' questions
        need an entity equality test between two resolved entity-typed values."""
        g = Gate(ctx(p1="American", p2="American"))
        v = g.step({"step_id": "s1", "operator": "entity_equal",
                    "args": [span("p1", "American"), span("p2", "American")]})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertTrue(v.value)

    def test_entity_equal_different_entities(self):
        g = Gate(ctx(p1="American British"))
        v = g.step({"step_id": "s1", "operator": "entity_equal",
                    "args": [span("p1", "American"), span("p1", "British")]})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertFalse(v.value)

    def test_entity_equal_from_prior_steps(self):
        """Equality test where both entities come from prior admitted steps."""
        g2 = Gate(ctx(p1="x"))
        import gate as _g
        g2.admitted["s0a"] = (_g.TVal("entity", "French"), None)
        g2.admitted["s0b"] = (_g.TVal("entity", "French"), None)
        v = g2.step({"step_id": "s1", "operator": "entity_equal",
                     "args": [stepref("s0a"), stepref("s0b")]})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertTrue(v.value)

    def test_entity_equal_adversarial_number_as_entity_rejected(self):
        """'042' != '42' as entities even though they're the same number.
        Use separate docs so each token is unambiguous."""
        g = Gate(ctx(p1="042", p2="42"))
        v = g.step({"step_id": "s1", "operator": "entity_equal",
                    "args": [span("p1", "042"), span("p2", "42")]})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertFalse(v.value)  # "042" != "42" as entity strings


class TestRunTrace(unittest.TestCase):
    def test_full_chain_halts_on_rejection(self):
        """A 3-step trace where step 2 is malformed: the trace must halt there
        and not attempt step 3."""
        c = ctx(p1="5 10 true")
        steps = [
            {"step_id": "s1", "operator": "numeric_compare",
             "args": [span("p1", "5"), span("p1", "10")], "params": {"op": "lt"}},
            {"step_id": "s2", "operator": "frobnicate", "args": []},  # bad
            {"step_id": "s3", "operator": "negate", "args": [stepref("s1")]},
        ]
        verdicts, gate = run_trace(c, steps)
        self.assertEqual(len(verdicts), 2)
        self.assertEqual(verdicts[0].status, Status.ADMIT)
        self.assertEqual(verdicts[1].status, Status.REJECT)

    def test_full_chain_all_admit(self):
        c = ctx(p1="5 10")
        steps = [
            {"step_id": "s1", "operator": "numeric_compare",
             "args": [span("p1", "5"), span("p1", "10")], "params": {"op": "lt"}},
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
        g = Gate(ctx(p1="true", p2="true"))
        v = g.step({"step_id": "s1", "operator": "negate",
                    "args": [span("p1", "true"), span("p2", "true")]})
        self.assertEqual(v.reason_code, ReasonCode.ARITY_MISMATCH)

    def test_leaf_missing_ref_type(self):
        g = Gate(ctx(p1="true"))
        v = g.step({"step_id": "s1", "operator": "negate", "args": [{"doc_id": "p1"}]})
        self.assertEqual(v.reason_code, ReasonCode.SCHEMA_INVALID)


class TestParseDateNaturalLanguage(unittest.TestCase):
    """_parse_date() must handle the free-text date formats seen in
    2WikiMultihopQA bridge_comparison docs."""

    def _parse(self, s):
        from gate import _parse_date
        return _parse_date(s)

    # --- ISO / structured (regression) ---

    def test_iso_ymd(self):
        d, prec = self._parse("1991-03-12")
        self.assertEqual(d.year, 1991)
        self.assertEqual(d.month, 3)
        self.assertEqual(prec, "day")

    def test_iso_year_only(self):
        d, prec = self._parse("1935")
        self.assertEqual(d.year, 1935)
        self.assertEqual(prec, "year")

    # --- "Month D, YYYY" ---

    def test_month_day_year_with_comma(self):
        d, prec = self._parse("August 3, 1927")
        self.assertEqual((d.year, d.month, d.day), (1927, 8, 3))
        self.assertEqual(prec, "day")

    def test_month_day_year_november(self):
        d, prec = self._parse("November 15, 1977")
        self.assertEqual((d.year, d.month, d.day), (1977, 11, 15))

    def test_month_day_year_no_comma(self):
        d, prec = self._parse("October 5 1985")
        self.assertEqual((d.year, d.month, d.day), (1985, 10, 5))
        self.assertEqual(prec, "day")

    # --- "D Month YYYY" ---

    def test_day_month_year(self):
        d, prec = self._parse("9 May 1926")
        self.assertEqual((d.year, d.month, d.day), (1926, 5, 9))
        self.assertEqual(prec, "day")

    def test_day_month_year_two_digit(self):
        d, prec = self._parse("17 November 1950")
        self.assertEqual((d.year, d.month, d.day), (1950, 11, 17))

    def test_day_month_year_september(self):
        d, prec = self._parse("20 September 1975")
        self.assertEqual((d.year, d.month, d.day), (1975, 9, 20))

    # --- Date ranges: take first date ---

    def test_date_range_em_dash(self):
        # "March 10, 1892 – March 1, 1952" → 1892-03-10
        d, prec = self._parse("March 10, 1892 – March 1, 1952")
        self.assertEqual((d.year, d.month, d.day), (1892, 3, 10))
        self.assertEqual(prec, "day")

    def test_date_range_hyphen(self):
        d, prec = self._parse("1892-03-10 - 1952-03-01")
        self.assertEqual((d.year, d.month, d.day), (1892, 3, 10))

    def test_year_range(self):
        # "1892–1952" → year precision, 1892
        d, prec = self._parse("1892–1952")
        self.assertEqual(d.year, 1892)
        self.assertEqual(prec, "year")

    # --- Multi-date strings: take first date ---

    def test_multi_date_string(self):
        # "25 October 1898 12 April 1979" → 1898-10-25
        d, prec = self._parse("25 October 1898 12 April 1979")
        self.assertEqual((d.year, d.month, d.day), (1898, 10, 25))

    # --- Non-dates must return None ---

    def test_non_date_returns_none(self):
        self.assertIsNone(self._parse("Dallas 362"))

    def test_non_date_movie_title_returns_none(self):
        self.assertIsNone(self._parse("Revenge of the Nerds III"))

    # --- Gate integration: temporal_order with natural-language dates ---

    def test_temporal_order_natural_language_month_day_year(self):
        g = Gate(ctx(p1="August 3, 1927", p2="November 15, 1977"))
        v = g.step({"step_id": "s1", "operator": "temporal_order",
                    "args": [span("p1", "August 3, 1927"), span("p2", "November 15, 1977")],
                    "params": {"op": "before"}})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertTrue(v.value)

    def test_temporal_order_natural_language_day_month_year(self):
        g = Gate(ctx(p1="9 May 1926", p2="17 November 1950"))
        v = g.step({"step_id": "s1", "operator": "temporal_order",
                    "args": [span("p1", "9 May 1926"), span("p2", "17 November 1950")],
                    "params": {"op": "before"}})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertTrue(v.value)

    def test_temporal_order_range_string_takes_first(self):
        # "March 10, 1892 – March 1, 1952" vs "1991-03-12"
        g = Gate(ctx(p1="March 10, 1892 – March 1, 1952", p2="1991-03-12"))
        v = g.step({"step_id": "s1", "operator": "temporal_order",
                    "args": [span("p1", "March 10, 1892 – March 1, 1952"),
                             span("p2", "1991-03-12")],
                    "params": {"op": "before"}})
        self.assertEqual(v.status, Status.ADMIT)
        self.assertTrue(v.value)

    def test_span_missing_doc_id_rejected(self):
        g = Gate(ctx(p1="true"))
        v = g.step({"step_id": "s1", "operator": "negate",
                    "args": [{"ref_type": "span", "text": "true"}]})
        self.assertEqual(v.reason_code, ReasonCode.SCHEMA_INVALID)

    def test_span_text_in_wrong_doc_rejected(self):
        """Text exists in p1 but step claims p2 which doesn't have it."""
        g = Gate(ctx(p1="true", p2="false"))
        v = g.step({"step_id": "s1", "operator": "negate",
                    "args": [span("p2", "true")]})
        self.assertEqual(v.reason_code, ReasonCode.PROVENANCE_SPAN_NOT_FOUND)


if __name__ == "__main__":
    unittest.main(verbosity=2)
