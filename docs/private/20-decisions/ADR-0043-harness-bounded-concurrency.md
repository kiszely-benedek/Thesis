---
adr: 0043
title: Run the harness's work items on a bounded thread pool (--concurrency N, default 1) with in-order commit of answers.jsonl and spend-cap reservations for calls in flight
status: accepted
date: 2026-10-03
supersedes: none — amends qa-system.md §11 ("sequentially") and the runner docstring
design: 40-design/plant-graph-first-and-effort-routing.md Part E
---

# ADR-0043 — Parallel model calls without losing replay, resume or the spend cap

## Context

PAID-02 answered 108 items one at a time; the main session reports about 50 minutes of wall time (not a row in
`_results.md`). Nearly all of it is waiting on HTTP: the runner calls `attempt` in a plain loop
(`harness/runner.py` `_fill_answers`). The guarantees that must survive are built in today: `answers.jsonl` is
byte-identical on replay, a resume skips finished rows, and the spend cap stops before money could pass it
(`spend_cap.py`). Three built facts constrain the change: the SQLite cache uses a default `sqlite3.connect`, which
refuses use from another thread (`llm/cache.py`); one `UsageMeter` holds one question's state and the retrieval sender
reads its `question_id` (`attempt.py`); and the scheduling-dependent fields `n_cached` and `spent_usd` are already
excluded from `answers.jsonl` (`qa/models.py`).

Production concurrency — many users querying one knowledge graph — is a separate concern: Neo4j serves concurrent
reads, and nothing here changes the store.

## Options considered

**A. Sequential (status quo).** Simplest; every paid step costs an hour of waiting per hundred items.

**B. Threads.** A `ThreadPoolExecutor` of N workers runs `attempt`; a single writer commits rows in work-item order.
I/O-bound work, so the GIL is not the limit. Needs a lock around the cache and the call log, one meter per item, and
reservations in the spend guard.

**C. asyncio.** The natural model for many HTTP calls, but the client, cache, senders and every strategy's call path
would become async — a rewrite of tested code for the same wall-clock gain.

**D. Processes.** Each process rebuilds the corpus (seconds to a minute at H1000), shares the SQLite file across
processes, and the spend cap becomes per process.

**E. Several harness runs at once by hand** (one per strategy). Needs no code; the cap is per run, so the total spend
is uncapped, and the user must coordinate run ids.

## Decision

**B.**
1. `--concurrency N`, default 1 (today's behaviour exactly), maximum 8. A paid run with N > 1 must pass
   `--cost-per-question-usd`, so the first reservations are not zero.
2. **Ordered commit.** Items keep their index in today's order (corpus, strategy, question, repeat). Workers return
   results to the writer, which appends only the next index in order (a reorder buffer). The provider-error retry pass
   keeps today's place: after the first pass, in the same order.
3. **Per-item state.** Each item gets its own `UsageMeter` and its own retrieval sender bound to that item's question
   id. Strategy caches built on first use (`RoutingGraphs`, the item graph, the tag index) are warmed once per corpus
   before the pool starts.
4. **Spend cap with calls in flight.** Under one lock: `reserve(expected)` before an item starts, where `expected` =
   max(dearest question seen, the estimate); refused if spent + all open reservations + expected would reach the cap.
   `check_before_call` counts spent + the other items' open reservations + the dearest call seen. At an item's end its
   reservation is released and its real spend added. A refusal stops new submissions; items in flight finish; the
   writer commits the in-order prefix; finished items beyond it are not written but their calls are cached, so a resume
   replays them free.
5. **Shared resources.** The SQLite cache opens with `check_same_thread=False` and serializes `get`/`put` behind a
   lock; `calls.jsonl` appends behind a lock (its line order may vary; it is a log, not part of the replay contract).
   Should: one in-flight call per cache key, so two items needing the same prompt pay once.
6. **Acceptance (offline, fake transport):** `answers.jsonl` byte-identical for N = 1 and N = 4, live and replay; a cap
   that trips with four items in flight writes an in-order prefix and a resume completes the identical file; projected
   spend counts open reservations; a provider error retried in the second pass lands where it lands today.

## Rationale

- Threads are the boring option for I/O-bound calls and touch the fewest tested files; the replay, resume and cap
  guarantees are kept by construction (ordered commit, cache-backed resume, reservations) rather than by hope.
- Default 1 means no existing run, test or replay changes unless the flag is typed.

## Consequences

- Throughput (estimate): with N workers and no provider rate limit, wall time falls toward 1/N of today's; the
  slowest item still bounds the tail (PAID-02 had query calls up to 142 s). OpenRouter's rate limits for these models
  are not verified; start at N = 4 and record the wall time.
- Overshoot bound, stated in the run summary: the cap can be passed only by what items in flight spend beyond their
  reservations.
- **Revisit if** provider errors (429) rise with N (then lower N, or add a token bucket); or a replay at N > 1 is ever
  not byte-identical to N = 1 (a bug: fix before any reported run).

**Accepted 2026-10-03 (user, in chat: "Elfogadom a dolgokat, mehet")** Accepted 2026-10-03 (user, in chat: "Elfogadom a dolgokat, mehet") with the main session's recommendations. Default concurrency 1; 4 for paid runs.
