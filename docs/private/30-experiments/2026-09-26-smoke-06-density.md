---
exp: SMOKE-06
date: 2026-09-26
question: After the depth-first splitter fix (ADR-0017, task T4b), do generated sheets match a real sheet in both node density and off-page-connector density?
status: done
---

## Setup
`uv run python -m plantgraph.benchmark.scale_smoke --n-units N --budget B --seed 0 --no-memory --json`,
N ∈ {1000, 2900}, B ∈ {4, 16}, default `flow_greedy`. "Before" = pre-T4b `strategies.py` (commit `3c97587`),
"after" = working tree with the depth-first `_flow_order`. Run by the T4b coder; the 1000/16 "after" point was
re-run by the main session (345 sheets, 14,687 nodes, 1,566 pairs — identical). Working-tree code, uncommitted at
run time. Python 3.12.10, pyDEXPI 1.2.0.

## Result

| units | budget | | sheets | nodes | pairs | nodes/sheet | stubs/sheet | seed→DiGraph s | split s |
|---|---|---|---|---|---|---|---|---|---|
| 1000 | 4 | before | 1378 | 14687 | 6162 | 10.66 | 8.94 | 15.57 | 1.23 |
| 1000 | 4 | after | 1378 | 14687 | 3230 | 10.66 | 4.69 | 15.35 | 0.66 |
| 1000 | 16 | before | 345 | 14687 | 6099 | 42.57 | 35.36 | 15.25 | 1.20 |
| 1000 | 16 | after | 345 | 14687 | **1566** | **42.57** | **9.08** | 15.32 | 0.59 |
| 2900 | 4 | before | 4015 | 43043 | 18048 | 10.72 | 8.99 | 48.31 | 3.67 |
| 2900 | 4 | after | 4015 | 43043 | 9473 | 10.72 | 4.72 | 46.01 | 3.22 |
| 2900 | 16 | before | 1004 | 43043 | 17945 | 42.87 | 35.75 | 45.77 | 3.67 |
| 2900 | 16 | after | 1004 | 43043 | **4558** | **42.87** | **9.08** | 45.45 | 3.10 |

## Reading
At budget 16 after the fix, a generated sheet has **~42.7 nodes** (EX01: 36 conceptual nodes) and **9.08 connector
stubs** (OPEN100: 8.0). Both densities are now close to the real references at once. The headline H1000 corpus
(2,900 units, budget 16) is **1,004 sheets / 43,043 nodes**, built in ~45 s. Cut edges fell ~4× at budget 16
(6,099 → 1,566), so the benchmark's cross-sheet structure now reflects the process flow instead of an
interleaving of the whole plant. The architect's scratch prediction (3,230 / 1,566 pairs, 9.1 stubs/sheet) matched
exactly. Round trip and the G1 resolver gate still pass (328 tests).

## Threats
- One seed. EX01 is one real sheet and OPEN100 is 12; "realistic density" rests on those two references.
- Timings are single runs on one machine, with other processes active.
