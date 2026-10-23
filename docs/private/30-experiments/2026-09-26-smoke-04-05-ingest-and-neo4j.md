---
exp: SMOKE-04, SMOKE-05
date: 2026-09-26
question: Does the resolver rebuild the plant exactly at headline scale (SMOKE-04), and does the first Neo4j load of the H1000 corpus stay inside K-NEO (SMOKE-05)?
status: done
---

## Setup
`uv run python -m plantgraph.ingest synthetic --n-units N --budget 16 --seed 0 [--check] [--no-neo4j] [--corpus-id ID]`
(T8 CLI; depth-first `flow_greedy`, ADR-0017). Code: working tree on top of `38c70ed` with T6–T8 uncommitted
(all 408 tests green). Neo4j Kernel 2026.09.0 (enterprise), local, `neo4j://127.0.0.1:7687`, database `neo4j`,
batch size 5,000. Python 3.12.10. Single machine, single runs.

**K-NEO** (`40-design/kg-construction.md` §7.6, set before any measurement): the load of the 2,900-unit,
budget-16 corpus fails if `LoadReport.total_s` > 600 s or the load fails; at most one batch-size change.

## Result

**SMOKE-04 — resolver gate at scale (no Neo4j, `--check`):**

| units | sheets | store nodes | store relationships | pairs predicted | unresolved | pair P / R | gate_equal | generate s | split s | localize s | resolve s | check s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1,000 | 345 | 18,165 | 37,467 | 1,566 | 0 | 1.0 / 1.0 | **true** | 15.94 | 0.57 | 0.26 | 0.70 | 0.65 |
| 2,900 | 1,004 | 53,164 | 109,684 | 4,558 | 0 | 1.0 / 1.0 | **true** | 46.44 | 2.60 | 0.82 | 2.00 | 1.85 |

Store nodes/relationships are the occurrence graph written to Neo4j (sheet items, connector stubs, sheet and corpus
nodes, and their links) — not the 43,043-node plant graph. Identity scores are `null` because the default
`duplication_rate` is 0.0, so no identity groups exist (the CLI has no flag for it yet).

**SMOKE-05 — first Neo4j load, 2,900 units, corpus `smoke05-u2900-b16`:**

| run | wipe s | schema s | nodes s | relationships s | verify s | **total s** | K-NEO (600 s) |
|---|---|---|---|---|---|---|---|
| 1 (empty corpus) | 0.02 | 0.01 | 8.32 | 15.61 | 0.70 | **24.66** | pass, ≈24× margin |
| 2 (wipe + reload) | 4.17 | 0.02 | 6.77 | 14.65 | 1.15 | **26.75** | pass, ≈22× margin |

Written and verified both times: 53,164 nodes, 109,684 relationships (counts matched the plan).

## Reading
The whole KG-construction pipeline — generate, split into 1,004 sheets, localize, resolve without the answer key,
load into Neo4j — runs end to end at the headline size, and the resolver reproduces the plant exactly. The load
is ~25 s, far inside K-NEO, so **the fallback (in-memory networkx instead of Neo4j) is not needed at H1000**.
Generation (~46–48 s) dominates the pipeline, as in SMOKE-02. The corpus was left loaded in the local database so
it can be inspected in Neo4j Browser (wipe with `neo4j_loader.wipe_corpus`).

## Threats
- One seed, single runs, one machine with other processes active; the wipe of an existing corpus adds ~4 s.
- Clean labels only (splitter defaults except budget/order); the harder dials are covered by tests, not measured
  at scale. H4000 (~11,600 units) is still unmeasured at every stage.
