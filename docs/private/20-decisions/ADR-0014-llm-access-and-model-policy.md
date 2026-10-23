---
adr: 0014
title: Local models for development, OpenRouter for every reported run; every run pinned and replayable
status: accepted
date: 2026-09-25
accepted: 2026-09-26
full: full/ADR-0014-llm-access-and-model-policy.md
supersedes: none
---

# ADR-0014 — Which LLMs, and how runs stay reproducible

**Question.** Which models answer and judge in the experiments, and how does a reported number stay
re-runnable?

**Options**
- **M1** Paid API only — the strongest models, but every debugging run costs money.
- **M2** Local models only — free, but small open models fail at reading a whole graph in the prompt
  (ChatP&ID: LLaMA3.1:8B 0.28, Qwen3:14B 0.43). The baseline would lose to model weakness, not to scale,
  which confounds the claim.
- **M3** Local models for development; the paid API for every run that lands in `_results.md`.

**Decision: M3, through OpenRouter** (user, 2026-09-26: OpenAI leaning, many models to try).
1. Every reported run is **pinned** — model id, date, parameters, a hash of the prompt template — at a fixed
   temperature.
2. Every prompt and response is **cached**, so a run can be replayed without API access.
3. **A pilot comes first:** measure the context-window wall, cost per question, latency and run-to-run variance.
   Only then fix the model and the question counts. Prices and window sizes come from the provider's docs and
   the pilot, **never from memory**.
4. The model is **frozen for a whole sweep.** The context window is where whole-graph prompting hits its
   wall, so switching models mid-sweep would move the crossover.

**Why.** Paid calls go only where a number is reported, and the professor can re-run every reported number.

**Costs.** A caching client to build, and a pilot before any thesis experiment.

**Open.** The OpenRouter key goes in `OPENROUTER_API_KEY`; do OpenRouter's terms allow publishing the cache?
