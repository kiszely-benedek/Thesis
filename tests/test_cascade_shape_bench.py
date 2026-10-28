"""The shape bench: error classes, timeout verdicts, recorded-query extraction, generic shapes."""

from __future__ import annotations

import threading

import pytest

from plantgraph.qa.cascade.shape_bench import (
    BenchQuery,
    BenchRow,
    classify_error,
    measure_guarded,
    measure_query,
    queries_from_run_rows,
    render_table,
    run_bench,
    verdict_at,
)
from plantgraph.qa.cascade.shape_queries import generic_shapes, set_shapes
from plantgraph.qa.cypher import CypherExecutionError, CypherResult, WriteClauseError

_TIMEOUT = "Neo.ClientError.Transaction.TransactionTimedOutClientConfiguration: The transaction"
_MEMORY = "Neo.TransientError.General.MemoryPoolOutOfMemoryError: limit"


class _Source:
    def close(self) -> None:
        pass

    def __init__(self, error: Exception | None = None, n_rows: int = 2) -> None:
        self._error, self._n_rows = error, n_rows

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        if self._error:
            raise self._error
        rows = [{"tag": str(i)} for i in range(min(self._n_rows, row_cap))]
        return CypherResult(rows=rows, truncated=self._n_rows > row_cap)


def _row(outcome: str, seconds: float) -> BenchRow:
    return BenchRow(
        query_id="q",
        group="g",
        outcome=outcome,
        seconds=seconds,
        n_rows=0,
        truncated=False,  # type: ignore[arg-type]
    )


def test_error_text_is_sorted_into_timeout_memory_or_other() -> None:
    assert classify_error(_TIMEOUT) == "timeout"
    assert classify_error(_MEMORY) == "memory"
    assert classify_error("Neo.ClientError.Statement.SyntaxError: x") == "error"


def test_a_finished_query_records_rows_and_the_cut_flag() -> None:
    query = BenchQuery(query_id="a", group="g", query="MATCH (n) RETURN n")
    row = measure_query(_Source(n_rows=5), query, timeout_s=10, row_cap=3)  # type: ignore[arg-type]
    assert (row.outcome, row.n_rows, row.truncated) == ("ok", 3, True)


@pytest.mark.parametrize(
    ("error", "outcome"),
    [
        (CypherExecutionError(_TIMEOUT), "timeout"),
        (CypherExecutionError(_MEMORY), "memory"),
        (WriteClauseError("CREATE"), "rejected"),
    ],
)
def test_a_failed_query_records_how_it_ended(error: Exception, outcome: str) -> None:
    query = BenchQuery(query_id="a", group="g", query="MATCH (n) RETURN n")
    assert measure_query(_Source(error), query, timeout_s=10, row_cap=3).outcome == outcome  # type: ignore[arg-type]


def test_the_verdict_at_a_smaller_timeout_follows_the_measured_time() -> None:
    assert verdict_at(_row("ok", 25.0), 30) == "ok"
    assert verdict_at(_row("ok", 25.0), 20) == "timeout"
    assert verdict_at(_row("timeout", 120.0), 120) == "timeout"
    assert verdict_at(_row("error", 0.1), 20) == "error"


def test_only_timeout_and_memory_queries_are_taken_from_a_stored_run() -> None:
    rows: list[dict[str, object]] = [
        {"question_id": "q1", "trace": {"retrieval": {"cypher": "A", "cypher_error": _TIMEOUT}}},
        {"question_id": "q2", "trace": {"retrieval": {"cypher": "B", "cypher_error": "Syntax"}}},
        {"question_id": "q3", "trace": {"retrieval": {"cypher": "C"}}},
        {"question_id": "q4", "trace": {"retrieval": {"cypher": "D", "cypher_error": _MEMORY}}},
    ]
    assert [q.query_id for q in queries_from_run_rows(rows, "recorded")] == ["q1", "q4"]


def test_generic_shapes_cover_each_anchor_and_route() -> None:
    shapes = generic_shapes(["P-1"], [("A", "B")])
    assert len(shapes) == len(set_shapes("P-1")) + 4
    assert all("P-1" in s.query for s in shapes[:4])


def test_a_tag_with_a_quote_is_refused() -> None:
    with pytest.raises(ValueError, match="quote"):
        set_shapes("P-1' RETURN 1 //")


def test_the_table_shows_the_verdict_per_timeout() -> None:
    table = render_table([_row("ok", 25.0)], [20, 30])
    assert "| @20s | @30s |" in table
    assert "timeout | ok" in table


class _HangingSource(_Source):
    def __init__(self) -> None:
        super().__init__()
        self.closed = False
        self.release = threading.Event()

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        self.release.wait(5)  # stands for a server that ignores its timeout
        return CypherResult(rows=[], truncated=False)

    def close(self) -> None:
        self.closed = True
        self.release.set()


def test_a_query_that_outlives_the_watchdog_is_recorded_as_hung() -> None:
    query = BenchQuery(query_id="h", group="g", query="MATCH (n) RETURN n")
    row = measure_guarded(
        _HangingSource(),  # type: ignore[arg-type]
        query,
        timeout_s=1,
        row_cap=3,
        hang_after_s=0.2,
    )
    assert row.outcome == "hung"
    assert "ignored" in row.error


def test_after_a_hung_query_the_connection_is_closed_and_reopened() -> None:
    sources: list[_Source] = []

    def open_source() -> _Source:
        sources.append(_HangingSource() if not sources else _Source())
        return sources[-1]

    queries = [BenchQuery(query_id=i, group="g", query="Q") for i in ("a", "b")]
    rows = run_bench(open_source, queries, timeout_s=1, row_cap=3, hang_after_s=0.2)  # type: ignore[arg-type]
    assert [r.outcome for r in rows] == ["hung", "ok"]
    assert len(sources) == 2
