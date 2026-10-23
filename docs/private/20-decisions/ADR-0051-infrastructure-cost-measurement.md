---
adr: 0051
title: Measure infrastructure cost as physical resources — one-time build, standing footprint, per-question local compute — from zero-spend replays and a corpus-level probe; translate to money only through a cited reference price
status: accepted (user, 2026-10-11) — all five open questions of the design note answered as recommended
date: 2026-10-10
supersedes: none
design: 40-design/infra-cost.md
---

# ADR-0051 — How infrastructure cost is measured and reported

## Context

The official task statement (feladatkiírás, 2026-10-10, deliverable 5) asks for evaluation at ~100 and ~1,000
sheets on accuracy, **infrastructure and token cost**, and latency, and for an analysis of how the optimal
retrieval strategy changes with plant size. Accuracy, token cost and latency are measured per question by the
harness and aggregated by the cascade report. Infrastructure cost is not measured, and what the repo records today
cannot be reported as it stands (design `infra-cost.md` §1, computed 2026-10-10):

- `timings.jsonl`'s `local_compute_s` is taken with `time.monotonic`, which on this machine's Python 3.12.10 is
  `GetTickCount64()` with a resolution of **0.015625 s**. In the agent runs 65–68 % of the values are exactly 0
  (`AGL3-D100`, `AGL3-D1000`), so the median is 0.000 s — an artefact of the clock, not a measurement.
- The runs were made at `--concurrency 4` (`run_agent_luna_r3.sh`, `run_cypher_luna.sh`); concurrency is not
  recorded in `run_config.json`, and four threads share one GIL, so per-question wall time includes waiting.
- Local compute is one number: Neo4j time, plant-API time and prompt building are not separated.
- Ingest timings are single runs: the same D1000 config took 21.56 s to generate in `neo4jplant/D1000/ingest.json`
  and 36.68 s when rebuilt in `runs/AGL3-D1000/corpora.json` (×1.7).
- Nothing records store size, memory, startup time or the machine.
- The Neo4j store is reused across wipe/load cycles: its metrics report 27,533,248 bytes of reserved free space
  (`store.size.available_reserved`) next to 75,921,884 bytes of store (`store.size.database`). A size read after a
  wipe-and-reload includes space left behind by an earlier corpus.

Four choices have real alternatives.

## Options considered

### Point 1 — What "infrastructure cost" is reported as

**A. Money only (full TCO).** Deploy each strategy on a cloud instance and read the bill. Directly comparable with
token cost, but violates "single developer machine", costs real money, and the bill depends on how long the
machine was left on rather than on the strategy.
**B. Physical quantities as the primary result, money derived from them only through a cited reference price.**
Three classes: one-time build (ingest stages, load, startup), standing footprint (store on disk, RAM of the
in-memory graph, process peak memory, Neo4j page cache used), per-question local compute (split into database,
graph-API and other). A money column is added only when a public price list can be cited with URL and access date;
otherwise it is left out.
**C. Physical quantities only.** Most honest, but leaves the reader unable to set infrastructure against token cost,
which is the comparison the task statement implies.

### Point 2 — How per-question local compute is measured

**A. Reuse the stored `timings.jsonl`.** Free, but quantised to 15.6 ms, contaminated by concurrency 4, not split.
**B. Replay the stored runs at zero spend.** Same harness, cache-only client (already supported: no `--allow-paid-calls`
means no network and a stop at the first cache miss), `--concurrency 1`, `time.perf_counter` instead of
`time.monotonic`, and two new split timers (database, graph API). The replay must reproduce the source run's
`answers.jsonl` byte for byte, which proves the same computation was timed.
**C. A separate micro-benchmark.** Extract every Cypher query and tool call from the traces and re-execute them
in isolation. Clean attribution, but a parallel tool that skips the glue code (prompt building, parsing, rendering),
and its numbers would not be the ones the cascade report puts into latency.

### Point 3 — How memory is measured

**A. `tracemalloc` only** (as `benchmark/scale_smoke.py` already does). No new dependency, deterministic, but it
counts Python allocations only and distorts timing 2.9–9.1× (measured 2026-09-20, `scale_smoke.py` docstring).
**B. Process peak working set / RSS only**, via `psutil`. What a deployment must provision, cross-platform, but it
includes the interpreter and every imported library, so it does not isolate the graph.
**C. Both, in separate processes.** `tracemalloc` gives the net bytes retained by the graph structures
(view + item graph); `psutil` gives the process peak and the Neo4j JVM's resident memory. Adds `psutil`
(BSD-3-Clause) as a dependency. (A ctypes call to `GetProcessMemoryInfo` would avoid the dependency but is
Windows-only code that a reader has to trust.)

### Point 4 — How the Neo4j store is sized

**A. Read the size after the usual wipe-and-reload.** No change, but it includes space reserved by earlier corpora,
so D100's size would depend on what was loaded before it.
**B. Recreate the database before each measured load** (`CREATE OR REPLACE DATABASE neo4j WAIT`, enterprise
edition, which this DBMS is), checkpoint after the load (`CALL db.checkpoint()`), then read the size of the database
directory and Neo4j's own `store.size.database` metric. The user's "one corpus in Neo4j" rule holds: it is still
one database holding one corpus.
**C. Compact a copy offline** (`neo4j-admin database copy`). Gives a compacted size, but needs the DBMS stopped
and measures a store nobody queries.

## Decision

1. **Point 1 → B.** Physical quantities in three classes are the result. Money is a derived column, computed from
   one cited public on-demand price list. Without a citation there is no money column.
2. **Point 2 → B.** Zero-spend replays at concurrency 1 with `perf_counter` and database/graph-API split timers.
   A replay whose `answers.jsonl` is not byte-identical to its source is not reported.
3. **Point 3 → C.** `tracemalloc` for the graph structures in a memory-only process; `psutil` for process peaks.
   Timing and memory are never measured in the same process.
4. **Point 4 → B**, with **A as the declared fallback** if replacing the default database is refused. In that case
   the reserved-space metric is reported next to the size.

## Rationale

- The thesis claim is that the best strategy depends on plant size. Infrastructure cost can only support it if it
  is broken down by strategy and measured at each size. The three classes do that. The strategies differ in
  *which* resources they need: Cypher needs a database server, the agent needs the graph in process memory,
  ContextRAG needs neither but a prompt that grows with the plant. Money alone would hide that difference.
- Point 2 B is the only option that costs $0, reuses the existing harness and report code, and comes with a proof
  (byte identity) that the measured computation is the evaluated one.
- Point 3 C follows the project's own finding that `tracemalloc` distorts timing, and keeps the SMOKE-01/02 memory
  rows comparable (same method).
- Point 4 B makes the store size a property of the corpus, not of the machine's history.

## Consequences

- Easy: every infrastructure number is reproducible from a commit, a seed, a run id and `environment.json`.
  The cascade report gets correct local compute just by being pointed at the replay runs.
- Costs: one new dependency (`psutil`); about two coder days (four tasks, design §10); about an hour of machine
  time; **no paid calls**.
- Limitation stated in the thesis: one laptop (AMD Ryzen 9 5900HX, 16 GB, NVMe SSD, Windows 11 Pro).
  Absolute times do not transfer to other machines; the ratios between D100 and D1000, and between strategies,
  are the result.
- Runs made before this ADR keep their `timings.jsonl`. Old rows are marked `clock = "monotonic"` and are not
  used for infrastructure figures.
- Revisit if a replay cannot reproduce a source run (code drift since the run). That run is then re-measured on a
  `git worktree` at its recorded commit, or reported only with the quantised timings and the caveat.
