# Infrastructure cost report

Machine: AMD Ryzen 9 5900HX with Radeon Graphics (8 cores / 16 threads), 15.4 GiB RAM, Windows-11-10.0.26200-SP0, Python 3.12.10, plugged in
Code: commit a526e084da82738c191a0032669dfa441f7857f7

## Self-checks

| Check | Result | Detail |
|---|---|---|
| M1 replay answers byte-identical to the source run | PASS | 4 of 4 replays identical |
| M2 clock resolution | PASS | every record has a clock step of at most 1e-06 s and every replay row was timed with perf_counter |
| M3 parts add up (db + graph API <= local; server <= client) | PASS | 0 violations in 1080 rows (tolerance 1 ms) |
| M4 repeat spread (max/min within x1.5) | FLAG | repeats disagree by more than x1.5: D100 ingest.load_nodes (x1.81), D100 startup.neo4j_open_check (x2.28), D1000 startup.neo4j_open_check (x1.69), D4000 startup.neo4j_open_check (x1.65) |
| M5 right corpus, right size | PASS | database counts equal the load plan and the load report in every repeat |
| M6 two size sources | FLAG | D100: the server's store.size.database metric is present in 1 of 3 repeats only | D100: the server's store.size.database metric differs from the bytes on disk by more than 10% in 1 of 1 repeats: it lags, so the bytes on disk are the figure and the metric is secondary | D4000: the server's store.size.database metric differs from the bytes on disk by more than 10% in 3 of 3 repeats: it lags, so the bytes on disk are the figure and the metric is secondary |
| M7 zero spend | PASS | no replay allowed paid calls, total spend $0 |
| Old-run rows | FLAG | the replay missed the cache or differed from its source, so the original run's timings are shown instead: need on D100, need on D1000 (coarse monotonic clock, concurrency 4, no split) |
| Database-only rows | FLAG | local compute of these rows is database time only (the stored query run again plus the row formatting; no query-writing model call, no answer-prompt build, no answer parsing): cypher_db_only on D100, cypher_db_only on D1000. The model latency and token cost in the same row come from the source run. |

## I1 - corpus footprint (median, then min to max over the repeats)

| Quantity | D100 | D1000 | D4000 |
|---|---|---|---|
| size: sheets | 101 | 1,000 | 4,000 |
| size: nodes | 3,867 | 37,124 | 148,296 |
| size: relationships | 11,653 | 111,668 | 446,441 |
| size: properties | 34,369 | 329,830 | 1,318,348 |
| ingest: generate | 1.66 s (1.66 s to 1.69 s) | 16.10 s (15.99 s to 16.13 s) | 68.74 s (67.02 s to 75.90 s) |
| ingest: split | 0.0566 s (0.0543 s to 0.0642 s) | 1.58 s (1.58 s to 1.58 s) | 16.95 s (12.99 s to 17.89 s) |
| ingest: localize | 0.0251 s (0.0244 s to 0.0254 s) | 0.4267 s (0.4213 s to 0.4302 s) | 2.15 s (2.08 s to 2.15 s) |
| ingest: resolve | 0.0330 s (0.0310 s to 0.0376 s) | 0.6017 s (0.5979 s to 0.6112 s) | 3.28 s (3.20 s to 3.33 s) |
| ingest: plan | 0.1510 s (0.1487 s to 0.1602 s) | 1.40 s (1.39 s to 1.41 s) | 5.53 s (5.39 s to 5.60 s) |
| ingest: load_schema | 0.0863 s (0.0813 s to 0.0985 s) | 0.0712 s (0.0704 s to 0.0727 s) | 0.1210 s (0.1186 s to 0.1226 s) |
| ingest: load_nodes | 0.3941 s (0.3743 s to 0.6784 s) ! | 1.88 s (1.85 s to 1.88 s) | 7.71 s (7.71 s to 8.37 s) |
| ingest: load_relationships | 0.5681 s (0.5450 s to 0.6581 s) | 3.69 s (3.69 s to 3.70 s) | 20.40 s (20.16 s to 25.41 s) |
| ingest: load_verify | 0.1427 s (0.1292 s to 0.1531 s) | 0.3255 s (0.3060 s to 0.3461 s) | 1.47 s (1.43 s to 1.76 s) |
| ingest total (stages above) | 3.11 s (3.09 s to 3.52 s) | 26.06 s (25.97 s to 26.08 s) | 127.34 s (124.43 s to 135.23 s) |
| store on disk (data + indexes) | 3.0 MiB (3.0 MiB to 3.0 MiB) | 19.4 MiB (19.4 MiB to 19.4 MiB) | 76.4 MiB (76.4 MiB to 76.4 MiB) |
| transaction logs on disk (follow retention, not the corpus) | 1.1 MiB (1.1 MiB to 1.1 MiB) | 10.7 MiB (10.7 MiB to 10.7 MiB) | 46.2 MiB (46.2 MiB to 46.2 MiB) |
| page cache needed (derived: disk x 1.2, Neo4j manual) | 3.6 MiB (3.6 MiB to 3.6 MiB) | 23.3 MiB (23.3 MiB to 23.3 MiB) | 91.6 MiB (91.6 MiB to 91.6 MiB) |
| store size per server metric (secondary, may lag) | 0.0 MiB | - | 0.0 MiB (0.0 MiB to 0.0 MiB) |
| startup: rebuild | 1.89 s (1.89 s to 1.91 s) | 19.55 s (19.42 s to 19.91 s) | 93.90 s (92.46 s to 95.57 s) |
| startup: graph_view | 0.0187 s (0.0183 s to 0.0188 s) | 0.5021 s (0.5013 s to 0.5063 s) | 1.94 s (1.94 s to 1.95 s) |
| startup: tier_runs | 0.0008 s (0.0008 s to 0.0008 s) | 0.0009 s (0.0008 s to 0.0010 s) | 0.0008 s (0.0008 s to 0.0009 s) |
| startup: schema_text | 0.0001 s (0.0001 s to 0.0001 s) | 0.0001 s (0.0001 s to 0.0001 s) | 0.0001 s (0.0001 s to 0.0001 s) |
| startup: neo4j_open_check | 0.0164 s (0.0158 s to 0.0361 s) ! | 0.0604 s (0.0394 s to 0.0664 s) ! | 0.1720 s (0.1208 s to 0.1992 s) ! |
| startup: item_graph | 0.2060 s (0.2060 s to 0.2088 s) | 1.75 s (1.72 s to 2.00 s) | 8.04 s (8.03 s to 8.07 s) |
| startup total | 2.15 s (2.14 s to 2.16 s) | 22.11 s (21.68 s to 22.23 s) | 104.09 s (102.58 s to 105.73 s) |
| startup without rebuild (total - rebuild) | 0.2420 s (0.2414 s to 0.2640 s) | 2.32 s (2.26 s to 2.56 s) | 10.16 s (10.11 s to 10.19 s) |
| ContextRAG prompt build | 0.3352 s (0.3341 s to 0.3353 s) | 3.50 s (3.47 s to 3.65 s) | 14.42 s (14.23 s to 14.50 s) |
| app process peak after imports | 170.6 MiB (170.2 MiB to 170.7 MiB) | 170.3 MiB (170.2 MiB to 170.6 MiB) | 170.6 MiB (170.6 MiB to 170.6 MiB) |
| app process peak at end of probe | 245.4 MiB (244.0 MiB to 245.9 MiB) | 847.6 MiB (847.1 MiB to 848.1 MiB) | 2,862.3 MiB (2,861.9 MiB to 2,863.1 MiB) |
| Neo4j process resident memory | 1,181.5 MiB (1,173.9 MiB to 1,192.6 MiB) | 1,243.4 MiB (1,241.3 MiB to 1,243.5 MiB) | 1,228.2 MiB (1,227.9 MiB to 1,274.2 MiB) |
| page cache in use (usage ratio x size) | 4.9 MiB (4.9 MiB to 4.9 MiB) | 21.5 MiB (21.5 MiB to 21.5 MiB) | 79.1 MiB (79.1 MiB to 79.1 MiB) |
| graph view in memory (tracemalloc net) | 4.0 MiB | 38.8 MiB | 155.9 MiB |
| plant graph in memory (tracemalloc net) | 10.8 MiB | 103.0 MiB | 411.8 MiB |
| traced peak during both builds | 18.4 MiB | 173.5 MiB | 694.4 MiB |

- D100: the server's store.size.database metric is present in 1 of 3 repeats only
- D100: the server's store.size.database metric differs from the bytes on disk by more than 10% in 1 of 1 repeats: it lags, so the bytes on disk are the figure and the metric is secondary
- D4000: the server's store.size.database metric differs from the bytes on disk by more than 10% in 3 of 3 repeats: it lags, so the bytes on disk are the figure and the metric is secondary

## I2 - local compute per strategy and corpus

| Strategy | Corpus | Basis | DB server | Graph in memory | Questions | Median | p90 | Max | Sum | DB client | DB server time | Graph API | Other | Local share of latency | Token $/question |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cypher_db_only (cypher_rag_plant) | D100 | db_replay | yes | no | 180 | 0.0200 s | 0.0322 s | 0.1416 s | 3.38 s | 3.36 s | 3.01 s | 0.0000 s | 0.0194 s | 0.3% | $0.00039 |
| cypher_db_only (cypher_rag_plant) | D1000 | db_replay | yes | no | 180 | 0.0305 s | 0.0548 s | 0.2623 s | 5.93 s | 5.91 s | 4.69 s | 0.0000 s | 0.0210 s | 0.5% | $0.00040 |
| cypher (cypher_rag_plant) | D100 | replay | yes | no | 180 | 0.0043 s | 0.0061 s | 0.0652 s | 0.8566 s | 0.7533 s | 0.4340 s | 0.0000 s | 0.1033 s | 0.1% | $0.00039 |
| agent (graph_agent_low_steps) | D100 | replay | no | yes | 180 | 0.0006 s | 0.0089 s | 0.0310 s | 0.4969 s | 0.0000 s | 0.0000 s | 0.3995 s | 0.0974 s | 0.0% | $0.00051 |
| need (hierarchical_need_rules_plant) | D100 | old_run | no | yes | 180 | 0.0310 s | 0.0620 s | 0.4220 s | 6.50 s | - | - | - | - | 0.1% | $0.00261 |
| cypher (cypher_rag_plant) | D1000 | replay | yes | no | 180 | 0.0157 s | 0.0293 s | 0.1996 s | 3.14 s | 3.02 s | 1.98 s | 0.0000 s | 0.1183 s | 0.3% | $0.00040 |
| agent (graph_agent_low_steps) | D1000 | replay | no | yes | 180 | 0.0007 s | 0.0889 s | 0.3024 s | 4.49 s | 0.0000 s | 0.0000 s | 4.38 s | 0.1183 s | 0.2% | $0.00063 |
| need (hierarchical_need_rules_plant) | D1000 | old_run | no | yes | 180 | 0.0320 s | 0.3130 s | 1.26 s | 22.26 s | - | - | - | - | 0.2% | $0.00322 |

## I3 - growth

| Quantity | Corpora | From | To | Ratio |
|---|---|---|---|---|
| size: sheets | D100 to D1000 | 101 | 1,000 | x9.90 |
| size: nodes | D100 to D1000 | 3,867 | 37,124 | x9.60 |
| size: relationships | D100 to D1000 | 11,653 | 111,668 | x9.58 |
| size: properties | D100 to D1000 | 34,369 | 329,830 | x9.60 |
| ingest: generate | D100 to D1000 | 1.66 s | 16.10 s | x9.72 |
| ingest: split | D100 to D1000 | 0.0566 s | 1.58 s | x27.86 |
| ingest: localize | D100 to D1000 | 0.0251 s | 0.4267 s | x17.02 |
| ingest: resolve | D100 to D1000 | 0.0330 s | 0.6017 s | x18.21 |
| ingest: plan | D100 to D1000 | 0.1510 s | 1.40 s | x9.26 |
| ingest: load_schema | D100 to D1000 | 0.0863 s | 0.0712 s | x0.82 |
| ingest: load_nodes | D100 to D1000 | 0.3941 s | 1.88 s | x4.76 |
| ingest: load_relationships | D100 to D1000 | 0.5681 s | 3.69 s | x6.50 |
| ingest: load_verify | D100 to D1000 | 0.1427 s | 0.3255 s | x2.28 |
| ingest total (stages above) | D100 to D1000 | 3.11 s | 26.06 s | x8.39 |
| store on disk (data + indexes) | D100 to D1000 | 3.0 MiB | 19.4 MiB | x6.49 |
| transaction logs on disk (follow retention, not the corpus) | D100 to D1000 | 1.1 MiB | 10.7 MiB | x9.84 |
| page cache needed (derived: disk x 1.2, Neo4j manual) | D100 to D1000 | 3.6 MiB | 23.3 MiB | x6.49 |
| startup: rebuild | D100 to D1000 | 1.89 s | 19.55 s | x10.32 |
| startup: graph_view | D100 to D1000 | 0.0187 s | 0.5021 s | x26.82 |
| startup: tier_runs | D100 to D1000 | 0.0008 s | 0.0009 s | x1.07 |
| startup: schema_text | D100 to D1000 | 0.0001 s | 0.0001 s | x1.01 |
| startup: neo4j_open_check | D100 to D1000 | 0.0164 s | 0.0604 s | x3.69 |
| startup: item_graph | D100 to D1000 | 0.2060 s | 1.75 s | x8.50 |
| startup total | D100 to D1000 | 2.15 s | 22.11 s | x10.27 |
| startup without rebuild (total - rebuild) | D100 to D1000 | 0.2420 s | 2.32 s | x9.58 |
| ContextRAG prompt build | D100 to D1000 | 0.3352 s | 3.50 s | x10.43 |
| app process peak after imports | D100 to D1000 | 170.6 MiB | 170.3 MiB | x1.00 |
| app process peak at end of probe | D100 to D1000 | 245.4 MiB | 847.6 MiB | x3.45 |
| Neo4j process resident memory | D100 to D1000 | 1,181.5 MiB | 1,243.4 MiB | x1.05 |
| page cache in use (usage ratio x size) | D100 to D1000 | 4.9 MiB | 21.5 MiB | x4.41 |
| graph view in memory (tracemalloc net) | D100 to D1000 | 4.0 MiB | 38.8 MiB | x9.61 |
| plant graph in memory (tracemalloc net) | D100 to D1000 | 10.8 MiB | 103.0 MiB | x9.57 |
| traced peak during both builds | D100 to D1000 | 18.4 MiB | 173.5 MiB | x9.40 |
| size: sheets | D1000 to D4000 | 1,000 | 4,000 | x4.00 |
| size: nodes | D1000 to D4000 | 37,124 | 148,296 | x3.99 |
| size: relationships | D1000 to D4000 | 111,668 | 446,441 | x4.00 |
| size: properties | D1000 to D4000 | 329,830 | 1,318,348 | x4.00 |
| ingest: generate | D1000 to D4000 | 16.10 s | 68.74 s | x4.27 |
| ingest: split | D1000 to D4000 | 1.58 s | 16.95 s | x10.74 |
| ingest: localize | D1000 to D4000 | 0.4267 s | 2.15 s | x5.04 |
| ingest: resolve | D1000 to D4000 | 0.6017 s | 3.28 s | x5.46 |
| ingest: plan | D1000 to D4000 | 1.40 s | 5.53 s | x3.95 |
| ingest: load_schema | D1000 to D4000 | 0.0712 s | 0.1210 s | x1.70 |
| ingest: load_nodes | D1000 to D4000 | 1.88 s | 7.71 s | x4.11 |
| ingest: load_relationships | D1000 to D4000 | 3.69 s | 20.40 s | x5.53 |
| ingest: load_verify | D1000 to D4000 | 0.3255 s | 1.47 s | x4.53 |
| ingest total (stages above) | D1000 to D4000 | 26.06 s | 127.34 s | x4.89 |
| store on disk (data + indexes) | D1000 to D4000 | 19.4 MiB | 76.4 MiB | x3.93 |
| transaction logs on disk (follow retention, not the corpus) | D1000 to D4000 | 10.7 MiB | 46.2 MiB | x4.30 |
| page cache needed (derived: disk x 1.2, Neo4j manual) | D1000 to D4000 | 23.3 MiB | 91.6 MiB | x3.93 |
| startup: rebuild | D1000 to D4000 | 19.55 s | 93.90 s | x4.80 |
| startup: graph_view | D1000 to D4000 | 0.5021 s | 1.94 s | x3.87 |
| startup: tier_runs | D1000 to D4000 | 0.0009 s | 0.0008 s | x0.97 |
| startup: schema_text | D1000 to D4000 | 0.0001 s | 0.0001 s | x1.07 |
| startup: neo4j_open_check | D1000 to D4000 | 0.0604 s | 0.1720 s | x2.85 |
| startup: item_graph | D1000 to D4000 | 1.75 s | 8.04 s | x4.60 |
| startup total | D1000 to D4000 | 22.11 s | 104.09 s | x4.71 |
| startup without rebuild (total - rebuild) | D1000 to D4000 | 2.32 s | 10.16 s | x4.39 |
| ContextRAG prompt build | D1000 to D4000 | 3.50 s | 14.42 s | x4.12 |
| app process peak after imports | D1000 to D4000 | 170.3 MiB | 170.6 MiB | x1.00 |
| app process peak at end of probe | D1000 to D4000 | 847.6 MiB | 2,862.3 MiB | x3.38 |
| Neo4j process resident memory | D1000 to D4000 | 1,243.4 MiB | 1,228.2 MiB | x0.99 |
| page cache in use (usage ratio x size) | D1000 to D4000 | 21.5 MiB | 79.1 MiB | x3.68 |
| graph view in memory (tracemalloc net) | D1000 to D4000 | 38.8 MiB | 155.9 MiB | x4.02 |
| plant graph in memory (tracemalloc net) | D1000 to D4000 | 103.0 MiB | 411.8 MiB | x4.00 |
| traced peak during both builds | D1000 to D4000 | 173.5 MiB | 694.4 MiB | x4.00 |
| agent.local_median_s | D100 to D1000 | 0.0006 s | 0.0007 s | x1.22 |
| agent.local_p90_s | D100 to D1000 | 0.0089 s | 0.0889 s | x10.04 |
| agent.local_sum_s | D100 to D1000 | 0.4969 s | 4.49 s | x9.04 |
| agent.token_usd_per_question | D100 to D1000 | $0.00051 | $0.00063 | x1.23 |
| cypher.local_median_s | D100 to D1000 | 0.0043 s | 0.0157 s | x3.65 |
| cypher.local_p90_s | D100 to D1000 | 0.0061 s | 0.0293 s | x4.77 |
| cypher.local_sum_s | D100 to D1000 | 0.8566 s | 3.14 s | x3.67 |
| cypher.token_usd_per_question | D100 to D1000 | $0.00039 | $0.00040 | x1.03 |
| cypher_db_only.local_median_s | D100 to D1000 | 0.0200 s | 0.0305 s | x1.53 |
| cypher_db_only.local_p90_s | D100 to D1000 | 0.0322 s | 0.0548 s | x1.70 |
| cypher_db_only.local_sum_s | D100 to D1000 | 3.38 s | 5.93 s | x1.75 |
| cypher_db_only.token_usd_per_question | D100 to D1000 | $0.00039 | $0.00040 | x1.03 |
| need.local_median_s | D100 to D1000 | 0.0310 s | 0.0320 s | x1.03 |
| need.local_p90_s | D100 to D1000 | 0.0620 s | 0.3130 s | x5.05 |
| need.local_sum_s | D100 to D1000 | 6.50 s | 22.26 s | x3.42 |
| need.token_usd_per_question | D100 to D1000 | $0.00261 | $0.00322 | x1.24 |
