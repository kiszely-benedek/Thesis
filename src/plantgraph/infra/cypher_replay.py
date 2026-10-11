"""Query-timing replay of a stored Cypher-tier run: the database's share of the time, no LLM.

A Cypher-tier question has two halves: a language model writes a Cypher query (Cypher is Neo4j's
graph query language), then the database runs it. A normal replay of a stored run needs the
model's replies from the cache, and those replies depend on the order of the database's rows,
which changes after every reload. This replay skips the model: it takes the query the run
recorded and executes it again, one question at a time, through the same call the strategy uses
(`run_cypher`) plus the strategy's own row formatting.

What it measures: the database round-trip, the server's own share of it, and the formatting of
the rows. What it does NOT measure: the query-writing call, the answer-prompt build and the answer
parsing. The report labels the rows accordingly (basis `db_replay`).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.cypher import CypherExecutionError, CypherSource, WriteClauseError
from plantgraph.qa.harness.usage_meter import TimingRow
from plantgraph.qa.local_timer import DB_CLIENT, DB_SERVER, LocalTimer, deactivate
from plantgraph.qa.models import Outcome, QuestionResult
from plantgraph.qa.strategies.cypher_rag import format_context

#: Files the replay writes into its run folder (next to `timings.jsonl`, `environment.jsonl`).
REPLAY_META_FILE = "db_replay.json"

#: How the replayed query ended: it ran, the write filter refused it before it was sent, or the
#: database refused it (syntax error, timeout, out of memory).
ReplayOutcome = Literal["ok", "write_clause_rejected", "database_error"]


class CypherReplayRow(TimingRow):
    """One line of the replay's `timings.jsonl`: a `TimingRow` plus how the query ended."""

    replay_outcome: ReplayOutcome
    #: True when the original run's question ended as `RETRIEVAL_ERROR`.
    original_retrieval_error: bool
    n_rows: int


class CypherReplayMeta(BaseModel):
    """What the report needs to know about a replay run folder besides its timings."""

    model_config = ConfigDict(frozen=True)

    source_run: str
    strategy: str
    corpus_id: str
    timeout_s: float
    row_cap: int
    n_source_questions: int
    n_original_retrieval_errors: int
    n_replay_errors: int
    #: Plain-words statement of what these timings cover, copied into the report.
    measures: str = (
        "database time only: the stored query run again plus the row formatting; "
        "no query-writing call, no answer-prompt build, no answer parsing"
    )


@dataclass(frozen=True)
class RecordedQuery:
    """The query a stored run wrote for one question, and whether that question had failed."""

    question_id: str
    query: str
    original_retrieval_error: bool


def recorded_queries(rows: Sequence[QuestionResult]) -> list[RecordedQuery]:
    """The generated query of every row of a stored Cypher-tier run, in run order.

    Raises:
        ValueError: a row has no recorded query, so the replay would silently skip a question.
    """
    queries: list[RecordedQuery] = []
    for row in rows:
        query = row.trace.get("retrieval", {}).get("cypher")
        if not query:
            raise ValueError(
                f"expected a recorded query (trace.retrieval.cypher) for {row.question_id}, "
                "found none; the replay does not skip questions"
            )
        failed = row.outcome is Outcome.RETRIEVAL_ERROR
        queries.append(RecordedQuery(row.question_id, query, failed))
    return queries


def time_one_query(
    source: CypherSource,
    recorded: RecordedQuery,
    *,
    strategy: str,
    timeout_s: float,
    row_cap: int,
    clock: Callable[[], float] = time.perf_counter,
) -> CypherReplayRow:
    """Run one recorded query on the database and time it as the harness times a question."""
    timer = LocalTimer(clock=clock)
    token = timer.activate()
    started = clock()
    try:
        outcome, n_rows = _execute(source, recorded.query, timeout_s, row_cap)
    finally:
        deactivate(token)
    wall_s = clock() - started
    return CypherReplayRow(
        question_id=recorded.question_id,
        strategy=strategy,
        repeat=0,
        local_compute_s=wall_s,
        spent_usd=0.0,
        n_cached_retrieval_calls=0,
        clock="perf_counter",
        wall_s=wall_s,
        db_client_s=timer.seconds_of(DB_CLIENT),
        db_server_s=timer.seconds_of(DB_SERVER),
        n_db_queries=timer.calls_of(DB_CLIENT),
        replay_outcome=outcome,
        original_retrieval_error=recorded.original_retrieval_error,
        n_rows=n_rows,
    )


def _execute(
    source: CypherSource, query: str, timeout_s: float, row_cap: int
) -> tuple[ReplayOutcome, int]:
    """The strategy's own steps after the model call: run the query, format the rows."""
    try:
        result = source.run_cypher(query, timeout_s, row_cap)
    except WriteClauseError:
        return "write_clause_rejected", 0
    except CypherExecutionError:
        return "database_error", 0
    format_context(
        query, result, row_cap, source.label_names()
    )  # timed too: the strategy does it before answering
    return "ok", len(result.rows)


def replay_queries(
    source: CypherSource,
    queries: Sequence[RecordedQuery],
    *,
    strategy: str,
    timeout_s: float,
    row_cap: int,
    clock: Callable[[], float] = time.perf_counter,
) -> list[CypherReplayRow]:
    """Execute the queries one after another (concurrency 1), each timed on its own."""
    return [
        time_one_query(
            source, recorded, strategy=strategy, timeout_s=timeout_s, row_cap=row_cap, clock=clock
        )
        for recorded in queries
    ]
