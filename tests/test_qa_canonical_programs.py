"""API-02: every dev family's canonical primitive program reproduces its reference answers.

Run on the three hand-built toy plants and on one generated, split and resolved corpus, so a
program is checked both against hand-counted answers and against the real resolver's output.
"""

from __future__ import annotations

import networkx as nx
import pytest

import qa_toy_plant
import qa_toy_plant_dev2
import qa_toy_plant_t7
from graph_plant_builder import GraphPlantBuilder
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.harness.api_expressiveness import (
    evaluate_programs,
    output_equals_reference,
    render_table,
    sample_per_family,
)
from plantgraph.qa.harness.canonical_programs import PROGRAMS, run_canonical_program
from plantgraph.qa.models import AnswerType, Question, QuestionFamily
from plantgraph.qa.plant_api.item_graph import ItemGraph, build_item_graph
from plantgraph.qa.questions.families import FAMILY_CANDIDATE_GENERATORS, all_candidates
from plantgraph.resolution.localize import localize
from plantgraph.resolution.resolver import resolve
from qa_plant_api_toy import EdgeSpecs, ItemSpecs, build_graph

_TOYS = {
    "base": (
        qa_toy_plant.build_toy_plant,
        qa_toy_plant.build_toy_sheets,
        qa_toy_plant.build_toy_manifest,
    ),
    "t7": (
        qa_toy_plant_t7.build_plant,
        qa_toy_plant_t7.build_sheets,
        qa_toy_plant_t7.build_manifest,
    ),
    "dev2": (
        qa_toy_plant_dev2.build_plant,
        qa_toy_plant_dev2.build_sheets,
        qa_toy_plant_dev2.build_manifest,
    ),
}


def _toy_item_graph(plant: nx.DiGraph[str], sheets: list[SheetGraph]) -> ItemGraph:
    """The item graph a perfect resolver would build from the toy: one item per node, by tag."""
    sheet_of = {node: sheet.sheet_id for sheet in sheets for node in sheet.graph.nodes}
    tag_of = {node: str(data["tag"]) for node, data in plant.nodes(data=True)}
    items: ItemSpecs = {
        tag_of[node]: (data["node_class"], data.get("unit_id"), (sheet_of[node],))
        for node, data in plant.nodes(data=True)
    }
    edges: EdgeSpecs = [
        (tag_of[source], data["relation"], tag_of[target], ())
        for source, target, data in plant.edges(data=True)
    ]
    return build_graph(items, edges)


def _candidates(
    plant: nx.DiGraph[str], manifest: SplitManifest, sheets: list[SheetGraph]
) -> dict[QuestionFamily, list[Question]]:
    return all_candidates(plant, manifest, sheets, corpus_id="toy", seed=0)


@pytest.mark.parametrize("toy", sorted(_TOYS))
def test_every_program_equals_the_reference_on_every_toy_candidate(toy: str) -> None:
    build_plant, build_sheets, build_manifest = _TOYS[toy]
    plant = build_plant()
    sheets = build_sheets(plant)
    graph = _toy_item_graph(plant, sheets)
    candidates = _candidates(plant, build_manifest(), sheets)

    wrong = [
        q.question_id
        for questions in candidates.values()
        for q in questions
        if not output_equals_reference(q, run_canonical_program(graph, q))
    ]

    assert wrong == []
    assert sum(len(questions) for questions in candidates.values()) > 20


def test_the_dev2_toy_exercises_every_dev_new_family() -> None:
    plant = qa_toy_plant_dev2.build_plant()
    candidates = _candidates(
        plant, qa_toy_plant_dev2.build_manifest(), qa_toy_plant_dev2.build_sheets(plant)
    )

    for family in (
        QuestionFamily.CONNECTED,
        QuestionFamily.DOWNSTREAM_IN_UNIT,
        QuestionFamily.INSTRUMENTS_OF_ITEM,
        QuestionFamily.UPSTREAM_SOURCES,
        QuestionFamily.SAME_UNIT,
        QuestionFamily.LOOPS_NEAR_ITEM,
    ):
        assert candidates[family], family


def test_every_family_has_exactly_one_program() -> None:
    assert set(PROGRAMS) == set(QuestionFamily) == set(FAMILY_CANDIDATE_GENERATORS)


def test_programs_reproduce_the_reference_on_a_resolved_corpus_with_duplicated_drawings() -> None:
    config = GeneratorConfig(seed=7)
    builder = GraphPlantBuilder(config.plant_id)
    plan_plant(config, builder)
    sheets, manifest = split(
        builder.graph, SplitConfig(sheet_equipment_budget=2, seed=7, duplication_rate=0.5)
    )
    localized, _ = localize(sheets)
    graph = build_item_graph(NetworkxGraphView("gen", localized, resolve(localized)))
    candidates = all_candidates(builder.graph, manifest, sheets, corpus_id="gen", seed=7)

    sample = sample_per_family(candidates, 40, seed=0)
    rows = evaluate_programs(sample, graph)

    assert set(rows) == set(QuestionFamily)
    assert {family: row.share for family, row in rows.items()} == {
        f: 1.0 for f in QuestionFamily
    }, render_table(rows)


# --- the comparison itself must be able to say no -----------------------------------------------


def _question(answer_type: AnswerType, reference: object, *, answerable: bool = True) -> Question:
    return Question(
        question_id="q",
        corpus_id="c",
        family=QuestionFamily.NEIGHBOURS_DOWNSTREAM,
        template_id="t",
        template_version="1",
        text="?",
        answer_type=answer_type,
        answerable=answerable,
        reference=reference,  # type: ignore[arg-type]
        generator_seed=0,
    )


def test_a_set_output_must_equal_the_reference_set() -> None:
    question = _question(AnswerType.TAG_SET, ["A", "B"])

    assert output_equals_reference(question, ["b", "A"])
    assert not output_equals_reference(question, ["A"])
    assert not output_equals_reference(question, ["A", "B", "C"])
    assert not output_equals_reference(question, None)


def test_a_path_output_must_be_the_reference_route_not_just_a_valid_one() -> None:
    question = _question(AnswerType.TAG_PATH, ["A", "B", "C"])

    assert output_equals_reference(question, ["A", "B", "C"])
    assert not output_equals_reference(question, ["A", "C"])


def test_an_unanswerable_question_expects_not_present() -> None:
    question = _question(AnswerType.TAG_SET, None, answerable=False)

    assert output_equals_reference(question, None)
    assert not output_equals_reference(question, ["A"])


def test_a_boolean_output_is_compared_as_yes_or_no() -> None:
    question = _question(AnswerType.BOOLEAN, "yes")

    assert output_equals_reference(question, "yes")
    assert not output_equals_reference(question, "no")


def test_a_program_that_a_primitive_rejects_is_counted_as_an_error() -> None:
    plant = qa_toy_plant_dev2.build_plant()
    graph = _toy_item_graph(plant, qa_toy_plant_dev2.build_sheets(plant))
    wrong_family = _question(AnswerType.TAG_SET, ["X"]).model_copy(
        update={"anchors": ["NOT-A-TAG"], "family": QuestionFamily.NEIGHBOURS_DOWNSTREAM}
    )
    sheets = qa_toy_plant_dev2.build_sheets(plant)
    candidates = _candidates(plant, qa_toy_plant_dev2.build_manifest(), sheets)
    right = candidates[QuestionFamily.INSTRUMENTS_OF_ITEM]

    rows = evaluate_programs([wrong_family, *right], graph)

    assert rows[QuestionFamily.NEIGHBOURS_DOWNSTREAM].n_errors == 1
    assert rows[QuestionFamily.NEIGHBOURS_DOWNSTREAM].share == 0.0
    assert rows[QuestionFamily.INSTRUMENTS_OF_ITEM].share == 1.0
