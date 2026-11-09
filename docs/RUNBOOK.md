# hard-gated-slm-chain-pilot — README

A pilot kit to test the riskiest assumptions behind "gate a small model's reasoning
steps mechanically" (the single-model Arm 2 vs. Arm 0 question), without needing this
agent to run any model itself. You bring the model; this kit brings the gate, the
coverage scripts, the sample data, the harness, and the pre-registration.

**Read `VERIFICATION.md` first** if you want the literature corrections from round 2
before anything else — the Nature MI paper's finding is about agentic tasks, not static
QA like what's tested here, which changes how much weight that citation can carry.

## Run order and time budget (weekend = ~10-12 hours; see PREREG.md Section 6 for the full G1-G3 breakdown)

| Step | Command | Time | Needs a model? |
|---|---|---|---|
| 0. Install nothing — everything here is Python 3.9+ stdlib only, except the optional risk-coverage plot (matplotlib). | `python --version` (3.9+) | 1 min | no |
| 1. Run the gate's own test suite. | `python -m unittest test_gate.py -v` | 2 min | no |
| 2. Run the harness's mock-endpoint test suite. | `python -m unittest test_harness_mock.py -v` | 1 min | no |
| 3. FinQA coverage (G1, FinQA half — already run this round; numbers in `data/finqa_coverage_full.json`). To re-run: | `python coverage_finqa.py --download` | 2 min | no |
| 4. Generate the 2Wiki sample (already run this round; files exist). To re-run: | `python sample_2wiki.py --pages 40` | 3 min (network-bound) | no |
| 5. **Your time starts mattering here.** Annotate `annotation_sheet.csv` by hand per `ANNOTATION_GUIDE.md`'s rubric and worked examples (100 rows). | — | **~1.5-2 hours** | no |
| 6. 48 hours later: re-annotate a fresh copy, compute Cohen's kappa (script in `ANNOTATION_GUIDE.md`). | — | ~1.5-2 hours (on a later day) | no |
| 7. Apply G1's decision thresholds (PREREG.md Section 6). If it kills, stop here — total spend so far is ~3-4 hours of your time plus this round's agent time. | — | 10 min | no |
| 8. Start a local model endpoint (table below), then run the formalization trace (G2, the W1 test): | `python harness.py --mode A --endpoint http://localhost:11434/v1 --model llama3.2:3b --input sample_2wiki.jsonl --limit 30 --out runs/mode_a_run1.jsonl` | ~15-30 min (model-speed-dependent) | **yes** |
| 9. Manually score 20-30 traces from step 8 against `failure_taxonomy.md`, filling in `scoring_sheet.csv`. | — | **~2-3 hours** | no (reviewing output, no model calls) |
| 10. Apply G2's thresholds. If ambiguous (30-50%), repeat step 8-9 with a bigger model (an 8B local model, or an API model via the same `--endpoint`/`--model` flags pointed at a real API). If it kills outright, stop — total spend ~6-8 hours. | — | +~1 hour if retrying | maybe |
| 11. **Only if both G1 and G2 promote** (this is explicitly beyond the weekend budget — see PREREG.md): run modes B and C on the full decomposable set, do the paired McNemar analysis and risk-coverage plot. | `python harness.py --mode B ...` and `--mode C ...` | 6-8+ hours | yes |

Total through G2 (steps 0-10): **~10-12 hours**, matching the brief's weekend budget.
Step 11 (G3) is a deliberate overflow into a second weekend or more — do not try to
compress it into the first one.

## Starting a local OpenAI-compatible endpoint

Pick one. `harness.py --endpoint` wants the base URL WITHOUT `/chat/completions` on the
end (the script appends that itself).

**Ollama (simplest to get running):**
```
ollama serve
ollama pull llama3.2:3b          # or qwen2.5:3b, gemma2:2b, phi3.5
python harness.py --endpoint http://localhost:11434/v1 --model llama3.2:3b ...
```

**llama.cpp server:**
```
./llama-server -m /path/to/model.gguf --port 8080 -c 4096
python harness.py --endpoint http://localhost:8080/v1 --model local-model ...
```

**vLLM (OpenAI-compatible server mode, needs a real GPU for most 1-4B models at
reasonable speed, though small quantized models can run CPU-only too):**
```
python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-3.2-3B-Instruct --port 8000
python harness.py --endpoint http://localhost:8000/v1 --model meta-llama/Llama-3.2-3B-Instruct ...
```

**A real API model (for the G2 "try a bigger model" step), e.g. OpenAI-compatible
providers:**
```
export HARNESS_API_KEY=sk-...          # harness.py reads this env var automatically
python harness.py --endpoint https://api.openai.com/v1 --model gpt-4o-mini ...
```

## File map

- `OPERATORS.md` — the closed operator set specification (Task B1).
- `gate.py` / `test_gate.py` — the reference mechanical gate + 43 unit tests (Task B2).
- `coverage_finqa.py` — automatic FinQA gold-program coverage scan (Task C1).
- `sample_2wiki.py` — stratified 2WikiMultihopQA sampler, writes `sample_2wiki.csv` +
  `sample_2wiki.jsonl` (Task C2).
- `ANNOTATION_GUIDE.md` / `annotation_sheet.csv` — manual decomposability annotation
  protocol and template (Task C3).
- `harness.py` / `prompts/` / `test_harness_mock.py` — model-agnostic formalization
  harness, modes A/B/C, Arm 4/4b stubs, mock-endpoint tests (Task C4).
- `failure_taxonomy.md` / `scoring_sheet.csv` — manual trace-review categories and
  template (Task C4).
- `PREREG.md` — pre-registration: hypotheses, arms, matched-compute definition, paired
  analysis, stage gates (Task D).
- `VERIFICATION.md` — Task A's closed verification items, with corrections to round 1.

## What this kit does NOT do (by instruction, this round)

No multi-agent code (Arms 1/3 are not implemented, not even stubbed). No training or
fine-tuning code. No model inference performed by the agent that built this — every
model-dependent step above is yours to run.
