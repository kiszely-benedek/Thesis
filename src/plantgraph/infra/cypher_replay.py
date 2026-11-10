"""Query-timing replay of a stored Cypher-tier run: the database's share of the time, no LLM.

A Cypher-tier question has two halves: a language model writes a Cypher query (Cypher is Neo4j's
graph query language), then the database runs it. A normal replay of a stored run needs the
model's replies from the cache, and those replies depend on the order of the database's rows,
which changes after every reload. This replay skips the model: it takes the query the run
recorded (the tag check and every attempt) and sends it again, one question at a time, through
the same guarded call the strategy uses (`GuardedCypherSource.run_cypher`, so a hung query ends
as it does live) plus the strategy's own row formatting. A question that sent no query (it timed
out or hit a provider error before one was written) replays as a row with zero queries.

What it measures: the database round-trip, the server's own share of it, and the formatting of
the rows. What it does NOT measure: the query-writing call, the answer-prompt build and the answer
parsing. The report labels the rows accordingly (basis `db_replay`).
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from plantgraph.qa.cypher import CypherExecutionError, CypherSource, WriteClauseError
from plantgraph.qa.cypher_guard import HANG_GRACE_S, GuardedCypherSource
from plantgraph.qa.harness.usage_meter import TimingRow
from plantgraph.qa.local_timer import DB_CLIENT, DB_SERVER, LocalTimer, deactivate
from plantgraph.qa.models import Outcome, QuestionResult
from plantgraph.qa.strategies.cypher_rag import format_context
from plantgraph.qa.tag_check import TAG_CHECK_TIMEOUT_S, tag_lookup_query

#: Files the replay writes into its run folder (next to `timings.jsonl`, `environment.jsonl`).
REPLAY_META_FILE = "db_replay.json"

#: How the replayed query ended: it ran, the write filter refused it before it was sent, the
#: database refused it (syntax error, timeout, hang, out of memory), or the question had sent
#: no query at all (`no_query`; only its tag check, if any, was replayed).
ReplayOutcome = Literal["ok", "write_clause_rejected", "database_error", "no_query"]


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
    #: Replayed queries the write filter or the database refused.
    n_replay_errors: int
    #: Questions that had sent no query; they replay as rows with zero (or only tag-check) queries.
    n_without_query: int = 0
    #: Plain-words statement of what these timings cover, copied into the report.
    measures: str = (
        "database time only: the recorded queries (tag check and every attempt) sent again "
        "plus the row formatting; no query-writing call, no answer-prompt build, "
        "no answer parsing"
    )


@dataclass(frozen=True)
class RecordedQuery:
    """Everything one stored question sent to the database, in the order it was sent.

    `tag_check_query` runs first (it is `None` when the question named no tag-like word),
    then every query-writing attempt in turn: a timed-out first attempt and its repair both cost
    database time. The last attempt is the one whose rows the answer used. A question that sent
    no query has no attempts (and no tag check, or only the tag check).
    """

    question_id: str
    attempt_queries: tuple[str, ...]
    original_retrieval_error: bool
    tag_check_query: str | None = None

    @property
    def n_queries(self) -> int:
        """How many statements the replay sends for this question."""
        return len(self.attempt_queries) + (self.tag_check_query is not None)


def recorded_queries(rows: Sequence[QuestionResult]) -> list[RecordedQuery]:
    """The queries of every row of a stored Cypher-tier run, in run order.

    A row with no recorded query (timed out, provider error) is kept, with no attempts, so the
    replay still has one row per source question.
    """
    return [_recorded_query(row) for row in rows]


def _recorded_query(row: QuestionResult) -> RecordedQuery:
    retrieval = row.trace.get("retrieval", {})
    attempts = _attempt_queries(retrieval)
    failed = row.outcome is Outcome.RETRIEVAL_ERROR
    return RecordedQuery(row.question_id, attempts, failed, _tag_check_query(retrieval))


def _attempt_queries(retrieval: dict[str, Any]) -> tuple[str, ...]:
    """The queries of all attempts; a run without an `attempts` list has only `cypher`."""
    # An attempt whose model reply held no query has "" and sent nothing to the database.
    listed = [a.get("cypher") for a in retrieval.get("attempts", [])]
    queries = tuple(query for query in listed if query)
    if queries:
        return queries
    last = retrieval.get("cypher")
    return (last,) if last else ()


def _tag_check_query(retrieval: dict[str, Any]) -> str | None:
    """Rebuild the tag lookup from the tags the trace recorded (found first, then missing).

    The tag order may differ from the question's; the statement is the same size and cost.
    A failed lookup (`tag_check_error`) recorded no tags, so it cannot be rebuilt.
    """
    tags = [*retrieval.get("tags_found", []), *retrieval.get("tags_missing", [])]
    return tag_lookup_query(tags) if tags else None


def time_one_query(
    source: CypherSource,
    recorded: RecordedQuery,
    *,
    strategy: str,
    timeout_s: float,
    row_cap: int,
    clock: Callable[[], float] = time.perf_counter,
) -> CypherReplayRow:
    """Run all of a question's recorded queries in order and time them as one question."""
    timer = LocalTimer(clock=clock)
    token = timer.activate()
    started = clock()
    try:
        outcome, n_rows = _execute_question(source, recorded, timeout_s, row_cap)
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


def _execute_question(
    source: CypherSource, recorded: RecordedQuery, timeout_s: float, row_cap: int
) -> tuple[ReplayOutcome, int]:
    """Tag check, then every attempt; the last attempt's outcome is the question's."""
    if recorded.tag_check_query is not None:
        _run_and_ignore(source, recorded.tag_check_query, TAG_CHECK_TIMEOUT_S, row_cap)
    if not recorded.attempt_queries:
        return "no_query", 0
    *earlier, last = recorded.attempt_queries
    for query in earlier:
        _run_and_ignore(source, query, timeout_s, row_cap)
    return _execute(source, last, timeout_s, row_cap)


def _run_and_ignore(source: CypherSource, query: str, timeout_s: float, row_cap: int) -> None:
    """Send a query whose rows the replay does not use (a tag check, a repaired attempt).

    A failure here is not the question's outcome: the strategy tolerated it too.
    """
    try:
        source.run_cypher(query, timeout_s, row_cap)
    except (WriteClauseError, CypherExecutionError):
        pass


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
    hang_grace_s: float = HANG_GRACE_S,
    clock: Callable[[], float] = time.perf_counter,
) -> list[CypherReplayRow]:
    """Execute the queries one after another (concurrency 1), each timed on its own.

    The source is wrapped in the live strategy's `GuardedCypherSource` (timeout plus hang
    grace), so a query that hangs the server ends here as it would in a real run.
    """
    guarded = (
        source
        if isinstance(source, GuardedCypherSource)
        else GuardedCypherSource(source, hang_grace_s=hang_grace_s)
    )
    return [
        time_one_query(
            guarded, recorded, strategy=strategy, timeout_s=timeout_s, row_cap=row_cap, clock=clock
        )
        for recorded in queries
    ]
