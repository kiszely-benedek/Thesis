"""The Cypher query-timing replay: recorded queries, timing of one query, and the report row."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from infra_report_builders import corpus as corpus_data
from plantgraph.infra.cypher_replay import (
    REPLAY_META_FILE,
    CypherReplayMeta,
    CypherReplayRow,
    RecordedQuery,
    recorded_queries,
    replay_queries,
    time_one_query,
)
from plantgraph.infra.report import build_infra_report
from plantgraph.infra.report_inputs import ReportRequest, load_db_replay_data, load_report_inputs
from plantgraph.qa.cypher import CypherExecutionError, CypherResult, WriteClauseError
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.harness.runner import run_harness
from plantgraph.qa.local_timer import DB_CLIENT, DB_SERVER, add_local_seconds, local_timer
from plantgraph.qa.models import Outcome, QuestionResult
from plantgraph.qa.tag_check import TAG_CHECK_TIMEOUT_S
from qa_harness_toy import CORPUS_ID, Toy, abstaining_transport, build_toy, make_config


class _Clock:
    """A clock that moves only when a test says so."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class _StubSource:
    """A database stand-in: ticks the fake clock inside `run_cypher` like the real view does."""

    def __init__(self, clock: _Clock, error: Exception | None = None) -> None:
        self._clock = clock
        self._error = error
        self.sent: list[tuple[str, float]] = []  # (query, timeout) in the order received

    def label_names(self) -> frozenset[str]:
        return frozenset({"Pump", "CorpusNode"})

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        self.sent.append((query, timeout_s))
        if isinstance(self._error, WriteClauseError):
            raise self._error  # refused before the database is touched: nothing is timed
        with local_timer(DB_CLIENT):
            self._clock.now += 0.25
        add_local_seconds(DB_SERVER, 0.1)
        if self._error is not None:
            raise self._error
        return CypherResult(rows=[{"tag": "P-1"}], truncated=False)


def _time(
    question_id: str, clock: _Clock, error: Exception | None, failed: bool = False
) -> CypherReplayRow:
    return time_one_query(
        _StubSource(clock, error),  # type: ignore[arg-type]
        RecordedQuery(question_id, ("MATCH (n) RETURN n",), failed),
        strategy="cypher_rag_plant",
        timeout_s=30,
        row_cap=200,
        clock=clock,
    )


def test_a_successful_query_is_timed_with_its_database_split() -> None:
    row = _time("q1", _Clock(), None)
    assert row.replay_outcome == "ok" and row.n_rows == 1
    assert row.db_client_s == 0.25 and row.db_server_s == 0.1
    assert row.n_db_queries == 1 and row.local_compute_s == 0.25
    assert row.clock == "perf_counter" and row.spent_usd == 0.0


def test_a_database_error_is_executed_and_marked() -> None:
    row = _time("q1", _Clock(), CypherExecutionError("syntax"), failed=True)
    assert row.replay_outcome == "database_error"
    assert row.original_retrieval_error and row.n_db_queries == 1


def test_a_write_clause_never_reaches_the_database() -> None:
    row = _time("q1", _Clock(), WriteClauseError("CREATE"))
    assert row.replay_outcome == "write_clause_rejected" and row.n_db_queries == 0


@pytest.fixture(scope="module")
def toy(tmp_path_factory: pytest.TempPathFactory) -> Toy:
    return build_toy(tmp_path_factory.mktemp("replay-toy"))


def _source_run(toy: Toy, runs_root: Path, run_id: str) -> list[QuestionResult]:
    run_harness(
        config=make_config(toy, allow_paid_calls=True).model_copy(update={"run_id": run_id}),
        corpus_roles={CORPUS_ID: "dev"},
        corpora_root=toy.corpora_root,
        questions_root=toy.questions_root,
        runs_root=runs_root,
        cache_path=runs_root / "cache.sqlite",
        http_client=abstaining_transport().as_httpx_client(),
        progress=lambda _message: None,
        concurrency=1,
        cost_per_question_usd=0.01,
    )
    return RunDir(runs_root / run_id).read_rows()


def _with_query(row: QuestionResult, query: str | None, outcome: Outcome) -> QuestionResult:
    trace = {"retrieval": {"cypher": query} if query else {}}
    return row.model_copy(update={"trace": trace, "outcome": outcome})


def test_recorded_queries_keep_run_order_and_the_failure_flag(toy: Toy, tmp_path: Path) -> None:
    rows = _source_run(toy, tmp_path, "SRC")
    marked = [
        _with_query(rows[0], "MATCH (a) RETURN a", Outcome.ANSWERED),
        _with_query(rows[1], "BAD", Outcome.RETRIEVAL_ERROR),
    ]
    queries = recorded_queries(marked)
    assert [q.question_id for q in queries] == [r.question_id for r in marked]
    assert [q.original_retrieval_error for q in queries] == [False, True]


def _row_with_trace(row: QuestionResult, retrieval: dict[str, object]) -> QuestionResult:
    return row.model_copy(update={"trace": {"retrieval": retrieval}})


def test_every_attempt_and_the_tag_check_are_recorded_in_order(toy: Toy, tmp_path: Path) -> None:
    row = _source_run(toy, tmp_path, "SRC")[0]
    retrieval = {
        "cypher": "REPAIRED",
        "attempts": [{"cypher": "SLOW"}, {"cypher": ""}, {"cypher": "REPAIRED"}],
        "tags_found": ["P-1"],
        "tags_missing": ["P-9"],
    }
    [recorded] = recorded_queries([_row_with_trace(row, retrieval)])
    assert recorded.attempt_queries == ("SLOW", "REPAIRED")  # the empty reply sent nothing
    assert recorded.tag_check_query is not None and "'P-1', 'P-9'" in recorded.tag_check_query
    assert recorded.n_queries == 3


def test_a_run_without_an_attempts_list_replays_its_one_query(toy: Toy, tmp_path: Path) -> None:
    row = _source_run(toy, tmp_path, "SRC")[0]
    [recorded] = recorded_queries([_row_with_trace(row, {"cypher": "ONLY"})])
    assert recorded.attempt_queries == ("ONLY",) and recorded.tag_check_query is None


def test_the_replay_sends_the_tag_check_then_every_attempt_as_one_timed_question() -> None:
    clock = _Clock()
    source = _StubSource(clock)
    recorded = RecordedQuery("q1", ("SLOW", "REPAIRED"), False, tag_check_query="TAGS")
    row = time_one_query(
        source,  # type: ignore[arg-type]
        recorded,
        strategy="cypher_rag_lines",
        timeout_s=30,
        row_cap=200,
        clock=clock,
    )
    assert [query for query, _ in source.sent] == ["TAGS", "SLOW", "REPAIRED"]
    assert source.sent[0][1] == TAG_CHECK_TIMEOUT_S and source.sent[1][1] == 30
    assert row.n_db_queries == 3 and row.db_client_s == 0.75 and row.replay_outcome == "ok"


def test_a_failed_first_attempt_does_not_decide_the_outcome() -> None:
    clock = _Clock()
    source = _StubSource(clock, CypherExecutionError("timeout"))
    recorded = RecordedQuery("q1", ("SLOW", "REPAIRED"), False)
    row = time_one_query(
        source,  # type: ignore[arg-type]
        recorded,
        strategy="cypher_rag_lines",
        timeout_s=30,
        row_cap=200,
        clock=clock,
    )
    assert row.n_db_queries == 2 and row.replay_outcome == "database_error"


def test_a_row_without_a_recorded_query_replays_as_a_row_with_zero_queries(
    toy: Toy, tmp_path: Path
) -> None:
    rows = _source_run(toy, tmp_path, "SRC")
    [recorded] = recorded_queries([_with_query(rows[0], None, Outcome.TIMED_OUT)])
    assert recorded.attempt_queries == () and recorded.n_queries == 0

    source = _StubSource(_Clock())
    [row] = replay_queries(
        source,  # type: ignore[arg-type]
        [recorded],
        strategy="cypher_rag_lines",
        timeout_s=30,
        row_cap=200,
    )

    assert row.replay_outcome == "no_query" and row.n_db_queries == 0 and not source.sent


def test_a_question_with_only_a_tag_check_replays_just_that_query() -> None:
    clock = _Clock()
    source = _StubSource(clock)
    row = time_one_query(
        source,  # type: ignore[arg-type]
        RecordedQuery("q1", (), False, tag_check_query="TAGS"),
        strategy="cypher_rag_lines",
        timeout_s=30,
        row_cap=200,
        clock=clock,
    )
    assert [query for query, _ in source.sent] == ["TAGS"]
    assert row.replay_outcome == "no_query" and row.n_db_queries == 1


class _HangingSource(_StubSource):
    """A database that never answers a query; `close` frees the blocked call, as a real one does."""

    def __init__(self) -> None:
        super().__init__(_Clock())
        self.released = threading.Event()

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        self.released.wait(5.0)
        raise CypherExecutionError("connection closed")

    def close(self) -> None:
        self.released.set()


def test_the_replay_goes_through_the_guard_so_a_hung_query_ends_at_timeout_plus_grace() -> None:
    source = _HangingSource()
    [row] = replay_queries(
        source,  # type: ignore[arg-type]
        [RecordedQuery("q1", ("HANGS",), False)],
        strategy="cypher_rag_lines",
        timeout_s=0.05,
        row_cap=200,
        hang_grace_s=0.05,
    )
    assert row.replay_outcome == "database_error"
    assert source.released.is_set()  # the guard closed the stuck connection


def test_the_replay_meta_does_not_claim_the_stored_query_was_run_again() -> None:
    measures = CypherReplayMeta(
        source_run="S", strategy="s", corpus_id="D", timeout_s=1, row_cap=1,
        n_source_questions=0, n_original_retrieval_errors=0, n_replay_errors=0,
    ).measures  # fmt: skip
    assert "run again" not in measures and "recorded queries" in measures


def _write_replay_folder(source_rows: list[QuestionResult], folder: Path) -> None:
    folder.mkdir(parents=True)
    clock = _Clock()
    lines = [_time(row.question_id, clock, None).model_dump_json() for row in source_rows]
    (folder / "timings.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    meta = CypherReplayMeta(
        source_run="SRC",
        strategy="cypher_rag_plant",
        corpus_id="D100",
        timeout_s=30,
        row_cap=200,
        n_source_questions=len(source_rows),
        n_original_retrieval_errors=0,
        n_replay_errors=0,
    )
    (folder / REPLAY_META_FILE).write_text(meta.model_dump_json(), encoding="utf-8")


def test_the_loader_takes_timings_from_the_replay_and_cost_from_the_source(
    toy: Toy, tmp_path: Path
) -> None:
    rows = _source_run(toy, tmp_path / "old", "SRC")
    _write_replay_folder(rows, tmp_path / "runs" / "INF-CYPL-D100")
    data = load_db_replay_data(
        tmp_path / "runs", "INF-CYPL-D100", tmp_path / "old", "cypher", "D100"
    )
    assert data.basis == "db_replay" and not data.allow_paid_calls
    assert len(data.timings) == len(rows)
    assert data.answers_cost_usd == pytest.approx(sum(r.total_cost_usd or 0.0 for r in rows))


def test_a_replay_that_misses_a_question_is_refused(toy: Toy, tmp_path: Path) -> None:
    rows = _source_run(toy, tmp_path / "old", "SRC")
    _write_replay_folder(rows[:-1], tmp_path / "runs" / "INF-CYPL-D100")
    with pytest.raises(ValueError, match="in order"):
        load_db_replay_data(tmp_path / "runs", "INF-CYPL-D100", tmp_path / "old", "cypher", "D100")


def _write_corpus_files(root: Path) -> None:
    data = corpus_data("D100", 1.0)
    for number, ingest in enumerate(data.ingests, start=1):
        path = root / "ingest" / "D100" / f"rep{number}" / "ingest.json"
        path.parent.mkdir(parents=True)
        path.write_text(ingest.model_dump_json(), encoding="utf-8")
    probe_dir = root / "probe" / "D100"
    probe_dir.mkdir(parents=True)
    for number, startup in enumerate(data.startups, start=1):
        (probe_dir / f"rep{number}.json").write_text(startup.model_dump_json(), encoding="utf-8")


def test_the_report_labels_database_only_rows(toy: Toy, tmp_path: Path) -> None:
    rows = _source_run(toy, tmp_path / "old", "SRC")
    _write_replay_folder(rows, tmp_path / "runs" / "INF-CYPL-D100")
    _write_corpus_files(tmp_path)
    request = ReportRequest(
        ingest_root=tmp_path / "ingest",
        probe_root=tmp_path / "probe",
        runs_root=tmp_path / "runs",
        corpora=["D100"],
        compute_corpora=["D100"],
        replay_templates={},
        old_run_templates={},
        old_runs_root=tmp_path / "old",
        price_json=None,
        db_replay_templates={"cypher": "INF-CYPL-{c}"},
    )
    report = build_infra_report(load_report_inputs(request))
    assert [row.basis for row in report.compute] == ["db_replay"]
    assert report.compute[0].db_client_sum_s is not None
    assert any("database time only" in check.detail for check in report.checks)
    json.loads(report.model_dump_json())
