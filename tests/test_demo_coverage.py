"""Tests for the demo's `coverage` command: a fake cascade, counting hits, misses and equality."""

from __future__ import annotations

import pytest

from plantgraph.demo.app.api_models import RecordedAnswer
from plantgraph.demo.app.cascade_pool import Asker
from plantgraph.demo.app.coverage import (
    NO_TIER,
    CorpusCoverage,
    format_coverage,
    measure_coverage,
)
from plantgraph.qa.cascade.live_models import LiveAnswer, NeedsPaidCall, TierReport
from plantgraph.qa.models import AnswerType, FinalAnswer, Outcome, Question, QuestionFamily
from plantgraph.qa.strategies.base import AskedQuestion


def _question(question_id: str) -> Question:
    return Question(
        question_id=question_id, corpus_id="T", family=QuestionFamily.LOOKUP_TYPE,
        template_id="t", template_version="1", text=f"text {question_id}",
        answer_type=AnswerType.CLASS_NAME, answerable=True, reference="Pump", generator_seed=1,
    )  # fmt: skip


def _tier(name: str, strategy: str) -> TierReport:
    return TierReport(
        tier=name, strategy=strategy, model_id="m", outcome=Outcome.ANSWERED, accepted=True,
        latency_s=1.0, wall_s=0.1, cost_usd=0.0, spent_usd=0.0, n_calls=1, n_cached=1,
        n_steps=None, stop_reason=None, n_rows=None,
    )  # fmt: skip


def _live(answer: str | None, by: str | None) -> LiveAnswer:
    final = None if answer is None else FinalAnswer(answer=answer, not_present=False)
    return LiveAnswer(
        question_text="q", corpus_id="T", answer_type=AnswerType.CLASS_NAME, policy="p",
        evaluated_policy=True, notice=None, outcome=Outcome.ANSWERED, final_answer=final,
        answered_by=by, fell_back=False, tiers=(_tier("t1", "s1"), _tier("t2", "s2")),
        latency_s=1.0, wall_s=0.1, cost_usd=0.0, spent_usd=0.0, from_cache=True, trace_sheets=(),
    )  # fmt: skip


def _recorded(strategy: str, answer: str) -> RecordedAnswer:
    return RecordedAnswer(
        run_id="r", strategy=strategy, outcome=Outcome.ANSWERED, correct=True, answer=answer,
        cost_usd=0.0, latency_s=1.0,
    )  # fmt: skip


class _FakeAsker:
    def __init__(self, replies: dict[str, LiveAnswer | NeedsPaidCall]) -> None:
        self._replies = replies

    def ask(self, asked: AskedQuestion) -> LiveAnswer | NeedsPaidCall:
        return self._replies[asked.text]


class _FakeSource:
    """A cascade source that fails the test if a paid cascade is requested."""

    tiers: tuple[str, ...] = ("t1", "t2")
    tier1_store = True

    def __init__(self, replies: dict[str, LiveAnswer | NeedsPaidCall]) -> None:
        self._asker = _FakeAsker(replies)

    def asker(self, *, paid: bool, tier2_only: bool) -> Asker:
        if paid:
            pytest.fail("coverage asked for a paid cascade")
        return self._asker

    def close(self) -> None:
        pass


def _measure(replies: dict[str, LiveAnswer | NeedsPaidCall]) -> CorpusCoverage:
    questions = {qid: _question(qid) for qid in ("a", "b", "c", "d", "e")}
    recorded = {
        "a": (_recorded("s1", "Pump"),),
        "b": (_recorded("s2", "Valve"),),
        "c": (_recorded("s1", "Pump"),),
    }
    return measure_coverage("T", questions, recorded, _FakeSource(replies))


def test_counts_hits_misses_per_tier_and_answered_by() -> None:
    coverage = _measure(
        {
            "text a": _live("Pump", "t1"),
            "text b": _live("Tank", "t2"),  # differs from the recorded "Valve"
            "text c": _live(None, None),  # a hit nobody answered
            "text d": NeedsPaidCall(missing_tier="t1", reason="x"),
            "text e": NeedsPaidCall(missing_tier="t2", reason="y"),
        }
    )
    assert (coverage.n_questions, coverage.n_hits) == (5, 3)
    assert coverage.misses_by_tier == {"t1": 1, "t2": 1}
    assert coverage.answered_by == {"t1": 1, "t2": 1, NO_TIER: 1}


def test_equality_counts_only_comparable_hits() -> None:
    coverage = _measure(
        {
            "text a": _live("Pump", "t1"),  # equal
            "text b": _live("Tank", "t2"),  # comparable, not equal
            "text c": _live(None, None),  # nothing to compare
            "text d": _live("Pump", "t1"),  # no recorded row
            "text e": _live("Pump", "t1"),  # no recorded row
        }
    )
    assert (coverage.n_hits, coverage.n_comparable, coverage.n_equal) == (5, 2, 1)


def test_all_misses_report_has_no_policy() -> None:
    miss = NeedsPaidCall(missing_tier="t1", reason="x")
    coverage = _measure({f"text {q}": miss for q in "abcde"})
    assert coverage.n_hits == 0
    assert "(none ran)" in format_coverage(coverage)


def test_format_shows_every_count() -> None:
    coverage = _measure({f"text {q}": _live("Pump", "t1") for q in "abcde"})
    text = format_coverage(coverage)
    assert "full cache hits : 5/5" in text
    assert "answers equal to the recorded runs: 2/2 comparable of 5 hits" in text
