---
adr: 0025
title: Make a unit span several sheets — larger units, split by unit with balanced sheets at budget 18
status: accepted
date: 2026-10-01
supersedes: ADR-0017 in part (decision item 3, the headline split); qa-system.md §13.1 headline split config
---

# ADR-0025 — Units span sheets, a sheet belongs to one unit

**Question.** UNITS-01 (2026-10-01) found every generated sheet showing 2–8 units: units are smaller than a sheet.
Real unit P&IDs are the reverse (HNF-64103 3.2.5.2 "the unit P&ID"; OPEN100 is split per system, 1–2 sheets each,
`splitter.md` §3; DEXPI attaches a drawing to a unit, `pid-structural-rules.md` P5, S16). The user approved making
units larger (2026-10-01). How, without losing ADR-0017's density calibration?

**Evidence** (architect scratch probe 2026-10-01, `ingest.pipeline.build_synthetic_corpus`, seed 0 unless stated,
DRAWING_ONLY; "balanced" = a scratch re-implementation of the chunking below; figures re-measured after the code lands):

| Config | Nodes | Sheets | Nodes/sheet | Stubs/sheet | Sheets with 1 unit | Sheets per unit |
|---|---|---|---|---|---|---|
| today: 290 u × 3–8 eq, `flow_greedy` b16 | 4,145 | 98 | 42.30 | 8.63 | 0 of 98 | 1–5 (mean 1.61) |
| 290 u × 3–8, `by_unit` b16 | 4,145 | 290 | 14.29 | 2.57 | 290 of 290 | 1 |
| 33 u × 24–72, `flow_greedy` b16 | 4,009 | 99 | 40.49 | 9.27 | 48 of 99 | 2–9 (mean 4.97) |
| 33 u × 24–72, `by_unit` b16 (greedy chunks) | 4,009 | 113 | 35.48 | 7.10 | all | 2–5; tail sheets with **1** equipment |
| 33 u × 24–72, `by_unit` b18 balanced, seeds 0/1/2 | 4,009–4,228 | 101–109 | **37.53–39.69** | **7.41–7.59** | all | 2–4 (mean 3.06–3.30) |
| 320 u × 24–72, `by_unit` b18 balanced (H1000 size) | 39,231 | 999 | **39.27** | **7.55** | all | 2–4 (mean 3.12) |

**References.** EX01 has 36 nodes/sheet and OPEN100 8.0 stubs/sheet (range 2–12). ADR-0017's headline gave 15.97
equipment/sheet; balanced b18 gives 15.35–15.87.

**"Units shown" depends on what is counted.**
- **Equipment only:** the table's column. UNITS-01 instead counted **every node carrying a `unit_id`**; recounted by
  the architect, that reproduces UNITS-01 exactly (mode 5 on 132 sheets; 440 / 430 / 85 / 45 sheets per unit).
- **Every node:** the balanced b18 rows show one unit on only 82 of 101 sheets (~H100) and 829 of 999 (H1000).
  The extra units come from valves on cross-unit streams (owned by the source unit, `plant-generator.md` §3.3 step 4)
  that cluster with the receiving unit's equipment, and from the actuating functions that control them.
- **With unit-aware clustering** (a node with `unit_id` U is owned only by equipment of U; scratch): **every sheet**
  shows one unit (101/101 and 109/109 at ~H100, seeds 0–1; 999/999 at H1000). Density is unchanged
  (37.53–39.69 nodes/sheet; 7.38–7.55 stubs/sheet), and G1 holds.

**Options**
- **U1** Larger units, keep `flow_greedy`. Half the sheets still mix units (48 of 99): depth-first order dives into
  a downstream unit mid-unit. Fails the goal.
- **U2** `by_unit` with today's units. Density collapses (14.29 nodes/sheet); a unit is one sheet. Fails ADR-0017.
- **U3** Larger units, `by_unit`, greedy chunks, budget 16. One unit per sheet, but 35.48 nodes/sheet and tail sheets
  holding a single equipment item.
- **U4** Larger units, `by_unit`, **balanced** chunks (a unit of n equipment → m = ⌈n/B⌉ sheets whose equipment
  counts differ by at most 1), **unit-aware clustering**, **budget 18**. Same sheet count as U3 at that budget, no
  degenerate sheets, no foreign-unit valve on a sheet.

**Decision: U4.**
1. ~~Headline generator: `equipment_per_unit_min/max = 24/72` (mean 48 ≈ 3 sheets per unit).~~ *(amended on acceptance, 2026-10-01, user: **1–2 sheets per unit**, as in OPEN100.)* Headline generator: `equipment_per_unit_min/max = 18/36` — with balanced chunks at budget 18 a unit of 18 is one sheet and 19–36 is two. **Unmeasured:** the 24/72 evidence above does not carry over; equipment/sheet will be lower on two-sheet units, so SMOKE-07's density band decides, and if it fails the budget is revisited with the user. **A declared parameter,
   not a calibration**: no source gives unit size; OPEN100 gives 1–2 sheets per system, the user asked for
   "several". Code defaults (3/8) stay for tests.
2. Headline split: `by_unit`, with balanced chunks **and unit-aware clustering**, `sheet_equipment_budget = 18`,
   DRAWING_ONLY (ADR-0023). 18 is chosen because balanced chunking at 18 reproduces ADR-0017's ≈16 equipment per
   sheet; budget 16 measured 33.56–35.48 nodes/sheet, below the EX01 reference. Both refinements live inside `by_unit`
   only; the other strategies are unchanged.
3. Headline points stay defined in **sheets** (ADR-0015: ~10, ~100, ~1,000), reached by the smallest `n_units`
   giving `n_sheets ≥ target`. The node counts follow (probe: 999 sheets ↔ 39,231 nodes, vs 43,043 before) and are
   reported beside sheets, as ADR-0015 already requires. Not fixing nodes avoids a second dial.
4. One source of truth: a headline preset in code (`ingest/headline.py`), used by the CLI, so no command drifts.
5. **Gates** before any headline corpus is used. These are criteria, not predictions, checked at H100 and H1000,
   seed 0:
   - every sheet shows exactly one unit, **counted over every node carrying a `unit_id`** (UNITS-01's rule);
   - nodes/sheet in [36, 43];
   - stubs/sheet in OPEN100's [2, 12];
   - G1 true (ADR-0027).

**Why.** The Hierarchical strategy (plant → unit → sheet) and the `CROSS_UNIT` / `COUNT_IN_UNIT` families assume a
unit is a group of sheets. Today it is a fraction of one. `by_unit` is the rule-grounded partition
(`pid-structural-rules.md` §8 item 5); `flow_greedy` cannot give one unit per sheet even with large units.

**Costs.** One strategy change, a preset, a size search; SMOKE-06's density row is re-measured (SMOKE-07). Measured
side effects at ~H100: `CROSS_UNIT` candidates fall from 160 to 20 (33 units), and every `COUNT_IN_UNIT`
candidate moves to k ≥ 3 (297 of 297). A10 (~10 sheets) holds only 3–4 units.

**Revisit if** SMOKE-07 leaves either density band, or the availability gate (ADR-0029) finds `CROSS_UNIT`
underpowered at H1000.

**Accepted 2026-10-01 (user, in chat)** with the unit-size amendment in decision item 1 (1–2 sheets per unit instead of 2–4).
