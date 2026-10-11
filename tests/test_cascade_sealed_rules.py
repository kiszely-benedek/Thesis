"""The sealed test's pure rules: intervals, cost elasticity, the claim verdicts, the scopes."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from plantgraph.qa.cascade.evaluate import LatencyBound
from plantgraph.qa.cascade.report_claims import (
    cost_elasticity,
    judge_k1,
    judge_k2,
    judge_k3,
    judge_q5,
    judge_scale_claim,
    not_run_verdicts,
)
from plantgraph.qa.cascade.report_scopes import (
    SCOPE_HEADLINE,
    SCOPE_HELD_OUT,
    load_splits,
    scope_ids,
)
from plantgraph.qa.cascade.stats import (
    Interval,
    bootstrap_interval,
    median,
    unpaired_bootstrap,
    wilson_interval,
)
from plantgraph.qa.models import Question


def _ci(estimate: float, low: float, high: float) -> Interval:
    return Interval(estimate=estimate, ci_low=low, ci_high=high)


def _mean_gap(a: list[float], b: list[float]) -> float:
    return sum(b) / len(b) - sum(a) / len(a)


# --- intervals ---


def test_wilson_interval_stays_inside_zero_and_one_at_the_ceiling() -> None:
    perfect = wilson_interval(100, 100)
    none = wilson_interval(0, 100)

    assert perfect.estimate == 1.0
    assert 0.96 < perfect.ci_low < 1.0
    assert perfect.ci_high == pytest.approx(1.0)
    assert (none.ci_low, none.estimate) == (0.0, 0.0)


def test_wilson_interval_known_value() -> None:
    # 97 of 100, worked by hand: centre 0.9526, half-width 0.0371 -> [0.915, 0.990]
    interval = wilson_interval(97, 100)

    assert interval.ci_low == pytest.approx(0.915, abs=0.001)
    assert interval.ci_high == pytest.approx(0.990, abs=0.001)


def test_wilson_interval_rejects_bad_counts() -> None:
    with pytest.raises(ValueError, match="successes <= total"):
        wilson_interval(5, 4)


def test_unpaired_bootstrap_is_deterministic_and_brackets_the_difference() -> None:
    small = [1.0] * 90 + [0.0] * 10
    large = [1.0] * 80 + [0.0] * 20

    first = unpaired_bootstrap(small, large, _mean_gap)
    second = unpaired_bootstrap(small, large, _mean_gap)

    assert first == second
    assert first.estimate == pytest.approx(-0.10)
    assert first.ci_low < -0.10 < first.ci_high
    assert first.ci_high < 0.05  # the samples differ clearly


def test_bootstrap_interval_of_a_median() -> None:
    interval = bootstrap_interval([float(x) for x in range(1, 102)], median)

    assert interval.estimate == 51.0
    assert interval.ci_low < 51.0 < interval.ci_high


# --- cost elasticity ---


def test_elasticity_of_a_doubled_cost_at_ten_times_the_sheets() -> None:
    assert cost_elasticity(1.0, 2.0, 100, 1000) == pytest.approx(math.log(2) / math.log(10))
    assert cost_elasticity(1.0, 2.0, 100, 1000) == pytest.approx(0.301, abs=0.0005)


def test_elasticity_of_a_cost_that_grows_with_the_plant_is_one() -> None:
    assert cost_elasticity(0.001, 0.01, 100, 1000) == pytest.approx(1.0)


def test_elasticity_rejects_a_zero_cost_and_a_shrinking_plant() -> None:
    with pytest.raises(ValueError, match="positive costs"):
        cost_elasticity(0.0, 1.0, 100, 1000)
    with pytest.raises(ValueError, match="small < large"):
        cost_elasticity(1.0, 1.0, 1000, 100)


# --- claim verdicts on hand-made numbers ---

FLAT_COST = _ci(0.1, 0.0, 0.2)
NO_CHANGE = _ci(0.0, -0.01, 0.01)


def test_q4_passes_when_the_interval_touches_zero_from_below() -> None:
    verdict = judge_scale_claim("cascade_v3", "headline", _ci(-0.02, -0.05, 0.0), FLAT_COST)

    assert verdict.status == "PASS"
    assert verdict.rule == "Q4 (primary) cascade_v3"


def test_q4_fails_on_accuracy_just_below_zero_with_the_registered_wording() -> None:
    falling = _ci(-0.03, -0.06, -0.001)

    verdict = judge_scale_claim("cascade_v3", "headline", falling, FLAT_COST)

    assert verdict.status == "FAIL"
    assert "accuracy falls with scale" in verdict.headline
    assert "near-linearly" not in verdict.headline


def test_q4_elasticity_must_be_strictly_below_half() -> None:
    at_half = judge_scale_claim("cascade_v3", "headline", NO_CHANGE, _ci(0.5, 0.4, 0.6))
    below = judge_scale_claim("cascade_v3", "headline", NO_CHANGE, _ci(0.499, 0.4, 0.6))

    assert at_half.status == "FAIL"
    assert "cost grows near-linearly with the plant" in at_half.headline
    assert below.status == "PASS"


def test_q4_of_another_policy_is_labelled_q4_prime() -> None:
    verdict = judge_scale_claim("always_g_luna", "headline", NO_CHANGE, FLAT_COST)

    assert verdict.rule == "Q4' always_g_luna"


def test_k1_needs_no_accuracy_loss_and_clearly_lower_cost_and_latency() -> None:
    lower = _ci(-1.0, -2.0, -0.1)

    assert judge_k1("headline", NO_CHANGE, lower, lower).status == "PASS"


def test_k1_cost_interval_touching_zero_is_not_lower() -> None:
    lower = _ci(-1.0, -2.0, -0.1)
    touching = _ci(-1.0, -2.0, 0.0)

    verdict = judge_k1("headline", NO_CHANGE, touching, lower)

    assert verdict.status == "FAIL"
    assert verdict.headline.endswith("the cascade saves nothing")


def test_k1_names_every_failed_part() -> None:
    worse = _ci(-0.05, -0.08, -0.01)
    flat = _ci(0.0, -1.0, 1.0)

    verdict = judge_k1("headline", worse, flat, flat)

    assert "the cascade loses accuracy" in verdict.headline
    assert "the cascade saves nothing" in verdict.headline


def test_k2_and_q5_need_the_interval_strictly_above_zero() -> None:
    assert judge_k2("headline", _ci(0.1, 0.01, 0.2)).status == "PASS"
    assert judge_k2("headline", _ci(0.1, 0.0, 0.2)).status == "FAIL"
    assert judge_k2("headline", None).status == "INCOMPLETE"
    assert judge_q5("headline", _ci(0.2, 0.05, 0.3)).status == "PASS"
    failed = judge_q5("headline", _ci(0.0, -0.1, 0.1))
    assert failed.status == "FAIL"
    assert "free-form Cypher matches the typed API" in failed.headline


def test_q5_says_so_when_cypher_is_clearly_better() -> None:
    verdict = judge_q5("headline", _ci(-0.2, -0.3, -0.1))

    assert any("free-form Cypher is the better arm" in d for d in verdict.details)


def test_k3_compares_point_estimates_with_the_bounds() -> None:
    bound = LatencyBound()
    ok = judge_k3("headline", bound, _ci(10.0, 8, 12), _ci(60.0, 40, 70))
    slow = judge_k3("headline", bound, _ci(10.1, 8, 12), _ci(30.0, 20, 40))

    assert ok.status == "PASS"  # the limits themselves pass (<=)
    assert slow.status == "FAIL"
    assert "not fast enough at plant scale" in slow.headline


def test_q1_to_q3_are_reported_as_not_run() -> None:
    verdicts = not_run_verdicts()

    assert [v.rule for v in verdicts] == ["Q1", "Q2", "Q3"]
    assert {v.status for v in verdicts} == {"NOT_RUN"}


# --- scopes ---


def _question(question_id: str, family: str) -> Question:
    fields: dict[str, Any] = {
        "question_id": question_id,
        "corpus_id": "T",
        "family": family,
        "template_id": family,
        "template_version": "1",
        "text": "?",
        "answer_type": "BOOLEAN",
        "answerable": True,
        "reference": "yes",
        "generator_seed": 1,
    }
    return Question.model_validate(fields)


QUESTIONS = [
    _question("T:1", "CONNECTED"),
    _question("T:2", "LOOP_ACTUATED_VALVE"),
    _question("T:3", "CONNECTED"),
    _question("T:4", "CONNECTED"),
]
SPLITS = {"T:1": "dev-old", "T:2": "dev-old", "T:3": "held-out", "T:4": "held-out-wording"}


def test_headline_leaves_out_the_excluded_family_and_the_wordings() -> None:
    scopes = scope_ids(QUESTIONS, SPLITS)

    assert scopes[SCOPE_HEADLINE] == {"T:1", "T:3"}
    assert scopes[SCOPE_HELD_OUT] == {"T:3"}


def test_without_splits_only_the_headline_scope_exists() -> None:
    scopes = scope_ids(QUESTIONS, None)

    assert scopes == {SCOPE_HEADLINE: {"T:1", "T:3", "T:4"}}


def _write_splits(root: Path, splits: dict[str, str]) -> None:
    (root / "T").mkdir()
    (root / "T" / "splits.json").write_text(json.dumps(splits), encoding="utf-8")


def test_load_splits_reads_the_file_beside_the_questions(tmp_path: Path) -> None:
    _write_splits(tmp_path, SPLITS)

    assert load_splits(tmp_path, "T", QUESTIONS) == SPLITS
    assert load_splits(tmp_path, "other", QUESTIONS) is None


def test_load_splits_refuses_a_file_that_does_not_cover_the_questions(tmp_path: Path) -> None:
    _write_splits(tmp_path, {k: v for k, v in SPLITS.items() if k != "T:4"})

    with pytest.raises(ValueError, match="exactly once"):
        load_splits(tmp_path, "T", QUESTIONS)


def test_load_splits_refuses_an_unknown_split_name(tmp_path: Path) -> None:
    _write_splits(tmp_path, {**SPLITS, "T:1": "dev"})

    with pytest.raises(ValueError, match="splits from"):
        load_splits(tmp_path, "T", QUESTIONS)
