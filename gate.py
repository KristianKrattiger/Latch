"""
gate.py -- reference mechanical admission gate for the hard-gated-SLM-chain pilot.

Implements the operator set and schema defined in OPERATORS.md. Pure stdlib, no
third-party dependencies, so it runs anywhere Python 3.9+ runs.

This module answers exactly one question per step: "is this a well-typed application
of operator O to already-admitted inputs, with provenance that checks out?" It does
NOT judge truth, relevance, or whether the right operator/operands were chosen. See
OPERATORS.md's "Known false-pass class" section before trusting a green run.

Public API:
    Context(docs: dict[str, str])
    Gate(context: Context, expected_result_type: str | None = None)
    gate.step(step: dict) -> Verdict
    Verdict.status in {"ADMIT", "REJECT", "ABSTAIN"}
    Verdict.reason_code: str | None
    Verdict.value: Any  (the evaluated result, only meaningful on ADMIT)
"""

from __future__ import annotations

import datetime
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Reason codes (stable list -- do not rename without updating OPERATORS.md)
# ---------------------------------------------------------------------------

class ReasonCode(str, Enum):
    SCHEMA_INVALID = "SCHEMA_INVALID"
    UNKNOWN_OPERATOR = "UNKNOWN_OPERATOR"
    ARITY_MISMATCH = "ARITY_MISMATCH"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    PROVENANCE_SPAN_NOT_FOUND = "PROVENANCE_SPAN_NOT_FOUND"
    PROVENANCE_SPAN_TEXT_MISMATCH = "PROVENANCE_SPAN_TEXT_MISMATCH"
    UNADMITTED_STEP_REF = "UNADMITTED_STEP_REF"
    CYCLE_DETECTED = "CYCLE_DETECTED"
    RESULT_TYPE_MISMATCH = "RESULT_TYPE_MISMATCH"
    NON_TRANSITIVE_RELATION = "NON_TRANSITIVE_RELATION"
    DIVISION_BY_ZERO = "DIVISION_BY_ZERO"
    AMBIGUOUS_DATE_PRECISION = "AMBIGUOUS_DATE_PRECISION"
    TIE = "TIE"
    EVAL_ERROR = "EVAL_ERROR"


class Status(str, Enum):
    ADMIT = "ADMIT"
    REJECT = "REJECT"
    ABSTAIN = "ABSTAIN"


@dataclass
class Verdict:
    status: Status
    reason_code: Optional[ReasonCode] = None
    value: Any = None
    message: str = ""

    def __repr__(self) -> str:
        if self.status == Status.ADMIT:
            return f"ADMIT(value={self.value!r})"
        return f"{self.status.value}({self.reason_code.value if self.reason_code else '?'}: {self.message})"


# ---------------------------------------------------------------------------
# Context: the only source of ground truth for leaf provenance
# ---------------------------------------------------------------------------

@dataclass
class Context:
    """docs: mapping of doc_id -> full text of that document/paragraph."""
    docs: Dict[str, str]

    def span_text(self, doc_id: str, start: int, end: int) -> Optional[str]:
        doc = self.docs.get(doc_id)
        if doc is None:
            return None
        if start < 0 or end > len(doc) or start >= end:
            return None
        return doc[start:end]


# ---------------------------------------------------------------------------
# Typed values. We keep a tiny internal type system: bool, number, entity,
# date, set, relation. "entity" and "relation" are just tagged strings --
# the gate does not attempt to understand what they denote, only that they
# are provenanced spans or prior-step outputs of the declared type.
# ---------------------------------------------------------------------------

class TVal:
    """A typed value flowing through the gate: (type_name, python_value)."""
    __slots__ = ("type_name", "value")

    def __init__(self, type_name: str, value: Any):
        self.type_name = type_name
        self.value = value

    def __repr__(self):
        return f"TVal({self.type_name}, {self.value!r})"


# Transitive-relation whitelist (OPERATORS.md #7). Deliberately tiny.
TRANSITIVE_RELATIONS = {"located_in", "part_of", "subclass_of"}

DATE_FORMATS = ("%Y-%m-%d", "%Y-%m", "%Y")


def _parse_date(s: str) -> Optional[Tuple[datetime.date, str]]:
    """Returns (date, precision) where precision in {'day','month','year'}."""
    for fmt, prec in zip(DATE_FORMATS, ("day", "month", "year")):
        try:
            d = datetime.datetime.strptime(s.strip(), fmt).date()
            return d, prec
        except ValueError:
            continue
    return None


def _coerce_number(s: Any) -> Optional[float]:
    if isinstance(s, (int, float)):
        return float(s)
    if isinstance(s, str):
        cleaned = s.strip().replace(",", "").replace("$", "").rstrip("%")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Operator definitions: (arity_or_None_for_variadic, expected_arg_types,
# param_schema, eval_fn). eval_fn receives resolved TVal args + raw params
# dict and must return a Verdict (so it can itself raise ABSTAIN/REJECT for
# evaluation-time conditions like division by zero or ties).
# ---------------------------------------------------------------------------

def _eval_numeric_compare(args: List[TVal], params: dict) -> Verdict:
    op = params.get("op")
    if op not in {"lt", "le", "gt", "ge", "eq", "neq"}:
        return Verdict(Status.REJECT, ReasonCode.TYPE_MISMATCH, message="bad op for numeric_compare")
    a, b = args[0].value, args[1].value
    result = {
        "lt": a < b, "le": a <= b, "gt": a > b, "ge": a >= b,
        "eq": a == b, "neq": a != b,
    }[op]
    return Verdict(Status.ADMIT, value=result)


def _eval_count(args: List[TVal], params: dict) -> Verdict:
    items = args[0].value
    return Verdict(Status.ADMIT, value=len(items))


def _eval_negate(args: List[TVal], params: dict) -> Verdict:
    return Verdict(Status.ADMIT, value=not args[0].value)


def _eval_conjoin(args: List[TVal], params: dict) -> Verdict:
    xs = [a.value for a in args] if len(args) > 1 else list(args[0].value)
    return Verdict(Status.ADMIT, value=all(xs))


def _eval_disjoin(args: List[TVal], params: dict) -> Verdict:
    xs = [a.value for a in args] if len(args) > 1 else list(args[0].value)
    return Verdict(Status.ADMIT, value=any(xs))


def _eval_temporal_order(args: List[TVal], params: dict) -> Verdict:
    op = params.get("op")
    if op not in {"before", "after", "same"}:
        return Verdict(Status.REJECT, ReasonCode.TYPE_MISMATCH, message="bad op for temporal_order")
    (d_a, prec_a), (d_b, prec_b) = args[0].value, args[1].value
    if prec_a != prec_b:
        # conservative: only ABSTAIN if the coarser precision could flip the outcome.
        # Truncate BOTH dates to the coarser of the two precisions; if they collapse
        # to the same bucket, the finer-grained ordering is genuinely undetermined.
        coarser = prec_a if _precision_rank(prec_a) < _precision_rank(prec_b) else prec_b
        coarse_a = _truncate_to(d_a, coarser)
        coarse_b = _truncate_to(d_b, coarser)
        if coarse_a == coarse_b:
            return Verdict(Status.ABSTAIN, ReasonCode.AMBIGUOUS_DATE_PRECISION,
                            message="mixed-precision dates collide at the coarser precision")
    result = {"before": d_a < d_b, "after": d_a > d_b, "same": d_a == d_b}[op]
    return Verdict(Status.ADMIT, value=result)


def _precision_rank(p: str) -> int:
    return {"day": 2, "month": 1, "year": 0}[p]


def _truncate_to(d: datetime.date, prec: str) -> Tuple[int, int, int]:
    if prec == "year":
        return (d.year, 0, 0)
    if prec == "month":
        return (d.year, d.month, 0)
    return (d.year, d.month, d.day)


def _eval_set_membership(args: List[TVal], params: dict) -> Verdict:
    x, items = args[0].value, args[1].value
    return Verdict(Status.ADMIT, value=x in items)


def _eval_transitive_chain(args: List[TVal], params: dict) -> Verdict:
    rel_ab, rel_bc = args[0].value, args[1].value
    if rel_ab != rel_bc:
        return Verdict(Status.REJECT, ReasonCode.NON_TRANSITIVE_RELATION,
                        message=f"cannot chain distinct relations {rel_ab!r} and {rel_bc!r}")
    if rel_ab not in TRANSITIVE_RELATIONS:
        return Verdict(Status.REJECT, ReasonCode.NON_TRANSITIVE_RELATION,
                        message=f"{rel_ab!r} is not on the transitive-relation whitelist")
    return Verdict(Status.ADMIT, value=rel_ab)


def _eval_arithmetic(args: List[TVal], params: dict) -> Verdict:
    op = params.get("op")
    if op not in {"add", "sub", "mul", "div"}:
        return Verdict(Status.REJECT, ReasonCode.TYPE_MISMATCH, message="bad op for arithmetic")
    a, b = args[0].value, args[1].value
    if op == "div" and b == 0:
        return Verdict(Status.ABSTAIN, ReasonCode.DIVISION_BY_ZERO)
    result = {"add": a + b, "sub": a - b, "mul": a * b, "div": a / b if b != 0 else math.nan}[op]
    return Verdict(Status.ADMIT, value=result)


def _eval_date_diff(args: List[TVal], params: dict) -> Verdict:
    unit = params.get("unit")
    if unit not in {"days", "months", "years"}:
        return Verdict(Status.REJECT, ReasonCode.TYPE_MISMATCH, message="bad unit for date_diff")
    (d_a, prec_a), (d_b, prec_b) = args[0].value, args[1].value
    if prec_a != prec_b:
        return Verdict(Status.ABSTAIN, ReasonCode.AMBIGUOUS_DATE_PRECISION,
                        message="date_diff needs matching precision")
    delta_days = (d_a - d_b).days
    if unit == "days":
        value = delta_days
    elif unit == "months":
        value = (d_a.year - d_b.year) * 12 + (d_a.month - d_b.month)
    else:
        value = d_a.year - d_b.year
    return Verdict(Status.ADMIT, value=value)


def _eval_arg_extreme(args: List[TVal], params: dict) -> Verdict:
    mode = params.get("mode")
    if mode not in {"max", "min"}:
        return Verdict(Status.REJECT, ReasonCode.TYPE_MISMATCH, message="bad mode for arg_extreme")
    items = args[0].value  # list of (entity, number)
    if not items:
        return Verdict(Status.REJECT, ReasonCode.TYPE_MISMATCH, message="empty items list")
    key = max if mode == "max" else min
    best_val = key(v for _, v in items)
    winners = [e for e, v in items if v == best_val]
    if len(winners) > 1:
        return Verdict(Status.ABSTAIN, ReasonCode.TIE, message=f"tie among {winners}")
    return Verdict(Status.ADMIT, value=winners[0])


def _eval_aggregate(args: List[TVal], params: dict) -> Verdict:
    op = params.get("op")
    if op not in {"sum", "avg", "min", "max"}:
        return Verdict(Status.REJECT, ReasonCode.TYPE_MISMATCH, message="bad op for aggregate")
    items = args[0].value
    if not items:
        return Verdict(Status.REJECT, ReasonCode.TYPE_MISMATCH, message="empty items list")
    value = {"sum": sum(items), "avg": sum(items) / len(items), "min": min(items), "max": max(items)}[op]
    return Verdict(Status.ADMIT, value=value)


@dataclass
class OpSpec:
    arity: Optional[int]          # None = variadic (conjoin/disjoin accept 1 list OR N bools)
    arg_types: List[str]          # expected type per positional arg ("number","bool","entity","date","set","relation","list_bool","list_entity_number","list_number")
    eval_fn: Callable[[List[TVal], dict], Verdict]


OPERATORS: Dict[str, OpSpec] = {
    "numeric_compare": OpSpec(2, ["number", "number"], _eval_numeric_compare),
    "count": OpSpec(1, ["set"], _eval_count),
    "negate": OpSpec(1, ["bool"], _eval_negate),
    "conjoin": OpSpec(None, ["bool"], _eval_conjoin),       # variadic bools, or 1 list_bool
    "disjoin": OpSpec(None, ["bool"], _eval_disjoin),
    "temporal_order": OpSpec(2, ["date", "date"], _eval_temporal_order),
    "set_membership": OpSpec(2, ["entity", "set"], _eval_set_membership),
    "transitive_chain": OpSpec(2, ["relation", "relation"], _eval_transitive_chain),
    "arithmetic": OpSpec(2, ["number", "number"], _eval_arithmetic),
    "date_diff": OpSpec(2, ["date", "date"], _eval_date_diff),
    "arg_extreme": OpSpec(1, ["list_entity_number"], _eval_arg_extreme),
    "aggregate": OpSpec(1, ["list_number"], _eval_aggregate),
}

# What "result_type" each operator produces, for the final-step result-type check.
OPERATOR_RESULT_TYPE: Dict[str, str] = {
    "numeric_compare": "bool", "count": "number", "negate": "bool", "conjoin": "bool",
    "disjoin": "bool", "temporal_order": "bool", "set_membership": "bool",
    "transitive_chain": "relation", "arithmetic": "number", "date_diff": "number",
    "arg_extreme": "entity", "aggregate": "number",
}


# ---------------------------------------------------------------------------
# The Gate
# ---------------------------------------------------------------------------

class Gate:
    def __init__(self, context: Context, expected_result_type: Optional[str] = None):
        self.context = context
        self.expected_result_type = expected_result_type
        self.admitted: Dict[str, Tuple[TVal, Any]] = {}  # step_id -> (resolved TVal, raw verdict value)
        self._admission_order: List[str] = []

    # -- leaf resolution -----------------------------------------------
    def _resolve_leaf(self, arg: dict, expected_type: str) -> Tuple[Optional[TVal], Optional[Verdict]]:
        if not isinstance(arg, dict) or "ref_type" not in arg:
            return None, Verdict(Status.REJECT, ReasonCode.SCHEMA_INVALID, message="leaf missing ref_type")

        if arg["ref_type"] == "step":
            step_id = arg.get("step_id")
            if step_id not in self.admitted:
                return None, Verdict(Status.REJECT, ReasonCode.UNADMITTED_STEP_REF,
                                      message=f"step {step_id!r} not admitted (or references itself/future step)")
            tval, _ = self.admitted[step_id]
            return tval, None

        if arg["ref_type"] == "span":
            doc_id, start, end = arg.get("doc_id"), arg.get("start"), arg.get("end")
            if doc_id is None or start is None or end is None:
                return None, Verdict(Status.REJECT, ReasonCode.SCHEMA_INVALID, message="span missing fields")
            text = self.context.span_text(doc_id, start, end)
            if text is None:
                return None, Verdict(Status.REJECT, ReasonCode.PROVENANCE_SPAN_NOT_FOUND,
                                      message=f"no such span {doc_id}[{start}:{end}]")
            # the arg may also carry an expected literal "text" for a stronger provenance
            # check (did the model's claimed span text match what's actually there?)
            claimed = arg.get("text")
            if claimed is not None and claimed != text:
                return None, Verdict(Status.REJECT, ReasonCode.PROVENANCE_SPAN_TEXT_MISMATCH,
                                      message=f"claimed {claimed!r} != actual {text!r}")
            return self._coerce_span(text, expected_type)

        return None, Verdict(Status.REJECT, ReasonCode.SCHEMA_INVALID, message=f"bad ref_type {arg['ref_type']!r}")

    def _coerce_span(self, text: str, expected_type: str) -> Tuple[Optional[TVal], Optional[Verdict]]:
        if expected_type == "number":
            n = _coerce_number(text)
            if n is None:
                return None, Verdict(Status.REJECT, ReasonCode.TYPE_MISMATCH, message=f"{text!r} is not a number")
            return TVal("number", n), None
        if expected_type == "date":
            parsed = _parse_date(text)
            if parsed is None:
                return None, Verdict(Status.REJECT, ReasonCode.TYPE_MISMATCH, message=f"{text!r} is not a date")
            return TVal("date", parsed), None
        if expected_type in ("entity", "relation"):
            return TVal(expected_type, text.strip()), None
        if expected_type == "bool":
            lowered = text.strip().lower()
            if lowered not in ("true", "false"):
                return None, Verdict(Status.REJECT, ReasonCode.TYPE_MISMATCH, message=f"{text!r} is not a bool literal")
            return TVal("bool", lowered == "true"), None
        if expected_type == "set":
            # sets are not expected to come from a single raw span in v1 -- they should
            # be built by a prior step. A raw span claiming to BE a set is a type error.
            return None, Verdict(Status.REJECT, ReasonCode.TYPE_MISMATCH, message="a raw span cannot be a set")
        return None, Verdict(Status.REJECT, ReasonCode.TYPE_MISMATCH, message=f"unhandled expected_type {expected_type!r}")

    # -- main entry point -----------------------------------------------
    def step(self, step_obj: dict) -> Verdict:
        # 1. schema validation
        if not isinstance(step_obj, dict):
            return Verdict(Status.REJECT, ReasonCode.SCHEMA_INVALID, message="step is not an object")
        required = ("step_id", "operator", "args")
        for key in required:
            if key not in step_obj:
                return Verdict(Status.REJECT, ReasonCode.SCHEMA_INVALID, message=f"missing field {key!r}")
        step_id = step_obj["step_id"]
        if step_id in self.admitted:
            # re-admitting the same id is a schema error in this reference gate
            return Verdict(Status.REJECT, ReasonCode.SCHEMA_INVALID, message=f"duplicate step_id {step_id!r}")

        op_name = step_obj["operator"]
        if op_name not in OPERATORS:
            return Verdict(Status.REJECT, ReasonCode.UNKNOWN_OPERATOR, message=op_name)
        spec = OPERATORS[op_name]
        args_raw = step_obj["args"]
        if not isinstance(args_raw, list):
            return Verdict(Status.REJECT, ReasonCode.SCHEMA_INVALID, message="args must be a list")

        # 2. cycle detection: a step may not (directly or transitively) reference itself.
        #    Since refs can only point to already-admitted steps, and admission is
        #    strictly sequential, cycles are structurally impossible UNLESS a step
        #    references its own step_id before being admitted -- check that explicitly.
        for a in args_raw:
            if isinstance(a, dict) and a.get("ref_type") == "step" and a.get("step_id") == step_id:
                return Verdict(Status.REJECT, ReasonCode.CYCLE_DETECTED, message="step references itself")

        # 3. arity check
        variadic_list_types = {"conjoin": "list_bool", "disjoin": "list_bool"}
        if op_name in variadic_list_types and len(args_raw) == 1:
            arity_ok = True  # single list-of-bool arg form
        elif spec.arity is None:
            arity_ok = len(args_raw) >= 1
        else:
            arity_ok = len(args_raw) == spec.arity
        if not arity_ok:
            return Verdict(Status.REJECT, ReasonCode.ARITY_MISMATCH,
                            message=f"{op_name} expected {spec.arity}, got {len(args_raw)}")

        # 4. resolve + type-check each argument
        resolved: List[TVal] = []
        # special-case variadic list-accepting ops with a single list arg
        if op_name in ("conjoin", "disjoin") and len(args_raw) == 1 and isinstance(args_raw[0], dict) \
                and args_raw[0].get("ref_type") == "step":
            tval, err = self._resolve_leaf(args_raw[0], "list_bool")
            if err:
                return err
            if tval.type_name != "list_bool":
                return Verdict(Status.REJECT, ReasonCode.TYPE_MISMATCH,
                                message=f"expected list_bool, got {tval.type_name}")
            resolved = [tval]
        else:
            for i, a in enumerate(args_raw):
                expected_type = spec.arg_types[0] if len(spec.arg_types) == 1 else (
                    spec.arg_types[i] if i < len(spec.arg_types) else spec.arg_types[-1])
                tval, err = self._resolve_leaf(a, expected_type)
                if err:
                    return err
                if tval.type_name != expected_type and not (expected_type == "list_entity_number" and tval.type_name == "list_entity_number") \
                        and not (expected_type == "list_number" and tval.type_name == "list_number"):
                    return Verdict(Status.REJECT, ReasonCode.TYPE_MISMATCH,
                                    message=f"arg {i}: expected {expected_type}, got {tval.type_name}")
                resolved.append(tval)

        # 5. evaluate
        params = step_obj.get("params", {})
        try:
            verdict = spec.eval_fn(resolved, params)
        except Exception as exc:  # pragma: no cover - defensive
            return Verdict(Status.REJECT, ReasonCode.EVAL_ERROR, message=str(exc))

        if verdict.status == Status.ADMIT:
            # 6. result-type check, only meaningful if caller declared one AND this
            #    step claims to be the final/answer step.
            declared_result_type = step_obj.get("result_type")
            if declared_result_type is not None:
                produced_type = OPERATOR_RESULT_TYPE.get(op_name)
                if produced_type != declared_result_type:
                    return Verdict(Status.REJECT, ReasonCode.RESULT_TYPE_MISMATCH,
                                    message=f"operator produces {produced_type}, step declares {declared_result_type}")
            if step_obj.get("is_final") and self.expected_result_type is not None:
                produced_type = OPERATOR_RESULT_TYPE.get(op_name)
                if produced_type != self.expected_result_type:
                    return Verdict(Status.REJECT, ReasonCode.RESULT_TYPE_MISMATCH,
                                    message=f"final step produces {produced_type}, "
                                            f"question expects {self.expected_result_type}")
            out_type = OPERATOR_RESULT_TYPE.get(op_name)
            # list-typed intermediate outputs get a synthetic type tag so later
            # steps (e.g., aggregate consuming a count's output) type-check sanely.
            self.admitted[step_id] = (TVal(out_type, verdict.value), verdict.value)
            self._admission_order.append(step_id)

        return verdict


# A tiny convenience helper the harness/coverage script can reuse directly.
def run_trace(context: Context, steps: List[dict], expected_result_type: Optional[str] = None):
    """Runs a list of step dicts through a fresh Gate in order. Returns
    (verdicts: list[Verdict], gate: Gate). Stops (but still returns) on the first
    non-ADMIT verdict, matching the 'rejection halts the chain' design."""
    gate = Gate(context, expected_result_type=expected_result_type)
    verdicts = []
    for s in steps:
        v = gate.step(s)
        verdicts.append(v)
        if v.status != Status.ADMIT:
            break
    return verdicts, gate
