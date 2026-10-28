"""Shape bench: how long do recorded and generic Cypher queries really take, and do they finish?

The Cypher tier gives each query a time limit (a *timeout*: the database aborts the query when
it runs longer). The tuning design (`qa-tuning-v2.md` §4.2) must choose that limit and the row cap
(the most rows kept from a result) from measurements, not guesses. This module runs a list of
queries against a database *without calling any language model* and records, per query, how long
it took, how many rows came back and how it ended.

One run at the largest timeout answers every smaller one as well: a query that finished in 40 s
finishes under a 120 s limit and times out under a 30 s limit; a query that was aborted at the
largest limit was aborted at the smaller ones too. `verdict_at` derives the outcome per limit.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.cypher import CypherExecutionError, CypherSource, WriteClauseError

#: How one query ended. `timeout` and `memory` are the database aborting it; `error` is any other
#: refusal (syntax error, ...); `rejected` is our write-clause filter, before anything was sent;
#: `hung` is the server ignoring its own timeout (seen once: SHORTEST 1 on a 326-item route), so the
#: client gave up after the watchdog limit.
BenchOutcome = Literal["ok", "timeout", "memory", "error", "rejected", "hung"]

#: Seconds of grace past the query timeout before the client declares the server hung.
HANG_GRACE_S = 30.0


class BenchQuery(BaseModel):
    """One query to measure: a stable id, a group (where it came from) and the Cypher text."""

    model_config = ConfigDict(frozen=True)

    query_id: str
    group: str
    query: str


class BenchRow(BaseModel):
    """The measurement of one query at the bench's largest timeout."""

    model_config = ConfigDict(frozen=True)

    query_id: str
    group: str
    outcome: BenchOutcome
    seconds: float
    n_rows: int
    #: True when the result had more rows than the row cap (the rest were dropped).
    truncated: bool
    #: The database's message for a failed query, cut to 200 characters.
    error: str = ""


def classify_error(message: str) -> BenchOutcome:
    """Map the database's error text to `timeout`, `memory` or `error`."""
    if "TransactionTimedOut" in message:
        return "timeout"
    if "MemoryPool" in message or "OutOfMemory" in message:
        return "memory"
    return "error"


def measure_query(
    source: CypherSource,
    bench_query: BenchQuery,
    *,
    timeout_s: float,
    row_cap: int,
    clock: Callable[[], float] = time.perf_counter,
) -> BenchRow:
    """Run one query once and record its wall time, rows and outcome."""
    started = clock()
    outcome: BenchOutcome = "ok"
    n_rows, truncated, error = 0, False, ""
    try:
        result = source.run_cypher(bench_query.query, timeout_s, row_cap)
        n_rows, truncated = len(result.rows), result.truncated
    except WriteClauseError as refusal:
        outcome, error = "rejected", str(refusal)
    except CypherExecutionError as failure:
        outcome, error = classify_error(str(failure)), str(failure)
    return BenchRow(
        query_id=bench_query.query_id,
        group=bench_query.group,
        outcome=outcome,
        seconds=clock() - started,
        n_rows=n_rows,
        truncated=truncated,
        error=error[:200],
    )


def measure_guarded(
    source: CypherSource,
    bench_query: BenchQuery,
    *,
    timeout_s: float,
    row_cap: int,
    hang_after_s: float,
) -> BenchRow:
    """`measure_query` in a worker thread; a query still running after `hang_after_s` is `hung`.

    The worker is a daemon thread: if the server never answers, the caller closes the source's
    connection (see `run_bench`), which makes the blocked call raise and the thread end.
    """
    done: list[BenchRow] = []
    worker = threading.Thread(
        target=lambda: done.append(
            measure_query(source, bench_query, timeout_s=timeout_s, row_cap=row_cap)
        ),
        daemon=True,
    )
    worker.start()
    worker.join(hang_after_s)
    if done:
        return done[0]
    return BenchRow(
        query_id=bench_query.query_id,
        group=bench_query.group,
        outcome="hung",
        seconds=hang_after_s,
        n_rows=0,
        truncated=False,
        error=f"hung: server ignored the {timeout_s:g} s timeout for {hang_after_s:g} s",
    )


def _close_quietly(source: CypherSource) -> None:
    """Close the connection of a hung query without letting `close` hang the bench too."""
    closer = threading.Thread(target=source.close, daemon=True)
    closer.start()
    closer.join(10.0)


def run_bench(
    open_source: Callable[[], CypherSource],
    queries: Sequence[BenchQuery],
    *,
    timeout_s: float,
    row_cap: int,
    hang_after_s: float | None = None,
    on_row: Callable[[BenchRow], None] = lambda row: None,
) -> list[BenchRow]:
    """Measure the queries one after another; `on_row` sees each row as soon as it is done.

    After a `hung` query the connection is closed and `open_source` is called again, so one
    hung query cannot block the rest. The last source is closed before returning.
    """
    limit = timeout_s + HANG_GRACE_S if hang_after_s is None else hang_after_s
    source = open_source()
    rows: list[BenchRow] = []
    try:
        for bench_query in queries:
            row = measure_guarded(
                source, bench_query, timeout_s=timeout_s, row_cap=row_cap, hang_after_s=limit
            )
            on_row(row)
            rows.append(row)
            if row.outcome == "hung":
                _close_quietly(source)
                source = open_source()
    finally:
        source.close()
    return rows


def verdict_at(row: BenchRow, timeout_s: float) -> BenchOutcome:
    """What the row's query would have done under a (smaller or equal) timeout.

    Assumes `row` was measured at a timeout >= `timeout_s`; the caller passes the bench's own
    limits, so this holds.
    """
    if row.outcome == "ok" and row.seconds >= timeout_s:
        return "timeout"
    return row.outcome


def read_queries(path: Path) -> list[BenchQuery]:
    """Read a JSONL query file: one `{"query_id", "group", "query"}` object per line.

    Raises:
        ValueError: a line is not such an object.
    """
    queries: list[BenchQuery] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            queries.append(BenchQuery.model_validate_json(line))
        except ValueError as error:
            raise ValueError(
                f"expected a bench query on line {number} of {path}: {error}"
            ) from error
    return queries


def queries_from_run_rows(rows: Sequence[dict[str, object]], group: str) -> list[BenchQuery]:
    """The recorded queries of a stored Cypher run that were aborted by timeout or memory.

    `rows` are the parsed lines of the run's `answers.jsonl`; the trace keeps the generated
    query and the database's error text.
    """
    queries: list[BenchQuery] = []
    for row in rows:
        trace = row.get("trace")
        retrieval = trace.get("retrieval", {}) if isinstance(trace, dict) else {}
        error = str(retrieval.get("cypher_error", ""))
        if classify_error(error) not in ("timeout", "memory") or not retrieval.get("cypher"):
            continue
        queries.append(
            BenchQuery(query_id=str(row["question_id"]), group=group, query=retrieval["cypher"])
        )
    return queries


def read_run_rows(answers_path: Path) -> list[dict[str, object]]:
    """The parsed lines of a run's `answers.jsonl`."""
    lines = answers_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def render_table(rows: Sequence[BenchRow], timeouts: Sequence[float]) -> str:
    """A Markdown table: one line per query, its time, rows and the verdict at each timeout."""
    heads = " | ".join(f"@{t:g}s" for t in timeouts)
    lines = [
        f"| group | query | time s | rows | cut | {heads} | error |",
        "|---|---|---|---|---|" + "---|" * len(timeouts) + "---|",
    ]
    for row in rows:
        verdicts = " | ".join(verdict_at(row, t) for t in timeouts)
        lines.append(
            f"| {row.group} | {row.query_id} | {row.seconds:.1f} | {row.n_rows} | "
            f"{'yes' if row.truncated else ''} | {verdicts} | {row.error[:60]} |"
        )
    return "\n".join(lines)
