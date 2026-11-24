"""Task T6b (design 17.15 S2, S6): every family builds on v2.2 plants; kept questions are clean.

About 30 sheets here; the 100-sheet seeds 1-5 and the 1,000-sheet plant are the report's measurement
(`plantgraph.qa.exp0009.availability_table`), too slow for the unit suite.
"""

from __future__ import annotations

import pytest
from t6b_plants import corpus

from plantgraph.qa.exp0009.availability_table import FamilyCount, families_below, family_counts
from plantgraph.qa.models import QuestionFamily
from plantgraph.qa.questions.families import FAMILY_CANDIDATE_GENERATORS, all_candidates
from plantgraph.qa.questions.families_heldout import heldout_candidates
from plantgraph.qa.questions.untagged import carries_marker, refuse_untagged


def _counts(untagged: bool) -> list[FamilyCount]:
    synthetic = corpus(1, untagged=untagged)
    return family_counts(synthetic.plant, synthetic.manifest, synthetic.sheets, corpus_id="T6B")


@pytest.mark.parametrize("untagged", [True, False])
def test_every_registered_family_builds_without_an_exception(untagged: bool) -> None:
    built = {count.family for count in _counts(untagged)}
    assert set(FAMILY_CANDIDATE_GENERATORS) <= built


def test_a_tagged_plant_refuses_only_where_a_line_blind_is_a_source() -> None:
    # a spectacle blind at the head of a battery-limit line prints no tag, valve tagging aside
    refused = {count.family for count in _counts(untagged=False) if count.refused}
    assert refused <= {QuestionFamily.UPSTREAM_SOURCES}


def test_an_untagged_plant_refuses_candidates_in_the_families_that_name_valves() -> None:
    refused = {count.family for count in _counts(untagged=True) if count.refused}
    assert {QuestionFamily.NEIGHBOURS_DOWNSTREAM, QuestionFamily.FLOW_PATH} <= refused


def test_a_family_with_no_kept_candidate_is_listed_below_the_minimum() -> None:
    counts = [
        FamilyCount(family=QuestionFamily.FLOW_PATH, candidates=40, refused=35),
        FamilyCount(family=QuestionFamily.CONNECTED, candidates=40, refused=0),
    ]
    assert families_below(counts) == [QuestionFamily.FLOW_PATH]


@pytest.mark.parametrize("untagged", [True, False])
def test_no_kept_question_holds_the_marker(untagged: bool) -> None:
    synthetic = corpus(1, untagged=untagged)
    args = (synthetic.plant, synthetic.manifest, synthetic.sheets)
    candidates = all_candidates(*args, corpus_id="T6B", seed=31)
    candidates.update(heldout_candidates(*args, corpus_id="T6B", seed=31, v2=True))
    kept, _shares = refuse_untagged(candidates)
    assert any(kept.values())
    assert not any(carries_marker(q) for questions in kept.values() for q in questions)
