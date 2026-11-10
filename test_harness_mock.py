"""
test_harness_mock.py -- end-to-end harness test against a MOCK endpoint (no real
model, no network). Verifies modes A/B/C, JSON extraction robustness (including
malformed outputs), and the gate hookup, all without needing a model running.

Run with: python -m unittest test_harness_mock.py -v
"""

import unittest
from dataclasses import asdict

import harness
from harness import CallRecord


SAMPLE_QUESTION = {
    "id": "q1",
    "type": "comparison",
    "question": "Which number is bigger, the one in doc A or doc B?",
    "answer": "doc A",
    "result_type": "bool",
    "docs": {
        "p0": {"title": "A", "text": "The value here is 42."},
        "p1": {"title": "B", "text": "The value here is 7."},
    },
}


def make_mock_caller(response_text: str, error: str = None):
    def _caller(base_url, model, messages, mode, **kw):
        return CallRecord(model=model, mode=mode, forward_passes=1,
                           input_tokens=50, output_tokens=20,
                           token_count_source="estimated", wall_time_s=0.01,
                           raw_response_text=response_text, error=error)
    return _caller


WELL_FORMED_STEPS = """[
  {"step_id": "s1", "operator": "numeric_compare",
   "args": [
     {"ref_type": "span", "doc_id": "p0", "start": 18, "end": 20, "text": "42"},
     {"ref_type": "span", "doc_id": "p1", "start": 18, "end": 19, "text": "7"}
   ],
   "params": {"op": "gt"}, "result_type": "bool", "is_final": true}
]"""

FENCED_STEPS = "Sure, here you go:\n```json\n" + WELL_FORMED_STEPS + "\n```\nHope that helps!"

MALFORMED_NOT_JSON = "I think the answer is probably doc A because 42 > 7."

MALFORMED_TRUNCATED_JSON = '[{"step_id": "s1", "operator": "numeric_compare", "args": ['

SPAN_MISMATCH_STEPS = """[
  {"step_id": "s1", "operator": "numeric_compare",
   "args": [
     {"ref_type": "span", "doc_id": "p0", "start": 18, "end": 20, "text": "99"},
     {"ref_type": "span", "doc_id": "p1", "start": 18, "end": 19, "text": "7"}
   ],
   "params": {"op": "gt"}, "result_type": "bool", "is_final": true}
]"""  # claims "99" but the actual text at those offsets is "42" -- adversarial


class TestJsonExtraction(unittest.TestCase):
    def test_bare_array_parses(self):
        steps, err = harness.extract_steps_json(WELL_FORMED_STEPS)
        self.assertIsNone(err)
        self.assertEqual(len(steps), 1)

    def test_fenced_code_block_parses(self):
        steps, err = harness.extract_steps_json(FENCED_STEPS)
        self.assertIsNone(err)
        self.assertEqual(steps[0]["operator"], "numeric_compare")

    def test_non_json_prose_fails_cleanly(self):
        steps, err = harness.extract_steps_json(MALFORMED_NOT_JSON)
        self.assertIsNone(steps)
        self.assertEqual(err, "no_valid_json_found")

    def test_truncated_json_fails_cleanly(self):
        steps, err = harness.extract_steps_json(MALFORMED_TRUNCATED_JSON)
        self.assertIsNone(steps)
        self.assertEqual(err, "no_valid_json_found")

    def test_empty_array_is_valid_parse(self):
        """An empty array is a legitimate formalizer output (per the few-shot prompt's
        Example 2: 'no operator needed'), not a parse failure."""
        steps, err = harness.extract_steps_json("[]")
        self.assertIsNone(err)
        self.assertEqual(steps, [])


class TestModeA(unittest.TestCase):
    def test_mode_a_well_formed(self):
        result = harness.run_mode_a(SAMPLE_QUESTION, "http://fake", "fake-model",
                                     caller=make_mock_caller(WELL_FORMED_STEPS))
        self.assertIsNone(result["parse_error"])
        self.assertEqual(len(result["parsed_steps"]), 1)
        self.assertEqual(result["mode"], "A")

    def test_mode_a_malformed_output_recorded_not_crashed(self):
        result = harness.run_mode_a(SAMPLE_QUESTION, "http://fake", "fake-model",
                                     caller=make_mock_caller(MALFORMED_NOT_JSON))
        self.assertIsNone(result["parsed_steps"])
        self.assertEqual(result["parse_error"], "no_valid_json_found")

    def test_mode_a_endpoint_error_recorded_not_crashed(self):
        result = harness.run_mode_a(SAMPLE_QUESTION, "http://fake", "fake-model",
                                     caller=make_mock_caller("", error="connection refused"))
        self.assertEqual(result["parse_error"], "connection refused")
        self.assertIsNone(result["parsed_steps"])


class TestModeB(unittest.TestCase):
    def test_mode_b_well_formed_admits_and_evaluates(self):
        result = harness.run_mode_b(SAMPLE_QUESTION, "http://fake", "fake-model",
                                     caller=make_mock_caller(WELL_FORMED_STEPS))
        self.assertEqual(result["final_status"], "ADMIT")
        self.assertTrue(result["answer"])  # 42 > 7 -> True
        self.assertEqual(result["gate_verdicts"][0]["status"], "ADMIT")

    def test_mode_b_parse_failure_abstains(self):
        result = harness.run_mode_b(SAMPLE_QUESTION, "http://fake", "fake-model",
                                     caller=make_mock_caller(MALFORMED_NOT_JSON))
        self.assertEqual(result["final_status"], "ABSTAIN_PARSE_FAILURE")
        self.assertIsNone(result["answer"])

    def test_mode_b_adversarial_span_mismatch_rejected_not_silently_admitted(self):
        """This is the key adversarial case for the whole pilot: a model that claims
        a span says '99' when the context actually says '42' at those offsets must be
        REJECTed, not ADMITted with a wrong value baked in."""
        result = harness.run_mode_b(SAMPLE_QUESTION, "http://fake", "fake-model",
                                     caller=make_mock_caller(SPAN_MISMATCH_STEPS))
        self.assertEqual(result["final_status"], "ABSTAIN_GATE_REJECTION")
        self.assertEqual(result["gate_verdicts"][0]["reason_code"], "PROVENANCE_SPAN_TEXT_MISMATCH")

    def test_mode_b_empty_steps_is_abstain_not_crash(self):
        result = harness.run_mode_b(SAMPLE_QUESTION, "http://fake", "fake-model",
                                     caller=make_mock_caller("[]"))
        self.assertEqual(result["final_status"], "ABSTAIN_GATE_REJECTION")  # no ADMIT steps at all


class TestModeC(unittest.TestCase):
    def test_mode_c_extracts_answer_line(self):
        text = "Doc A has 42, doc B has 7, so A is bigger.\nAnswer: doc A"
        result = harness.run_mode_c(SAMPLE_QUESTION, "http://fake", "fake-model",
                                     caller=make_mock_caller(text))
        self.assertEqual(result["answer"], "doc A")

    def test_mode_c_missing_answer_line_is_none_not_crash(self):
        text = "I'm not sure which is bigger."
        result = harness.run_mode_c(SAMPLE_QUESTION, "http://fake", "fake-model",
                                     caller=make_mock_caller(text))
        self.assertIsNone(result["answer"])


class TestArmStubsRaiseCleanly(unittest.TestCase):
    def test_arm4_stub_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            harness.run_arm4_self_consistency(SAMPLE_QUESTION, "http://fake", "fake-model")

    def test_arm4b_stub_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError):
            harness.run_arm4b_pal_style(SAMPLE_QUESTION, "http://fake", "fake-model")


class TestHttpErrorCapture(unittest.TestCase):
    def test_http_error_body_captured_in_error_field(self):
        """call_endpoint should capture the response body from HTTP errors,
        not just the status line. This is critical for diagnosing server-side
        failures (e.g. Ollama 500s) after the fact."""
        import io
        import urllib.error
        from unittest.mock import patch

        error_body = b'{"error":"model not loaded"}'
        http_error = urllib.error.HTTPError(
            url="http://fake/v1/chat/completions",
            code=500, msg="Internal Server Error",
            hdrs=None, fp=io.BytesIO(error_body))

        with patch("urllib.request.urlopen", side_effect=http_error):
            record = harness.call_endpoint("http://fake/v1", "m", [], "A")
        self.assertIn("500", record.error)
        self.assertIn("model not loaded", record.error)


class TestMatchedComputeLedgerFields(unittest.TestCase):
    def test_call_record_has_required_ledger_fields(self):
        record = make_mock_caller(WELL_FORMED_STEPS)("http://fake", "m", [], "A")
        d = asdict(record)
        for field_name in ("forward_passes", "input_tokens", "output_tokens",
                           "token_count_source", "wall_time_s"):
            self.assertIn(field_name, d)


if __name__ == "__main__":
    unittest.main(verbosity=2)
