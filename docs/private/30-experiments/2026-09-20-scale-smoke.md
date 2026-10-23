---
run: SMOKE-01, SMOKE-02, SMOKE-03
date: 2026-09-20
question: Does seed → DiGraph → split survive a plant of thousands of sheets inside the §2 kill criterion?
status: done
---

# SMOKE-01 / 02 / 03 — scale smoke, and the round trip at scale

**Tooling runs, not thesis experiments.** They answer the engineering question in
`40-design/plant-generator.md` §9 step 7 and check the §2 kill criterion. They deliberately do **not**
carry `EXP-000X` numbers, which stay reserved for the retrieval experiments that answer the thesis claim
(EXP-0001…EXP-0005 in `_results.md`).

Two sizes were run. **SMOKE-01** (1,000 units) was the §9 step 7 requirement of at least 1,000 sheets.
**SMOKE-02** (2,900 units) was added because SMOKE-01 evidenced only *hundreds and just over one
thousand* sheets, while the professor's target phrase is "hundreds or thousands".

## Setup

| | |
|---|---|
| Command | `python -m plantgraph.benchmark.scale_smoke --n-units N --budget 4 --seed 0 [--no-memory]` |
| Commit | **`b30414b`** — the runs were taken on the working tree that became this commit; the tree was clean and the gates green immediately after, so the two are the same code. |
| Machine | this developer machine, Windows 11, AMD64, one process |
| Python | 3.12.10 |
| Libraries | `pydexpi` 1.2.0, networkx 3.6.1, pydantic 2.13.4 |
| Config | `GeneratorConfig(seed=0, n_units=N)` at current defaults; `SplitConfig(seed=0, sheet_equipment_budget=4)` |
| Loader | `LinearGraphLoader` (the fast path), **not** pyDEXPI's stock `GraphLoader` |

**Four runs, two per size, on purpose.** Timings come from `--no-memory` runs and peak memory from
separate traced runs, because tracing inflates the timings — threat 2. Within each size the two runs
produced **identical** node, edge, sheet and connector-pair counts: an incidental determinism check
across processes.

## Result

**Sizes produced**

| | SMOKE-01 (1,000 units) | SMOKE-02 (2,900 units) | growth |
|---|---|---|---|
| `DiGraph` nodes | 14,687 | **43,043** | ×2.93 |
| `DiGraph` edges | 16,171 | **47,405** | ×2.93 |
| **Sheets** | 1,378 | **4,015** | ×2.91 |
| Connector pairs | 6,162 | **18,048** | ×2.93 |

**Timings — what the kill criterion is judged on** (`--no-memory`, `time.perf_counter`, seconds)

| Stage | SMOKE-01 | SMOKE-02 | growth |
|---|---|---|---|
| build (`DexpiModel`) | 1.447 | 4.973 | ×3.44 |
| loader (complete graph, linear) | 3.396 | 10.994 | ×3.24 |
| conceptual (pyDEXPI abstraction) | 8.472 | 31.817 | ×3.76 |
| adapter (→ schema `DiGraph`) | 0.752 | 1.632 | ×2.17 |
| **seed → `DiGraph`** (sum of the four) | **14.07** | **49.42** | ×3.51 |
| split | 1.143 | 4.548 | ×3.98 |
| **full path, generate → split** | **15.21** | **53.96** | ×3.55 |

**Peak memory** (traced runs): SMOKE-01 **278.1 MiB** (291,585,831 B); SMOKE-02 **785.7 MiB**
(823,846,082 B), ×2.83.

## Reading

**The kill criterion in §2 is not met at either size, so H1 stands and no fallback to H3 is needed.**

- **(a) "seed → `DiGraph` exceeds 10 minutes, or runs out of memory, for the largest plant the EXP-0002
  sweep needs."** Measured **49.42 s at 4,015 sheets** against a 600 s threshold — **8.2 % of the budget,
  a margin of about 12×**. At 1,000 units the margin was 43×. Peak memory 786 MiB is substantial but
  nowhere near exhausting this machine.
- **(b) "invariant 11 or 12 cannot be made to pass."** Both pass
  (`test_linear_graph_loader_equals_the_stock_graph_loader`,
  `test_conversion_report_has_no_unmapped_topology_edges_and_resolves_every_valve_unit`). 238 tests pass;
  ruff, ruff format and mypy --strict clean.

**Scaling behaviour, measured over one 2.9× step.** Size grew ×2.93 and time grew ×3.51, so the path is
**slightly superlinear, not quadratic** — the danger the stock `GraphLoader` showed (§7: instances ×5.2,
time ×28.6) does **not** appear on the linear-loader path. Memory grew ×2.83, i.e. **roughly linear in
graph size**. Two points is a trend, not a law; see threat 1.

**§7's estimates are now measurements, and they held up.**

| §7 said | Now measured |
|---|---|
| "about 1,370 sheets" at 1,000 units, budget 4 (splitter **not run**) | **1,378 sheets**, splitter run |
| seed → `DiGraph` 15.114 s at 1,000 units (prototype, 2026-09-13) | **14.07 s** |
| "4,000 [sheets] at that budget needs about 16,000 equipment, roughly 2,900 units… **about a minute**" | **4,015 sheets at 2,900 units in 53.96 s** |
| peak memory **"not measured"** | **278.1 MiB** / **785.7 MiB** |

The §7 estimate of "about a minute" for the 2,900-unit case was **right**, which is worth recording: the
reasoning behind it was sound, not lucky guessing at an order of magnitude.

**What this licenses us to say.** "The generator produces a plant of **over 4,000 sheets in under a
minute** on one laptop, using under 800 MiB." That covers the professor's "hundreds or thousands of
sheets". It does **not** license anything about tens of thousands.

## Threats

1. **Two sizes, one seed, one machine, one process, one budget.** The superlinear trend is fitted to
   **two points**. Nothing was run above 2,900 units, so the largest plant EXP-0002 might need is still
   an extrapolation. The 12× headroom is comfortable but shrinking faster than size grows.
2. **`tracemalloc` inflates timings, which is why timing and memory runs are separate.** Measured
   2026-09-20 at `n_units=50, budget=4, seed=0`: build 4.3×, loader 4.6×, conceptual 9.1×, adapter 4.1×,
   split 2.9×. Whole-run inflation: **5.9× at 1,000 units** (89.99 s traced vs 15.21 s) and **5.19× at
   2,900 units** (279.97 s vs 53.96 s). Had traced timings been filed, SMOKE-02 would have read 280 s
   against a 600 s criterion — **inside the same order of magnitude as the threshold**, which would have
   been a materially misleading result. The untraced conceptual figure at 50 units (0.378 s) agrees with
   the 2026-09-13 prototype (0.349 s); the traced one (3.424 s) agrees with neither. Recorded in
   `scale_smoke.py`'s module docstring.
3. **`tracemalloc` peak is not RSS.** It counts Python-level allocations only, excluding interpreter
   overhead and non-Python allocation. Treat 786 MiB as a lower bound on process memory.
4. **The sheet budget of 4 is arbitrary and unsourced.** `00-index.md` records that no source states how
   many items a sheet holds. The sheet counts scale with a parameter we chose, not with a fact.
5. ~~**The `rejoin` path was not exercised.**~~ **Measured separately the same day — see SMOKE-03 below.
   The concern was real but the magnitude was not: 3.18 s at 4,015 sheets, and the round trip holds.**
6. **Environment drift from the prototype.** Python 3.12.10 here against 3.13.1 there, pydantic 2.13.4
   against 2.13.5. The two tables are not strictly like-for-like.
7. ~~**Uncommitted tree.**~~ **Resolved:** that tree is now committed as `b30414b`, and `git status` was clean with all four gates green immediately afterwards.

---

# SMOKE-03 — does the round trip still hold at scale, and is `rejoin` a hotspot?

**Why.** Every existing round-trip test (`test_splitter.py:42`, `test_generator_integration.py:30`,
`test_pydexpi_adapter.py:259`) runs at `GeneratorConfig` defaults — **4 units**. The invariant
"splitting loses nothing and invents nothing" had therefore **never been shown on a large plant**, and
§7 suspected `rejoin._stub_edge_attrs` of scanning the sheet list once per pair.

**Confirmed as a real quadratic term.** `rejoin.py:88` is
`next(candidate for candidate in sheets if candidate.sheet_id == sheet_id)` — a linear scan of the sheet
list, executed once per connector pair, i.e. **O(pairs × sheets)**.

**Setup.** Same machine, libraries and config as SMOKE-01/02; `budget=4`, `seed=0`; `split` then `rejoin`
timed with `perf_counter`, and the rejoined graph compared to the original on node and edge sets. Probe
script was a scratchpad file, not committed.

| units | sheets | pairs | split (s) | **rejoin (s)** | **round trip equal?** |
|---|---|---|---|---|---|
| 25 | 38 | 164 | 0.018 | 0.007 | **True** |
| 50 | 69 | 303 | 0.029 | 0.014 | **True** |
| 100 | 135 | 581 | 0.058 | 0.030 | **True** |
| 200 | 269 | 1,229 | 0.131 | 0.060 | **True** |
| 400 | 543 | 2,446 | 0.514 | 0.144 | **True** |
| 1,000 | 1,378 | 6,162 | 1.134 | **0.504** | **True** |
| 2,900 | 4,015 | 18,048 | 3.862 | **3.176** | **True** |

**Reading.**

1. **The round-trip invariant holds at 4,015 sheets.** This is the first time it has been demonstrated
   above a handful of sheets, and it is the benchmark's central correctness claim. (Node and edge sets
   only — the full attribute-by-attribute comparison is what the test suite does at small size.)
2. **The quadratic term is real but currently harmless.** Over the 1,000 → 2,900 step, size grew ×2.9
   and `rejoin` grew **×6.30**, against ×2.93 for a linear term and ×8.5 for a fully quadratic one — so
   the scan is now the dominant cost inside `rejoin` and still growing. In absolute terms it is **3.18 s
   out of a ~54 s pipeline, about 6 %.**
3. **It does not threaten the §2 kill criterion**, which governs seed → `DiGraph` and does not include
   `rejoin` at all. Nothing about SMOKE-01/02's verdict changes.

**Recommendation, not done.** Replacing the scan with a `dict[sheet_id, SheetGraph]` built once turns
O(pairs × sheets) into O(pairs) and is a few lines in `rejoin.py`. Worth doing **before** a size much
past 4,000 sheets, not urgent today. `rejoin` is test-only code, so this is a test-runtime concern, not
a product one.

**Threats.** One seed, one machine, one budget. The 25–400 rows and the 1,000/2,900 rows come from two
separate processes. The equality check here is node/edge sets, not attributes.

## Follow-ups

- Optional: the `dict` fix in `rejoin.py` (above), plus a `--rejoin` flag on `scale_smoke` so the
  round trip at scale becomes reproducible rather than a scratchpad run.
- If EXP-0002 needs more than ~4,000 sheets, run a third size before assuming the trend holds.
