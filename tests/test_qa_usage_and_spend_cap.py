"""Total per-question cost (QAR-T1) and the hard spend cap, offline with the fake transport.

`allow_paid_calls=True` appears only together with an injected `FakeTransport`, which
serves scripted costs and opens no socket; no test passes the CLI flag.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from plantgraph.llm.fake_transport import FakeTransport, ScriptedReply
from plantgraph.llm.models import ChatResponse
from plantgraph.qa.cypher import CypherResult
from plantgraph.qa.harness.runner import run_harness
from plantgraph.qa.harness.spend_cap import SpendCapReached, SpendGuard
from plantgraph.qa.harness.summary import RunSummary
from plantgraph.qa.harness.usage_meter import TimingRow, UsageMeter
from plantgraph.qa.models import CallUsage, Outcome, QuestionResult, RunConfig
from plantgraph.store.neo4j_plan import LoadPlan
from qa_harness_toy import ABSTAIN_REPLY, CORPUS_ID, Toy, build_toy, make_config

_CALL_COST = 0.01
_CYPHER_PARAMS = {"timeout_s": 5, "row_cap": 3}


@pytest.fixture(scope="module")
def toy(tmp_path_factory: pytest.TempPathFactory) -> Toy:
    return build_toy(tmp_path_factory.mktemp("usage-toy"))


def _response(cost: float | None, *, cached: bool = False, latency: float = 1.0) -> ChatResponse:
    return ChatResponse(
        text="x",
        prompt_tokens=10,
        completion_tokens=5,
        cost_usd=cost,
        latency_s=latency,
        provider_response_id=None,
        finish_reason="stop",
        from_cache=cached,
        created_at=datetime(2026, 10, 2),
    )


# ---------------------------------------------------------------- UsageMeter


def test_meter_sums_retrieval_calls_and_leaves_the_final_call_out() -> None:
    meter = UsageMeter(SpendGuard(None))
    meter.begin("q1")
    meter.record(_response(0.01), 0.5, is_final=False)
    meter.record(_response(0.02, cached=True, latency=2.0), 0.0, is_final=False)
    meter.record(_response(0.04), 0.7, is_final=True)

    usage = meter.end()

    assert usage.n_calls == 2 and usage.n_cached == 1
    assert usage.prompt_tokens == 20 and usage.completion_tokens == 10
    assert usage.cost_usd == pytest.approx(0.03)  # as billed first time, cached call included
    assert usage.llm_latency_s == pytest.approx(3.0)
    assert usage.spent_usd == pytest.approx(0.01)  # the cached call spent nothing now
    assert meter.spent_usd == pytest.approx(0.05)  # the final call counts for spending
    assert meter.seconds_in_calls == pytest.approx(1.2)


def test_meter_cost_is_none_when_a_call_reports_none() -> None:
    meter = UsageMeter(SpendGuard(None))
    meter.begin("q1")
    meter.record(_response(0.01), 0.0, is_final=False)
    meter.record(_response(None), 0.0, is_final=False)

    usage = meter.end()

    assert usage.cost_usd is None and usage.n_cost_missing == 1


def test_begin_resets_the_previous_question() -> None:
    meter = UsageMeter(SpendGuard(None))
    meter.begin("q1")
    meter.record(_response(0.01), 0.5, is_final=False)
    meter.begin("q2")

    assert meter.question_id == "q2"
    assert meter.end() == CallUsage()
    assert meter.seconds_in_calls == 0.0


def test_total_cost_is_final_plus_retrieval() -> None:
    row = _row(cost=0.04, retrieval=CallUsage(n_calls=1, cost_usd=0.01, prompt_tokens=3))
    assert row.total_cost_usd == pytest.approx(0.05)
    assert row.total_tokens == row.prompt_tokens + row.completion_tokens + 3
    assert _row(cost=0.04, retrieval=None).total_cost_usd == 0.04
    assert _row(cost=0.04, retrieval=CallUsage(cost_usd=None)).total_cost_usd is None


def _row(*, cost: float | None, retrieval: CallUsage | None) -> QuestionResult:
    return QuestionResult(
        run_id="r",
        question_id="q",
        strategy="s",
        repeat=0,
        outcome=Outcome.ANSWERED,
        final_answer=None,
        correct=False,
        f1=None,
        prompt_tokens=10,
        completion_tokens=5,
        cost_usd=cost,
        latency_s=1.0,
        context_chars=0,
        retrieval_usage=retrieval,
    )


# ---------------------------------------------------------------- SpendGuard


def test_guard_counts_only_live_spend_and_stops_before_the_cap() -> None:
    guard = SpendGuard(0.05, estimate_usd=0.02)
    guard.add(_response(0.02, cached=True))  # a cache hit is free
    guard.check_before_question()
    guard.add(_response(0.02))
    guard.add(_response(0.02))

    with pytest.raises(SpendCapReached, match="cap of 0.050000"):
        guard.check_before_question()  # 0.04 spent + 0.02 expected passes 0.05


def test_guard_without_a_cap_never_stops() -> None:
    guard = SpendGuard(None, estimate_usd=10.0)
    guard.add(_response(5.0))
    guard.check_before_question()
    guard.check_before_call()


# ---------------------------------------------------------------- the harness


def _transport(cost: float = _CALL_COST, text: str = ABSTAIN_REPLY) -> FakeTransport:
    return FakeTransport(default_reply=ScriptedReply(text=text, cost_usd=cost))


def _run(toy: Toy, tmp_path: Path, fake: FakeTransport, **overrides: object) -> RunSummary:
    return run_harness(
        config=make_config(toy, **overrides),
        corpus_roles={CORPUS_ID: "dev"},
        corpora_root=toy.corpora_root,
        questions_root=toy.questions_root,
        runs_root=tmp_path / "runs",
        cache_path=tmp_path / "cache.sqlite",
        http_client=fake.as_httpx_client(),
        progress=lambda _message: None,
        cypher_source_factory=_stub_database,  # type: ignore[arg-type]
    )


class _StubSource:
    def corpus_id(self) -> str:
        return "stub"

    def schema_text(self) -> str:
        return "STUB-SCHEMA"

    def run_cypher(self, query: str, timeout_s: float, row_cap: int) -> CypherResult:
        return CypherResult(rows=[{"tag": "X"}], truncated=False)

    def close(self) -> None:
        pass


def _stub_database(plan: LoadPlan) -> _StubSource:
    return _StubSource()


def _read(tmp_path: Path, name: str) -> list[str]:
    return (tmp_path / "runs" / "toy" / name).read_text("utf-8").splitlines()


def _rows(tmp_path: Path) -> list[QuestionResult]:
    return [QuestionResult.model_validate_json(line) for line in _read(tmp_path, "answers.jsonl")]


def test_cypher_cost_counts_the_query_call_and_logs_the_question_id(
    toy: Toy, tmp_path: Path
) -> None:
    fake = _transport(text='{"answer": "Pump", "not_present": false}')
    summary = _run(
        toy, tmp_path, fake, strategies={"cypher_rag": _CYPHER_PARAMS}, allow_paid_calls=True
    )

    rows = _rows(tmp_path)
    for row in rows:
        assert row.cost_usd == pytest.approx(_CALL_COST)  # the final call alone, as before
        assert row.retrieval_usage is not None and row.retrieval_usage.n_calls == 1
        assert row.total_cost_usd == pytest.approx(2 * _CALL_COST)
    assert summary.mean_total_cost_usd["cypher_rag"] == pytest.approx(2 * _CALL_COST)
    # F2: the retrieval call carries the question id, so calls.jsonl joins per question
    calls = [json.loads(line) for line in _read(tmp_path, "calls.jsonl")]
    queries = [call for call in calls if call["purpose"] == "cypher"]
    assert sorted(call["question_id"] for call in queries) == sorted(r.question_id for r in rows)
    assert all(call["question_id"] is not None for call in calls)


def test_answers_hold_no_live_only_numbers_and_timings_go_to_their_own_file(
    toy: Toy, tmp_path: Path
) -> None:
    _run(
        toy,
        tmp_path,
        _transport(),
        strategies={"cypher_rag": _CYPHER_PARAMS},
        allow_paid_calls=True,
    )

    answers_text = "\n".join(_read(tmp_path, "answers.jsonl"))
    assert "n_cached" not in answers_text and "spent_usd" not in answers_text
    timings = [TimingRow.model_validate_json(line) for line in _read(tmp_path, "timings.jsonl")]
    assert len(timings) == len(toy.questions)
    assert all(t.local_compute_s >= 0.0 for t in timings)
    assert all(t.spent_usd == pytest.approx(2 * _CALL_COST) for t in timings)


def test_replay_of_a_cypher_run_keeps_the_usage_and_marks_calls_cached(
    toy: Toy, tmp_path: Path
) -> None:
    _run(
        toy,
        tmp_path,
        _transport(),
        strategies={"cypher_rag": _CYPHER_PARAMS},
        allow_paid_calls=True,
    )
    live = _rows(tmp_path)
    (tmp_path / "runs" / "toy" / "answers.jsonl").unlink()
    (tmp_path / "runs" / "toy" / "timings.jsonl").unlink()

    replay_fake = _transport()
    _run(toy, tmp_path, replay_fake, strategies={"cypher_rag": _CYPHER_PARAMS})

    assert replay_fake.requests == []
    replayed = _rows(tmp_path)
    assert [r.retrieval_usage for r in replayed] == [r.retrieval_usage for r in live]
    timings = [TimingRow.model_validate_json(line) for line in _read(tmp_path, "timings.jsonl")]
    assert all(t.spent_usd == 0.0 and t.n_cached_retrieval_calls == 1 for t in timings)


def test_run_stops_before_exceeding_the_cap_and_resume_continues_without_duplicates(
    toy: Toy, tmp_path: Path
) -> None:
    cap = 3.5 * _CALL_COST  # room for three one-call questions, not for a fourth
    first = _transport()
    summary = _run(toy, tmp_path, first, allow_paid_calls=True, max_spend_usd=cap)

    assert summary.stopped_by_spend_cap
    stopped_rows = _rows(tmp_path)
    assert len(stopped_rows) == 3 and len(first.requests) == 3
    assert sum(row.total_cost_usd or 0.0 for row in stopped_rows) <= cap

    second = _transport()
    resumed = _run(toy, tmp_path, second, allow_paid_calls=True, max_spend_usd=100.0)

    assert not resumed.stopped_by_spend_cap
    ids = [row.question_id for row in _rows(tmp_path)]
    assert sorted(ids) == sorted(q.question_id for q in toy.questions)  # none twice, none missing
    assert len(second.requests) == len(toy.questions) - 3


def test_the_cap_counts_retrieval_calls_and_can_stop_inside_a_question(
    toy: Toy, tmp_path: Path
) -> None:
    # no question has been seen yet, so the first one starts; its second call would pass the cap
    cap = 1.5 * _CALL_COST
    fake = _transport()
    summary = _run(
        toy,
        tmp_path,
        fake,
        strategies={"cypher_rag": _CYPHER_PARAMS},
        allow_paid_calls=True,
        max_spend_usd=cap,
    )

    assert summary.stopped_by_spend_cap
    assert len(fake.requests) == 1  # only the query-writing call was paid
    assert not (tmp_path / "runs" / "toy" / "answers.jsonl").exists()

    # resuming: the paid query call is a cache hit, so only the rest is billed
    again = _transport()
    _run(
        toy,
        tmp_path,
        again,
        strategies={"cypher_rag": _CYPHER_PARAMS},
        allow_paid_calls=True,
        max_spend_usd=100.0,
    )
    assert len(again.requests) == 2 * len(toy.questions) - 1


def test_cache_hits_never_count_against_the_cap(toy: Toy, tmp_path: Path) -> None:
    _run(toy, tmp_path, _transport(), allow_paid_calls=True, max_spend_usd=100.0)
    (tmp_path / "runs" / "toy" / "answers.jsonl").unlink()

    fake = _transport()
    summary = _run(toy, tmp_path, fake, allow_paid_calls=True, max_spend_usd=0.5 * _CALL_COST)

    assert not summary.stopped_by_spend_cap  # every call is cached, so nothing is spent
    assert fake.requests == []
    assert len(_rows(tmp_path)) == len(toy.questions)


def test_a_paid_run_without_a_cap_is_refused_before_anything_happens(
    toy: Toy, tmp_path: Path
) -> None:
    fake = _transport()
    with pytest.raises(ValueError, match="--max-spend-usd"):
        _run(toy, tmp_path, fake, allow_paid_calls=True, max_spend_usd=None)

    assert not (tmp_path / "runs").exists()
    assert fake.requests == []


def test_the_cap_is_recorded_in_the_run_config(toy: Toy, tmp_path: Path) -> None:
    _run(toy, tmp_path, _transport(), allow_paid_calls=True, max_spend_usd=7.0)

    stored = RunConfig.model_validate_json(_read_text(tmp_path, "run_config.json"))
    assert stored.max_spend_usd == 7.0


def _read_text(tmp_path: Path, name: str) -> str:
    return (tmp_path / "runs" / "toy" / name).read_text("utf-8")
