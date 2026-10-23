---
component: cascade v2 — tier 1 cypher_rag_plant, tier 2 graph_agent (the model composes the plant primitives), tier 3 only by a pre-registered rule; a pre-registered latency bound; graph_agent fixes; harness request timeout and question deadline
status: draft — awaiting review
related: [ADR-0048 (proposed); ADR-0046, ADR-0047, ADR-0034, ADR-0035, ADR-0043, ADR-0045; method-and-effort-cascade.md; question-aware-retrieval.md §3, §5]
date: 2026-10-08
author: architect (Opus 5.5)
---

# Design — cascade v2: Cypher first, the graph agent second, under a latency bound

## 0. Recommendation

| # | Item | Decision |
|---|---|---|
| R1 | Structure | **`cascade_v2`**: tier 1 `cypher_rag_plant` @ glm-low (unchanged, ADR-0046 acceptance rule); tier 2 **`graph_agent` v2** @ GLM (accept iff ANSWERED); **no tier 3** unless rule V4 (§9.3) adds GLM-low need_rules; fallback = the tier-1 answer. `cascade_v2_iso` (UPSTREAM_TO_FIRST_VALVE starts at tier 2) is the S3-style label variant. |
| R2 | Rule accelerator | **None.** No need-classifier shortcut in front of or inside the agent. Tier 1 already is the fast path (§3.3). |
| R3 | Latency bound (pre-registered) | **LB-1** median total latency ≤ **10 s**; **LB-2** p90 ≤ **60 s**; **LB-3** an answer later than **C = 120 s** counts as no answer (`TIMED_OUT`, wrong) for every arm — applied offline to recorded latencies and enforced live as a question deadline. Accuracy for selection is **acc@120**. |
| R4 | Latency accounting | Question latency = final call + every retrieval-side call (+ local compute when recorded). **Today the cascade and the QAR-P2 row count only the final call** (§1, F1–F3); corrected first (CV2-T1). |
| R5 | graph_agent fixes | System-side only, no question rewording: (a) `path` results state direction semantics; an undirected path is labelled "not a flow path" and marks edges walked against their direction; (b) `traverse` marks boundary items `[end]`; (c) an empty tag lookup says the tag is absent and that another spelling will not match; (d) a step reply that hits the output cap ends the loop (`runaway`); (e) a call may carry `"done": true` (finish with the call); (f) agent steps at **low or default effort, chosen by rule V1** on a paid pilot. |
| R6 | Harness | Per-request timeout = the question's remaining budget; question deadline C = 120 s (`--question-deadline-s`, default off); a timeout is an ordinary committed row with outcome `TIMED_OUT`, never a provider error, never blocks the ordered commit; a cache tombstone keeps replay byte-identical. |
| R7 | Step bound | **Keep `max_steps = 6`**; raise to 8 only by rule V5 (§7). |
| R8 | Dev plan | Pilot on the 90 QAR-P2 questions (two step efforts, staged 18 → 90), then D100 180, then D1000 180; ≈ **$1.56 estimated, caps total $2.75**; rules V1–V5 fixed here before any v2 paid call; H100 (seed 2), H1000 and the held-out families stay sealed until F1. |

Coder tasks: CV2-T1…T5 now, CV2-T6 at F1 (§10). ADR: ADR-0048 (proposed).

## 1. Evidence

All "computed" rows: architect scratch computation 2026-10-08 over `data/runs/cv1/runs/*/answers.jsonl`,
`timings.jsonl` and `data/runs/cv1/q5/D100/questions.jsonl`; percentiles by linear interpolation (numpy default),
so they may differ slightly from figures in `_results.md` that used another method. Total latency = `latency_s` +
`retrieval_usage.llm_latency_s` + `timings.local_compute_s`.

| # | Finding | Source |
|---|---|---|
| F1 | **The QAR-P2 latency is the final call only.** graph_agent on the 90: final-call latency median 3.5 s / mean 38.5 / max 1,035.4; **total** median **23.7 s**, mean **99.8**, p90 **358.2**, p95 499.0, max 1,122.2. 5,520 s of the 8,985 s total LLM time is in agent steps. | `QAR-P2-D100` (computed) |
| F2 | Same 90 questions, total latency: need_rules (DEV10) median 9.5 / mean 37.5 / p90 131.8; Cypher median 4.7 / mean 7.2 / p90 9.2. **graph_agent is the slowest arm, not the fastest.** | `DEV10-D100`, `CYP-D100-low` (computed) |
| F3 | **CASCADE-00 latencies are final-call only too** (`cascade/signals.py` reads `row.latency_s`). cascade_v1 (tiers 1–2 + fallback) total: D100 median **5.7** / mean 23.3 / p90 **57.1** (final-only 2.3 / 19.2 / 52.6); D1000 median **7.5** / mean 31.3 / p90 **107.9** (final-only 2.5 / 26.6 / 104.1). always-N total: D100 8.7 / 35.5 / 122.0; D1000 14.9 / 51.8 / 167.5. always-C total: D100 4.8 / 6.8 / 10.6; D1000 5.1 / 7.6 / 11.4. | four DEV10/CYP runs (computed); costs match CASCADE-00 ($0.2425, $0.3757) |
| F4 | Correct answers within a cutoff (total latency). D100 180: need_rules 157 raw → 152 @120 s, 157 @180 s; cascade_v1 167 → 160 @120, 165 @180; Cypher 141 at every cutoff ≥ 30 s. D1000: need_rules 151 → 145 @120, 149 @180; cascade_v1 161 → 154 @120, 156 @180; Cypher 130. Pilot 90: graph_agent 80 → **72 @120**; need_rules 78 → 74; Cypher 70 → 70. | computed |
| F5 | graph_agent stops: done 81, max_steps 5, errors 4; outcomes ANSWERED 85, PARSE_FAILURE 5 (all final-step runaways at 16,384 tokens: NO_PATH 1, UPSTREAM_ISOLATION 2, UPSTREAM_SOURCES 2). | `_results.md` QAR-P2; computed |
| F6 | **Step-level runaways:** 10 of 265 agent-step replies hit 16,384 completion tokens (empty → "not JSON"), in 6 questions; 22 steps used > 4,096 tokens; 24 steps took > 60 s; step latency median 5.5 s, p90 39.4, max 250.5. All 4 `errors` stops are two cap-hit replies in a row. | computed |
| F7 | If the loop stopped at the first cap-hit reply: 5 of the 6 questions get an identical final context (nothing was gathered after it), saving **802.8 s** over the 90 (8.9 s per question on average); 1 (CROSS_UNIT, correct) gathered one more result after the cap hit and could change. | computed |
| F8 | **NO_PATH 0/5:** in all five, `path(directed=true)` returned "no path" (a 34-character observation); the agent then called `path(directed=false)`, which found a path that ignores flow direction, and the final step listed that path as the flow path (4 answered wrongly, 1 runaway at 16,384). Final-step completion tokens on these: 9,493 / 10,110 / 962 / 16,384 / 298. Cypher returned an empty result and abstained correctly on 4. | `QAR-P2-D100` traces |
| F9 | **UPSTREAM_ISOLATION 2/5:** no agent call used `stop_at`; every one gathered the whole upstream closure (785–1,239 characters) and left "first operated valve on each route" to the model; 2 final-step runaways, 2 two-step runaways (`errors`), 1 wrong abstention. The plant API expresses the family exactly (`canonical_programs._upstream_isolation`: traverse upstream, stop_at OperatedValve). | traces; `qa/harness/canonical_programs.py` |
| F10 | **UPSTREAM_SOURCES 3/5:** the agent traversed upstream correctly every time; the observation does not mark which items have nothing flowing in, so the model derives it from edge lists; 2 runaways (one in the final step, one as two cap-hit steps). | traces |
| F11 | **UNANSWERABLE_TAG 5/5 correct but all 5 hit max_steps:** after `find` returned "0 items" the agent retried other spellings and wildcards (`*33-4*`, `FV38-2`, `LCV*`) — the result does not say that matching already ignores case and spaces and has no patterns. These are the **only** 5 max_steps stops. | traces |
| F12 | Step use: 2:47, 3:20, 4:12, 5:3, 6:8 (8 used all 6: the 5 above + CONNECTED, CROSS_UNIT, LOOPS_NEAR_ITEM, which ended `done` at step 6, all correct). 81 `done` replies, median latency 5.5 s each. | `_results.md` QAR-P2; computed |
| F13 | **hier_agent vs graph_agent, same 84 questions:** 79 vs 77 correct; total latency median 23.7 vs 22.6 s, p90 163.6 vs 203.5 s (index percentile); cost $0.225 vs $0.184. The rule-built seed did not make the median faster and cost 22 % more. | `QAR-P2-D100` (computed) |
| F14 | No request timeout exists: `ChatClient` sets none (SDK default), so httpx's per-read timeout applies; a 1,035 s final call completed and one hier_agent call hung ≥ 20 min, blocking the ordered commit (W41 log). The per-read timeout does not bound a call's total time. | `llm/client.py`; `50-progress/2026-W41.md` |
| F15 | **Reference vs primer conflict (UPSTREAM_ISOLATION):** the reference stops at the first `OPERATED_VALVE_CLASSES` node, control valves included (`qa-system.md` §family table); the primer says control valves are "not generally suitable for isolation" (HSE HSG253, ADR-0041). **7 of the 20 dev isolation references contain a control valve** (D100 4/10, D1000 3/10). | `questions/D100|D1000/questions.jsonl` (computed); `primer_pid_v1.txt` |
| F16 | Tier-3 candidates on the 35 need_rules runaways: GLM-64k 21/35 at mean 296.9 s (rejected, ADR-0047); mimo 19/35, mean 89.8 s, $0.5307; GLM-low 14/35, mean 16.9 s, $0.0823. | `_results.md` CP-P2 |

**Consequence.** graph_agent is accurate (80/90, best of the three on the same questions) but, counted honestly, slow:
its time goes into reasoning inside agent steps and into final steps that must compute from raw closures. The
latency criterion of ADR-0047 cannot be judged until latency is counted per question, so the first task fixes the
measurement, and the bound is stated in terms of total latency.

## 2. Which part of the claim it serves

The claim: the best retrieval strategy depends on corpus scale. Cascade v2 measures, per corpus, (a) how many
questions the cheap structured query settles (tier-1 share and precision), (b) whether a model composing typed
primitives handles the rest within a user-acceptable time, and (c) how both move from D100 to D1000 (and H100 to
H1000). F3 already shows a scale effect on latency: cascade_v1 meets a 60 s p90 at D100 (57.1 s) and misses it at
D1000 (107.9 s). Making latency a pre-registered bound turns that into a reportable result rather than an anecdote.

## 3. Structure

### 3.1 Tiers

```
tier 1  cypher_rag_plant    glm-5.3-flash low       accept: ANSWERED ∧ rows > 0 ∧ ¬not_present   (ADR-0046, unchanged)
tier 2  graph_agent v2      glm-5.3-flash; steps at effort V1, final step default    accept: ANSWERED
tier 3  none — unless rule V4 adds need_rules_plant @ glm-low                         accept: ANSWERED
final   tier-1 answer if tier 1 was ANSWERED, else the last tier's outcome
cutoff  summed total latency > 120 s  →  TIMED_OUT (wrong), whatever the tier said
```

The final-answer step (`final_answer.txt`, `legend_plant.txt`, primer) is **not** changed, so the existing
`CYP-D100-low` / `CYP-D1000-low` runs still pass the join's prompt-hash checks and are reused as tier 1 (no paid
Cypher run, no Neo4j swap; graph_agent walks the in-memory item graph).

### 3.2 Escalation signals (gold-free, `Signals`)

| Signal | Tier | Use |
|---|---|---|
| outcome, `n_rows`, `not_present` | 1 | ADR-0046 acceptance, unchanged (precision 0.944 / 0.921, CASCADE-00) |
| outcome (ANSWERED / PARSE_FAILURE / TIMED_OUT) | 2 | acceptance |
| `stop_reason` ∈ {done, max_steps, errors, runaway, deadline, prompt_budget, overflow} | 2 | reported; input to rule V4 only |
| total latency, total cost | all | summed over tiers tried; cutoff C |
| need label | all | only for the `_iso` variant |

Not used for acceptance: tier-2 abstention. Twenty of 180 questions are unanswerable; a label-free rule cannot tell
a right abstention from a wrong one, and with no tier 3 an escalation would have nowhere to go.

### 3.3 Why no rule accelerator (R2)

Options: **A** none; **B** a "hint" — when `RuleNeedClassifier` is confident, the label's primitive program is run
for free and shown as a pre-executed `$r0` the agent may ignore; **C** a bypass — confident label → need_rules
answers, the agent is skipped. C is the old cascade's tier 2 under another name and is a required path for known
shapes. B is hier_agent's seed in a smaller box: on the same 84 questions the seed gave +2 correct, no median latency
gain, +22 % cost (F13), and the user rejected code-written seeds as not generalising. Tier 1 already answers ≈ 2/3
of dev questions in ≈ 5 s (F3) with no family knowledge. **A is chosen.** Revisit only if, after F1-independent dev
runs, cascade_v2 misses LB-2 *and* the escalated questions the rules classifier labels confidently are the slow
ones; then B is designed as a separate arm with a structural test that the agent's prompt and loop are byte-identical
with the hint off (so it can never be required).

### 3.4 Tier 3

With a 120 s cutoff, tier 3 is reachable only when tier 2 fails **fast**. In QAR-P2 the agent's failures were slow
(the 10 wrong or unanswered took 35.6–1,122.2 s total; 8 of them > 200 s; computed). After the v2 fixes, a failing tier 2
ends at the latest at the deadline, which leaves no budget. mimo (mean 89.8 s on runaway questions, F16) cannot fit
in what is left in most cases; GLM-low (16.9 s) can. So: **no tier 3 by default**, GLM-low added only by rule V4.

## 4. The latency bound (pre-registered, R3)

**Definition.** Question latency = recorded latency of the final call + every retrieval-side call of every tier
tried (+ `local_compute_s` from `timings.jsonl` when present; the report flags rows without it). Over one corpus:

| Bound | Value | Measured anchor (total latency, F3/F4) |
|---|---|---|
| LB-1 median | ≤ 10 s | cascade_v1 5.7 (D100) / 7.5 (D1000); always-N 8.7 / 14.9; graph_agent alone 23.7 (pilot 90). External anchor: the 10 s limit for keeping a user's attention (Nielsen, *Usability Engineering*, 1993, ch. 5) — **not yet filed via /paper-intake; researcher to verify before the thesis cites it.** |
| LB-2 p90 | ≤ 60 s | cascade_v1's own D100 tail (57.1 s): v2 must keep v1's D100 tail at both scales. cascade_v1 misses it at D1000 (107.9); always-N misses it at both (122.0 / 167.5). |
| LB-3 cutoff C | 120 s per question | ≈ 2 × LB-2. Removes the pathological cases (1,035 s, ≥ 20 min) and every 16k runaway (133–245 s, ADR-0046 E2/E3) while costing always-N 5 / 6 correct answers (D100 / D1000) and cascade_v1 7 / 7 (F4). 180 s was the alternative: it costs always-N 0 / 2 but keeps 3-minute waits as successes. |

Why three numbers: a mean alone moves 11.5 s on 90 questions from one 1,035 s call; p95 on 180 questions rests on 9
questions; a cutoff alone does not penalise a uniformly slow system.

**How the report checks it (CV2-T1).** For every policy and reference, per corpus: correct raw and **acc@C**
(any decision whose summed latency > C is scored wrong), latency median / mean / p90 / p95 / max, and
`LB-1 PASS|FAIL`, `LB-2 PASS|FAIL`. The cutoff is applied identically to every arm, including the existing DEV10
and CYP runs made without a deadline, so comparisons stay paired. A paired bootstrap of acc@C and of latency per
question is added beside the existing ones. Runs made under the live deadline cannot show raw accuracy beyond C;
the report says so.

## 5. graph_agent v2 — failures and fixes (system-side only)

All fixes act on tool semantics, tool-result wording or the loop; no benchmark question is reworded. Each was
motivated by a dev family, so each is written to be true of the graph in general, and the held-out families test
whether it generalises (stated threat).

### 5.1 NO_PATH (F8)

Cause: a valid, terse "no path" result plus an available undirected path whose rendering looks exactly like a flow
path. Fix in `plant_api/results.py` + `primitives.py` + `tool_registry.py`:
- not found, directed: `$r1: no path from P-11-5 to P-20-1 along the edge direction (send_to: source to target). Flow cannot reach P-20-1 from P-11-5.`
- found, `directed=false`: header `path … IGNORING EDGE DIRECTION, 41 hops, 17 edges walked against their direction (marked [against direction]); this is not a flow path`, and each such edge line carries `[against direction]`.
- `path` description: "directed=false ignores edge direction: it shows whether two items are linked at all, never a flow route."
- prompt rule (generic): "A result that says there is no path, or that no item has a tag, is itself evidence: you may finish."

Alternative rejected: removing `directed` from `path` (shrinks the algebra; "connected at all" questions need it).
Alternative rejected: a final-answer prompt rule (shared, frozen file; would break the tier-1 join and comparability).

### 5.2 UPSTREAM_ISOLATION and UPSTREAM_SOURCES (F9, F10)

Cause: the agent gathers raw closures and leaves set computations to the final step, which then reasons for minutes.
Fixes:
- `traverse` marks boundary members: `[end]` = no further edge in the walk direction within the walked relations
  (a source when walking upstream, a sink downstream); `[hop limit]` = not expanded because of `max_hops`. Both are
  standard properties of a closure, not family tools. Needs `Closure` to report `ends` and `cut_by_hops`
  (`plant_api/traversal.py`).
- `traverse` description gains one generic usage line: "to find the nearest item of a kind on every route (the
  first valve, the first pump), set stop_at to that kind; stop items are marked [stop]."
- F15 is **not** fixed here: whether a control valve counts as an isolation point is a reference-definition
  question for the user (§11 U4). Unmeasured hypothesis: the conflict contributes to the final-step reasoning.

### 5.3 Runaways and stalls (F5, F6, F7, F14)

- **Cap-hit step ends the loop** (`stop_reason="runaway"`): a step reply with `completion_tokens ≥ pin.max_output_tokens`
  stops the loop and the final step answers from what was gathered (F7: 5 of 6 identical, −802.8 s on 90).
- **Deadline-aware loop**: before each step, if the remaining question budget < `final_reserve_s` (30 s) the loop
  stops (`deadline`) and the final step runs with the remaining budget. 30 s > graph_agent's final-call p90 on
  answered questions (19.3 s, computed) — fixed by that measurement, not tuned.
- **Step effort** (rule V1): `AgentParams.step_effort ∈ {default, low}`; low sets `reasoning.effort=low` on
  agent-step requests only, the final step keeps the run's pin. Evidence for trying it: step latency is reasoning
  (≈ 62 completion tokens per second across all steps; a first `traverse` took 7,587 tokens / 236 s); GLM-low was the
  fastest tier-3 candidate (16.9 s mean, F16) and Cypher query writing already runs at low. Accuracy at low on agent
  steps is **unmeasured** — hence the pilot.
- **Finish with the call**: `{"call": {...}, "done": true}` runs the tool and stops if it succeeded; a refused call
  continues the loop. Saves the separate `done` reply (81 of them, median 5.5 s each, F12) — saving is an estimate.
- Final-step runaways (5/90) are not prevented, only bounded: they become `TIMED_OUT` at C instead of PARSE_FAILURE
  after 260–1,035 s.

### 5.4 Empty tag lookups (F11)

`find` with a `tag` filter and zero matches, and the unknown-tag error, both say: `No item has tag 'FV-33-4' in this
plant. Tags are already matched ignoring case and spaces; patterns and wildcards are not supported, so another
spelling will not match.`

## 6. Harness: request timeout and question deadline (R6)

**Options.** **T-a** httpx/SDK timeout only — one line, but it is per read, and F14 shows a 1,035 s call completed
under the SDK default; it does not bound total time. **T-b** streaming with a wall-clock check between chunks —
bounded and cancellable, but rewrites response assembly, usage and cost reading in `ChatClient`. **T-c** the
blocking call runs on a small client-owned "abandon" thread pool; the caller waits `future.result(timeout)`; on
expiry the call is abandoned (its thread finishes in the background). **T-d** a harness-only item timeout in
`pool.py` — the item's thread keeps making agent calls after its row is written. **Chosen: T-c**, driven by a
question deadline in `UsageMeter`.

**Mechanics.**
1. `UsageMeter` knows `deadline_s` (C, or None) and `recorded_elapsed_s` = sum of the **recorded** `latency_s` of
   the item's calls so far (cached or live, so the decision is the same on replay). Before a call:
   `remaining = C − recorded_elapsed_s`; ≤ 0 → raise `QuestionDeadline` without calling; else pass `timeout_s=remaining`.
2. `ChatClient.complete(..., timeout_s)`: live, wait at most `timeout_s`; on expiry write a **tombstone**
   (`finish_reason="client_timeout"`, `latency_s = timeout_s`, empty text, `cost_usd=None`) under the request's
   cache key, log `error_kind="timeout"`, raise `RequestTimedOut`. A cache hit on a tombstone whose `latency_s ≥` the
   current `timeout_s` raises the same; a smaller one is a miss (a later run with a larger budget may retry).
3. The abandoned call, if it returns, is logged with `error_kind="late_after_timeout"` and its cost; it is **not**
   cached; its cost is charged to the `SpendGuard` (`charge_late`). Overshoot bound (stated in the run summary):
   abandoned calls in flight × the dearest call seen.
4. `attempt`: `RequestTimedOut` / `QuestionDeadline` in the final step → row with **`Outcome.TIMED_OUT`** (scored
   wrong, counted in accuracy — unlike PROVIDER_ERROR), `retrieval_usage.n_abandoned`. In an agent step → the loop
   stops with `deadline` (§5.3). It is an ordinary `Answered` result: committed in order, never re-queued, never
   blocks. Worker slots free immediately because the abandoned thread belongs to the client's pool, not the worker pool.
5. Cost of a `TIMED_OUT` row in the cascade: recorded costs + `n_abandoned × $0.0106` (the measured mean cost of a
   16k runaway, ADR-0046 E2 — an upper-bound estimate, flagged); the report also sums the actual late costs from
   `calls.jsonl` as a check.
6. `--question-deadline-s` (default None = today's behaviour; every existing replay stays byte-identical); stored in
   `RunConfig.question_deadline_s` (default None, old configs parse). v2 paid runs use 120.

## 7. Step bound (R7)

Measured (F12): 82 of 90 finished by step 5; the 5 `max_steps` stops are exactly the 5 UNANSWERABLE_TAG questions,
all correct, and their cause is fixed in §5.4; 5.6 % < ADR-0034's 10 % trigger. With finish-with-call the 3 questions
that ended at step 6 would end at step 5. The deadline, not `max_steps`, is now the latency guard; `max_steps` only
bounds cost. **Keep 6.**

**Rule V5 (fixed now):** on the D100 v2 run, raise `max_steps` to 8 (prompt text follows) before D1000 iff more than
10 % of questions stop at `max_steps`, **or** at least 3 `max_steps` stops are wrong answers. Never lowered on dev
data. If raised, the 180 D100 questions are re-run at 8 (estimate $0.52, cap $0.80) so D100 and D1000 use one value.

## 8. Data model changes

```python
# qa/agent/models.py
StopReason = Literal["done", "max_steps", "prompt_budget", "errors", "overflow", "runaway", "deadline"]
class AgentParams(BaseModel):                 # frozen, extra="forbid"
    max_steps: int = 6
    observation_chars: int = 4_000
    max_items_listed: int = 50
    max_prompt_chars_total: int = 150_000
    seed_chars: int = 12_000                  # hier_agent only (dropped arm, kept for QAR-P2 replay)
    step_effort: Literal["default", "low"] = "default"
    final_reserve_s: float = 30.0

# qa/agent/actions.py — ToolCall gains `finish: bool = False` ({"call": ..., "done": true})

# qa/models.py
class Outcome(str, Enum): ...; TIMED_OUT = "TIMED_OUT"   # scored wrong, counted in accuracy
class CallUsage(BaseModel): ...; n_abandoned: int = 0
class RunConfig(BaseModel): ...; question_deadline_s: float | None = None

# llm/models.py
class RequestTimedOut(Exception): allotted_s: float     # not a ProviderError

# plant_api/results.py
class SubgraphMember: ...; is_end: bool = False; hop_limited: bool = False
class PathResult: ...; directed: bool = True; against_direction: tuple[int, ...] = ()   # edge positions

# qa/cascade/models.py
class Signals: ...; latency_s = total; final_latency_s: float; latency_complete: bool; stop_reason: str | None
class LatencyBound(BaseModel): median_s: float = 10.0; p90_s: float = 60.0; cutoff_s: float = 120.0
```

## 9. Dev evaluation plan

### 9.1 Runs (paid steps by the user, each logged; concurrency 4; balance read after each)

Per-question basis: graph_agent QAR-P2 total $0.2581 / 90 = **$0.00287** (default-effort steps; used as the upper
estimate for low too). D1000 scale factor 1.24 = DEV10 per-question cost D1000 / D100 ($0.0032 / $0.0026, ADR-0046
§9). Caps ≈ 1.5× estimate (1.6× at D1000, less known).

| Step | What | Questions | Estimate | Hard cap |
|---|---|---|---|---|
| V2-P0 | free: CV2-T1 report on existing runs → corrected latency notes on QAR-P2, CASCADE-00; API-02 still 1.0 after CV2-T3 | — | $0 | — |
| V2-P1a | graph_agent v2, steps **default**, deadline 120, D100, 18 of the q5 90 (one per family) | 18 | $0.05 | $0.10 |
| V2-P1b | same, steps **low** | 18 | ≤ $0.05 | $0.10 |
| — | *stop rule:* stop and report if either stage has invalid-action rate > 10 % (ADR-0034 trigger), a crash, or < 12/18 correct | | | |
| V2-P1c/d | both configurations on the remaining 72 of q5 | 2 × 72 | $0.41 | $0.60 |
| V2-D100 | V1-chosen configuration on all 180 D100 (the 90 replay free from the cache) | 90 new | $0.26 | $0.40 |
| V2-D1000 | same on all 180 D1000 (DEV10-D1000's questions) | 180 | $0.64 | $1.05 |
| V2-T3 (only if V4 triggers) | need_rules_plant @ glm-low on the tier-2-unaccepted questions, both corpora | ≤ 60 | ≤ $0.14 (CP-P2: $0.0823 / 35) | $0.30 |
| (V5 only) | D100 re-run at max_steps 8 | 180 | $0.52 | $0.80 |

Recommended spend ≈ **$1.56** (caps $2.75) without V5; budget left ≈ $19.55 of $25 ($5.45 used, W41 log).

### 9.2 Candidates (fixed now; adding one later needs an ADR and is labelled post hoc)

`cascade_v2`, `cascade_v2_iso` (new); `cascade_v1`, `cascade_v1_iso` (existing runs); references always-G,
always-N, always-C, random escalation at v2's tier-2 share, oracle cascade. All scored by acc@120 and LB-1/LB-2.

### 9.3 Selection rules (pre-registered before any v2 paid call)

- **V1 — step effort** (on the q5 90): low if acc@120(low) ≥ acc@120(default) − 2 **and** p90(low) < p90(default);
  else default.
- **V2 — select on D100:** eligible = meets LB-1 and LB-2 on D100. Pick the eligible candidate with the highest
  acc@120; tie → lower mean cost per question; if none is eligible, pick the lowest p90 and report "latency bound
  not met on dev".
- **V3 — confirm on D1000:** the D100 choice is confirmed if it is eligible on D1000 **and** its acc@120 ≥ the best
  D1000 candidate's − 2. Else the best eligible D1000 candidate is chosen and the change is reported as a scale
  effect (the thesis claim, observed on dev).
- **V4 — tier 3:** let U = questions tier 2 did not accept on D100. Add GLM-low need_rules as tier 3 iff |U| ≥ 9
  (5 %) **and** the median summed latency at which U's questions leave tier 2 is ≤ 60 s (so ≥ 60 s of budget
  remains). Keep it iff it adds ≥ 2 correct within C on D100 and ≥ 1 on D1000.
- **V5 — max_steps:** §7.
- The ADR-0046 S3 thresholds for `_iso` variants are subsumed by V2/V3 (all four cascades compete on one metric).

### 9.4 What stays sealed

H100 (seed 2, ADR-0045) and H1000 (seed 0): no paid run before F1. The held-out families
(`heldout-families.sealed.md`, sha256 `905c79…f63b`) are opened only by QAR-T10 after F1. F1 adds: `qa/agent/*`,
`plant_api/*`, `prompts/agent_graph_system.txt`, the selected policy files, `AgentParams` values (incl.
`step_effort`, `final_reserve_s`), `LatencyBound`, and the run's `question_deadline_s` (CV2-T6).

### 9.5 Test claims (ADR-0046 K1, K2 kept; K3 added)

K1's comparator becomes always-<tier 2 of the selected policy> (always-G for cascade_v2). **K3:** on H1000 the
selected policy meets LB-1 and LB-2 (point estimates; bootstrap CIs of median and p90 reported). Wording if not:
"the cascade is not fast enough at plant scale". All test runs use the 120 s deadline, comparators included.

## 10. Ordered coder tasks (Sonnet, one at a time; each green on ruff, mypy --strict, pytest; all offline)

| # | Task | Files | Acceptance tests | Size |
|---|---|---|---|---|
| CV2-T1 | **Total latency and the cutoff in the cascade report.** `Signals.latency_s` = final + retrieval LLM latency (+ local compute from `timings.jsonl` when the run dir has it; `latency_complete` flag); `final_latency_s` kept; `LatencyBound`; acc@C for every policy and reference; LB-1/LB-2 verdict lines; paired bootstrap of acc@C | `qa/cascade/{signals,join,models,evaluate,references,report,report_models,report_render,report_verdicts}.py`, `tests/test_cascade_*.py`, toy fixtures | toy: a two-tier decision's latency sums retrieval latency of both tiers; a correct answer at 121 s is wrong under C = 120 for every arm alike; metamorphic gold flip still byte-identical; LB verdicts on hand-made numbers; golden report updated; optional local check (skipped without `data/`): cascade_v1 D100 total median 5.7 s / p90 57.1 s, acc@120 160 | M |
| CV2-T2 | **Request timeout, question deadline, `TIMED_OUT`.** §6 in full | `llm/{client,cache,models,fake_transport}.py`, `qa/models.py`, `qa/harness/{usage_meter,attempt,fill,spend_cap,cli,run_dir}.py`, tests | fake transport with a blocking response: call returns `RequestTimedOut` within timeout + 0.5 s; tombstone written; replay raises the same; `answers.jsonl` byte-identical live vs replay at N = 1 and N = 4 with one hanging item; items after it are committed; the late response is logged and charged; no call starts once recorded elapsed ≥ C; deadline None → all existing harness golden tests unchanged | M/L |
| CV2-T3 | **Plant API wording.** §5.1, §5.2, §5.4: path direction semantics and `[against direction]`, `[end]` / `[hop limit]`, empty-tag sentence, tool descriptions | `qa/plant_api/{results,primitives,traversal,tool_registry}.py`, tests | golden renderings on a toy item graph (directed no-path, undirected path with two reversed edges, upstream traverse whose sources are `[end]` and whose hop-limited item is not); API-02 canonical programs still 1.0 on dev families; API-01 unchanged | S/M |
| CV2-T4 | **Agent loop v2 and prompt.** cap-hit stop, deadline-aware loop with `final_reserve_s`, finish-with-call, `step_effort` step pin; system prompt rules (finish-with-call syntax, "no path / no such tag is evidence", reading `[end]` and `[against direction]`) | `qa/agent/{loop,actions,models,strategies,prompts}.py`, `qa/prompts/agent_graph_system.txt`, `qa/harness/registry.py` (remaining-budget callable into `LlmDeps`), tests | scripted fake sender: cap-hit reply → `runaway`, no further step call; call + done runs the tool and stops; call + done with a refused call continues; remaining budget < reserve → `deadline` before the call, final step still runs; step requests carry `reasoning.effort=low` and the final request does not; `RequestTimedOut` in a step → `deadline` | M |
| — | *Main session: V2-P0 (free), then V2-P1a/b → stop rule → P1c/d → V1 → V2-D100 → V5 → V2-D1000 → V2/V3/V4 verdicts; each paid step run by the user* | | | |
| CV2-T5 | **v2 policies and verdicts.** `cascade_v2.json`, `cascade_v2_iso.json`, `always_g.json`; V1–V5 verdict functions printed PASS/FAIL; `TIMED_OUT` rows with `n_abandoned` costed per §6.5; stop-reason table for tier 2 | `qa/cascade/{policies/*.json,report_verdicts,signals,report_groups}.py`, tests | V-rule logic unit-tested on hand-made numbers incl. ties and the "none eligible" branch; a toy `TIMED_OUT` tier-2 row escalates to the fallback; import ban (policy and signals import no gold modules) still holds | S/M |
| CV2-T6 | **F1 additions** (at the freeze) | `qa/harness/freeze.py`, test | manifest test fails on a one-byte change to a policy file, the agent prompt, `AgentParams` or `LatencyBound` | S |

CV2-T5 may run before the paid steps if the main session prefers the verdicts printed by the tool rather than by
hand; it depends only on CV2-T1.

## 11. Open user decisions (recommendation first)

- **U1** Adopt cascade v2 (Cypher → graph_agent v2 → tier-1 fallback; tier 3 only by V4; no accelerator). Recommended.
- **U2** The latency bound: median ≤ 10 s, p90 ≤ 60 s, cutoff 120 s, enforced live as the question deadline.
  Recommended. Alternative: cutoff 180 s (fewer correct answers lost, 3-minute waits counted as success).
- **U3** Approve the dev plan (§9.1): ≈ $1.56, caps $2.75, staged, stop rule after 18 questions.
- **U4** Isolation reference vs primer (F15): recommended — keep the frozen reference as primary and add a free,
  offline sensitivity re-score with a "control valves do not isolate" reference variant, reported beside it; a
  change of the primary reference would need its own ADR before F1.
- **U5** Add K3 (latency) to the test claims. Recommended.
- **U6** Dated correction notes on the QAR-P2 and CASCADE-00 rows: their latencies are final-call only (F1, F3).
  Recommended.

Open (not for the user): O1 OpenRouter keep-alive behaviour for non-streaming calls is the suspected reason the
SDK's per-read timeout never fired — not verified; T-c does not depend on it. O2 concurrency 4 may inflate per-call
latency through provider queueing; record wall time per run. O3 Nielsen (1993) to be filed by `/paper-intake` or
replaced by a filed source.

## 12. Figures and sources

| Figure | Source |
|---|---|
| 80/90, 78/90, 70/90, $0.258, $0.249, $0.023, stops 81/5/4, steps 2:47 … 6:8, NO_PATH 0/5, UPSTREAM_ISOLATION 2/5, $5.45 used | `_results.md` QAR-P2; `50-progress/2026-W41.md` |
| 167/180, 161/180, $0.2425, $0.3757, precision 0.944 / 0.921 | `_results.md` CASCADE-00, CP-P1 |
| 21/35 296.9 s; 19/35 89.8 s $0.5307; 14/35 16.9 s $0.0823 | `_results.md` CP-P2 |
| $0.0106 per runaway, 133–245 s runaways, $0.0026 / $0.0032 per question | `method-and-effort-cascade.md` E2, §9 (ADR-0046) |
| every total-latency figure, acc@C counts, step statistics, F7–F13 counts, F15 counts | architect scratch computation 2026-10-08 over `data/runs/cv1/runs/{QAR-P2-D100,DEV10-*,CYP-*-low}/` and `data/runs/cv1/{q5,questions}/` — **computed, not yet a `_results.md` row** |
| all paid estimates in §9.1 | arithmetic on the rows above — **estimates** |
| 10 s attention limit | Nielsen 1993 — **not yet filed; to verify** |

## Addendum 2026-10-10 — accuracy round 2 (main session, from the CASCADE-V2 dev report)

The selected `cascade_v2_iso` misses 4/180 (D100) and 5/180 (D1000). Per-question diagnosis from the stored
traces (free, local):

| # | Questions | Tier | Cause | System-side fix (generic, no question rewording) |
|---|---|---|---|---|
| A1 | LOOPS_NEAR_ITEM ×5 (C-26-1, E-49-3; P-223-2, E-471-2, P-35-2) | Cypher accepted | The query returns each loop's controller tag **and** its control valve's tag (e.g. `TIC-49-1`, `TV-49-1`); the agent answers all five correctly. | Cypher prompt schema note: a control loop is identified by its controller/loop tag; the valve it actuates is a separate item with its own (ISA-derived) tag (ADR-0044). Re-run tier 1 on D100/D1000 (≈ $0.09). |
| A2 | UPSTREAM_ISOLATION P-13-5 (D100) | agent | `traverse(stop_at={"node_class": "Valve"})` — a class name that does not exist — silently matched nothing; the agent then abstained. | Filters validate vocabulary: an unknown `node_class`/`label` value is a refused call listing the valid values (generic). |
| A3 | NO_PATH V-15-6→TK-485-3 (D1000) | agent (Cypher 0 rows) | Directed `path` said no flow path; the agent still called `directed=false`, wandered to the prompt budget, and the final step listed the undirected route. | Undirected `path` returns only "linked: yes/no, N hops, M edges against direction, sheets" — no item list to copy; the tool description already says it never answers a flow question. |
| A4 | UPSTREAM_ISOLATION TK-425-6 (D1000) | agent (iso starts at tier 2) | The agent kept traversing past each first valve (15 traverses), hit the prompt budget; the final call then timed out. Cypher had the right answer. | Re-check with A2/A3 in place; the V2/V3 choice between `cascade_v2` and `_iso` is re-made on the new runs. |
| A5 | UPSTREAM_ISOLATION V-2-2 (D100) | agent | Gold includes control valve PV-2-6; the agent (following the primer) left it out and added check valve CHV-2-20. | U4 (accepted): report the offline "control valves do not isolate" re-score beside the primary key. Check valves are not operated isolation valves either — check the key's definition. |
| A6 | UNANSWERABLE_TAG (correct, 6–12 steps) | agent | Retries other spellings after an empty tag lookup. | Loop-level: a second empty tag lookup in the same question returns "already searched: no such tag; finish" (generic duplicate-miss notice). |

All are tool/prompt wording or validation changes before the F1 freeze, not new tools (ADR-0034 holds). Dev
re-runs: tier 1 Cypher both corpora, tier 2 agent both corpora (cache replays unchanged steps) — estimate from
CASCADE-V2 costs ≈ $0.09 + ≈ $0.30, caps $0.20 + $0.60.

## Addendum 2026-10-11 — accuracy round 3 (main session, after the model switch, ADR-0050)

| # | Questions | Tier | Cause | System-side fix (generic, no question rewording) |
|---|---|---|---|---|
| A6b | UNANSWERABLE_TAG (correct, 6–17 steps) | agent | The agent meets an unknown tag through a *refused* call (`path`, `traverse`), not an empty `find`, then tries similar existing tags (findings log L14). | Done 2026-10-11: `UnknownTagError`; every unknown-tag text says not to try other tags in its place; a refusal counts as a miss, so the second miss gets the firmer notice; one prompt clause. |
| A7 | UPSTREAM_SOURCES ×6 (D1000, Luna; GLM chased them by repeated traversals) | agent | **Plant-scale truncation.** An upstream walk from a D1000 item reaches thousands of items; members are listed nearest first and cut at the item limit (50), so exactly the items the question asks for — where the walk ends — are never shown. D100 sets are small enough to list. | `Subgraph.render`: when members are cut, add one line naming the walk's **unlisted boundary items** (`[end]`, `[stop]`, `[hop limit]`), capped at the item limit, with their count. Boundary items are the most informative part of a large walk; nothing else changes. Re-run tier 2 on D1000 and D100. |

Model setting adopted with ADR-0050: agent steps at low effort, FINAL answer at **high** (`pin_luna_final_high.json`).
On the same cached steps the final at low effort lost list items and over-listed isolation valves: D100 170 → 175/180,
D1000 168 → 169/180 (runs `AGL-*` vs `AGLH-*`).
