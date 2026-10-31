---
adr: 0062
title: R5 question draw — FIRST_MEETING_POINT out of every sealed v2 corpus, H100g2's questions redrawn, and an output-preserving speed-up of two held-out generators after E7
status: proposed
date: 2026-10-30
supersedes: none. Corrects the reason given in ADR-0059 point 6 and in EXP-0007 plan §9 point 4. Records a deviation from plan §9 point 5 ("no `src` change between E7 and the end of R5").
---

# ADR-0062 — Deviations in the R5 question draw

## Context

- **The draw crashed.** `make_test_set.sh` stopped on 2026-10-29 with a `MemoryError` in
  `first_meeting_point_candidates` on H1000g2, about 5 hours in. Nothing was paid and no system saw a test question.
- **The reason on record was wrong.** ADR-0059 point 6 and plan §9 point 4 say FIRST_MEETING_POINT has 0 candidates
  on v2. Measured from `availability.json` counts, it has 0 at H1g2, H3g2 and H10g2, **71 at H30g2** and **481 at
  H100g2**, of which 20 were drawn into H100g2's set. The previous session told the user the opposite ("0 candidates
  at 100 sheets"), and the uncommitted skip was built on that.
- **The skip alone would have broken the comparison.** With it, H100g2 keeps 20 FIRST_MEETING_POINT questions while
  H1000g2, H100g2d0 and H100g2d50 have none. The claims compare H100g2 with H1000g2, and the report's headline scope
  leaves out only LOOP_ACTUATED_VALVE (`report_claims.py`), so the headline sets would differ by one family.
- **Two more generators would have failed or stalled.** On a 1,000-sheet dev plant VALVES_ON_PATH peaked at 8.75 GB,
  and ROUTE_AVOIDING had not finished after 30 minutes. They run after FIRST_MEETING_POINT, so the crash hid them.
- **What the family measures on v2.** It accepts a meeting point only if it is equipment or a valve. On v2 most
  streams join at tees, so it sees only the joins that happen directly at an item: a partial, biased subset.

## Options considered

**1 — FIRST_MEETING_POINT**
- **A. Leave it out of all four sealed v2 corpora, and redraw H100g2.** The set then equals the registered one: 18
  dev + 5 held-out families, 560 questions per corpus, ≈ 440 headline, 46 in the C1 subset.
- **B. Rewrite its enumeration so it fits in memory, and keep it everywhere.** More questions on a family that
  covers only part of v2's joins, and the opposite of what plan §7 registered (the headline excludes it).
- **C. Keep H100g2 as drawn and skip the family elsewhere.** Free, but the headline sets differ. Ruled out.
- **D. Filter the 20 questions out of H100g2 by hand.** Keeps the other questions, but the file would no longer be
  the output of the recorded recipe.

**2 — VALVES_ON_PATH and ROUTE_AVOIDING**
- **A. Sample the sources.** Faster, but changes the recipe, and the user has ruled out sampling (quality over speed).
- **B. Run them unchanged.** 8–9 GB peak on a 15.4 GB machine, and an unknown run time after a crash that already
  cost 5 hours.
- **C. Change how they compute, not what they produce.** No reach kept across sources; ROUTE_AVOIDING finds the
  cutting items by dominators, then builds one tree for the chosen item only. Output must be byte-identical.

## Decision

- **1A.** FIRST_MEETING_POINT is excluded from every sealed v2 corpus. H100g2's pool and questions are redrawn by the
  same recipe, with the same seeds. The first draw is kept outside the repository, unread.
- **2C.** Accepted only with a byte-identity check of old against new code on dev corpora.

## Rationale

- 1A restores exactly what was pre-registered. Only the stated reason changes, from "no candidates" to "excluded,
  because it covers only joins at items".
- The redraw breaks no hygiene rule: T7.sha256 did not exist, no harness call had read the set, and only counts were
  looked at. Plan §9 point 2 forbids overwriting a *frozen* set; this one was not frozen.
- The redraw changes which questions are drawn in the bins FIRST_MEETING_POINT used to share. That is the recorded
  recipe applied to the registered family list, and it happened before anyone saw a question or an answer.
- 2C changes no question. `src/plantgraph/qa/questions/` is outside `V2T_FROZEN_FILES`, so the system under test is
  unchanged and E7 stands. It is still a change to `src` after E7, so it is recorded here rather than passed over.

**Run order (added 2026-10-31).** Plan §7 ran the Cypher tier on all four corpora first, then the agent. A Cypher
replay turned out to take as long as its run (about 23 minutes per 560 questions at concurrency 1), which would
have delayed the headline numbers by about five hours. After H100g2's Cypher run and replay, `run_sealed.sh` was
stopped between two steps and reordered: H1000g2 Cypher, the agent on both headline corpora, the claims report,
then the descriptive arms and F1. Steps, ids, caps, seeds and questions are unchanged; only the order moved.

**Replay gate (added 2026-10-31).** The replay of `S7-CYP-H1000g2` stopped at a cache miss after 231 rows, all equal
to the run. One query took 22.6 s in the run and passed the 30 s limit in the replay, which then asked for a repair
query the cache does not hold (`replays/INF-S7-CYP-H1000g2/timing_note.md`). A Cypher replay at 1,000 sheets therefore
cannot always finish, because timeouts depend on machine load. `run_sealed.sh` accepts a replay that did not read
`identical` only if a written `timing_note.md` stands beside it. The alternatives were to raise the limit, which
changes the frozen system, or to patch the harness to skip misses, which it is frozen against.

**Cap raise (added 2026-10-31).** `S7-AG-H1000g2` stopped at its $1.00 cap after 535 of 560 questions ($0.93 spent):
the agent cost $0.00174 per question against the $0.00133 the cap assumed. Stop rule 3 applied, and the user approved
raises of at most $1 in all. `run_sealed.sh` adds $0.90 per run on top of the hashed `caps_r5.json`, which is unchanged:
S7-AG-H1000g2 +$0.15, S7-AG-H100g2d0 and d50 +$0.05 each, S7F1-CYP +$0.10 each, S7F1-AG +$0.20 and +$0.25.

**Hygiene note (2026-10-31).** While diagnosing the replay, the main session printed the trace of one test question
(`H1000g2:FEEDING_UNITS:111`): its Cypher query and its raw reply, against plan §9 point 5. Nothing was changed
because of it: the system stayed frozen and no question or run was altered. The query was also run directly on the
test database to time it, with no LLM call.

## Consequences

- Plan §9 point 4 is corrected. ADR-0059 stays as written; this ADR holds the correction.
- R4 keeps its numbers: its H30g2 set holds FIRST_MEETING_POINT, but it appears only in the "all" scope, not in the
  19 common families behind X1–X2.
- The thesis reports the family as excluded on the sealed v2 corpora, with the measured counts, not as absent.
- **Revisit if** the byte-identity check fails: then 2C is off, and the generators run unchanged or the recipe is
  reconsidered with the user.
