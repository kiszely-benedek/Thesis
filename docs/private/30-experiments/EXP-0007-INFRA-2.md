---
run: INFRA-2, the infrastructure cost of the tuned system V2T-A on the sealed v2 corpora H100g2 and H1000g2
date: 2026-11-04
commits: code at e91abb5 + the INFRA-2 script (uncommitted at run time); E7 fdad31f checked by the script
status: done (07:57 → 10:19, exit 0, zero paid calls)
design: 40-design/infra-cost.md (v2 addendum); ADR-0051
---

# INFRA-2: what V2T-A costs in machine resources at 100 and 1,000 sheets

**Result.** At 1,000 sheets the plant store takes 55.4 MiB on disk (+ 33.6 MiB transaction logs), Neo4j runs at
1.37 GiB resident memory, and the application peaks at 1.72 GiB. Per question, the agent tier's local compute is
negligible (median 0.0013 s, 1.1 % of latency); the Cypher tier is database-bound (database time median 0.07 s,
p90 7.5 s, up to the 30 s limit). Loading the store takes about 30 s; the 456 s ingest is almost all plant
generation (422 s), which a real plant would replace with reading its files.

Source: `data/runs/exp0007/infra/report.md` (script `data/runs/exp0007/run_infra_v2.sh`, log `$TEMP/claude_infra2.log`).
Machine: Ryzen 9 5900HX 8C/16T, 15.4 GiB, Windows 11, plugged in. Temporary database `e7tune`; the demo database
was not touched. Medians over 3 fresh-database repeats (min–max in the report).

## Footprint

| Quantity | H100g2 | H1000g2 | Ratio |
|---|---|---|---|
| nodes / relationships | 8,787 / 29,560 | 91,789 / 308,283 | ×10.4 |
| store on disk (data + indexes) | 6.3 MiB | 55.4 MiB | ×8.9 |
| transaction logs (follow retention) | 3.0 MiB | 33.6 MiB | ×11.1 |
| ingest: generate | 5.2 s | 421.6 s | ×81 |
| ingest: split + localize + resolve + plan | 0.9 s | 9.4 s | ×10.6 |
| ingest: load into Neo4j (schema, nodes, relationships, verify) | 5.3 s | 26.8 s | ×5.0 |
| ingest total | 11.3 s | 456.2 s | ×40 |
| app startup without regeneration | 0.45 s | 5.31 s | ×11.8 |
| app startup with regeneration (what the live app does today) | 6.1 s | 408.3 s | ×67 |
| Neo4j resident memory | 1,270 MiB | 1,370 MiB | ×1.08 |
| app peak at end of probe | 330 MiB | 1,720 MiB | ×5.2 |
| plant graph in app memory (tracemalloc) | 25.0 MiB | 265.6 MiB | ×10.6 |
| ContextRAG prompt build (not deployable at this size) | 0.79 s | 8.54 s | ×10.8 |

## Local compute per question (560 questions per corpus)

| Tier | Basis | H100g2 median / p90 | H1000g2 median / p90 | Local share of latency |
|---|---|---|---|---|
| agent (graph_agent_lines) | cache-only replay, concurrency 1, identical to R5 | 0.0011 / 0.040 s | 0.0013 / 0.50 s | 0.1 % → 1.1 % |
| Cypher, database time only | stored queries re-run | 0.039 / 0.61 s | 0.070 / 7.54 s | 8.9 % → 29.8 % |
| Cypher, full (R5 run, concurrency 4) | fallback, see below | 0.064 / 0.99 s | 0.18 / 31.8 s | 24.2 % → 49.5 % |

Token cost per question beside it (from R5): agent $0.00155 → $0.00170, Cypher $0.00076 → $0.00075.

## Reading

- Every footprint figure grows about linearly with sheets (×9–11 for ×10 sheets), except Neo4j's resident memory
  (flat: it is mostly the server's own reservation) and plant generation (×81, the generator, not the system).
- The live app regenerates the plant from its seed at startup (402 s at 1,000 sheets). Without that, it starts in
  5.3 s. For a real plant the regeneration would be replaced by loading the stored graph; stated as a limitation of
  the prototype, not measured.
- The Cypher tier is the part that feels scale: its database time p90 grows ×12 and some queries reach the 30 s
  limit. The agent tier's work stays in memory and below 1.1 % of latency.

## Checks and caveats

- M1, M2, M3, M5, M7 pass (report "Self-checks"). M4 flags spread > ×1.5 in small H100g2 stages (first repeat cold),
  as in INFRA-1. M6: the server's store-size metric is missing or lags; bytes on disk are the figure.
- The cache-only Cypher replays stopped on query timing near the 30 s limit (`INF2-CYP-H100g2` after 157 rows,
  `INF2-CYP-H1000g2` after 231 rows, every replayed row equal to R5). The report then shows R5's own timings for the
  full Cypher row (coarse clock, concurrency 4); the database-only row is the precise one.
- The probe used `cascade_v4`, not `cascade_v4_iso`: the probe refuses label-routed policies; the two have the same
  tiers and pins, so startup is the same.
- No price table: no reference price was cited, so no money figure is given for infrastructure (ADR-0051).
- v1 for comparison (INFRA-1, D100 / D1000): store 3.0 / 19.4 MiB, Neo4j ~1.2 GiB, app peak 245 / 848 MiB.
