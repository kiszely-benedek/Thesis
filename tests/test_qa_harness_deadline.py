"""`--question-deadline-s` through the harness: `TIMED_OUT` rows, ordered commit, replay (CV2-T2).

One toy item hangs (the fake backend answers it slowly); with a short deadline it times
out, every other item is answered, and the file is the same at any pool size and on replay.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import pytest

from plantgraph.llm.fake_transport import FakeTransport
from plantgraph.llm.models import ChatResponse, QuestionDeadline, RequestTimedOut
from plantgraph.qa.harness.attempt import _ACTIVE_METER, active_remaining_s
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.harness.runner import run_harness
from plantgraph.qa.harness.spend_cap import SpendGuard
from plantgraph.qa.harness.summary import RunSummary
from plantgraph.qa.harness.usage_meter import UsageMeter
from plantgraph.qa.models import Outcome, QuestionResult
from qa_harness_toy import CORPUS_ID, Toy, abstaining_transport, build_toy, make_config
from test_qa_harness_concurrency import scale_questions

_N_QUESTIONS = 8
_HANGING = "variant-003"
_DEADLINE_S = 0.2
_HANG_S = 0.7


@pytest.fixture(scope="module")
def toy(tmp_path_factory: pytest.TempPathFactory) -> Toy:
    small = build_toy(tmp_path_factory.mktemp("deadline-toy"))
    return scale_questions(small, small.questions_root.parent / "scaled", _N_QUESTIONS)


def _hanging_transport() -> FakeTransport:
    """Answers at once, except the question whose text ends `(variant 3)`."""

    def latency(prompt: str) -> float:
        return _HANG_S if "(variant 3)" in prompt else 0.0

    return abstaining_transport(latency_for_prompt=latency)


def _run(
    toy: Toy, root: Path, *, concurrency: int, paid: bool, runs: str, fake: FakeTransport
) -> RunSummary:
    config = make_config(toy, allow_paid_calls=paid, question_deadline_s=_DEADLINE_S)
    return run_harness(
        config=config,
        corpus_roles={CORPUS_ID: "dev"},
        corpora_root=toy.corpora_root,
        questions_root=toy.questions_root,
        runs_root=root / runs,
        cache_path=root / "cache.sqlite",
        http_client=fake.as_httpx_client(),
        cost_per_question_usd=0.001,
        concurrency=concurrency,
        progress=lambda _message: None,
    )


def _rows(root: Path, runs: str) -> list[QuestionResult]:
    return RunDir(root / runs / "toy").read_rows()


def _answers(root: Path, runs: str) -> bytes:
    return (root / runs / "toy" / "answers.jsonl").read_bytes()


def _stable_bytes(root: Path, runs: str) -> bytes:
    """The rows minus `latency_s` of answered items: a live call's own duration differs per run."""
    rows = [
        row if row.outcome is Outcome.TIMED_OUT else row.model_copy(update={"latency_s": 0.0})
        for row in _rows(root, runs)
    ]
    return "".join(row.model_dump_json() + "\n" for row in rows).encode("utf-8")


def test_the_hanging_item_is_timed_out_and_the_items_after_it_are_committed_in_order(
    toy: Toy, tmp_path: Path
) -> None:
    _run(toy, tmp_path, concurrency=1, paid=True, runs="one", fake=_hanging_transport())

    rows = _rows(tmp_path, "one")
    assert [row.question_id for row in rows] == [f"variant-{i:03d}" for i in range(_N_QUESTIONS)]
    timed_out = [row for row in rows if row.outcome is Outcome.TIMED_OUT]
    assert [row.question_id for row in timed_out] == [_HANGING]
    row = timed_out[0]
    assert not row.correct and row.final_answer is None
    assert row.latency_s == _DEADLINE_S
    assert row.retrieval_usage is not None and row.retrieval_usage.n_abandoned == 1
    assert all(r.outcome is Outcome.ANSWERED for r in rows if r is not row)


def test_four_workers_write_the_same_bytes_as_one_and_replay_matches_both(
    toy: Toy, tmp_path: Path
) -> None:
    _run(toy, tmp_path, concurrency=1, paid=True, runs="one", fake=_hanging_transport())
    _run(toy, tmp_path, concurrency=4, paid=True, runs="four", fake=_hanging_transport())
    assert _stable_bytes(tmp_path, "four") == _stable_bytes(tmp_path, "one")

    replay_fake = _hanging_transport()
    _run(toy, tmp_path, concurrency=4, paid=False, runs="replay", fake=replay_fake)

    assert _answers(tmp_path, "replay") == _answers(tmp_path, "four")
    assert replay_fake.requests == []


def test_the_late_answer_of_the_hanging_item_reaches_calls_jsonl(toy: Toy, tmp_path: Path) -> None:
    _run(toy, tmp_path, concurrency=1, paid=True, runs="one", fake=_hanging_transport())

    calls = tmp_path / "one" / "toy" / "calls.jsonl"
    deadline = time.monotonic() + 3.0
    kinds: list[str | None] = []
    while time.monotonic() < deadline and "late_after_timeout" not in kinds:
        time.sleep(0.05)
        kinds = [json.loads(line)["error_kind"] for line in calls.read_text().splitlines()]

    assert kinds.count("timeout") == 1
    assert kinds.count("late_after_timeout") == 1


def test_a_resume_does_not_ask_a_timed_out_question_again(toy: Toy, tmp_path: Path) -> None:
    _run(toy, tmp_path, concurrency=1, paid=True, runs="one", fake=_hanging_transport())
    before = _answers(tmp_path, "one")

    fake = _hanging_transport()
    _run(toy, tmp_path, concurrency=1, paid=True, runs="one", fake=fake)

    assert fake.requests == []
    assert _answers(tmp_path, "one") == before


# --- the meter: the recorded-latency budget -------------------------------------------------


def _response(latency_s: float) -> ChatResponse:
    return ChatResponse(
        text="x",
        prompt_tokens=1,
        completion_tokens=1,
        cost_usd=0.0,
        latency_s=latency_s,
        provider_response_id=None,
        finish_reason="stop",
        from_cache=True,  # a cached response still counts its recorded latency
        created_at=datetime(2026, 10, 8),
    )


def test_each_call_gets_the_deadline_minus_the_recorded_time() -> None:
    meter = UsageMeter(SpendGuard(None), deadline_s=10.0)
    meter.begin("q")
    budgets: list[float | None] = []

    def call(timeout_s: float | None) -> ChatResponse:
        budgets.append(timeout_s)
        return _response(4.0)

    meter.timed_call(call, is_final=False)
    meter.timed_call(call, is_final=True)

    assert budgets == [10.0, 6.0]


def test_no_call_starts_once_the_recorded_time_reaches_the_deadline() -> None:
    meter = UsageMeter(SpendGuard(None), deadline_s=5.0)
    meter.begin("q")
    meter.timed_call(lambda _timeout: _response(5.0), is_final=False)
    started: list[bool] = []

    def call(_timeout: float | None) -> ChatResponse:
        started.append(True)
        return _response(0.0)

    with pytest.raises(QuestionDeadline):
        meter.timed_call(call, is_final=True)

    assert started == []


def test_a_timeout_counts_its_budget_as_recorded_time_and_as_an_abandoned_call() -> None:
    meter = UsageMeter(SpendGuard(None), deadline_s=10.0)
    meter.begin("q")

    def hang(timeout_s: float | None) -> ChatResponse:
        raise RequestTimedOut("abandoned", timeout_s or 0.0)

    with pytest.raises(RequestTimedOut):
        meter.timed_call(hang, is_final=False)

    assert meter.recorded_elapsed_s == 10.0
    assert meter.end().n_abandoned == 1


def test_without_a_deadline_a_call_gets_no_budget() -> None:
    meter = UsageMeter(SpendGuard(None))
    meter.begin("q")
    budgets: list[float | None] = []

    def call(timeout_s: float | None) -> ChatResponse:
        budgets.append(timeout_s)
        return _response(99.0)

    meter.timed_call(call, is_final=True)

    assert budgets == [None]


def test_a_late_charge_counts_toward_the_spend_cap() -> None:
    guard = SpendGuard(1.0)
    late = _response(1.0).model_copy(update={"cost_usd": 0.4, "from_cache": False})

    guard.charge_late(late)

    assert guard.spent_usd == pytest.approx(0.4)


def test_the_remaining_budget_shrinks_with_each_recorded_call() -> None:
    meter = UsageMeter(SpendGuard(None), deadline_s=10.0)
    meter.begin("q")
    meter.timed_call(lambda _timeout: _response(4.0), is_final=False)

    assert meter.remaining_s == 6.0
    assert UsageMeter(SpendGuard(None)).remaining_s is None


def test_the_agent_reads_the_budget_of_the_item_its_thread_is_answering() -> None:
    meter = UsageMeter(SpendGuard(None), deadline_s=10.0)
    meter.begin("q")
    meter.timed_call(lambda _timeout: _response(3.0), is_final=False)

    token = _ACTIVE_METER.set(meter)
    try:
        inside = active_remaining_s()
    finally:
        _ACTIVE_METER.reset(token)

    assert inside == 7.0
    assert active_remaining_s() is None  # outside `attempt` there is no item, so no budget
