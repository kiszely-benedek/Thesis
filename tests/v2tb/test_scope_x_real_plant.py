"""Scope X on a small real v2.2 plant (8 units, seed 1): builds, and kept questions are clean."""

from __future__ import annotations

from functools import cache

from plants_b import real_corpus

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.plan_models import OperatingPosition
from plantgraph.benchmark.v2.valve_positions import positions_of
from plantgraph.qa.models import AnswerType, QuestionFamily
from plantgraph.qa.questions.scope_x import FamilyOutcome, scope_x_candidates
from plantgraph.qa.questions.untagged import UNTAGGED_MARKER, carries_marker
from plantgraph.qa.v2tb.descriptor import PlantIndex
from plantgraph.qa.v2tb.scoring_b import reference_nodes
from plantgraph.qa.v2tb.visible import POSITION_CODES


@cache
def _positions() -> dict[str, OperatingPosition]:
    plan = generate_plant_v2(GeneratorConfigV22(seed=1, n_units=8)).plan
    return positions_of(plan.unit_plans)


@cache
def _outcomes() -> dict[QuestionFamily, FamilyOutcome]:
    corpus = real_corpus()
    return scope_x_candidates(
        corpus.plant, corpus.manifest, corpus.sheets, _positions(), corpus_id="REAL", seed=31
    )


def test_every_family_builds_and_every_candidate_is_kept_or_refused() -> None:
    for outcome in _outcomes().values():
        assert outcome.candidates == len(outcome.kept) + len(outcome.refusals), outcome.family


def test_every_kept_reference_resolves_to_real_valves_and_never_holds_the_marker() -> None:
    index = PlantIndex(real_corpus().plant)
    for outcome in _outcomes().values():
        for question in outcome.kept:
            assert not carries_marker(question)
            if question.answer_type is AnswerType.VALVE_SET:
                assert isinstance(question.reference, list) and question.reference
                assert reference_nodes(index, question.reference)
                assert UNTAGGED_MARKER not in str(question.reference)


def test_position_questions_carry_one_of_the_six_codes() -> None:
    kept = _outcomes()[QuestionFamily.POSITION_OF_VALVE].kept

    assert {q.reference for q in kept} <= set(POSITION_CODES)


def test_the_build_is_deterministic() -> None:
    corpus = real_corpus()
    again = scope_x_candidates(
        corpus.plant, corpus.manifest, corpus.sheets, _positions(), corpus_id="REAL", seed=31
    )

    assert again == _outcomes()
