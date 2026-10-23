---
adr: 0029
title: Let questions reach as far as the plant allows — no hop caps, doubling k-bins, a per-bin availability gate
status: accepted
date: 2026-10-01
supersedes: ADR-0013 in part (point 2: how k is binned); qa-system.md §9 bins {0, 1, 2, ≥3}, §12 step 6 and §13.3 "Sample size" (the floor now applies per powered bin)
---

# ADR-0029 — How far across sheet and unit boundaries a question reaches

**Question.** The user (2026-10-01): the essence of the test is how well we can ask **across sheet and unit
boundaries**, so the path limits must go "much higher". Today:
- `FLOW_PATH` stops at `DEFAULT_MAX_PATH_EDGES = 6` (`families_flow.py`), and `UPSTREAM_ISOLATION` reuses it as a hop
  limit;
- `UNANSWERABLE_TAG` takes at most 20 tags (`families_abstain.py`);
- bins are {0, 1, 2, ≥3}, with 97 questions per bin as the floor (`qa-system.md` §12).

**Evidence.** Architect probe, 2026-10-01, on the ADR-0025 configuration with the ADR-0027 fix, seed 0. Unbounded
shortest `send_to` paths from seeded random source samples:

| | ~H100 (33 u, 101 sheets), 300 sources | H1000 (320 u, 999 sheets), 3,000 sources |
|---|---|---|
| reachable (source, target) pairs | 8,897 | 116,592 |
| share within 6 hops | 16.7 % | 12.7 % |
| max hops / max k / max units crossed | 66 / 11 / 5 | 93 / 16 / 8 |
| k: 0 · 1 · 2 · 3–4 · 5–8 · 9–16 · 17+ | 1,026 · 1,204 · 1,409 · 2,493 · 2,629 · 136 · 0 | 9,925 · 11,408 · 12,810 · 25,956 · 41,635 · 14,858 · 0 |
| BFS time for the sample | 0.2 s | 3.4 s |

These reach figures were measured before ADR-0025's unit-aware clustering refinement, which changed pairs at ~H100
from 381 to 374. AVAIL-01 re-measures them on the final code.

Two consequences:
- **The cap drops most cross-boundary pairs.** A 6-hop cap throws away 83–87 % of reachable pairs, which are the
  long cross-boundary ones.
- **Enumeration does not scale today.** Every candidate becomes a `Question`, and `evidence_sheets` loops over every
  sheet per question (`evidence.py`, read in code, not profiled). Measured at H1000: `LOOKUP_TYPE` takes 119.6 s
  for 39,231 candidates and `LOOKUP_UNIT` 134.7 s. `FLOW_PATH` did not finish inside a 900 s limit, after the
  earlier five families had used 365.2 s.

**Options**
- **R1** Raise the cap to a larger constant and keep 4 bins. The ≥3 bin then pools k = 3…16, so the curve cannot
  show what happens far away.
- **R2** No cap, keep 4 bins. Same problem.
- **R3** No cap, **doubling bins** {0}, {1}, {2}, {3–4}, {5–8}, {9–16}, {17–32}, …, open-ended up to the
  corpus's max k. A per-bin availability gate decides which bins are powered.
- **R4** Stratify by units crossed instead of k. Units are coarser, and k is ADR-0013's x-axis.

**Decision: R3, with units crossed as a reported second axis.**
1. **Reach.**
   - `FLOW_PATH`: every `send_to`-reachable target, using today's shortest path and lexicographic tie-break.
   - `UPSTREAM_ISOLATION`: walks with a visited set instead of a hop cap.
   - `UNANSWERABLE_TAG`: one absent tag per (prefix, unit) group, with no cap.
2. **Bins.** Doubling, as in R3. Unanswerable questions keep their own bin.
3. **Per-anchor cap.** At most one question per (family, source anchor, bin). The target is drawn with a seeded
   rng, so questions are not dominated by a few hubs.
4. **Availability gate** (AVAIL-01, per corpus). A bin is **powered** when it holds at least 97 candidates after the
   cap. Powered bins are sampled at the pilot's count, never below 97. An underpowered bin takes all its
   candidates and is reported and flagged, never silently merged.
5. **Second axis.** Every `Question` carries `u`, the number of evidence edges whose endpoints have different
   `unit_id`s. Results are broken down by `u`. It has no target and no floor.
6. **Enumeration at scale.**
   - A node → sheets index is built once per corpus.
   - `FLOW_PATH` keeps only `(target, k)` per source, and builds a `Question` only for the target drawn per bin.
   - Criterion: the H1000 question-set build finishes inside 600 s (the K-NEO budget).
7. **Budget fallback** (extends §13.3). If the pilot cannot pay for the floor, merge the bins back to
   {0, 1, 2, ≥3} first, then {0, ≥1}. Never drop H100 or H1000.

**Why.** The claim is that strategy ranking changes with scale, and the scale effect acts through boundary
crossings. A cap at 6 hops removes exactly the regime where ContextRAG and a queryable KG should differ most. Doubling
bins keep each bin's k spread proportional. The gate turns "we could not find enough questions far away" into a
reported number instead of a silent absence.

**Costs.**
- **Questions.** Arithmetic: at H1000, 6 answerable bins plus unanswerable = 7 × 97 = **679** questions per
  corpus × strategy × repeat at the floor, against 5 × 97 = 485 today (+40 %). The pilot prices it.
- **Code.** About 3 question modules and `KBin`.
- **Prompt length.** Long paths make `TAG_PATH` answers long. The parse-failure rate is already reported per cell
  (G4 in §13.3).

**Revisit if** AVAIL-01 finds a bin above 2 underpowered at H1000, or the pilot prices the floor out (then step 7).

**Accepted 2026-10-01 (user, in chat).** As written, doubling bins included. The user states cost is not the binding constraint ("pénz egyelőre annyira nem számít, inkább eredmény legyen jó"); the bin-merge order stays only as a fallback. The user also wants several models tried (ADR-0014 follow-up).
