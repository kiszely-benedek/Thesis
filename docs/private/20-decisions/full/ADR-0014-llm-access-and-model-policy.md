---
adr: 0014
title: Local models for development, the funded API for every reported run, every run pinned and replayable
status: accepted
date: 2026-09-25
accepted: 2026-09-26
supersedes: none
---

# ADR-0014 — LLM access and model policy for experiments

**Scope.** This ADR covers the models **under test**: answerer, judge, and the text-to-Cypher step. It does
not cover the Claude Code agents that build the project. ADR-0006 governs those.

## Context

- **Access** (user, 2026-09-25): a mix of a **university-funded paid API** and **local models**. **The
  provider is not yet known.** `pyproject.toml` contains nothing LLM-related. Everything must run on one
  developer machine, whose GPU and RAM headroom for local models has **not been measured**.
- **Comparability.** ChatP&ID's headline setup is **GPT-5-mini answering and GPT-5-mini judging**, which
  gives ContextRAG **0.91**. GPT-5 on the conceptual graph gives **0.94** (`10-literature/2603.22528.md`).
  Whether the funded API offers that family is open.
- **Small local models change the baseline itself.** ChatP&ID reports that small open models **collapse on
  ContextRAG**: LLaMA3.1:8B **0.28**, Qwen3:14B **0.43**, "because they cannot parse GraphML". VectorRAG
  and PathRAG recover them to about **0.6–0.72** (same note).
- **The context window is an experimental variable.** EXP-0002 asks "At what node count does ContextRAG
  stop fitting / stop winning?" (`_results.md`). "Stop fitting" is set by the answering model's context
  window. That window is where ContextRAG's hard wall sits, so changing the model mid-sweep moves the
  crossover. The ChatP&ID note estimates that ContextRAG "is not available at all" at about 38,000 nodes
  (about 10,000 conceptual). That figure is the note's estimate, not a measurement.
- **Cost per task does not transfer.** ChatP&ID reports **$0.0044 per task** for ContextRAG, on a graph
  of **212 nodes condensed to 53**. ContextRAG's prompt grows with the serialized graph, so that figure says
  nothing about cost at our scale. **No price and no context-window size is quoted in this ADR.** Both are
  to be looked up in the provider's documentation and measured in the pilot.

## Options considered

**M1. Paid API only.**

- **Case.** It offers the strongest models, and if the provider matches ChatP&ID it is comparable to them.
  There is no local hardware question.
- **Cost.**
  - Every development iteration costs budget, and the budget cap is unknown.
  - Hosted models change or are retired, so a result can become impossible to rerun unless calls are
    cached.
  - Development depends on network access and rate limits.

**M2. Local models only.**

- **Case.** Calls are free and can run offline. The weights can be pinned by file hash, which makes the
  model fully reproducible.
- **Cost.**
  - By ChatP&ID's own numbers, small open models fail ContextRAG **because they cannot parse GraphML**.
    The baseline we argue against would then lose to model weakness rather than to scale, and an
    "inversion" would appear already at single-sheet size. **That confounds the claim.**
  - Model size is capped by one machine's hardware, which is unmeasured.
  - EXP-0001 cannot use ChatP&ID's model family.

**M3. Hybrid.**

- Local models for development and iteration: plumbing, harness tests, prompt-format debugging.
- **The paid API for every reported run.** A reported run is anything that lands in `_results.md`.
- Every reported run is **pinned**:
  - provider;
  - model id (a dated snapshot id where the provider offers one, otherwise the alias plus the run date);
  - all generation parameters;
  - a prompt-template hash.
- **Temperature is fixed** at a value chosen per model in the pilot. If a model exposes no temperature
  control, the run records that.
- **Every prompt and response is logged and cached.** The cache key is a hash of provider, model id,
  parameters and full prompt. Each entry stores the response, token counts, latency and timestamp. A
  reported run is **replayable from the cache without API access**.

## Decision

**Recommended: M3.** The concrete model choice is **not** made here. It is settled by a small pilot and
recorded in a follow-up ADR.

**Pilot, before EXP-0001 and EXP-0002:**

1. List the models the funded API actually offers. **Consult the provider's current documentation** (for
   an Anthropic provider, the `claude-api` skill) for model ids, context windows, pricing, and the
   snapshot and deprecation policy. **None of these may be taken from memory.**
2. For each candidate answerer, **measure** the largest serialized plant graph that fits, using generator
   plants of increasing size. This is ContextRAG's hard wall, and it is EXP-0002's first measurement
   anyway.
3. Measure cost per task and latency at two plant sizes. The budget is then an **estimate** with the basis
   (questions × strategies × scale points × repeats + judge calls) × measured cost per call. It is written
   down before the sweep starts.
4. Measure run-to-run variance on a small fixed question set. That variance sets the number of repeats.
   ChatP&ID used 2.
5. Pick the **judge** from a different model family than the answerer (ADR-0013). If the funded API
   offers only one family, the judge comes either from a second provider or from a local model. A local
   judge's agreement with programmatic scores must then be measured (ADR-0013, point 7) before any result
   relies on it.

**Freeze rule.** The **model, parameters and prompts are frozen before the first reported run of a
sweep**. A sweep is never reported across a model change. If a pinned model is retired mid-thesis, either
all reported numbers are rerun on the replacement, or the thesis relies on the cache and says so.

**Implementation pointer (for the design note, then `coder`):**

- a thin client wrapper with the cache, for example under `src/plantgraph/llm/`;
- one JSONL call log per experiment run.

Adding an LLM client library to `pyproject.toml` is part of that work. Whether the cache is published with
the benchmark depends on the provider's terms, which is an open question below.

## Rationale

- **M2 confounds the claim.** A baseline that fails for parsing reasons cannot be the thing that "inverts
  at scale".
- **M1 spends budget on iterations that are never reported.**
- **M3 puts the paid calls only where a number is reported**, and it makes every reported number auditable
  and rerunnable by the professor from the log. That serves the repo rule "never invent a number" at the
  level of LLM calls.
- **Pinning the answerer before EXP-0002 is required by the claim itself.** The location of the crossover
  is partly a property of the model's context window. The thesis must report which window, not wander
  across several.

## Consequences

**Enables:**

- cheap iteration;
- replayable reported runs;
- a context-window figure for the chosen model that is **measured** in the pilot, not quoted;
- a budget estimate with a stated basis before spending starts.

**Costs:**

- a caching client to build and test;
- a pilot before any thesis experiment;
- prompts tuned on local models may behave differently on the paid model. They are re-checked on the paid
  model in the pilot before the freeze.

**Open questions (user):**

1. Which provider is the university-funded API, and does it offer ChatP&ID's GPT-5-mini family? If not,
   EXP-0001 compares the method, not the model (ADR-0013, point 8).
2. What are the budget cap and rate limits?
3. Do the provider's terms allow storing responses and publishing the cache with the benchmark?
4. What local hardware is available (GPU and memory)? To be measured, not assumed.
5. Is the context window **taken as given** by the chosen model, or **chosen** so the wall falls inside
   the swept range? Recommendation: take it as given and report it. Treat it as a second variable only if
   a second answerer is affordable. If the chosen model's window fits the whole largest plant, only "stop
   winning" is testable, not "stop fitting", and the thesis must say so.

**Revisit if:**

- the pinned model is retired before the final runs;
- the budget runs out mid-sweep;
- the pilot shows that the funded provider's models cannot run ContextRAG on the single-sheet baseline at
  all.

## Outcome log

- **2026-09-26:** Accepted by the user 2026-09-26 as recommended (M3). **Provider, same day (user):** *"I think it will be openai, but we can try out many things, I will buy credits on openrouter"* — reported runs go through **OpenRouter**, which puts several model families behind one API; that also makes the cross-family judge (ADR-0013) cheap to arrange. Concrete model ids still come from the pilot, not from memory.
