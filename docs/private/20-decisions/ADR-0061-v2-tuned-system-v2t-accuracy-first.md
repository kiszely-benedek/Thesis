---
adr: 0061
title: Tune a separately labelled system V2T on fresh tuning plants, accuracy first — a line view through fittings in both tiers, one Cypher repair round, cascade_v4 without a deadline, gold definitions unchanged
status: accepted
date: 2026-10-27
supersedes: none. Applies ADR-0057 Q2 and the ADR-0060 status amendment ("tune before R4/R5, as a new system"). For V2T only, it replaces ADR-0048 R3 (acc@120 as the selection metric) and the "fixed by design, not tuned" rule in the `AgentParams` docstring (`qa/agent/models.py`). It also replaces ADR-0060 decision 1B's unchanged-path check as the headline gate; the F1 replays of 1B stay. ADR-0029, ADR-0044 U2, ADR-0053 (except the primary metric) and ADR-0059 point 5 carry over.
design: 40-design/qa-tuning-v2.md
---

# ADR-0061 — V2T: tuning the Q&A system on v2, accuracy first

## Context

- **The goal changed** (user, relaying the consultant, 2026-10-27). The system supports engineering work, so
  accuracy is what counts. Latency is reported, not optimised.
- **The dev check on D100g2** (EXP-0007 stage 3, `02af1df`, n = 163) gave Cypher 0.595, agent 0.840 and
  cascade_v3@120 0.896, against 0.733 and 0.972 on v1 D100.
- **The cascade already picks well.** Without the 120 s cutoff, cascade_v3 gets 148 right. That equals the two-tier
  oracle (86 + 51 + 11). The 15 other failures are wrong in both tiers, so only tier fixes can raise accuracy.
- **The causes are traced** (design §2):
  - **Untagged fittings.** On v2 they sit between items: ≈ 2,690 in the D100g2 gold graph. Neither tier looks
    through them: 7 failures.
  - **Inline components.** Strainers and inline mixers are listed where the question asks for "equipment items and
    valves": 5 agent answers.
  - **Result caps.** The agent's limits of 50 items and 4,000 chars cut results: 44 questions had a cut step.
  - **Cypher errors.** 23 syntax errors, 21 of them a stray last token. That predates v2: v1 D100 had 31 syntax
    errors. 15 timeouts, all unbounded path enumeration; v1 had none.
  - **The schema text still describes v1.** Interlock loop heads on v2 are `ProcessInstrumentationFunction`, and
    `unit_id` is a string: 10 Cypher failures.
  - **The 120 s cutoff** cost 2 answers that were correct but late.
- **Fixing timeouts alone would hurt.** 8 of the 9 timed-out isolation queries ask for every upstream valve
  instead of the first one per route. Today they escalate to the agent (10/10 correct); fixed, they would return
  wrong answers that the cascade accepts.
- **Constraints.** F1 and every v1 number stay. Tuning may use dev and tuning seeds only, never 5000–5999.
  Questions are never reworded to dodge a failure.

## Options considered

**1 — What is tuned**
- A. **Edit F1's files in place.** The v1 numbers would no longer be reproducible. Ruled out by ADR-0057 Q2.
- B. **A separately labelled system V2T, additive only (chosen).** New strategy names, prompt files, params,
  policies and one store profile. Shared code changes only behind defaults that reproduce F1, proven by
  byte-identical F1 replays.
- C. **V2T in new files only, with no shared file touched.** The plant API, cascade models and schema text would
  all have to be forked: twice the code to review, for the same guarantee that replays already give.

**2 — Untagged fittings** (design §4.1)
- A. Prompt text only.
- B. **A line view in both tiers (chosen).**
  - An item-to-item flow relation through fittings and inline components: `line_to` in a `plant_lines` Neo4j
    profile, relation group `"line"` in the plant API.
  - Each item gets a `kind`; a `Valve` umbrella label is added.
  - Items with no inflow or no outflow are marked as line ends.
  - `send_to` stays.
- C. Fold fittings out of the graph entirely.
- D. Route those questions to the agent.

**3 — Cypher timeouts**
- A. A longer timeout only.
- B. **Query-shape rules, the smaller `line_to` graph, timeout 120 s and repair on timeout (chosen).** Values are
  fixed first by a free shape bench.
- C. Hop caps. Rejected: they cut correct long answers (k = 58 occurs).
- D. Route path questions to the agent. Kept only as the isolation policy variant (option 5C).

**4 — Syntax errors**
- A. **One repair round with the database's error message (chosen).**
- B. A deterministic trim of a rejected last line.
- C. Higher reasoning effort for query writing.
- D. Resampling without the error message.

**5 — Cascade policy**
- A. Keep cascade_v3 at 120 s.
- B. **cascade_v4 (chosen).** The tuned tiers. A Cypher answer is accepted only if it was not cut at the row cap.
  No cutoff; a 900 s hang guard.
- C. **cascade_v4_iso as a candidate.** First-valve questions start at the agent. It is chosen by a rule fixed now.
- D. Always the agent.
- E. Run both tiers and arbitrate.

**6 — Gold definitions** (design §3)
- A. **Keep all three (chosen).**
  - UPSTREAM_SOURCES: a source is something nothing flows into. This is the question's own wording and v1's rule.
  - "Equipment items and valves" follows the DEXPI taxonomy: inline components are passed through.
  - The anchor is not part of its own reach.
- B. A v2-only scoring rule that strips tagged inline components from path answers.
- C. Redefine the families. That needs rewording, and the anchor change would alter the v1 gold.

**7 — Protocol**
- A. Tune on D100g2, the dev set already read.
- B. **Fresh plants (chosen).**
  - Tuning set T = X100g2s211.
  - Held-back validation V = X100g2s212 + X1000g2s213, run once, with F1 also run on V for a paired effect.
  - At most 3 rounds; stop rules fixed in design §7.3.
  - D100g2 is re-run in-sample only.
- C. Option B without V. That leaves no out-of-sample estimate of the tuning effect.

**8 — Primary metric for V2T**
- A. acc@120 (ADR-0048 R3).
- B. **Accuracy without a deadline, with acc@120 and latency reported (chosen).**
- C. acc@600.

## Decision

1B, 2B, 3B, 4A, 5B with the 5C rule (v4_iso replaces v4 iff its uncut accuracy on T is ≥ v4's), 6A, 7B and 8B.

Parameters:
- **V2T agent:** observation 32,000 chars, 400 items, prompt budget 600,000 chars. Steps, reserve and low step
  effort as F1.
- **V2T Cypher:** timeout 120 s, row cap 1,000, 1 repair round, a free check that the question's tags exist.
- **New final-answer rules**, V2T only:
  - a list of equipment items and valves names only those;
  - the start item is not listed;
  - a missing tag means "not present".

E7 freezes V2T, with the sha256 of every V2T file. The F1 replays and a cache-only replay of the V runs must be
byte-identical at E7. R4 and R5 then run once on V2T.

## Rationale

- **Thesis claim.** The claim compares retrieval strategies across scale on realistic plants. On v2 both graph tiers
  were handicapped by v1-era views: no fittings, the v1 instrument vocabulary, small result caps. Fixing that with
  **one rule applied to both tiers** keeps the comparison fair. It is also the steelman principle ADR-0060 applied
  to ContextRAG.
- **Accuracy first.** The cutoff and the caps were latency and cost guards. Under the new goal, time is traded for
  correctness wherever the traces show it helps. Latency stays visible as a secondary result.
- **Boring where possible.** The repair loop is standard execution feedback. The line view reuses the existing
  contraction pattern: an `ItemEdge.via` like the off-page stubs of ADR-0036. The policy machinery already exists
  (`cascade_v3_iso`).
- **No fitting to the yardstick.** Gold and scoring stay unchanged. Tuning sees no test seed, no held-out family,
  and V only once.

## Consequences

- **Makes easy:**
  - v1 results stay reproducible, proven by replays.
  - Each fix is measured on its own: line-view fidelity P = R = 1 against the gold's independent `next_path_items`,
    repair success per error class, a free shape bench, and the oracle gap per round.
- **Makes hard:**
  - The headline system is no longer F1. The thesis must report both, V2T on v2 and F1 on v1, and the paired
    F1-vs-V2T effect on V.
  - If ContextRAG is run later, it should use V2T's final-answer file to stay comparable.
- **Money:** tuning is estimated at $1.8–3.7, with caps of $5.46 (design §7.5). V2T's agent may cost up to about 3×
  F1 per question, so the R4/R5 caps are recomputed from V's measured costs.
- **Revisit if:**
  - line-view fidelity is below 1.0 on any plant;
  - the repair round fixes under 80 % of stray-token errors on T (then try option 4B or 4C);
  - the oracle gap on T exceeds 3 questions (then try 5E);
  - a family regresses by ≥ 2 T questions with no traced cause;
  - any F1 replay differs.

## Status

**Accepted 2026-10-27 (user, in chat: "Mind ok")** — all eight open questions of the design note answered as
recommended: the V2T package; accuracy without a deadline as the primary metric; UPSTREAM_SOURCES, the
strainer/inline-mixer rule and DOWNSTREAM_IN_UNIT's start-item rule unchanged (the system is fixed, not the gold);
F1 run on V as a paired baseline (≈ $0.44); the cost frame (estimate $1.8–3.7, caps ≈ $5.5); cascade_v4_iso by
the pre-registered rule on T.

**120 s: both settings are measured (user, 2026-10-27: "A-val is nézzük meg meg B-vel").**

| Setting | Cypher query timeout | Per-question cascade limit | Primary number reported |
|---|---|---|---|
| **V2T-A** | set from the QT-0 bench so that the agent keeps time (≈ 30–40 s expected) | 120 s total | accuracy within 120 s |
| **V2T-B** | 120 s | none (900 s hang guard only) | accuracy without a deadline |

The agent tier and every other V2T change are shared; only the Cypher tier's timeout and the cascade's limit
differ, so each tuning round runs the Cypher tier twice (≈ $0.08 extra per 163 questions at the measured
$0.000475/q) and the agent tier once. Both settings are tuned on T and measured once on V; which one is frozen at
E7 for R4/R5 (or both, as two labelled systems) is decided by the user after V, not by the results on test data.
