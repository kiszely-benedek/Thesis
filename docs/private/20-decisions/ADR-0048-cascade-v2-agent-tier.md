---
adr: 0048
title: Make graph_agent tier 2 of the cascade with no rule accelerator and no default tier 3, count every call in a question's latency, bound latency by a pre-registered median, p90 and 120 s cutoff, and enforce the cutoff with a replay-safe question deadline
status: accepted
accepted: 2026-10-10
date: 2026-10-08
supersedes: in part — ADR-0046 Decision point 1 (tier 2 and tier 3 configurations) and point 3 (S1–S3, replaced by V1–V5); ADR-0046 points 2 (acceptance and gold-free signals), 4 (K1, K2) and 5 carry over, K1's comparator becoming always-<selected tier 2>. Amends ADR-0034 point 2 (loop stops, actions) and ADR-0043 (timeouts in the pool). Implements ADR-0047 points 1, 3 and 6.
design: 40-design/cascade-v2.md
---

# ADR-0048 — Cascade v2: the graph agent as tier 2, under a latency bound

## Context

ADR-0047 made latency a criterion, rejected the 64k tier, dropped hier_agent and made graph_agent the next focus.
Reading the QAR-P2 run files (design note §1) changed three things:

- **Latency was undercounted.** Both the QAR-P2 row and the cascade report use the final call's latency only.
  Counted over every call, graph_agent's median is **23.7 s** (not 3.5), mean 99.8, p90 358.2 on the 90 pilot
  questions; need_rules 9.5 / 37.5 / 131.8; Cypher 4.7 / 7.2 / 9.2. cascade_v1's p90 is 57.1 s at D100 and 107.9 s at
  D1000 (computed, design §1 F1–F3).
- **The agent's failures are fixable in the system.** NO_PATH: an undirected `path` result was presented as a flow
  path (5/5). Isolation and sources: raw closures pushed set logic into minutes-long reasoning. 10 agent-step replies
  hit the 16,384-token cap. Unanswerable tags burnt all 6 steps on respellings (F8–F11).
- **No request timeout:** a 1,035 s call completed and one call hung ≥ 20 min, blocking the ordered commit (F14).

## Options considered

**1. Tier structure**
- **A. Cypher → graph_agent → tier-1 fallback, no tier 3 by default (chosen).** Tier 1 unchanged and reused from
  existing runs; tier 2 is the arm the user wants measured.
- **B. Cypher → graph_agent → need_rules @ default.** Old tier 2 as tier 3: within a 120 s cutoff almost never
  reachable after a slow agent failure (8 of the agent's 10 failures took > 200 s).
- **C. Cypher → graph_agent → mimo.** 19/35 on runaways but mean 89.8 s (CP-P2): does not fit what the cutoff leaves.
- **D. Cypher → graph_agent → GLM-low need_rules always.** Fits in time (16.9 s mean) but 14/35; added only if rule V4
  shows tier 2 fails fast enough and often enough.
- **E. Agent first (always-G).** Kept as a reference; tier 1 settles ≈ 2/3 of dev questions in ≈ 5 s.

**2. Rule accelerator.** **None (chosen)** / a confident-label "hint" observation / a confident-label bypass to
need_rules. Same 84 questions: the hier_agent seed gave 79 vs 77 correct, median 23.7 vs 22.6 s, cost +22 % (F13);
the bypass is a required code path for known shapes, which the user rejected.

**3. Latency bound.** Mean only (one 1,035 s call moves a 90-question mean by 11.5 s) / p95 (rests on 9 of 180
questions) / cutoff only (does not penalise a uniformly slow system) / **median ≤ 10 s + p90 ≤ 60 s + cutoff 120 s
(chosen)** / the same with a 180 s cutoff.

**4. Timeout mechanism.** SDK/httpx timeout (per read; did not stop the 1,035 s call) / streaming with a wall-clock
check (bounded and cancellable, rewrites the client) / **wait-with-timeout on a client-owned thread, abandon on
expiry, cache tombstone for replay (chosen)** / harness-only item timeout (the item keeps calling after its row is
written).

**5. Agent-step reasoning.** Default effort (as QAR-P2) / low effort on steps only / a lower step output cap (would
have cut 12 valid step replies between 4,096 and 16,383 tokens) — **low vs default decided by rule V1 on a paid
pilot; no lower cap; a cap-hit step ends the loop.**

## Decision

1. **Cascade v2** = option 1A with the ADR-0046 tier-1 acceptance rule; `cascade_v2_iso` is its label variant; tier
   3 (GLM-low need_rules) only by rule V4. No rule accelerator (2).
2. **Latency** of a question = final call + every retrieval-side call (+ local compute when recorded), summed over
   tiers tried.
3. **Pre-registered bound**, per corpus: **LB-1** median ≤ 10 s, **LB-2** p90 ≤ 60 s, **LB-3** a question whose
   latency exceeds **C = 120 s** is `TIMED_OUT` and scored wrong, applied identically to every arm offline; selection
   uses **acc@120**.
4. **Harness:** question deadline C (`--question-deadline-s`, default off), per-request timeout = remaining budget,
   option 4 mechanism; `TIMED_OUT` is an ordinary committed row (never re-queued, never blocking); late responses
   logged and charged to the spend guard, not cached.
5. **graph_agent v2:** direction-explicit `path` results, `[end]` / `[hop limit]` on traverse members, an explicit
   empty-tag result, cap-hit step → `runaway` stop, deadline-aware loop with a 30 s final-step reserve,
   finish-with-call, `step_effort` by V1. `max_steps` stays 6 (V5 may raise it to 8). The shared final-answer prompt
   does not change.
6. **Selection rules V1–V5** (design §9.3), fixed before any v2 paid call: V1 step effort on the 90 pilot questions;
   V2 select on D100 among eligible (LB-1 ∧ LB-2) candidates by acc@120; V3 confirm on D1000 within 2 questions of
   the best eligible, else switch and report as a scale effect; V4 tier 3; V5 max_steps.
7. **Test claim K3:** on H1000 the selected policy meets LB-1 and LB-2. K1's comparator is always-<selected tier 2>.
   All test runs use the 120 s deadline.

## Rationale

- The thesis claim is about scale; latency is now a user requirement (ADR-0047). cascade_v1 already shows the bound
  is binding at scale (p90 57.1 s at D100, 107.9 s at D1000), so the bound measures exactly the effect the thesis is
  about.
- The bound is anchored in measured numbers: LB-2 is cascade_v1's own D100 tail; the cutoff removes every 16k runaway
  (133–245 s) and the pathological cases while costing always-N 5 / 6 correct answers; LB-1 matches the measured
  medians of the cheap arms and a classic attention limit (to be verified).
- Agent fixes change tool semantics and wording that are true of the graph in general — the user's rule (natural
  questions only) and ADR-0034's "no tool per question type" both hold. The held-out families test generalisation.
- The timeout design keeps ADR-0043's guarantees (ordered commit, byte-identical replay, resume, spend cap) by
  deciding on recorded latencies and storing the timeout itself in the cache.
- Boring where possible: tier 1 untouched, plain JSON actions kept, threads not asyncio, no new tool.

## Consequences

- Money (estimates): pilot two step efforts on 90 questions, D100 and D1000 full runs ≈ $1.56, caps $2.75; V4 and V5
  add at most $0.14 and $0.52.
- Every latency number reported so far for multi-call strategies is low; QAR-P2 and CASCADE-00 get dated correction
  notes after CV2-T1 (free).
- Runs under the deadline cannot show raw accuracy beyond 120 s; the report says so.
- Stated threats: every agent fix was motivated by a dev family; several changes ship together, so a v2 − v1 delta
  cannot be attributed to one fix; concurrency may inflate per-call latency.
- The isolation reference treats control valves as isolation points, which contradicts the primer (7/20 dev
  references) — a separate user decision (design §11 U4).
- **Revisit if** no candidate meets LB-1 and LB-2 on D100; V3 switches the policy at D1000; the invalid-action rate
  exceeds 10 % (ADR-0034's native-tool-calling trigger); abandoned calls exceed 5 % of a run's calls (then streaming,
  option 4b); or a frozen file must change after F1.

## Acceptance (2026-10-10)

Accepted by the user in chat: U1–U6 all approved (U1 structure, U2 120 s cutoff with median ≤ 10 s / p90 ≤ 60 s,
U3 dev spend ≈ $1.56 with caps $2.75, U4 keep the isolation key plus an offline "control valves do not isolate"
re-score, U5 claim K3, U6 dated latency corrections). Amendments by the user, same message:

1. **No tier 3.** V4 is dropped. The user: tier 3 costs too much speed; effort goes into refining tiers 1 and 2
   for accuracy instead.
2. **No step cap as a design limit.** The agent's step count is not to be bounded by a fixed number; the question
   deadline (LB-3) is the only stop. V5 is dropped; `max_steps` becomes a large safety value only. Clarified to the
   user: a step is one LLM tool call, not a graph hop — a path across 1,000 sheets is one `path` call.
3. **Accuracy first, then speed.** Latency work (faster models, see the model scan) follows the accuracy work, or
   runs alongside it where it does not disturb the measurement.
4. **Rule accelerator stays open.** The user is not against a code path for recognised questions but notes it cannot
   cover free phrasing and that a wrong answer must be attributable (classifier misread vs system cannot answer).
   To be designed with that attribution measured (classifier label vs gold family on the dev questions, plus a
   natural-phrasing robustness set), not adopted on accuracy alone.
