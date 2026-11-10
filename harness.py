"""
harness.py -- model-agnostic formalization-trace harness for the W1 test
("do SLMs have anything left to do once inference is mechanical?").

Talks to ANY OpenAI-compatible chat-completions endpoint (ollama, llama.cpp server,
vLLM's OpenAI-compatible server, or a real API) via stdlib urllib -- no `openai` or
`requests` package required. You bring the model; this harness brings the scaffold.

Three modes, per round-2 Task C4:
  A - formalize-only: few-shot prompt asks the model to emit step JSON for a question
      given its context. Records raw output, parse success, gate verdict per step,
      and the final evaluated answer (if any).
  B - full Arm-2 scaffold: formalize -> gate each step as it's produced -> evaluate ->
      final answer, or ABSTAIN if any step is rejected and not recoverable.
  C - Arm-0 baseline: free-form CoT with the same model, no gate, no schema.

Matched-compute ledger: every call through `call_endpoint` is logged with model name,
forward-pass count (always 1 per call, by construction), input/output token counts
(from the API's `usage` field if the endpoint reports one, else a cheap `len(text)//4`
estimate -- flagged in the log as `token_count_source: "usage"` or `"estimated"`), wall
time, and (for modes B) separate gate time. Define matched compute, per PREREG.md, as
the SUM of forward passes and the SUM of tokens (including this estimate) across an
arm's full run on a question set -- not wall-clock, which depends on your hardware.

Stubs only, per scope: Arm 4 (self-consistency) and Arm 4b (PAL/PoT-style single model,
code-execution offload, no admission gate) are stubbed with clear TODOs and raise
NotImplementedError if called -- they are single-model arms, in scope to stub per the
task brief, but not implemented here. Arms 1 and 3 (multi-agent) are out of scope
entirely and do not appear in this file at all.

Usage:
    python harness.py --mode A --endpoint http://localhost:11434/v1 --model llama3.2:3b \
        --input sample_2wiki.jsonl --limit 10 --out runs/mode_a_run1.jsonl

Starting a local endpoint (see README.md for the full table):
    ollama serve                      # then ollama pull llama3.2:3b
    # harness talks to http://localhost:11434/v1/chat/completions
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional

from gate import Context, Gate, Status


# ---------------------------------------------------------------------------
# Endpoint calling (OpenAI-compatible /chat/completions), stdlib-only.
# ---------------------------------------------------------------------------

@dataclass
class CallRecord:
    model: str
    mode: str
    forward_passes: int
    input_tokens: int
    output_tokens: int
    token_count_source: str  # "usage" or "estimated"
    wall_time_s: float
    gate_time_s: float = 0.0
    raw_response_text: str = ""
    error: Optional[str] = None


def _estimate_tokens(text: str) -> int:
    # crude, stdlib-only fallback: ~4 chars/token for English. Flagged as an
    # estimate everywhere it's used -- do not report it as if it were exact.
    return max(1, len(text) // 4)


def call_endpoint(base_url: str, model: str, messages: List[dict], mode: str,
                   temperature: float = 0.2, max_tokens: int = 800,
                   timeout: int = 120) -> CallRecord:
    """POSTs to {base_url}/chat/completions. base_url should NOT include the trailing
    path, e.g. 'http://localhost:11434/v1' or 'https://api.openai.com/v1'."""
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                  headers={"Content-Type": "application/json"})
    api_key = os.environ.get("HARNESS_API_KEY")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        detail = f"HTTP Error {e.code}: {e.reason}"
        if error_body:
            detail += f" | body: {error_body}"
        return CallRecord(model=model, mode=mode, forward_passes=1, input_tokens=0,
                           output_tokens=0, token_count_source="estimated",
                           wall_time_s=time.time() - t0, error=detail)
    except urllib.error.URLError as e:
        return CallRecord(model=model, mode=mode, forward_passes=1, input_tokens=0,
                           output_tokens=0, token_count_source="estimated",
                           wall_time_s=time.time() - t0, error=str(e))
    wall_time = time.time() - t0

    try:
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        return CallRecord(model=model, mode=mode, forward_passes=1, input_tokens=0,
                           output_tokens=0, token_count_source="estimated",
                           wall_time_s=wall_time, error=f"unexpected response shape: {body}")

    usage = body.get("usage")
    prompt_text = "\n".join(m.get("content", "") for m in messages)
    if usage and "prompt_tokens" in usage and "completion_tokens" in usage:
        in_tok, out_tok, source = usage["prompt_tokens"], usage["completion_tokens"], "usage"
    else:
        in_tok, out_tok, source = _estimate_tokens(prompt_text), _estimate_tokens(text), "estimated"

    return CallRecord(model=model, mode=mode, forward_passes=1, input_tokens=in_tok,
                       output_tokens=out_tok, token_count_source=source,
                       wall_time_s=wall_time, raw_response_text=text)


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------

PROMPT_DIR = os.path.join(os.path.dirname(__file__), "prompts")


def load_prompt(name: str) -> str:
    with open(os.path.join(PROMPT_DIR, name), encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Step-JSON extraction from raw model output (models will not always comply)
# ---------------------------------------------------------------------------

JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", re.DOTALL)
BARE_ARRAY_RE = re.compile(r"(\[.*\])", re.DOTALL)


def extract_steps_json(raw_text: str):
    """Best-effort extraction of a JSON list of steps from raw model output.
    Returns (steps: list|None, parse_error: str|None). This function is deliberately
    forgiving (fenced code block, or a bare array anywhere in the text) because a
    rigid parser would conflate 'model didn't use markdown fences' with 'model
    didn't formalize correctly' -- those are different failure classes and the
    scoring sheet (failure_taxonomy.md) tracks them separately."""
    candidates = []
    m = JSON_BLOCK_RE.search(raw_text)
    if m:
        candidates.append(m.group(1))
    m2 = BARE_ARRAY_RE.search(raw_text)
    if m2:
        candidates.append(m2.group(1))
    candidates.append(raw_text)

    for c in candidates:
        try:
            parsed = json.loads(c)
            if isinstance(parsed, dict):
                parsed = [parsed]
            if isinstance(parsed, list):
                return parsed, None
        except (json.JSONDecodeError, ValueError):
            continue
    return None, "no_valid_json_found"


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def run_mode_a(question: dict, base_url: str, model: str, caller=call_endpoint) -> dict:
    """Formalize-only. No gate. Records parse success and raw steps."""
    system = load_prompt("formalize_system.txt")
    fewshot = load_prompt("formalize_fewshot.txt")
    docs_text = "\n".join(f"[{did}] {d['text']}" for did, d in question["docs"].items())
    user = (f"{fewshot}\n\nNOW FORMALIZE THIS QUESTION.\n\nContext:\n{docs_text}\n\n"
            f"Question: {question['question']}\nExpected answer type: {question.get('result_type', 'entity')}\n"
            "Respond with ONLY a JSON array of steps, nothing else.")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    record = caller(base_url, model, messages, mode="A")
    steps, parse_error = (None, record.error) if record.error else extract_steps_json(record.raw_response_text)
    return {
        "question_id": question.get("id"), "mode": "A", "call_record": asdict(record),
        "parsed_steps": steps, "parse_error": parse_error,
    }


def run_mode_b(question: dict, base_url: str, model: str, caller=call_endpoint) -> dict:
    """Full Arm-2 scaffold: formalize -> gate each step -> evaluate -> answer or abstain."""
    a_result = run_mode_a(question, base_url, model, caller)
    steps = a_result["parsed_steps"]
    if steps is None:
        return {**a_result, "gate_verdicts": [], "final_status": "ABSTAIN_PARSE_FAILURE", "answer": None}

    docs = {did: d["text"] for did, d in question["docs"].items()}
    context = Context(docs=docs)
    t_gate0 = time.time()
    gate = Gate(context, expected_result_type=question.get("result_type"))
    verdicts = []
    for s in steps:
        v = gate.step(s if isinstance(s, dict) else {})
        verdicts.append({"step_id": s.get("step_id") if isinstance(s, dict) else None,
                          "status": v.status.value,
                          "reason_code": v.reason_code.value if v.reason_code else None,
                          "value": v.value})
        if v.status != Status.ADMIT:
            break
    gate_time = time.time() - t_gate0
    a_result["call_record"]["gate_time_s"] = gate_time

    final_status = "ADMIT" if verdicts and all(v["status"] == "ADMIT" for v in verdicts) else "ABSTAIN_GATE_REJECTION"
    final_value = verdicts[-1]["value"] if final_status == "ADMIT" and verdicts else None
    return {**a_result, "gate_verdicts": verdicts, "final_status": final_status, "answer": final_value}


def run_mode_c(question: dict, base_url: str, model: str, caller=call_endpoint) -> dict:
    """Arm-0 baseline: free-form CoT, same model, no gate, no schema."""
    system = load_prompt("cot_baseline_system.txt")
    docs_text = "\n".join(f"[{did}] {d['text']}" for did, d in question["docs"].items())
    user = f"Context:\n{docs_text}\n\nQuestion: {question['question']}\n\nThink step by step, then give your final answer on the last line as 'Answer: <answer>'."
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    record = caller(base_url, model, messages, mode="C")
    answer = None
    if not record.error:
        m = re.search(r"Answer:\s*(.+)", record.raw_response_text, re.IGNORECASE)
        answer = m.group(1).strip() if m else None
    return {"question_id": question.get("id"), "mode": "C", "call_record": asdict(record), "answer": answer}


# ---------------------------------------------------------------------------
# Arm 4 / Arm 4b stubs (single-model, in-scope-to-stub per the task brief;
# NOT implemented here -- do not call these expecting results).
# ---------------------------------------------------------------------------

def run_arm4_self_consistency(question: dict, base_url: str, model: str, n_samples: int = 5, **kw):
    """TODO (not implemented in this pilot kit):
    1. Call run_mode_c n_samples times at temperature > 0 (e.g. 0.7).
    2. Extract each sample's final answer line.
    3. Majority-vote across the n_samples answers (exact string match after
       lowercasing/whitespace normalization is a reasonable first pass; a real
       implementation needs an answer-normalization function per dataset, which
       this pilot kit has not built).
    4. Matched-compute note: this arm's total token count is ~n_samples x one
       Arm-0 call. Make sure the comparison arm's budget reflects that multiplier,
       don't compare 1 gated call against 5 ungated samples and call it 'matched.'
    """
    raise NotImplementedError("Arm 4 (self-consistency) is stubbed, not implemented in this pilot kit.")


def run_arm4b_pal_style(question: dict, base_url: str, model: str, **kw):
    """TODO (not implemented in this pilot kit):
    1. Prompt the model to emit a Python snippet that computes the answer
       (PAL/PoT-style), using only values it can see in the provided context.
    2. Execute the snippet in a sandboxed subprocess (NOT exec() in-process --
       this pilot kit has not built a sandbox; do not skip that step when you
       implement this).
    3. Catch execution errors as a distinct failure class from wrong-answer.
    4. This arm has no admission gate at all -- it isolates whether 'offload
       computation to a mechanical executor' helps without any multi-step
       typed-combinator structure, which is the comparison round 1's W6
       flagged as missing (a cleaner test than self-consistency alone of
       whether mechanical offload, not gating, is doing the work).
    """
    raise NotImplementedError("Arm 4b (PAL/PoT-style) is stubbed, not implemented in this pilot kit.")


# ---------------------------------------------------------------------------
# CLI driver
# ---------------------------------------------------------------------------

def load_questions(path: str, limit: Optional[int] = None):
    questions = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
            if limit and len(questions) >= limit:
                break
    return questions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["A", "B", "C"], required=True)
    ap.add_argument("--endpoint", required=True, help="e.g. http://localhost:11434/v1")
    ap.add_argument("--model", required=True)
    ap.add_argument("--input", required=True, help="sample_*.jsonl")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    questions = load_questions(args.input, args.limit)
    runner = {"A": run_mode_a, "B": run_mode_b, "C": run_mode_c}[args.mode]

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    total_in_tok = total_out_tok = total_calls = 0
    with open(args.out, "w", encoding="utf-8") as outf:
        for i, q in enumerate(questions):
            print(f"[{i+1}/{len(questions)}] {q.get('id')}")
            result = runner(q, args.endpoint, args.model)
            outf.write(json.dumps(result) + "\n")
            cr = result.get("call_record", {})
            total_in_tok += cr.get("input_tokens", 0)
            total_out_tok += cr.get("output_tokens", 0)
            total_calls += cr.get("forward_passes", 0)

    print(f"\nMatched-compute ledger for this run: {total_calls} forward passes, "
          f"{total_in_tok} input tokens, {total_out_tok} output tokens "
          f"(total {total_in_tok + total_out_tok} tokens). Written per-question "
          f"detail to {args.out}.")


if __name__ == "__main__":
    main()
