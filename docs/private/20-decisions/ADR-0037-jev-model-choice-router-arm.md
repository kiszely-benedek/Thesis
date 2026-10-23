---
adr: 0037
title: Add a model-choice router arm — Jev scores each question's difficulty and picks one of a fixed set of pinned answer models — computed offline from fixed-model runs, beside the fixed-strategy results, never inside a sweep
status: accepted
date: 2026-10-02
supersedes: in part — ADR-0032 option D ("Jev also chooses the answering model", rejected there) is adopted as a separate arm under the conditions below; ADR-0032 Decision point 2's "the answering model stays the run's pin" still holds for every fixed-strategy run and for the strategy router. ADR-0014 point 4 (one model per sweep) is unchanged.
design: 40-design/merged-plant-layer-and-model-router.md Part B
---

# ADR-0037 — Jev picks the answer model by question difficulty

## Context

The user (2026-10-02, approved): Jev should also choose the **answer model** per question, cheap or strong, as a
separate experimental arm; the point is high quality at low cost. ADR-0032 limited Jev's router to the strategy
because the context wall moves with the model (ADR-0014 point 4). Budget: $25 OpenRouter balance in total, staged runs,
hard spend cap (user memory, 2026-10-02; QAR-T1 `--max-spend-usd`). At listing prices a strong model costs far more
per question than a cheap one (`question-aware-retrieval.md` §10.4; listing snapshot
`openrouter-models-2026-10-02.json`).

Key fact: if a fixed run of strategy S exists for every candidate model on the same questions, under the same frozen
prompts and parameters, then "Jev picks model m for question q" has a determined answer — the fixed (S, m) run's
answer to q, which a live routed run would replay byte for byte from the cache (same pin, same messages, same key).

## Options considered

**A. No model router** (ADR-0032 as accepted). Nothing to build; the cost–quality question stays unanswered.

**B. A live routed run.** Decide m(q), then run S with m. Costs new answer calls wherever (S, m) was not already run,
and needs harness changes (per-question pins).

**C. Offline routing over fixed-model runs.** Paid work = one fixed run per candidate model (needed anyway to compare
against each fixed model and the oracle) + tiny decision calls. The routed arm is a per-question selection among
existing answers; cost = the chosen run's billed cost + the decision's.

**D. Joint strategy × model routing.** Interesting, but the run matrix grows as strategies × models; out of scope.

## Decision

**C.**
1. **Candidates.** Two pinned models (ADR-0014 pins, each with its own measured context wall): *cheap* and *strong*.
   One of them is ADR-0019's answer pin, so its runs exist from EXP-0006; only the other needs a new fixed run.
   A third candidate is allowed only if the user asks; it costs one more fixed run.
2. **Wrapped strategy.** `hierarchical` (the ADR-0030 pair, an EXP-0006 arm, the cheapest selective arm per
   question). `hier_agent` is a could-item (one strong-model agent run is far more expensive, design note §B6).
3. **Deciders, all scoring "will the cheap model answer this correctly?" from the question text and the fixed corpus
   line only:** Jev `noul` (pinned `jev-1.13`, ADR-0032 rules); the same yes/no as a label-probability readout from the
   classifier pin (ADR-0033 U3, glm-5.3-flash); a free rules proxy (need label from ADR-0033's rules classifier).
   Policy: cheap if p ≥ τ, else strong; **τ = 0.5 fixed by design**, not tuned (tuning would need paid dev runs).
4. **Free comparisons:** always-cheap, always-strong, oracle (correct if any candidate is; cost of the cheapest correct
   one), random routing at the same strong share (seeded resampling), and a self-signal cascade (escalate when the
   cheap answer is `not_present`, a parse failure or did-not-fit). The decider's own accuracy: AUROC of p against
   "cheap model correct".
5. **When it is offline:** every routed question has a fixed answer for its chosen model, same F1 hashes, same
   strategy parameters, same repeat index; decisions see nothing a model produced. The report refuses otherwise and
   prints the missing slice. **New paid calls are needed** only for: the strong model's fixed run on the routed slice;
   the decisions themselves; a third candidate; a mixed-model question (e.g. cheap agent steps, strong final step);
   or any change to a frozen prompt.
6. **Pre-registered claims** (paired 95 % bootstrap CIs over questions, H1000 routed slice):
   - **M1** `model_routed_jev` − always-strong accuracy: CI contains 0 or lies above, **and** its mean total cost per
     question ≤ 0.5 × always-strong's. Wording if not: "routing loses accuracy" / "routing saves less than half".
   - **M2** `model_routed_jev` − random routing at the same strong share > 0, CI excludes 0. Wording if not: "Jev's
     difficulty score routes no better than chance at the same cost".
   - Reported, not claimed: Jev vs label-probability AUROC (ADR-0032 rule 3; audit 2609.32160 expects no typed-readout
     accuracy advantage), oracle regret, the τ curve (labelled post hoc).
7. **Futility stop (pre-registered):** after the first slice, if always-strong beats always-cheap by less than 0.02,
   routing has nothing to win; stop and report.

## Rationale

- Offline routing turns every reported number into a deterministic function of cached runs plus cached decisions:
  re-runnable by the professor without API access (ADR-0014), and no answer call is paid twice.
- The fixed runs are not overhead: M1 and the oracle need them anyway. The arm's extra cost is one strong-model run on
  a slice plus decisions.
- The sweep stays single-model per point, so the claim's x-axis (the wall) does not move; the routed arm is its own
  row with its model mix shown.
- It ties to the cost frontier of ADR-0035 and to the claim: the cheapest adequate model may change with plant scale
  and question type; the corpus line in the state lets the decider use scale.

## Consequences

- Money (estimate, design note §B6): a strong model at the listing snapshot's Claude Sonnet 5.5 price
  ($2 / $10 per million tokens) costs about $0.03–$0.06 per Hierarchical-type question, so a 120-question H1000 slice
  is about $3.6–$7.2; decisions cost cents. The strong model and the slice size are user decisions.
- Model routing for cost is established prior work; no paper in `10-literature/` covers it. A `researcher` novelty
  check is owed before the thesis claims anything about the router itself (candidates, not read: FrugalGPT, Chen et al.
  2023; RouteLLM, Ong et al. 2024). The defensible point is the domain and the scale axis.
- Needs J-T1 (System One client, `top_logprobs`) and QAR-T4 (rules classifier) built; the strong-model fixed run waits
  for ADR-0019 and F1.
- **Revisit if** the J-P2 repeatability probe flips more than 5 % of decisions (ADR-0032); the fixed runs were made
  under different F1 hashes (then the arm is not computable offline); or the user wants a mixed-model agent
  (then option B for that arm, with its own budget).

**Accepted 2026-10-03 (user, in chat).** Strong-model candidate: Claude Sonnet (to be confirmed by the pilot, ADR-0019); first slice 120 questions, extended only if informative. The user's sequencing (2026-10-03): first a cheap-model paid run; escalate to the strong model only on the questions the cheap one failed — the free cascade comparison of this ADR.
