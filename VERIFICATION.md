# VERIFICATION.md — Task A: closing round 1's open items

Status tags: **[verified]** = I opened the primary source directly this round.
**[secondhand]** = I have the abstract/a summary but not the full text.
**[not found]** = I could not locate the item; not substituted with a similar one.

## 1. Ling et al., "Deductive Verification of Chain-of-Thought Reasoning" (Natural Program)

**[verified].** https://arxiv.org/html/2306.03872 (also ar5iv mirror, NeurIPS 2023 proceedings
page: https://papers.nips.cc/paper_files/paper/2023/file/72393bd47a35f5b3bee4c609e7bba733-Supplemental-Conference.pdf)

Zhan Ling, Yunhao Fang, Xuanlin Li, Zhiao Huang, Mingu Lee, Roland Memisevic, Hao Su.
UC San Diego + Qualcomm AI Research. **NeurIPS 2023.**

What it verifies: **per-step, premises-only, via LM self-verification — not a symbolic
solver.** Proposes "Natural Program," a natural-language deductive format where each
step lists the *minimal* set of premises it used. Verification is then decomposed into
step-by-step subprocesses that see ONLY the necessary premises for that one step (not
the whole chain), and an LM is asked "does this follow, yes or no." The paper explicitly
defines "grounding error" as using information not present in the cited premises — a
softer, LM-judged analog of this pilot's `PROVENANCE_SPAN_TEXT_MISMATCH`, not a
mechanical check. **This is a soft, trained/prompted verifier, not a hard gate** — round
1 was right to flag it as a different animal from Logic-LM/SatLM's solver-based approach,
and this confirms it directly rather than guessing.

## 2. Nature Machine Intelligence 2026 paper

**[verified]**, and this materially corrects how round 1 used it.
https://www.nature.com/articles/s42256-026-01268-y (main text) +
https://media.springernature.com/.../42256_2026_1268_MOESM1_ESM.pdf (supplementary info)

Kim, Y., Gu, K., Park, C., et al. "Capable language models can outgrow the benefits of
collaboration." *Nature Machine Intelligence* **8**, 1157–1172 (2026). Supplementary
info reveals the original/working title was "Beyond more agents: quantifying when
multi-agent collaboration benefits large language model agents."

Confirmed directly: **260 configurations, six benchmarks, five architectures, three LLM
families, matched compute** — exact abstract language. Capability-saturation threshold
confirmed, with the specific caveat the authors themselves state and round 1 did not
carry forward: **"we therefore interpret this threshold as a practical selection rule
rather than a universal scaling principle."**

**The correction that matters for this pilot:** all six benchmarks are explicitly
**agentic** tasks — BrowseComp-Plus (web browsing), Finance Agent, PlanCraft (game
planning), WorkBench (workplace tasks), SWE-bench Verified, Terminal-Bench — defined by
the paper as requiring "(1) sustained multi-step interactions with an external
environment, (2) iterative information gathering under partial observability, and (3)
adaptive strategy refinement based on environmental feedback." The paper explicitly
contrasts this with **static, single-shot benchmarks** like HumanEval, where it reports
multi-agent coordination shows "fundamentally different scaling behaviour" (monotonic
improvement to 89% with five agents, the opposite pattern from the agentic-task finding),
and warns that "MAS evaluations have been conducted predominantly on non-agentic tasks,
potentially providing misleading guidance about when collaboration provides value."

**This pilot's intended tasks — 2WikiMultihopQA and FinQA — are static, single-shot QA,
not agentic tasks in this paper's sense.** There is no tool use, no environment, no
iterative feedback loop; the whole question is answered from a fixed provided context in
one shot. That means the capability-saturation threshold, as measured, is NOT known to
transfer to this pilot's benchmarks, and the paper's own HumanEval contrast suggests it
might not. **Round 1's framing — "does a hard gate shift the Nature MI capability-
saturation threshold" — needs to be stated as an open analogy, not a direct extension.**
If you want the direct-extension version of that question to be literally true, the
pilot's benchmarks would need to be agentic-shaped (tool-using, multi-turn), which this
kit does not build. PREREG.md states this limitation explicitly rather than quietly
inheriting round 1's framing.

## 3. Error-correlation figures

**[verified]**, with one correction: the exact 0.68/0.52/0.47 triplet (self/same-family/
cross-family) was reported in round 2 citing "LLMs as a Jury" (arXiv 2607.10139); that
specific paper was **not** re-opened this round, so those three numbers are carried
forward as **[secondhand]**, not newly verified. What **was** opened directly this round:

- **"Correlated Errors in Large Language Models"** (Elliot Kim, Avi Garg, Kenny Peng,
  Nikhil Garg; Cornell University), https://ar5iv.labs.arxiv.org/html/2506.07962.
  **[verified].** Confirmed directly: "over 350 LLMs ... on one leaderboard dataset,
  models agree 60% of the time when both models err" (vs. ~33% expected under
  independence on a 3-way-incorrect-answer-space leaderboard) and "larger and more
  accurate models have highly correlated errors, even with distinct architectures and
  providers." Figure 1 caption, read directly: "More accurate models have more correlated
  errors, and almost all model pairs have higher agreement rates than random disagreement
  on errors would imply."
- **"Don't Always Pick the Highest-Performing Model"** (Turkmen, Buyukates, Bastopcu),
  https://arxiv.org/html/2602.08003v1. **[verified].** Confirms the general phenomenon via
  a Gaussian-copula error-floor model and cites "Kim et al., 2025" for "diminishing or
  negative returns from coordination once single-agent accuracy exceeds ~45%" — almost
  certainly an earlier preprint of the same Nature MI paper above (same first author,
  same finding shape), which is a useful independent cross-confirmation that the
  capability-saturation finding predates and matches the final Nature MI publication.

## 4. "If Multi-Agent Debate is the Answer, What is the Question?" (2025)

**[secondhand]** for the full methodology — I read the abstract directly
(https://ar5iv.labs.arxiv.org/html/2502.08788) but the extracted page did not surface the
full benchmarks/models section text in this pass, only the abstract and references. Confirmed
from the abstract: "systematic evaluation of five representative MAD methods across nine
benchmarks using four foundational models," and the exact claim: "MAD methods fail to
reliably outperform simple single-agent baselines such as Chain-of-Thought and
Self-Consistency, even when consuming additional inference-time computation." Model
heterogeneity (Heter-MAD) is reported as the one lever that helps. The specific nine
benchmark names and four model names were not independently re-extracted this round;
treat that level of detail as unverified until the full PDF is read.

## 5. DebateCoder (2026, Pangu-1B)

**[secondhand]**, unchanged from round 2 — not reopened this round. Carried forward:
role-split debate (User/Technical/QA agents) on Pangu-1B, "Adaptive Confidence Gating"
at a 95% threshold, HumanEval/MBPP code-gen benchmarks, ~35% API-call reduction reported.
Gate mechanism is a soft confidence threshold on agent agreement, not a mechanical/
symbolic check. Whether compute is genuinely matched across its ablation arms was not
independently confirmed either round — flag as an open question if this paper becomes
load-bearing for anything.

## 6. SWRV follow-ups and the shared-task overview

**[verified].** The shared task is **XLLM@ACL 2025 — LLMSR** ("LLM for Structural
Reasoning"), https://xllms.github.io/LLMSR/, hosted by Jia, Zheng, Liu, Li, Bai. 24
training examples, derived from LogiQA (Liu et al. 2020/2021), three subtasks: Question
Parsing, CoT Parsing, step-level Verification.

Other team submissions found and opened directly:
- **"LLMSR@XLLM25: Less is More"** (3rd place) — multi-agent framework with
  reverse-prompt induction + retrieval-augmented synthesis to distill supervision from
  the 24 labeled examples. Does not report comparing symbolic vs. LM verifiers; focuses
  on data-efficient supervision for the parser stage.
- **"LLMSR@XLLM25: An Empirical Study of LLM for Structural Reasoning"** (Team asdfo123,
  Li/Wan/Sui, 5th place) — untuned Meta-Llama-3-8B-Instruct, few-shot prompting only, no
  fine-tuning or retrieval. Reports two findings directly relevant to this pilot's W1:
  **"Even an untuned 8B model can reliably parse conditions ... but struggles to
  decompose and verify chains of thought,"** and **"the bottleneck is not extraction but
  logical adjudication."** This refines round 1/2's W1 picture: condition-*extraction*
  (identifying what's stated) is comparatively easy even for an untuned 8B model; it's
  *segmenting a CoT into correct statement-evidence pairs* and *judging entailment* that's
  hard. The pilot's harness and failure taxonomy should track these as separate failure
  classes rather than lumping all of "formalization" together — `failure_taxonomy.md`
  does this (separates `SPAN_EXTRACTION_ERROR` from `WRONG_OPERATOR`/`WRONG_OPERANDS`
  from `MISSING_STEP`).

**None of the shared-task papers found report end-task QA accuracy** — all of them,
including SWRV itself, score against the shared task's own Macro-F1 metrics on parsing
and step-verification quality, not against whether the original question got answered
correctly. This reinforces the user's own SWRV reading directly: **the whole SWRV line
of work grades an existing CoT after the fact and blocks nothing downstream.**

### SWRV's own numbers, re-checked against the primary source

**[verified]** by reading the full paper body (not just the abstract) at
https://aclanthology.org/anthology-files/anthology-files/pdf/xllm/2025.xllm-1.29.pdf.
Confirmed exactly, in the paper's own words:
- "the Z3 solver's success rate is around 72%, leading to a *Reasoning_F1* score of
  0.078." **[verified]**
- "Fine-tuned parsers do not outperform the rule-based prompting base parser. The main
  reason might be limited training set (only 24 examples)..." **[verified]** — confirms
  the user's reading exactly.
- "Considering *Llama-3-8B-Instruct's* lacking in groundtruth of Z3 syntax, we employ
  *O3-mini-high* as the base model to generate Z3 formulations." **[verified]** — confirms
  "o3-mini-high wrote the Z3 formulations" exactly as read.
- "If the verifier is unable to draw a conclusion, it defaults to considering the
  reasoning step as correct." **[verified]** — confirms fail-open exactly as read.
- The precise baseline (0.033) / Llama-verifier (0.067) / o3-mini-high-verifier (0.124)
  numbers the user quoted appear in the paper's **Table 1/Table 2**, which did not
  extract as readable text in this pass (image-rendered tables) — the narrative text
  above is fully consistent with those numbers (Z3 at 0.078 sitting between a weaker
  LM-verifier and a stronger o3-mini-high verifier) but the exact four figures are
  **[secondhand]** relative to this pass specifically, not independently re-derived from
  the table. **Overall: the user's reading of SWRV is accurate on every point that was
  checked against primary text.**

## 7. Conjunction sweep, second pass

Queries run this session (cumulative across both rounds, not just this pass):
"symbolic verifier admission gate multi-agent small language models reasoning 2025",
"'hard constraint' OR 'symbolic gate' versus 'process reward model' multi-agent LLM
comparison survey", "deterministic verifier small language models multi-agent
collaboration matched compute baseline", plus the round-1 queries covering Logic-LM/
LINC/SatLM/PAL/PoT/DecomP/ReWOO/Binder/Dater/DSPy/constrained-decoding/Self-Ask/IRCoT
neighbors.

Closest 5 hits to the exact conjunction (hard admission gate + separate specialist
models + matched-compute single-model baseline): SWRV (hard verifier option, but
single-model, post-hoc grading, no admission gate blocking anything downstream); VPR
(hard oracle, but a training reward signal, not an inference-time admission gate, single
policy); DebateCoder (separate agents + gate, but the gate is soft/confidence-based);
ORCH (separate agents + deterministic routing, but routing/merge, not a per-step
mechanical type-check); Nature MI paper (matched-compute, separate agents, but no gate
of any kind, structural-variation only).

**Confidence the conjunction is fully unoccupied: low-medium, unchanged from round 1.**
This was not an exhaustive venue-by-venue sweep of the last six months of arXiv cs.CL/
cs.AI/cs.LG, nor of ACL/EMNLP 2026 or NeurIPS 2026 workshops or ICLR 2027 submissions
specifically — that would require either systematic API access to arXiv's listing feeds
or a much larger number of targeted queries than two sessions' worth of general web
search can guarantee full coverage of. Treat "low-medium" as an honest ceiling on this
method's confidence, not as a proxy for "probably open."
