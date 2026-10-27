---
adr: 0059
title: Count v2 composition on the plan with a corpus cross-check, draw the column's air-ejector package on its own sheet (tuning round 1), and give v2 test corpora seeds from a reserved range
status: accepted
date: 2026-10-27
supersedes: none. Amends the generator-v2 design notes: base §12.1's "computed on the sheet graphs" (now plan first, with a corpus cross-check), the §9 T16 row of the vocabulary note (now T16a + T16b), and §8's coverage count (79 → 77, following the 2026-10-25 decision). Extends ADR-0045's fresh-seed rule to v2. Uses one of ADR-0057's three tuning rounds.
design: 40-design/generator-v2-pid-vocabulary.md §14
---

# ADR-0059 — v2 composition on the plan, tuning round 1, v2 test seeds

## Context

T13–T15 completed every v2 pattern. Plan-level measurement (vocabulary note §14.1) shows the following:
- One pass/fail band fails: **max off-page stubs ≤ 21**. It reaches 26 (D100g2 seeds 1 and 3) and 29 (D1000g2).
  All sheets above 21 are U1's combined layout with the air-ejector vacuum (47 of 55 such sheets over 60 seeds).
- The share of sheets inside 40–134 symbols is 75–80 %. Q8 = A (2026-10-26) made that share a reported figure. The
  best combination of five candidate changes that keeps one unit per sheet reaches 89.5 %.
- `symbols.py` does not count `ProcessControlFunction` (every v2 controller), so 1.9–2.1 bubbles per sheet go
  uncounted.
- T12 measured 3.3 stubs per sheet on the corpus; T13 measured 5.06 on the plan. One D100g2 corpus build explains
  the gap exactly: at duplication 0 the corpus connectors equal the plan's crossings on 103 of 103 sheets. The plan
  also counts 3.88 open line ends per sheet, which pyDEXPI's graph keeps no node for.
- v2 test corpora (R4, R5) need fresh seeds (ADR-0057 point 5). Seeds 1–90 have now been used for plan-level
  tuning, and the current id function would name a seed-2 tuning plant `H100g2`.

## Options considered

**Where composition is counted.**
- **A. On the sheet graphs** (base §12.1 as written). The drawn graph is what the system reads. But it cannot see
  open line ends (Q7 = A counts them), and its stub and symbol counts move with ADR-0028's duplication rate, an
  experimental condition.
- **B. On the plan, with an exact corpus cross-check at duplication 0 (chosen).** It sees every stub Q7 = A
  defines and is independent of duplication. The cross-check proves the two levels agree where they can.
  Graph-only properties (degree-1 share, one unit per sheet) stay on the corpus.

**Fixing the stub maximum** (seeds 1–30, 60 units each, plan level).
- **C1. `p_column_combined` = 0.** Max 21: passes, but exactly at the limit. It deletes the FB&D combined layout,
  which matches D1 (≥ 153 symbols without fittings; v2's combined sheets have 160).
- **C2. The air-ejector package (2 × A/B ejectors and the inter-condenser) as its own U1 drawing group (chosen).**
  Max 19 (20 on seeds 31–90). WTP draws condensers and ejectors on their own sheet (H2 [HC]). No variant is lost and
  there is no new random draw.
- **C3–C5 and combinations**: a separate reboiler group, a split U2, a different merge cap. None fixes the stubs on
  its own. Together they lift the 40–134 share to 89.5 % at the cost of more, smaller sheets.
- **C6. Small units share a sheet with a neighbour.** This breaks ADR-0025 (one unit per sheet), prefix stability
  and the size search. Rejected.

**Test seeds.**
- **(a)** Next unused small integers. Easy to collide with tuning seeds later.
- **(b) A reserved range 5000–5999, fixed in a checked-in table before generation, with the composition CLI
  refusing those seeds (chosen).** No recorded run uses a seed in that range.
- **(c)** Seeds hashed from the corpus id. Auditable, but harder for a reader to check than (b), and it buys
  nothing extra.

## Decision

1. Composition bands are computed on the **plan** (`sheet_stats`). The corpus is checked against the plan exactly at
   duplication 0, and the deltas are reported at 0.25. The degree-1 share and "one unit per sheet" are measured on
   the sheet graphs.
2. **Counting-rule correction:** `ProcessControlFunction` counts as an instrument (PSGF + PIF incl. its pyDEXPI
   subclass). This restores base §12.1's rule; it is not a tuning.
3. **Tuning round 1 = C2.** The ADR-0057 tuning log then reads 1 of 3 rounds used.
4. The 40–134 share stays reported (Q8 = A), alongside the real-sample figure (10 of 15 sheets inside).
5. **v2 seeds:**
   - 0–999 for dev and tuning;
   - 5000–5999 for test: H1g2 = first seed in 5100–5399 with a one-sheet one-unit plan; H3g2, H10g2, H30g2 = 5001;
     H100g2 = 5002 (also for its duplication sensitivity runs at 0 and 0.5); H1000g2 = 5003.
   - Ids: `D` for seed 1, `H` for a registered test seed, `X…s{seed}` for any other seed.
6. Open items:
   - S6 exempts the condensate drain pot (H1 shows no PSV on it).
   - FIRST_MEETING_POINT stays at 0 candidates on v2 and is reported as unavailable.
   - `p_shared_farm_feed` defaults to 0.0 and is rejected above 0 (not implemented).
   - U3's recycle-gas port stays open.
   - The tank farm's two XVs in series stay.

## Rationale

- **Thesis claim.** R4 and R5 carry the headline numbers (ADR-0057 Q3 = B), so the corpus must be defensibly
  realistic and the measurement of that realism must not depend on an experimental knob. Point 1 gives one number
  per sheet whatever the duplication rate. Point 5 keeps the tuning instrument away from the test plants.
- **Boring option, grounded.** C2 is a drawing-group change copied from a real sheet set, inside the existing merge
  rule. Chasing 95 % would spend the remaining tuning rounds fitting one nuclear plant's range (OPEN100), which the
  real samples themselves do not follow.

## Consequences

- **Makes easy:**
  - a single, auditable composition table;
  - an exact plan-to-corpus reconciliation test;
  - test seeds a reviewer can check against the run configs.
- **Makes hard:** nothing measured is lost. Corpus-level stub counts are no longer quoted as the stub figure.
- **v1:** untouched. All changes are inside `benchmark/v2/` and `ingest/headline_v2.py`.
- **v2:**
  - Plans keep every node, tag, line and link for a fixed `(seed, n_units)`. Sheet groups change, and with them
    the `n_units` the size search returns (D100g2 seed 1: 63 units today → 59 with points 2 and 3, simulated).
  - The R0 figures are stale and must be re-taken.
- **Revisit if:**
  - a band fails in T16b's report (that is round 2);
  - the user reverses Q8 = A;
  - a real sheet set shows ejectors drawn with the column;
  - a test seed is found in any earlier run record.

## Status

Proposed 2026-10-27 (architect). **Accepted 2026-10-27 (user, in chat)**, with the vocabulary note's §14.7
questions answered as recommended:

| # | Question | Answer |
|---|---|---|
| 1 | Tuning round 1 | C2: the column's air-ejector package on its own sheet (not C1) |
| 2 | Share of sheets in 40–134 symbols | reported next to the real samples, no longer chased to 95 % |
| 3 | The ADR as a whole | accepted: plan as the authoritative count, PCF correction, round 1, seed ranges, the five open-item decisions |

Tuning rounds used: 1 of 3 (ADR-0057).

**Recorded 2026-10-27 (T16b), before any test corpus was generated:** H1g2 = seed **5100** (the first seed in
5100–5399 whose one-unit plan is one sheet after T16a; 104 of the 300 qualify). The full test-seed table is
`TEST_SEEDS_V2` in `ingest/headline_v2.py`.
