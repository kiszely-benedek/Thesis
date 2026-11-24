"""The pass rules at their boundaries, and the question sets the claims count."""

from __future__ import annotations

import pytest
from test_analysis_fixtures import NETWORK_TAG, R_FAMILIES, QSpec, _question, r_specs

from plantgraph.qa.cascade.report_claims import judge_scale_claim
from plantgraph.qa.cascade.stats import Interval
from plantgraph.qa.exp0009.analysis_claims import clearly_above_zero, no_accuracy_loss
from plantgraph.qa.exp0009.analysis_misc import touches_network
from plantgraph.qa.exp0009.analysis_scope import r_headline_ids, stripped_id, x_ids
from plantgraph.qa.models import QuestionFamily


def _interval(low: float, high: float) -> Interval:
    return Interval(estimate=(low + high) / 2, ci_low=low, ci_high=high)


@pytest.mark.parametrize(
    ("high", "passes"), [(-1e-9, False), (0.0, True), (1e-9, True), (0.3, True)]
)
def test_q4_passes_when_the_interval_contains_zero_or_lies_above_it(
    high: float, passes: bool
) -> None:
    interval = _interval(-0.5, high)
    assert no_accuracy_loss(interval) is passes
    # EXP-0008's own judge reads the accuracy part of Q4 the same way
    cheap = Interval(estimate=0.1, ci_low=0.0, ci_high=0.2)  # cost elasticity below 0.5
    verdict = judge_scale_claim("cascade_v4_iso", "headline", interval, cheap, "cascade_v4_iso")
    assert (verdict.status == "PASS") is passes


def test_an_interval_wholly_above_zero_also_passes_q4() -> None:
    assert no_accuracy_loss(_interval(0.1, 0.4))


@pytest.mark.parametrize(
    ("low", "passes"), [(-0.2, False), (0.0, False), (1e-9, True), (0.4, True)]
)
def test_sb2_needs_the_whole_interval_above_zero(low: float, passes: bool) -> None:
    assert clearly_above_zero(_interval(low, 0.9)) is passes


def test_stripping_the_corpus_prefix_pairs_a2_and_b_ids() -> None:
    assert stripped_id("H100g22p1:FLOW_PATH:3") == stripped_id("H100g22p1B:FLOW_PATH:3")
    with pytest.raises(ValueError, match="<corpus>:<rest>"):
        stripped_id("FLOW_PATH")


def test_scope_r_leaves_out_x_loop_and_wording_questions() -> None:
    specs = [
        *r_specs(20),
        QSpec("OPEN_VALVES_TO_ISOLATE:0", QuestionFamily.OPEN_VALVES_TO_ISOLATE, "x-dev", True),
        QSpec("POSITION_OF_VALVE:0", QuestionFamily.POSITION_OF_VALVE, "x-dev", True),
    ]
    questions = [_question("C", s) for s in specs]
    splits = {f"C:{s.key}": s.split for s in specs}
    r_ids = r_headline_ids(questions, splits)
    assert len(r_ids) == 20 and all(f"C:{f.value}:0" in r_ids for f in R_FAMILIES)
    assert x_ids(questions) == {"C:OPEN_VALVES_TO_ISOLATE:0", "C:POSITION_OF_VALVE:0"}


def test_a_question_touches_a_network_when_an_evidence_tag_is_in_a_network_unit() -> None:
    plain = _question(
        "C", QSpec("a", QuestionFamily.FLOW_PATH, "dev-old", True, tags=("GTV-47001",))
    )
    network = _question(
        "C", QSpec("b", QuestionFamily.FLOW_PATH, "dev-old", True, tags=(NETWORK_TAG,))
    )
    assert not touches_network(plain) and touches_network(network)
