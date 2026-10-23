---
component: infrastructure-cost measurement — one-time build, standing footprint, per-question local compute; zero-spend replays, an ingest store-size step, a startup/memory probe, an infra report
status: accepted (user, 2026-10-11)
related: [ADR-0051 (proposed); ADR-0015, ADR-0038, ADR-0043, ADR-0047, ADR-0048, ADR-0050; cascade-v2.md §1 R4; kg-construction.md §8; qa-system.md §10.1]
date: 2026-10-10
author: architect (Opus 5.5)
---

# Design — measuring infrastructure cost at D100 and D1000

## 0. Recommendation

| # | Item | Decision |
|---|---|---|
| R1 | What is measured | Three classes, physical units (ADR-0051 point 1): **one-time build** (ingest stages, Neo4j load, startup of the live cascade), **standing footprint** (store on disk, page cache used, Neo4j JVM resident memory, graph-structure bytes, app process peak), **per-question local compute** (database / graph API / other). |
| R2 | Per-question compute | Zero-spend **replays** of the source runs at `--concurrency 1`, `perf_counter` clock, two split timers; a replay counts only if its `answers.jsonl` is byte-identical to the source (ADR-0051 point 2). |
| R3 | Corpus-level quantities | `ingest` gains `--fresh-database` and `--neo4j-home` (store size after a checkpoint) and writes the machine record; a new `cascade infra-probe` times and sizes the live cascade's startup; memory in a separate process (ADR-0051 points 3–4). |
| R4 | Repeats | Ingest and probe **3 repeats** per corpus; report median and min–max. Replays once (a replay is already 180 questions). |
| R5 | Money | Derived only: a hand-filled `reference_price.json` with URL and access date; no file, no money column (ADR-0051 point 1). |
| R6 | Corpora | D100 and D1000 for everything; **D4000 for corpus-level quantities only** (no questions, no LLM), so growth has three points instead of two. |
| R7 | Cost | **$0 of OpenRouter.** About 2 coder days (INF-T1…T4), about 1 h of machine time. |

## 1. Evidence — what is captured today

All "computed" rows are an architect scratch computation over the stored files on 2026-10-10 (percentiles by linear
interpolation); the other rows are read directly from the cited file or command.

| # | Finding | Source |
|---|---|---|
| E1 | Ingest records per-stage wall time with `perf_counter`: D1000 generate 21.56 s, split 2.66, localize 0.33, resolve 0.83, check 1.49, plan 1.63, load_nodes 2.59, load_relationships 5.37, load_verify 0.60, load_total 8.59 (wipe 0.02). D100: generate 1.88, split 0.07, localize 0.03, resolve 0.15, plan 0.16, load_total 2.25 (of which wipe 0.51). | `data/runs/cv1/neo4jplant/{D100,D1000}/ingest.json` |
| E2 | The same D1000 config rebuilt by the harness took generate 36.68 s, split 3.39, localize 0.57, resolve 1.35, so single runs vary by up to ×1.7. | `runs/AGL3-D1000/corpora.json` vs E1 |
| E3 | Sizes: D100 101 sheets, 3,867 nodes, 11,653 relationships; D1000 1,000 sheets, 37,124 nodes, 111,668 relationships (plant profile). | E1 files, `counts` |
| E4 | `local_compute_s` = question wall time minus time inside model calls, clock `time.monotonic` (`qa/harness/attempt.py:179`, `usage_meter.py:40`). In the project venv (Python 3.12.10), `time.get_clock_info('monotonic')` is `GetTickCount64()`, resolution **0.015625 s**; `perf_counter` is `QueryPerformanceCounter()`, resolution 1e-07 s. | `.venv` interpreter |
| E5 | Recorded local compute (s), median / p90 / max / sum over 180, share of exact zeros. `AGL3-D100` 0.000 / 0.031 / 0.141 / 1.9, zeros 68 %; `AGL3-D1000` 0.000 / 0.239 / 1.048 / 14.3, zeros 65 %; `CYPL-D100` 0.078 / 0.125 / 0.625 / 13.9; `CYPL-D1000` 0.095 / 0.188 / 1.000 / 21.0; `DEV10-D100` (need_rules) 0.031 / 0.062 / 0.422 / 6.5; `DEV10-D1000` 0.032 / 0.313 / 1.265 / 22.3. | `runs/*/timings.jsonl` (computed) |
| E6 | Those runs used `--concurrency 4`; `run_config.json` does not record concurrency. | `data/runs/cv1/run_*.sh`; `RunConfig` |
| E7 | Local compute is not split: Cypher round-trips, plant-API tool calls and prompt building are one number. `Neo4jGraphView.run_cypher` already calls `result.consume()`, whose summary carries server-side `result_available_after` / `result_consumed_after` in ms (probe 2026-10-10: a count query on D1000 gave 19 ms / 1 ms). | `qa/neo4j_view.py:126–131`; read-only probe |
| E8 | Neo4j: Kernel 2026.09.0 enterprise, store format `block-block-1.1`; `server.memory.heap.initial_size=512m`, `heap.max_size=1G`, `pagecache.size=512m`. Directory sizes (`du -sh`): `data/databases/neo4j` 73 M, `data/transactions/neo4j` 256 M. Enterprise metrics are being written as CSV (187 files) and include `store.size.database` 75,921,884 B, `store.size.full` 338,022,879 B, `store.size.available_reserved` 27,533,248 B, `page_cache.usage_ratio` 0.139, `vm.heap.used`. `SHOW DATABASE … YIELD *` has no size column. | `%USERPROFILE%/.Neo4jDesktop2/Data/dbmss/dbms-056b4b53-…/{conf,metrics,data}`; `SHOW DATABASE` |
| E9 | The loader creates its constraint and three indexes `IF NOT EXISTS` before loading nodes, so index population happens during `load_nodes`. **"Index build" is not a separable stage**; on a fresh database, `load_schema` times creating the empty indexes. | `store/neo4j_plan.py:306–322`, `neo4j_loader.py` |
| E10 | Live startup (`cascade/live_ask.py:open_for_ask`) = `load_corpus_artifacts` (re-runs generate → split → localize → resolve from the seed) + `NetworkxGraphView` + `build_item_graph` (in `registry._build_agent`) + opening and checking Neo4j. The regeneration is a synthetic-benchmark artefact; a deployment would read a persisted graph instead. | code |
| E11 | Neo4j's manual: "First, estimate the total size of data and indexes, and then multiply with some factor, for example 20%, to allow for growth." | neo4j.com/docs/operations-manual/current/performance/memory-configuration/ (read 2026-10-10) |
| E12 | Measurement machine: ASUS Zenbook UM535QE, AMD Ryzen 9 5900HX (8 cores / 16 threads, 3,301 MHz max clock reported), 16,542,019,584 B RAM, WDC PC SN730 1 TB NVMe SSD, Windows 11 Pro. | `Get-CimInstance`, `Get-PhysicalDisk` |
| E13 | A harness run without `--allow-paid-calls` is cache-only (no network, stops at the first miss) and reproduces a finished run's `answers.jsonl` byte for byte. | `qa/harness/clients.py`, `runner.py` docstrings |
| E14 | ContextRAG prompt size without any model call: H100 1,649,451 chars, H1000 16,747,117 (PROMPT-04); ContextRAG is not a paid arm at plant scale (ADR-0038). | `30-experiments/_results.md` |

**Consequences for the design.** The ingest timings can be reused as they are (E1); they only need repeats (E2) and
a machine record. Per-question local compute must be re-measured (E4–E7). The data for this exists in the cache, so
re-measuring costs no money (E13). Store size must come from disk or from Neo4j's metrics, not from Cypher (E8), and
only on a fresh database (E8: reserved space).

## 2. Which part of the claim it serves

The claim: the best retrieval strategy depends on plant size. The task statement adds infrastructure cost as an axis
of "best". The strategies differ in **what kind** of infrastructure they need, and in **how** it grows with the plant:

| Strategy | Needs a database server | Needs the graph in process memory | Grows with the plant through |
|---|---|---|---|
| ContextRAG (baseline) | no | yes (to serialize it) | prompt size (E14): token cost, not infrastructure |
| `hierarchical_need_rules_plant` | no | yes (view + item graph) | in-process traversal time |
| `cypher_rag_plant` | **yes** | no (only the load plan for the schema text) | store size, page cache, query time |
| `graph_agent_low_steps` | no | yes (view + item graph) | in-process tool time, startup |
| `cascade_v3` (adopted, ADR-0050) | **yes** | **yes** | both of the above |

The report answers three questions for each strategy at D100 and D1000: what it costs once to build, what it
holds while it waits for questions, and what one question costs locally. The D1000/D100 ratio of each quantity
shows how that cost grows with the plant, which is the evidence the claim needs.

## 3. What is measured

| ID | Quantity | Class | Unit | How | Honesty note |
|---|---|---|---|---|---|
| Q1 | Ingest stage times: generate†, split†, localize, resolve, plan, load_schema, load_nodes, load_relationships, load_verify | one-time | s | existing `stage_seconds`, 3 repeats | † synthetic-only stages: a real deployment imports Proteus files instead (`import` stage). **There is no digitize stage** (ADR-0008). `load_wipe` is excluded from the load total because it depends on the previous corpus. Index build is inside `load_nodes` (E9). |
| Q2 | Store on disk | standing | bytes | after `CALL db.checkpoint()`: recursive size of `<neo4j-home>/data/databases/<db>`; also `store.size.database` from the metrics CSV when present | fresh database (ADR-0051 point 4); transaction logs reported separately, because their size follows the retention policy, not the corpus |
| Q3 | Logical size | standing | count | nodes, relationships, properties (`sum(size(keys(n)))` over nodes and over relationships) | machine-independent; the thesis's primary size axis |
| Q4 | Neo4j page cache needed | standing | bytes | **derived**: (Q2 data + indexes) × 1.2 per the Neo4j manual (E11) | labelled "derived from the manual's rule", not measured |
| Q5 | Neo4j page cache used after the Cypher replay | standing | bytes | `page_cache.usage_ratio` × `server.memory.pagecache.size` from metrics and settings, read after the replay | enterprise metrics only; `null` if the metrics directory is absent |
| Q6 | Neo4j JVM resident memory | standing | bytes | `psutil` RSS of the Neo4j process, after the replay | mostly set by the configured heap and page cache (E8), so reported together with the configuration, never as "required" |
| Q7 | Graph structures in process memory | standing | bytes | `tracemalloc` net bytes retained after building `NetworkxGraphView` and then `ItemGraph`; peak during the build | memory-only process (ADR-0051 point 3); comparable with SMOKE-01/02 |
| Q8 | App process peak memory | standing | bytes | `psutil` `peak_wset` (Windows) / `ru_maxrss` (POSIX) at the end of the probe | includes interpreter and libraries; reported next to a baseline taken after imports, before the corpus |
| Q9 | Startup time of the live cascade | one-time | s | probe stages: rebuild† (generate…resolve), view build, item-graph build, Neo4j open + `check_store`, schema text | † regeneration is a benchmark artefact (E10); startup is reported with and without it |
| Q10 | Per-question local compute | per question | s | replay `timings.jsonl`: `local_compute_s` (perf_counter), split into `db_client_s`, `db_server_s`, `graph_api_s`, `other_s` = local − db_client − graph_api | concurrency 1; byte-identical replay (R2) |
| Q11 | Local compute share of latency | per question | % | Q10 / (recorded LLM latency + Q10), per strategy and for `cascade_v3` through `Decision.tiers_tried` | shows whether infrastructure or the model dominates the wait |
| Q12 | ContextRAG prompt build | per question | s, chars | time `ContextRag` retrieval + prompt rendering without a call (the PROMPT-04 method), 3 repeats | question-independent: the whole graph is serialized every time |
| Q13 | Money (optional) | derived | USD | standing: reference instance $/h; marginal: $/h × Q10 / 3600 | only with `reference_price.json` (§4.5) |

**Not measured, and why.** Energy use, because a laptop has no meter and an estimate would be an invented number.
GPU, because none is used. Network, because everything is local apart from the model API, which is counted under
token cost. Index build as its own stage (E9).

## 4. How

### 4.1 Per-question local compute — zero-spend replays

1. **Clock.** In `qa/harness/attempt.py` (the question's wall time) and `qa/harness/usage_meter.py` (time inside
   calls), `time.monotonic` becomes `time.perf_counter`. Deadline decisions use *recorded* latencies, not the clock
   (`usage_meter.py` docstring), so replays reach the same decisions and stay byte-identical.
   `llm/client.py` keeps its clock: model latencies are seconds, and changing it would not change cached values anyway.
2. **Split timers.** A new module `qa/local_timer.py` holds a per-question `LocalTimer` in a `ContextVar`, following
   the `_ACTIVE_METER` pattern in `attempt.py`. Callers write `with local_timer("db"):`. With no active timer it
   does nothing, so tests and the demo are unaffected.
   - `Neo4jGraphView.run_cypher` times the session block as `db_client` and adds the summary's
     `result_available_after + result_consumed_after` (ms → s) as `db_server`.
   - `plant_api.tool_registry.call_tool` (agent tools) and `agent.seed.run_program` / the need strategies' program
     execution are timed as `graph_api`.
3. **Where the numbers go.** Only into `timings.jsonl`, never `answers.jsonl` or the trace, so byte identity holds.
   `TimingRow` gains optional fields (§5). Rows written before this change still parse.
4. **Run record.** Each harness invocation appends one `RunEnvironment` line to `<run>/environment.jsonl`: commit,
   dirty flag, machine, clock, concurrency (§5). `RunConfig` is not changed, so frozen configs and their hashes
   stay as they are.
5. **Replays.** For each source run, a new run id `INF-<source>` with the source's arguments taken from its
   `run_config.json` (strategy, params, pin, questions root, corpora root, deadline), the same cache file, no
   `--allow-paid-calls`, and `--concurrency 1`. Then `cmp` of the two `answers.jsonl` files. If they differ, that
   replay is not used (ADR-0051 consequences). A miss stops the replay at no cost.
6. **Source runs:** `CYPL-D100`, `CYPL-D1000` (Cypher tier), `AGL3-D100`, `AGL3-D1000` (agent tier; together they
   are `cascade_v3`), `DEV10-D100`, `DEV10-D1000` (need_rules). DEV10 was run at commit `767329e`, so code drift
   may make it miss; it is tried last, and if it misses its row is shown with the old timings, marked
   "quantised, concurrency 4".
7. **Cascade.** `python -m plantgraph.qa.cascade report` is run once more with the `INF-*` run directories as tier
   sources. Accuracy and cost come out identical because the answers are identical; latency now includes correct
   local compute.

### 4.2 One-time build and store footprint — ingest

`python -m plantgraph.ingest synthetic --headline --target-sheets N --seed 1 --store-profile plant --corpus-id ID`
gains two flags:

- `--fresh-database`: before loading, run `CREATE OR REPLACE DATABASE <db> WAIT` on the `system` database. If
  the server refuses (Community edition, or no admin rights), exit with a message that names the fallback
  (`wipe_all_neo4j.py` and reporting the reserved space). Never silently fall back.
- `--neo4j-home PATH`: after `load_verify`, run `CALL db.checkpoint()`, then measure Q2 (directory sizes of
  `data/databases/<db>` and `data/transactions/<db>`), Q3 (three count queries) and, if
  `PATH/metrics/neo4j.database.<db>.store.size.database.csv` exists, the last row of the store-size metrics.

`IngestResult` gains `environment: RunEnvironment | None` and `store_footprint: StoreFootprint | None`. Both are
optional, so earlier `ingest.json` files still validate. Repeats are separate invocations into
`data/runs/cv1/infra/ingest/<ID>/rep<k>/ingest.json`.

### 4.3 Startup and memory — `cascade infra-probe`

`python -m plantgraph.qa.cascade infra-probe --corpus ID --corpora-root R --policy cascade_v3 --run cypher=DIR
--run agent=DIR [--memory] [--neo4j-home PATH] --out FILE`

- **Timing mode** (default): replicate `open_for_ask` stage by stage with `perf_counter`: rebuild (and the
  rebuild's own `stage_seconds`, so the regeneration share is visible), `NetworkxGraphView`, `build_item_graph`,
  Neo4j open + `check_store`, `build_schema_text`. Also ContextRAG prompt build (Q12). Then Q8 (process peak, plus a
  baseline taken after imports) and, with `--neo4j-home`, Q5/Q6 read from metrics and `psutil`. **No model call:**
  the cascade is opened replay-only and never asked a question.
- **Memory mode** (`--memory`, a separate process): `tracemalloc.start()` after the rebuild, then build the view,
  snapshot, build the item graph, snapshot. Reports net retained bytes for each and the traced peak (Q7). No timings
  are reported in this mode (ADR-0051 point 3).
- The probe refuses to start if Neo4j does not hold `ID` (same `check_store`), so it cannot size the wrong corpus.

Reusing `open_live_cascade` itself would time the whole thing as one block. The probe therefore calls the same
public builder functions in the same order. A unit test pins that order to `open_for_ask` (§9).

### 4.4 Report — `cascade infra-report`

`python -m plantgraph.qa.cascade infra-report --ingest-root data/runs/cv1/infra/ingest --probe-root
data/runs/cv1/infra/probe --runs-root data/runs/cv1/runs --run cypher=INF-CYPL-{c} --run agent=INF-AGL3-{c}
--run need=INF-DEV10-{c} [--price-json data/runs/cv1/infra/reference_price.json] --out data/runs/cv1/infra/report.md`

Pure function `build_infra_report(inputs) -> InfraReport`, plus a renderer to Markdown, following the
`report.py` / `report_render.py` split already used by the cascade. Tables (no numbers here; they come from the runs):

- **I1 — corpus footprint** (rows D100, D1000, D4000; ratio columns): sheets, nodes, relationships, properties; ingest
  stages (median, min–max); store data bytes; transaction-log bytes; page cache needed (derived) / used; graph
  structures bytes (view, item graph); process peak; startup with and without regeneration.
- **I2 — per strategy × corpus**: needs DB / needs in-memory graph; local compute median / p90 / max / sum over the
  180, split db / graph_api / other; local share of latency; next to it the token $/question from the cascade
  report (not recomputed).
- **I3 — growth**: D1000 ÷ D100 for every I1 and I2 quantity, and the size ratio of the corpora (nodes) for comparison.
- **I4 — money** (only with a price file): standing $/h of the reference instance chosen in §4.5, and marginal
  $/question = $/h × local median / 3600, shown next to token $/question.

### 4.5 Money

`data/runs/cv1/infra/reference_price.json` is filled in by hand from one public on-demand price page, never by code:
`{provider, region, instance, vcpu, ram_gib, usd_per_hour, url, accessed}`. The instance is the smallest
general-purpose one whose RAM covers the measured need: Q6 (Neo4j) + Q8 (app peak) for `cascade_v3`. **Recommended
reference:** AWS EC2 on-demand, `eu-central-1` (Frankfurt), the most widely recognised list. The thesis states that
the marginal figure assumes one question at a time per instance, which is an upper bound. Standing cost per
question depends on query volume, which this work does not measure. It is shown only as the formula
`$/h ÷ questions per hour`, never as a single number.

## 5. Data model (Pydantic)

| Model | File | Fields |
|---|---|---|
| `TimingRow` (extended) | `qa/harness/usage_meter.py` | existing + `clock: Literal["monotonic","perf_counter"] = "monotonic"`, `wall_s: float \| None = None`, `db_client_s: float = 0.0`, `db_server_s: float = 0.0`, `n_db_queries: int = 0`, `graph_api_s: float = 0.0`, `n_graph_api_calls: int = 0` |
| `LocalTimer` (dataclass, not Pydantic: hot path) | `qa/local_timer.py` | `seconds: dict[str, float]`, `calls: dict[str, int]`; `add(kind, s)`; `local_timer(kind)` context manager; `activate()` returns a token |
| `MachineInfo` | `infra/environment.py` | `cpu_name`, `physical_cores`, `logical_cores`, `ram_bytes`, `os`, `python_version`, `power_plugged: bool \| None` |
| `RunEnvironment` | `infra/environment.py` | `git_commit`, `git_dirty`, `machine: MachineInfo`, `clock: str`, `clock_resolution_s: float`, `concurrency: int \| None`, `neo4j_version: str \| None`, `neo4j_memory_settings: dict[str, str]`, `recorded_at: datetime` |
| `StoreFootprint` | `infra/store_size.py` | `database: str`, `fresh_database: bool`, `data_bytes`, `tx_log_bytes`, `metrics_store_bytes: int \| None`, `metrics_reserved_bytes: int \| None`, `n_nodes`, `n_relationships`, `n_properties` |
| `StartupProbe` | `infra/probe_models.py` | `corpus_id`, `environment`, `stage_seconds: dict[str, float]`, `rebuild_stage_seconds: dict[str, float]`, `context_rag_build_s: float \| None`, `context_rag_chars: int \| None`, `process_baseline_bytes`, `process_peak_bytes`, `neo4j_rss_bytes: int \| None`, `page_cache_used_bytes: int \| None` |
| `MemoryProbe` | `infra/probe_models.py` | `corpus_id`, `environment`, `view_net_bytes`, `item_graph_net_bytes`, `traced_peak_bytes` |
| `InfraReport` and row models | `infra/report_models.py` | `CorpusFootprintRow`, `StrategyComputeRow`, `GrowthRow`, `MoneyRow \| None`, plus `reference_price: ReferencePrice \| None` |

New package `src/plantgraph/infra/` holds the machine record, store sizing and probe and report models. The probe
and report CLIs are subcommands of the existing `python -m plantgraph.qa.cascade` (no new entry point).
`psutil` is added to `[project] dependencies`.

## 6. Code changes, file by file

| File | Change |
|---|---|
| `qa/harness/attempt.py` | `perf_counter`; activate a `LocalTimer` per question next to the meter; copy its totals into `TimingRow` |
| `qa/harness/usage_meter.py` | default clock `perf_counter`; `TimingRow` fields (§5) |
| `qa/local_timer.py` (new) | `LocalTimer`, `local_timer(kind)`, `active_local_timer()` |
| `qa/neo4j_view.py` | `run_cypher`: `db_client` timing and `db_server` from the summary |
| `qa/plant_api/tool_registry.py`, `qa/agent/seed.py`, `qa/strategies/hierarchical_need.py` | wrap program/tool execution in `local_timer("graph_api")` |
| `qa/harness/runner.py` or `cli.py` | append `RunEnvironment` (with concurrency) to `environment.jsonl` |
| `infra/environment.py` (new) | `collect_machine_info()`, `collect_run_environment(...)`; CPU name from `winreg` on Windows, `/proc/cpuinfo` elsewhere; Neo4j settings via `SHOW SETTINGS YIELD name, value WHERE name STARTS WITH 'server.memory'` |
| `infra/store_size.py` (new) | `directory_bytes(path)`, `read_last_metric(csv)`, `measure_store(settings, neo4j_home) -> StoreFootprint` |
| `store/neo4j_loader.py` | `recreate_database(settings)` (the `CREATE OR REPLACE` call) and `checkpoint(settings)` |
| `ingest/__main__.py`, `ingest/pipeline.py`, `ingest/models.py` | flags `--fresh-database`, `--neo4j-home`; optional `environment`, `store_footprint` |
| `qa/cascade/cli.py` | subcommands `infra-probe`, `infra-report` |
| `qa/cascade/infra_probe.py`, `infra/probe_models.py` (new) | timing and memory modes (§4.3) |
| `infra/report.py`, `infra/report_models.py`, `infra/report_render.py` (new) | §4.4 |
| `pyproject.toml` | `psutil` |

## 7. Run plan (no paid calls)

Order matters because only one corpus may be in Neo4j at a time. No `pytest` may run during these steps:
integration tests write to Neo4j, and `--fresh-database` would destroy their fixtures and vice versa. Laptop plugged
in, same Windows power mode throughout, no other heavy process. The `power_plugged` field records the first two.

1. **Spike (5 min):** `CREATE OR REPLACE DATABASE neo4j WAIT` on this DBMS through `--fresh-database` with D100.
   If refused → fallback (ADR-0051 point 4 A), and record that in the run note.
2. **D100:** ingest ×3 with `--fresh-database --neo4j-home …` into `infra/ingest/D100/rep{1,2,3}`. The last one
   stays loaded. Replays `INF-CYPL-D100`, `INF-AGL3-D100`, `INF-DEV10-D100` at `--concurrency 1` + `cmp`. Then
   `infra-probe` ×3 (timing, with `--neo4j-home`, after the Cypher replay so Q5 reflects the questions) and
   `infra-probe --memory` ×1. The memory figure is deterministic up to allocator noise, so the repeat count is an
   open question (§12 Q4).
3. **D1000:** the same.
4. **D4000** (corpus-level only): ingest ×3, `infra-probe` ×3, `--memory` ×1; no replays, because there are no
   D4000 questions.
5. **Restore:** ingest D1000 normally, so the demo finds the corpus it expects (memory note: one plant in Neo4j).
6. `cascade report` with the `INF-*` tier runs; `infra-report`.

Machine-time estimate: built from E1/E2/E5 and ADR-0050's row counts, not measured. D1000 ingest is about
45–60 s per repeat. A replay is roughly the sum of local compute plus cache reads, so minutes per run. D4000 ingest
is an extrapolation from SMOKE-02 (49.42 s at 4,015 sheets, budget 4) and must be checked on the first repeat.
Together, under an hour.

## 8. How the measurement reports its own accuracy

| Check | Pass rule | Where it shows |
|---|---|---|
| M1 Same computation | replay `answers.jsonl` byte-identical to its source | `infra-report` refuses a run without a recorded `cmp` result, which the run script writes to `INF-*/replay_check.txt` |
| M2 Clock | every infra `TimingRow` has `clock = "perf_counter"`; `environment.clock_resolution_s` ≤ 1e-6 | report header |
| M3 Parts add up | per row: `db_client_s + graph_api_s ≤ local_compute_s` (+1 ms tolerance for timer overhead); `db_server_s ≤ db_client_s` | count of violations in the report; expected 0 |
| M4 Repeat spread | for each ingest and probe quantity: median, min, max, and max/min | I1; a spread above ×1.5 is flagged in the report, not hidden (E2 shows ×1.7 is possible) |
| M5 Right corpus, right size | the existing `load_verify` and `check_store` counts equal the load plan; Q3 node and relationship counts equal `IngestCounts` | report header |
| M6 Two size sources | directory bytes and `store.size.database` both shown | I1 |
| M7 No spend | every `INF-*` run's `spent_usd` sums to 0 and the run config has `allow_paid_calls = false` | report header |

## 9. Tests (no database unless stated)

- `LocalTimer`: nested and absent timers; a fake clock gives exact sums; no active timer means a no-op.
- `TimingRow`: an old `timings.jsonl` line parses with `clock = "monotonic"` and zero splits; a new line round-trips.
- Replay byte identity with the timer active: a toy harness run, live-with-fake-client then replay. `answers.jsonl` is
  identical, `timings.jsonl` is not compared.
- `directory_bytes` on a `tmp_path` tree; `read_last_metric` on a fixture CSV (header `t,value`, as in E8).
- `collect_machine_info` with monkeypatched sources; Windows and POSIX branches.
- `infra-probe` stage order equals `open_for_ask`'s builder order (a call-recording fake).
- `build_infra_report` on hand-made inputs; golden Markdown; M3 violation counted; a missing price file means no I4.
- **Not tested automatically:** `recreate_database` and `checkpoint` against the real server. An integration test
  would replace the database the user's corpus lives in. They are checked by the §7 spike instead, and
  `recreate_database` is unit-tested against a recording fake session only.

## 10. Coder tasks (Sonnet, sequential)

| Task | Scope | Files | Size |
|---|---|---|---|
| INF-T1 | Clock fix, `LocalTimer`, split timers, `TimingRow` fields, `environment.jsonl`, `infra/environment.py` | §6 rows 1–7 | M (½–¾ day) |
| INF-T2 | Ingest `--fresh-database`, `--neo4j-home`, checkpoint, `StoreFootprint` | `store/neo4j_loader.py`, `infra/store_size.py`, `ingest/*` | M (½ day) |
| INF-T3 | `cascade infra-probe` timing and memory modes, `psutil` | `qa/cascade/infra_probe.py`, `infra/probe_models.py`, `cli.py`, `pyproject.toml` | M (½ day) |
| INF-T4 | `cascade infra-report` + run script `data/runs/cv1/run_infra.sh` (§7, including `cmp` into `replay_check.txt`) | `infra/report*.py`, script | M (½ day) |

Total about 2 coder days. Each task is its own commit and test run. INF-T1 must land first, because the replays
depend on it.

## 11. Out of scope

Deploying anything to a cloud. Energy measurement. Tuning Neo4j memory settings (the Desktop defaults are measured
as they are and reported). Persisting the resolved graph to remove the regeneration from startup: that is a system
change, not a measurement (§12 Q3). Re-measuring runs older than the adopted policy's sources, other than DEV10.

## 12. Open questions

1. **Money column — keep it, and with which price list?** Recommendation: keep it, with AWS EC2 on-demand Frankfurt,
   filled in by hand with URL and date. Alternative: no money at all (I4 dropped). Only the user can decide whether
   the professor expects a currency figure.
2. **D4000 for corpus-level quantities?** Recommendation: yes. It costs about 15 minutes of machine time and gives
   growth three points. ADR-0015 already names ~4,000 as optional.
3. **Startup without regeneration.** The agent tier's startup is dominated by regenerating the synthetic plant (E1,
   E10). The report shows startup with and without it. Should a "load from a saved graph" path be built so the
   second figure is measured rather than subtracted? Recommendation: no, subtraction of measured stages is honest
   and costs nothing. Revisit only if the professor asks.
4. **Memory-probe repeats.** One `--memory` run per corpus is proposed (allocations are deterministic for a fixed
   seed apart from small allocator noise). Confirm, or ask for 3.
5. **H100/H1000.** Corpus-level infrastructure numbers read no gold and no answers, so they can be measured on the
   sealed corpora at any time. Per-question local compute comes free with the sealed test run, once INF-T1 has
   landed before that run. Recommendation: land INF-T1 before the sealed run.

### Answers (user, 2026-10-11)

All five accepted as recommended: (1) keep the money column, AWS EC2 on-demand Frankfurt, hand-filled with URL and
access date; (2) D4000 for corpus-level quantities; (3) startup without regeneration by subtracting the measured
stage, no saved-graph path; (4) one memory probe per corpus; (5) INF-T1 lands before the sealed H100/H1000 run.
