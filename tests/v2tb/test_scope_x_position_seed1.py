"""POSITION_OF_VALVE on the forced-untagged 100-sheet seed 1 plant (design `v2t-b` §10 R11, P5).

One shared build (about 20 s): the counts of the ruling's table, and the anchor of every
descriptor-form question over the dev view.
"""

from __future__ import annotations

from functools import cache

from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.valve_positions import positions_of
from plantgraph.qa.anchors import extract_anchors
from plantgraph.qa.exp0009.dev_plants import dev_corpus, forced_config
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.models import QuestionFamily
from plantgraph.qa.questions.scope_x import scope_x_candidates
from plantgraph.qa.questions.scope_x_models import FamilyOutcome, NamedBy
from plantgraph.qa.scoring import normalize_scalar

_FAMILY = QuestionFamily.POSITION_OF_VALVE


@cache
def _seed1() -> tuple[FamilyOutcome, NetworkxGraphView]:
    corpus = dev_corpus(100, 1, untagged=True)
    positions = positions_of(
        generate_plant_v2(forced_config(100, 1, untagged=True)).plan.unit_plans
    )
    outcome = scope_x_candidates(
        corpus.plant,
        corpus.manifest,
        corpus.sheets,
        positions,
        corpus_id="D100g22s1",
        seed=31,
        families=(_FAMILY,),
    )[_FAMILY]
    view = NetworkxGraphView("D100g22s1", corpus.localized_sheets, corpus.resolution)
    return outcome, view


def test_seed_1_has_the_counts_of_the_ruling() -> None:
    outcome, _view = _seed1()
    tag_form = [f for f in outcome.flags.values() if f.named_by is NamedBy.TAG]

    assert (outcome.candidates, len(outcome.refusals), len(outcome.kept)) == (1493, 113, 1380)
    assert len(tag_form) == 5


def test_a_descriptor_question_names_exactly_one_tag_and_it_is_next_to() -> None:
    outcome, view = _seed1()
    described = [
        q for q in outcome.kept if outcome.flags[q.question_id].named_by is NamedBy.DESCRIPTOR
    ]

    assert len(described) == 1375
    for question in described:
        found = extract_anchors(question.text, view)
        assert [normalize_scalar(tag.text) for tag in found.tags] == [
            normalize_scalar(question.anchors[0])
        ], question.text
        assert found.units == ()
