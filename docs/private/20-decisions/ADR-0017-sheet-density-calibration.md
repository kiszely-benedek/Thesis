---
adr: 0017
title: Fix the splitter's locality first, then split the headline corpora at budget 16 (EX01-like sheets)
status: accepted
accepted: 2026-09-26
date: 2026-09-26
supersedes: none
---

# ADR-0017 — How dense is a generated sheet?

**Question.** At budget 4 a sheet holds 10.7 nodes and EX01 holds 36, so "1,000 pages" (ADR-0015) means ~¼-size
pages. Raising the budget to 32 cuts pairs only from 6,162 to 6,071 (1,000 units, seed 0, main session 2026-09-26).
Why, and what density should the headline use?

**Root cause** (architect diagnostic 2026-09-26, same plant, scratch script, re-measured by rule 4). The default
`flow_greedy` (`split_models.py:56`) orders owners with `_flow_order`, a **breadth-first** walk (`strategies.py:208–232`,
FIFO at :226/:231). Every unit hangs off an earlier one (`generator.py:172–183`), so the one feed's BFS interleaves
all units. The ends of an edge sit a median of 287 order positions apart, and `_chunk_by_budget` (:251) cuts runs of 4–32.
Of the 6,232 cuttable (inter-cluster) edges, `flow_greedy` cuts 6,162 / 6,099 at budget 4 / 16; `random` cuts 6,230 / 6,220.
Cuts are 94.5 % `send_to`, and 4,972 of the 6,232 are intra-unit streams. Neither loops nor inter-unit streams dominate.

**Options**
- **D1** Keep budget 4, always report nodes next to sheets. No work; sheets stay ~¼ of EX01.
- **D2** Budget 16 as is: 42.6 nodes/sheet, but 35.4 stubs/sheet (4.4× OPEN100's 8.0), stated as a limitation.
- **D3** Make `_flow_order` depth-first, then budget 16. Scratch: 42.6 nodes and **9.1 stubs/sheet** (1,566 pairs).
- **D3′** Default to `modularity`, no code: 42.6 nodes, 9.9 stubs, but sheet numbers no longer follow flow.
- **D4** Sweep density as a second dial (budget ∈ {4, 16, 32} at a fixed node count). Every run multiplies.

**Decision: D3. D4 is a could-item.**
1. `_flow_order` becomes a depth-first preorder from the feeds, with the same sorted tie-break. It is shared with `by_unit`
   and `utility_aware`. Nothing else in the splitter changes.
2. Regression test: on a generated plant, `flow_greedy` cuts fewer edges than `random` at an equal budget.
3. Headline split: `flow_greedy`, `sheet_equipment_budget=16`, all else unchanged. 16 is measured. Budget 13–14
   would give 36 nodes by the measured 2.66 nodes per budget unit, but it is unrun.
4. Gate: re-run the SMOKE-01/02 configs at budget 16 under a new SMOKE id. SMOKE-04/05 (not yet run) use the new config.
5. Rows report sheets, nodes and stubs/sheet. SMOKE-01…03 stand for time, memory and round trip only.
6. Details: `splitter.md` §3 (new "Density calibration") and `qa-system.md` §13.1.

**Why**
- Only D3 matches both references at once. D2 inflates k, the number of cuts on an evidence path, which is the claim's x-axis.
- Pre-fix, `flow_greedy` ≈ `random`, so the strategy comparison in `splitter.md` §3 would be empty. That is a bug, not a taste.
- The pilot (CP1, 2026-10-04) and SMOKE-04/05 have not run yet, so no measured result is lost.

**Costs.** One function, one test and one SMOKE re-run. Coder time is an estimate: a small task, and coder speed is
unmeasured (ADR-0015). Machine time is ~1 min (14.07 s + 49.42 s, measured). Sizes by linear scaling (unrun): H100 ≈ 290
units ≈ 4,300 nodes; H1000 ≈ 2,900 units ≈ SMOKE-02's 43,043 nodes (measured feasible); H4000 ≈ 11,600 units ≈
170,000 nodes, unmeasured, which needs a new smoke. ContextRAG's wall comes ~4× earlier in sheets.

**Revisit if** the re-run's stubs/sheet leave OPEN100's range of 2–12, H1000 fails K-NEO (600 s), or real densities arrive.

## Outcome log
- **2026-09-26** Accepted by the user as recommended (D3): depth-first page order, then budget 16. Root cause verified by the main session in `strategies.py:208–232` (breadth-first `deque`/`popleft`). The architect's DFS numbers are from a scratch re-implementation; they are re-measured after the real fix.
