"""Harness accounting: abandoned time, late cost, the resume spend guard, canonical row order."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

from plantgraph.llm.fake_transport import FakeTransport
from plantgraph.llm.models import CallRecord, ChatResponse, RequestTimedOut
from plantgraph.qa.harness.fill import Invocation, spend_guard_for_resume
from plantgraph.qa.harness.run_dir import RunDir
from plantgraph.qa.harness.runner import run_harness
from plantgraph.qa.harness.spend_cap import SpendCapReached, SpendGuard
from plantgraph.qa.harness.usage_meter import UsageMeter
from plantgraph.qa.models import CallUsage, Outcome, QuestionResult
from qa_harness_toy import CORPUS_ID, Toy, abstaining_transport, build_toy, make_config


def _response(cost: float, *, cached: bool = False) -> ChatResponse:
    return ChatResponse(
        text="x",
        prompt_tokens=1,
        completion_tokens=1,
        cost_usd=cost,
        latency_s=1.0,
        provider_response_id=None,
        finish_reason="stop",
        from_cache=cached,
        created_at=datetime(2026, 11, 7),
    )


def _timed_out_call(latency_s: float) -> Callable[[float | None], ChatResponse]:
    def call(_timeout_s: float | None) -> ChatResponse:
        raise RequestTimedOut("abandoned", latency_s)

    return call


def _row(usage: CallUsage) -> QuestionResult:
    return QuestionResult(
        run_id="r",
        question_id="q1",
        strategy="s",
        repeat=0,
        outcome=Outcome.ANSWERED,
        final_answer=None,
        correct=False,
        f1=None,
        prompt_tokens=0,
        completion_tokens=0,
        cost_usd=None,
        latency_s=0.5,
        context_chars=0,
        trace={},
        retrieval_usage=usage,
    )


# --- abandoned-call time in the row -------------------------------------------


def test_an_abandoned_retrieval_call_is_in_the_usage_and_the_row_total() -> None:
    meter = UsageMeter(SpendGuard(None))
    meter.begin("q1")
    meter.record(_response(0.01), 0.1, is_final=False)
    with pytest.raises(RequestTimedOut):
        meter.timed_call(_timed_out_call(30.0), is_final=False)

    usage = meter.end()

    assert usage.abandoned_latency_s == 30.0 and usage.n_abandoned == 1
    assert usage.llm_latency_s == 1.0
    assert _row(usage).total_llm_latency_s == pytest.approx(0.5 + 1.0 + 30.0)


def test_an_abandoned_final_call_is_not_counted_twice() -> None:
    meter = UsageMeter(SpendGuard(None))
    meter.begin("q1")
    with pytest.raises(RequestTimedOut):
        meter.timed_call(_timed_out_call(30.0), is_final=True)

    assert meter.end().abandoned_latency_s == 0.0  # the row's own latency_s carries it


def test_usage_without_abandoned_time_keeps_its_bytes_and_old_rows_load() -> None:
    assert "abandoned_latency_s" not in CallUsage(n_calls=1).model_dump_json()
    assert CallUsage.model_validate_json('{"n_calls": 2}').abandoned_latency_s == 0.0
    assert "abandoned_latency_s" in CallUsage(abandoned_latency_s=2.0).model_dump_json()


# --- late cost and the resume spend guard -------------------------------------


def test_the_guard_reports_late_cost_separately() -> None:
    guard = SpendGuard(None)
    guard.add(_response(0.02))
    guard.charge_late(_response(0.005))

    assert guard.late_usd == pytest.approx(0.005)
    assert guard.spent_usd == pytest.approx(0.025)


def _call_line(response: ChatResponse | None, error_kind: str | None) -> str:
    record = CallRecord.model_validate(
        {
            "run_id": "r",
            "purpose": "answer",
            "cache_key": "k",
            "pin_hash": "p",
            "prompt_sha256": "s",
            "response": response.model_dump(mode="json") if response else None,
            "error_kind": error_kind,
        }
    )
    return record.model_dump_json() + "\n"


def test_run_dir_spent_usd_counts_cache_misses_and_late_answers_only(tmp_path: Path) -> None:
    run_dir = RunDir(tmp_path)
    lines = [
        _call_line(_response(0.01), None),
        _call_line(_response(0.02, cached=True), None),  # served from the cache: free now
        _call_line(None, "timeout"),
        _call_line(_response(0.04), "late_after_timeout"),  # billed though never cached
    ]
    run_dir.calls_path.write_text("".join(lines), encoding="utf-8")

    assert run_dir.spent_usd() == pytest.approx(0.05)
    assert RunDir(tmp_path / "empty").spent_usd() == 0.0


def test_the_resume_guard_is_seeded_with_real_spend_not_row_totals() -> None:
    cached_row = _row(CallUsage(cost_usd=0.5))  # its calls were served from the cache
    invocation = Invocation(True, 0.30, None)

    guard = spend_guard_for_resume(invocation, [cached_row], spent_usd=0.0)

    assert guard.spent_usd == 0.0
    guard.check_before_call()  # seeding with the row total of 0.5 would already be over the cap
    with pytest.raises(SpendCapReached):
        spend_guard_for_resume(invocation, [cached_row], spent_usd=0.3).check_before_call()


# --- row order after a retried provider error ---------------------------------


@pytest.fixture(scope="module")
def toy(tmp_path_factory: pytest.TempPathFactory) -> Toy:
    return build_toy(tmp_path_factory.mktemp("accounting-toy"))


def _run(toy: Toy, tmp_path: Path, fake: FakeTransport, runs_name: str) -> None:
    run_harness(
        config=make_config(toy, allow_paid_calls=True),
        corpus_roles={CORPUS_ID: "dev"},
        corpora_root=toy.corpora_root,
        questions_root=toy.questions_root,
        runs_root=tmp_path / runs_name,
        cache_path=tmp_path / f"{runs_name}.sqlite",
        http_client=fake.as_httpx_client(),
        progress=lambda _message: None,
    )


def _ids(tmp_path: Path, runs_name: str, file_name: str) -> list[str]:
    path = tmp_path / runs_name / "toy" / file_name
    return [json.loads(line)["question_id"] for line in path.read_text("utf-8").splitlines()]


def test_a_retried_row_lands_where_a_clean_run_puts_it(
    toy: Toy, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("plantgraph.llm.client.time.sleep", lambda _seconds: None)
    _run(toy, tmp_path, abstaining_transport(), "clean")
    # the first question fails on all 6 attempts, so it is deferred and retried last
    _run(toy, tmp_path, abstaining_transport(fail_times=6, fail_status=500), "retried")

    for file_name in ("answers.jsonl", "timings.jsonl"):
        assert _ids(tmp_path, "retried", file_name) == _ids(tmp_path, "clean", file_name)
    outcomes = (tmp_path / "retried" / "toy" / "answers.jsonl").read_text("utf-8")
    assert Outcome.PROVIDER_ERROR.value not in outcomes
