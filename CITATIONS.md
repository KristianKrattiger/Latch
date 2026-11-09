# CITATIONS

Every citation used anywhere in the Latch thread (idea notes, two literature-digging
rounds, the red-team, and this construction round), in one place, each with a working
URL and a status tag.

Status tags: **[verified]** = opened directly (full text, PDF, or a long enough
extracted quote to confirm the specific claim attributed to it) during this project's
research. **[verified-via-snippet]** = confirmed via a direct, specific quote returned
by a search tool that matches the claim exactly, but the full paper was not separately
opened and paginated through. **[secondhand]** = cited by another paper I verified, or
described in an earlier session from an abstract/summary only, not independently opened.
**[not found]** = named in an earlier round and could not be located; not substituted.

## Neurosymbolic / solver-augmented single-model reasoning (the direct prior art for Arm 2)

- **Logic-LM** — Pan, Albalak, Wang, Wang. *Findings of EMNLP 2023*, pp. 3806-3824.
  LLM formalizes -> deterministic symbolic solver infers -> self-refinement on solver
  errors. +39.2% over plain LLM, +18.4% over CoT, averaged across 5 logic datasets.
  https://arxiv.org/html/2305.12295 · https://aclanthology.org/2023.findings-emnlp.248/
  **[verified]**

- **LINC** — Olausson, Gu, Lipkin, Zhang, Solar-Lezama, Tenenbaum, Levy. *EMNLP 2023*,
  pp. 5153-5176. LLM translates NL to first-order logic; Prover9 theorem prover decides.
  A 15.5B open model + LINC beats GPT-3.5/GPT-4 CoT on ProofWriter by 38%/10%.
  https://ar5iv.labs.arxiv.org/html/2310.15164 **[verified]**

- **SatLM** — Ye, Chen, Dillig, Durrett. *NeurIPS 2023*. LLM emits a declarative SAT/SMT
  specification; a solver (Z3-class) derives the answer. Outperforms program-aided LMs
  by 23% on a GSM arithmetic subset; new SoTA on LSAT, BoardgameQA.
  https://ar5iv.labs.arxiv.org/html/2305.09656 **[verified]**

- **Faithful Chain-of-Thought (Faithful CoT)** — Lyu, Havaldar, Stein, Zhang, Rao, Wong,
  Apidianaki, Callison-Burch. *IJCNLP-AACL 2023*, pp. 305-329. Two-stage
  Translation (NL -> symbolic chain) + Problem Solving (deterministic solver executes).
  Beats standard CoT on 9/10 benchmarks across 4 domains.
  https://ar5iv.labs.arxiv.org/html/2301.13379 **[verified]**

- **Proof of Thought** — Ganguly, Iyengar, Chaudhary, Kalyanaraman. *NeurIPS 2024
  Workshop on System-2 Reasoning at Scale*. LLM emits a JSON DSL of sorts/functions/
  rules; a custom interpreter builds first-order-logic formulas; Z3 returns SAT/UNSAT
  plus proof/counterexample. This is the closest direct analog to Latch's own JSON step
  schema + mechanical-gate idea, at the single-model level.
  https://arxiv.org/html/2409.17270 **[verified]**

- **PAL (Program-Aided Language Models)** — Gao, Madaan, Zhou, Alon, Liu, Yang, Callan,
  Neubig. *ICML 2023*. LLM writes a Python program as the reasoning chain; a Python
  interpreter executes it. Beats PaLM-540B CoT by +15pp on GSM8K.
  https://arxiv.org/abs/2211.10435 **[verified]**

- **Program of Thoughts (PoT)** — Chen, Ma, Wang, Cohen. *TMLR*, 2023 (arXiv 2022).
  Near-identical mechanism to PAL, developed in parallel: delegate computation to an
  interpreter, keep the LLM to expressing the reasoning steps.
  https://arxiv.org/pdf/2211.12588 **[verified]**

- **Decomposed Prompting (DecomP)** — Khot, Trivedi, Finlayson, Fu, Richardson, Clark,
  Sabharwal. *ICLR 2023*. Decomposer LLM builds a prompting program over a shared
  library of sub-task handlers (which can themselves be symbolic functions) — the
  clearest prior-art precedent for "typed sub-task handlers instead of free text."
  https://ar5iv.labs.arxiv.org/html/2210.02406 **[verified]**

- **Robustness of Neurosymbolic Reasoners on First-Order Logic Problems** — 2025/2026.
  Finds neurosymbolic (LLM-to-FOL-to-solver) approaches are MORE robust to counterfactual
  perturbation than pure-neural CoT, but score LOWER overall — a genuine negative-leaning
  result worth weighing against the positive headline numbers above.
  https://arxiv.org/html/2509.17377 **[verified]**

## Multi-model / chained reasoning prior art (the direct prior art for Latch's original multi-SLM framing, not built this round)

- **Selection-Inference** — Creswell, Shanahan, Higgins. *ICLR 2023*. Two LLM modules
  (Selection, Inference) alternate; Inference never sees the original question, only
  what Selection hands it. A 7B model in this framework beats a 280B single-model
  baseline on a 10-task logical reasoning suite by >100%. The single closest prior-art
  system to "separate small models talking through a structured interface," though its
  interface is a natural-language statement, not a typed operator step.
  https://arxiv.org/abs/2205.09712 (ICLR submission) **[verified]**

## Multi-agent coordination, failure, and matched-compute literature (the evidence against the naive multi-SLM story)

- **"Capable language models can outgrow the benefits of collaboration"** — Kim, Gu,
  Park, et al. *Nature Machine Intelligence* 8, 1157-1172 (2026). 260 configurations,
  6 benchmarks, 5 coordination architectures, 3 LLM families, matched compute. Finds a
  capability-saturation threshold past which adding agents stops paying off. **Important
  correction, see VERIFICATION.md item 2:** all 6 benchmarks are explicitly *agentic*
  (tool use, multi-turn, partial observability); the paper itself reports the opposite
  scaling pattern on static benchmarks like HumanEval. Latch's own tasks (2Wiki, FinQA)
  are static — citing this paper as directly answering Latch's question is an open
  analogy, not a verified extension.
  https://www.nature.com/articles/s42256-026-01268-y **[verified]**

- **"Should we be going MAD? A Look at Multi-Agent Debate Strategies for LLMs"** —
  Smit, Duckworth, Grinsztajn, Barrett, Pretorius. *ICML 2024* (not 2025 — corrected
  this round). MAD systems, as commonly built, do not reliably beat self-consistency/
  ensembling; performance is highly sensitive to hyperparameters (esp. agreement level).
  https://arxiv.org/html/2311.17371v2 **[verified]**

- **"If Multi-Agent Debate is the Answer, What is the Question?"** (2025). Abstract
  confirms: 5 MAD methods across 9 benchmarks, 4 foundational models; MAD fails to
  reliably outperform CoT/self-consistency even at higher inference compute; model
  heterogeneity (Heter-MAD) is the one lever that helps. Full methodology/benchmark/
  model names not independently re-extracted this round.
  https://ar5iv.labs.arxiv.org/html/2502.08788 **[secondhand]** (abstract verified, body not re-read this round)

- **"Why Do Multi-Agent LLM Systems Fail?" (MAST)** — Cemri, Pan, Yang, Agrawal, Chopra,
  Tiwari, Keutzer, Parameswaran, Klein, Ramchandran, Zaharia, Gonzalez, Stoica. UC
  Berkeley. *NeurIPS 2025, Datasets & Benchmarks Track*. First empirically grounded
  taxonomy of MAS failures: 14 failure modes across 3 categories (specification issues,
  inter-agent misalignment, task verification), from 200+ traces across 7 frameworks.
  A later citing paper reports 79% of observed failures trace to specification/
  coordination issues, not base-model capability — directly relevant to whether adding
  a second small model would help or just add a new failure surface.
  https://arxiv.org/html/2503.13657v2 **[verified]**

- **ORCH** — Zhou, Chan. *Frontiers in Artificial Intelligence*, 2026. A genuine
  positive counter-example: deterministic multi-agent orchestration (EMA-guided routing
  + a dedicated merge step) DOES beat single-model baselines on MMLU/MMLU-Pro/GSM8K
  (0.94 vs. ~0.44 best single model on GSM8K). Shows determinism-based multi-agent gains
  are achievable via routing/merge — just not demonstrated via a reasoning-step
  admission gate specifically, which is the gap Latch's narrowed question sits in.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC12907423/ · arXiv:2602.01797 **[verified]**

## Gating mechanisms: hard/symbolic vs. soft/learned (the axis Latch's throughline claims to be about)

- **DebateCoder ("Adaptive Confidence Gating in Multi-Agent Collaboration...")** —
  Zhang, Li, Liu, Liu, Zhang, Zhou. 2026. Three-persona debate (User/Technical/QA
  agents) on Pangu-1B; a 95%-confidence-threshold gate skips debate on easy problems.
  70.12% Pass@1 on HumanEval, ~35% API-call reduction vs. MapCoder. **This gate is a
  soft confidence threshold, not a mechanical/symbolic check** — the closest named
  SLM-specific prior art to Latch's framing, but using the opposite (soft) gate type.
  https://arxiv.org/html/2601.21469 **[verified]**

- **"Verifiable Process Rewards for Agentic Reasoning" (VPR)** — Yuan, Xu, Wang, Yi, Gao,
  Zhang, Wang, Yu, Wu. Tsinghua University, 2026. Converts symbolic/algorithmic oracles
  into dense turn-level RL reward signals (not an inference-time admission gate — a
  *training* signal). Outperforms outcome-level and rollout-based process-reward
  baselines on Sokoban/Sudoku/Minesweeper-style environments.
  https://arxiv.org/html/2605.10325v2 **[verified]**

- **"Trust but Verify! A Survey on Verification Design for Test-time Scaling"** —
  Venktesh, Rathee, Anand. 2025-2026. Surveys verifier types/training mechanisms for
  test-time scaling; catalogs symbolic/solver-based verifiers as their own class,
  distinct from learned reward models — confirms "hard vs. soft gate" is an already-
  named axis in the literature, not an original framing.
  https://arxiv.org/html/2508.16665v1 **[verified]**

- **"Generate, Filter, Control, Replay: A Comprehensive Survey of Rollout Strategies for
  LLM Reinforcement Learning"** — Surana, Mundada, Jiang, Wang, Tang, et al. UC San
  Diego / UToronto. *TMLR*, 2026. Explicitly names "hard semantic gates" inside RLVR as
  deterministic, objective, hard-to-exploit checkers, contrasted with learned reward
  models — second independent confirmation that this axis already has a name in the
  field.
  https://arxiv.org/html/2605.02913v1 **[verified]**

## Error correlation / cross-model agreement as a verification signal (the evidence against "cross-model agreement as a second gate layer")

- **"LLMs as a Jury: Cross-Model Consensus Can Outperform Process Reward Models for LLM
  Reasoning"** — Ning Liu. 2026. The direct source of the 0.68/0.52/0.47 figures:
  pairwise error correlation falls in the order within-model self-consistency (ρ̄=0.68)
  > same-family (0.52) > cross-family (0.47) — confirmed via an exact quote match.
  https://arxiv.org/html/2607.10139v2 **[verified-via-snippet]**

- **"Correlated Errors in Large Language Models"** — Kim, Garg, Peng, Garg. Cornell
  University. 2025/2026. Over 350 LLMs on a leaderboard dataset: models agree 60% of
  the time when both err (vs. ~33% expected under independence); larger/more-accurate
  models have MORE correlated errors, even across distinct architectures/providers.
  https://ar5iv.labs.arxiv.org/html/2506.07962 **[verified]**

- **"Nine Judges, Two Effective Votes: Correlated Errors Undermine LLM Evaluation
  Panels"** — 2026. Independent corroboration: 9 frontier LLMs from 7 families provide
  only ~2 effective independent votes' worth of information on NLI tasks; cites the Kim
  et al. "60% agree when both wrong" finding directly, confirming that attribution.
  https://arxiv.org/html/2605.29800v1 **[verified]**

- **"Don't Always Pick the Highest-Performing Model"** — Turkmen, Buyukates, Bastopcu.
  2026. Formalizes the general error-floor phenomenon via a Gaussian-copula model;
  cites an earlier-preprint version of the Nature MI capability-saturation finding.
  https://arxiv.org/html/2602.08003v1 **[verified]**

## Step-level deductive verification (closest existing systems to Latch's actual gate mechanism)

- **"Deductive Verification of Chain-of-Thought Reasoning" (Natural Program)** — Ling,
  Fang, Li, Huang, Lee, Memisevic, Su. UC San Diego + Qualcomm AI Research. *NeurIPS
  2023*. Round-1 could not find this paper; located and verified this round. Verifies
  CoT steps by decomposing into a "Natural Program" where each step lists only its
  minimal necessary premises, then an LM (not a symbolic solver) judges entailment
  per-step. **This is a soft, LM-judged verifier, not a hard/mechanical gate** —
  confirms round 1's instinct that it's a different mechanism class from Logic-LM/SatLM.
  https://arxiv.org/html/2306.03872 **[verified]**

- **SWRV (Chen, Cao, Pan)** — *XLLM@ACL 2025 workshop*, shared task LLMSR. Parser
  extracts (statement, evidence) pairs from a Llama-3-8B-Instruct CoT; a Verifier
  (LM-based or Z3-via-custom-IR) labels each step True/False. Reasoning_F1: baseline
  0.033, Llama-3-8B verifier 0.067, Z3 verifier 0.078 (72% solver success), o3-mini-high
  verifier 0.124. Fails open (defaults "correct") when the verifier can't conclude.
  Grades an existing CoT after the fact; blocks nothing downstream; reports no end-task
  accuracy. Read in full this round, every specific claim in Kristian's own summary
  confirmed against the primary text (see VERIFICATION.md item 6 for the exact quotes).
  https://aclanthology.org/anthology-files/anthology-files/pdf/xllm/2025.xllm-1.29.pdf
  **[verified]**

- **LLMSR@XLLM25 shared task overview** — hosted by Jia, Zheng, Liu, Li, Bai. 24
  training examples derived from LogiQA; three subtasks (Question Parsing, CoT Parsing,
  step-level Verification). https://xllms.github.io/LLMSR/ **[verified]**

- **"LLMSR@XLLM25: An Empirical Study of LLM for Structural Reasoning"** (Team
  asdfo123, 5th place) — Li, Wan, Sui. Harbin Institute of Technology. Untuned
  Meta-Llama-3-8B-Instruct, few-shot only, no fine-tuning. Key finding directly relevant
  to Latch's W1 risk: "even an untuned 8B model can reliably parse conditions ... but
  struggles to decompose and verify chains of thought" — the bottleneck is logical
  adjudication, not condition-extraction. https://arxiv.org/abs/2505.12328 **[verified]**

- **"LLMSR@XLLM25: Less is More"** (3rd place) — Yuan, Sun, Yu, Wang, Du, Cui, Di. A
  multi-agent framework with reverse-prompt induction + GPT-4o-based retrieval-augmented
  synthesis to distill supervision from only 24 labeled examples; all modules fine-tuned
  from Llama-3-8B-Instruct via LoRA+. Does not report symbolic-vs-LM verifier comparison.
  https://arxiv.org/abs/2504.16408 **[verified]**

## Benchmarks used by this pilot kit

- **2WikiMultihopQA** — Ho, Nguyen, Sugawara, Aizawa. *COLING 2020*, pp. 6609-6625.
  192,606 multi-hop QA pairs built from Wikipedia + Wikidata, with structured evidence
  paths. License: **Apache 2.0**, confirmed directly against the upstream repo's LICENSE
  file this round. https://github.com/Alab-NII/2wikimultihop **[verified]**
  (This pilot's `sample_2wiki.py` pulls from the HF repackaging
  `framolfese/2WikiMultihopQA` via the public datasets-server API — same underlying
  data, Apache 2.0 license inherited from upstream.)

- **FinQA** — Chen, Chen, Smiley, Shah, Borova, Langdon, Moussa, Beane, Huang,
  Routledge, Wang. *EMNLP 2021*, pp. 3697-3711. 8,281 expert-written financial QA pairs
  with gold-annotated reasoning programs, from S&P 500 10-K filings. License: **MIT**,
  confirmed directly against the repo's LICENSE file this round.
  https://github.com/czyssrs/FinQA **[verified]**

## Items named but never resolved

None outstanding as of this round — every item flagged "not found" in the original
red-team (the Ling et al. Natural Program paper) was located and verified above. If a
future round names something new and it can't be found, it belongs in this section,
flagged honestly, not silently dropped or swapped for a similar-sounding paper.
