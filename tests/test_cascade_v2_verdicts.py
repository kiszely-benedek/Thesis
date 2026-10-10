"""The pre-registered rules V2 and V3 on hand-made numbers, ties and "none eligible" included."""

from __future__ import annotations

import pytest

from plantgraph.qa.cascade.evaluate import LatencyBound, Summary
from plantgraph.qa.cascade.report_verdicts_v2 import confirm_on_scale, select_on_dev

BOUND = LatencyBound()


def _summary(
    name: str, correct: int, cost: float = 0.003, median: float = 5.0, p90: float = 40.0
) -> Summary:
    return Summary(
        policy=name,
        corpus_id="D100",
        n_questions=180,
        n_correct=correct,
        cutoff_s=120.0,
        n_correct_at_cutoff=correct,
        n_timed_out=0,
        n_latency_incomplete=0,
        total_cost_usd=cost * 180,
        cost_per_question_usd=cost,
        latency_median_s=median,
        latency_mean_s=median,
        latency_p90_s=p90,
        latency_p95_s=p90,
        latency_max_s=p90,
        tier_shares={},
        tier_calls={},
    )


def _field(**overrides: Summary) -> dict[str, Summary]:
    """The four candidates, all eligible, with `overrides` replacing some."""
    base = {
        "cascade_v1": _summary("cascade_v1", 150),
        "cascade_v1_iso": _summary("cascade_v1_iso", 151),
        "cascade_v2": _summary("cascade_v2", 160),
        "cascade_v2_iso": _summary("cascade_v2_iso", 158),
    }
    return base | overrides


def test_v2_picks_the_most_accurate_eligible_candidate() -> None:
    summaries = _field(cascade_v2=_summary("cascade_v2", 170, p90=90.0))  # best but too slow

    selection = select_on_dev(summaries, BOUND)

    assert selection.chosen == "cascade_v2_iso"
    assert selection.verdict.status == "SELECTED"
    assert "not eligible" in selection.verdict.details[2]


def test_v2_tie_goes_to_the_cheaper_candidate() -> None:
    summaries = _field(
        cascade_v2=_summary("cascade_v2", 160, cost=0.004),
        cascade_v2_iso=_summary("cascade_v2_iso", 160, cost=0.003),
    )

    assert select_on_dev(summaries, BOUND).chosen == "cascade_v2_iso"


def test_v2_with_none_eligible_takes_the_lowest_p90_and_says_so() -> None:
    summaries = {
        name: _summary(name, 160, median=12.0, p90=70.0 + index)
        for index, name in enumerate(_field())
    }

    selection = select_on_dev(summaries, BOUND)

    assert selection.chosen == "cascade_v1"
    assert "latency bound not met on dev" in selection.verdict.headline


def test_v2_is_incomplete_while_a_candidate_is_missing() -> None:
    summaries = _field()
    del summaries["cascade_v2_iso"]

    selection = select_on_dev(summaries, BOUND)

    assert (selection.verdict.status, selection.chosen) == ("INCOMPLETE", None)
    assert "cascade_v2_iso" in selection.verdict.headline


@pytest.mark.parametrize(
    ("own_correct", "status"),
    [(158, "PASS"), (157, "FAIL")],  # best eligible is 160: within 2 passes, 3 behind fails
)
def test_v3_confirms_within_two_questions(own_correct: int, status: str) -> None:
    summaries = _field(
        cascade_v2=_summary("cascade_v2", 160),
        cascade_v2_iso=_summary("cascade_v2_iso", own_correct),
    )

    result = confirm_on_scale("cascade_v2_iso", summaries, BOUND)

    assert result.verdict.status == status
    assert result.chosen == ("cascade_v2_iso" if status == "PASS" else "cascade_v2")
    if status == "FAIL":
        assert "scale effect" in result.verdict.details[-1]


def test_v3_switches_when_the_choice_is_no_longer_eligible() -> None:
    summaries = _field(cascade_v2_iso=_summary("cascade_v2_iso", 170, p90=200.0))

    result = confirm_on_scale("cascade_v2_iso", summaries, BOUND)

    assert (result.verdict.status, result.chosen) == ("FAIL", "cascade_v2")


def test_v3_with_none_eligible_reports_the_lowest_p90() -> None:
    summaries = {
        name: _summary(name, 160, p90=100.0 + index) for index, name in enumerate(_field())
    }

    result = confirm_on_scale("cascade_v2", summaries, BOUND)

    assert result.verdict.status == "FAIL"
    assert result.chosen == "cascade_v1"
    assert "no candidate meets the latency bound" in result.verdict.headline


def test_v3_is_incomplete_without_a_v2_choice() -> None:
    assert confirm_on_scale(None, _field(), BOUND).verdict.status == "INCOMPLETE"
