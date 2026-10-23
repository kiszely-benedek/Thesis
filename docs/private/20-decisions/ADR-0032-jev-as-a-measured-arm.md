---
adr: 0032
title: Use TypeSafe Jev, pinned to jev-1.13, as a measured decider in EXP-0004 and as a strategy router — never jev-router or jev-latest, never as the answer model
status: accepted
date: 2026-10-02
supersedes: none — extends ADR-0014 (a second endpoint under the same pin, cache and paid-call rules)
design: 40-design/hierarchical-and-jev.md §5–§7
---

# ADR-0032 — Jev as a measured arm

## Context

Jev (TypeSafe, released 2026-09-15, emergent.sh/news/what-is-jev) is a typed-decision model that never writes
text. A request is a `state` text plus typed `questions`, each `noul` (a yes/no probability, 0–1) or `choice`
(pick one of the given `criteria`). OpenRouter serves it at `POST https://openrouter.ai/api/v1/systemone` with
model `jev-1.13` or `jev-latest`; the documented example response resolves `jev-1.13` to
`typesafe/jev-1.13-20260917` and reports `usage.input_tokens`, `output_tokens`, `cost`
(openrouter.ai/docs/guides/community/typesafe-sdk, read 2026-10-02). No seed or temperature parameter is
documented, the response carries no latency, and the shape of a `choice` answer is not shown in the docs.
Vendor claims, **unverified**: 70–500 ms latency; input $0.042 per million tokens, output free; "cannot yet prove
the pricing is unsubsidized"; "cannot hallucinate" only in the sense of output shape — decisions can be wrong.

`typesafe/jev-router` (OpenRouter listing snapshot `30-experiments/openrouter-models-2026-10-02.json`) picks a
model and reasoning effort per request and adapts over a session; its price is `-1` (dynamic). The snapshot does
not list `jev-1.13` itself as a chat model.

Novelty check 2026-10-02 (`10-literature/_novelty-log.md`): no Jev × P&ID / DEXPI / engineering-drawing work.
"Using Jev" is not novel by itself; arXiv 2609.32160 audits 28 early Jev papers and finds the typed readout has
no independent accuracy advantage over label-probability readouts (gains are latency and cost), and gives a
14-item evaluation checklist. arXiv 2604.16401 (GraphRAG-Router) already routes per query over GraphRAG methods
and LLMs on Wikipedia QA.

## Options considered

**A. No Jev.** Nothing to build. Gives up a cheap, fast decider the user sees as potentially publishable, and an
honest comparison is cheap if it is cached and pinned.

**B. Jev through `jev-router` or `jev-latest`.** Least setup. Not reproducible: the router adapts per session and
`latest` moves; a replayed number would not mean the same thing. Violates ADR-0014 points 1 and 4.

**C. Jev pinned to `jev-1.13`, used only where a decision is typed (identity pair: `noul`; strategy choice:
`choice`), always next to a label-probability chat-LLM readout on the same inputs, cached and replayable, the
resolved model id checked on every live call, following arXiv 2609.32160's checklist.**

**D. Jev also chooses the answering model per question.** Interesting, but the answering model is frozen for a
whole sweep (ADR-0014 point 4) because the context wall moves with the model, which is the claim's x-axis.

## Decision

**C.**
1. Pin: `jev-1.13`; the first live response's resolved id (expected `typesafe/jev-1.13-20260917`) is frozen in the
   run config; a live response with any other resolved id is a `ProviderError`, never silently accepted.
   `jev-latest` and `typesafe/jev-router` are refused by the pin validator in reported runs.
2. Uses: (i) EXP-0004 pair decider, `noul` (ADR-0031); (ii) a `RoutedStrategy` that picks one retrieval strategy
   per question with `choice`, from the question text and a fixed corpus descriptor (sheet and unit counts), never
   family, `k` or answer type. The answering model stays the run's pin.
3. Baselines on the same inputs: a label-probability readout from a pinned chat LLM (single-token yes/no or
   option letter, probability from top log-probabilities), a free-text chat LLM, and the free deciders.
4. One client path: a separate `SystemOneClient` behind the same paid-call guard (`allow_network` only from
   `--allow-paid-calls`), its own SQLite decision cache with `live`/`replay` modes, `calls.jsonl` records, key
   redaction.
5. Tier: the EXP-0004 Jev decider runs with EXP-0004; the router arm is a **should-item** after the fixed-strategy
   headline runs, because it re-uses their cached answers.

## Rationale

- The claim needs reproducible numbers; only a pinned, cached, id-checked Jev gives them.
- The label-probability baseline isolates what the typed readout adds, which is exactly the question the audit
  (2609.32160) says the early literature did not answer. Without it a good Jev number is not attributable.
- The defensible novelty is the domain and the measurement — cross-sheet tag identity on P&IDs with a generated
  answer key, and routing whose optimum changes with plant scale — not the model.

## Consequences

- Vendor dependence is a stated threat: if TypeSafe withdraws `jev-1.13`, the cache still replays every reported
  number, but nobody can extend it. The price may be subsidised (vendor's own words); cost is reported as billed
  on the day, with the date.
- Determinism is unknown: a paid repeatability probe (a few hundred decisions asked twice, cache bypassed) reports
  agreement before any reported run.
- The `choice` answer shape is parsed only after the first paid smoke records it; until then the parser rejects
  anything unexpected.
- **Revisit if** the resolved id changes under `jev-1.13`; the repeatability probe shows flips on more than 5 % of
  decisions (then report Jev as a distribution over 3 asks, or drop it); or the checklist transcription
  (`/paper-intake 2609.32160`) names a requirement this design cannot meet.

**Accepted 2026-10-02 (user, in chat).** As written: router arm as a should-item; the router sees the corpus-size line; it picks the strategy only (model choice stays frozen per ADR-0014; a router over pinned models is a possible later experiment). The user wants Jev's results counted as a publication candidate.
