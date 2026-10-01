"""`qa.questions.families*` — reference answers and `k` for QA-T6's families.

Uses the hand-built, hand-split toy plant from `tests/qa_toy_plant.py` so
every expected `k` can be verified by a human counting cut edges, plus two
corpora built through the real generator and splitter: a single-sheet one
(k must be 0 everywhere, since nothing was cut) and a ~25-unit one (to
report how many candidates each family yields at a realistic size).
"""

from __future__ import annotations

from collections import Counter

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.ingest.pipeline import build_synthetic_corpus
from plantgraph.qa.models import Question, QuestionFamily
from plantgraph.qa.questions.families import all_candidates
from plantgraph.qa.questions.families_flow import (
    flow_path_candidates,
    neighbours_downstream_candidates,
)
from plantgraph.qa.questions.families_lookup import lookup_type_candidates, lookup_unit_candidates
from plantgraph.qa.questions.families_loop import (
    loop_actuated_valve_candidates,
    loop_measured_equipment_candidates,
)
from qa_toy_plant import (
    N_ACTUATOR,
    N_CONTROLLER,
    N_PUMP,
    N_SENSOR,
    N_TANK,
    N_TANK_U2,
    N_VALVE,
    N_VESSEL,
    TAG_LOOP,
    TAG_PUMP,
    TAG_TANK,
    TAG_TANK_U2,
    TAG_VALVE,
    TAG_VESSEL,
    build_toy_manifest,
    build_toy_plant,
    build_toy_sheets,
)

_CORPUS_ID = "qa-toy"
_SEED = 0
_UNANSWERABLE_FAMILIES = {QuestionFamily.UNANSWERABLE_TAG, QuestionFamily.NO_PATH}

# Every internal node id in the toy plant — used to prove a question never
# names an item by its gold id (design "Question text refers to items by
# what is printed on the drawings").
_INTERNAL_IDS = (N_TANK, N_VALVE, N_PUMP, N_VESSEL, N_TANK_U2, N_SENSOR, N_CONTROLLER, N_ACTUATOR)


def _by_anchor(questions: list[Question], anchor: str) -> Question:
    matching = [q for q in questions if q.anchors and q.anchors[0] == anchor]
    assert len(matching) == 1, f"expected exactly one candidate anchored on {anchor!r}"
    return matching[0]


def test_lookup_type_is_the_nodes_own_class_and_k_is_always_zero() -> None:
    plant = build_toy_plant()
    manifest = build_toy_manifest()
    sheets = build_toy_sheets(plant)

    questions = lookup_type_candidates(plant, manifest, sheets, corpus_id=_CORPUS_ID, seed=_SEED)
    question = _by_anchor(questions, TAG_TANK)

    # LOOKUP_TYPE reads one node's own `node_class` property, no edge at
    # all — there is nothing for an off-page connector to stand between.
    assert question.reference == "Tank"
    assert question.k == 0


def test_lookup_unit_is_the_nodes_own_unit_and_k_is_always_zero() -> None:
    plant = build_toy_plant()
    manifest = build_toy_manifest()
    sheets = build_toy_sheets(plant)

    questions = lookup_unit_candidates(plant, manifest, sheets, corpus_id=_CORPUS_ID, seed=_SEED)
    question = _by_anchor(questions, TAG_TANK_U2)

    assert question.reference == "2"
    assert question.k == 0


def test_neighbours_downstream_k_matches_whether_the_one_edge_is_cut() -> None:
    plant = build_toy_plant()
    manifest = build_toy_manifest()
    sheets = build_toy_sheets(plant)

    questions = neighbours_downstream_candidates(
        plant, manifest, sheets, corpus_id=_CORPUS_ID, seed=_SEED
    )

    # TANK->VALVE crosses S1->S2: it is one of the four hand-cut edges, so k=1.
    tank_question = _by_anchor(questions, TAG_TANK)
    assert tank_question.reference == [TAG_VALVE]
    assert tank_question.k == 1

    # VESSEL->TANK_U2 stays on S4 with both ends: not cut, so k=0.
    vessel_question = _by_anchor(questions, TAG_VESSEL)
    assert vessel_question.reference == [TAG_TANK_U2]
    assert vessel_question.k == 0


def test_loop_actuated_valve_walks_controller_to_actuator_to_valve() -> None:
    plant = build_toy_plant()
    manifest = build_toy_manifest()
    sheets = build_toy_sheets(plant)

    questions = loop_actuated_valve_candidates(
        plant, manifest, sheets, corpus_id=_CORPUS_ID, seed=_SEED
    )
    question = _by_anchor(questions, TAG_LOOP)

    # Both evidence edges (CONTROLLER->ACTUATOR, ACTUATOR->VALVE) stay on S2: k=0.
    assert question.reference == TAG_VALVE
    assert question.k == 0


def test_loop_measured_equipment_walks_sensor_to_controller_back_to_equipment() -> None:
    plant = build_toy_plant()
    manifest = build_toy_manifest()
    sheets = build_toy_sheets(plant)

    questions = loop_measured_equipment_candidates(
        plant, manifest, sheets, corpus_id=_CORPUS_ID, seed=_SEED
    )
    question = _by_anchor(questions, TAG_LOOP)

    # TANK->SENSOR stays on S1 (not cut); SENSOR->CONTROLLER crosses S1->S2
    # (one of the four hand-cut edges): k=1.
    assert question.reference == TAG_TANK
    assert question.k == 1


def test_flow_path_k_counts_every_cut_edge_on_the_chosen_path() -> None:
    plant = build_toy_plant()
    manifest = build_toy_manifest()
    sheets = build_toy_sheets(plant)

    questions = flow_path_candidates(plant, manifest, sheets, corpus_id=_CORPUS_ID, seed=_SEED)

    # TANK -> TANK_U2: the full chain TANK->VALVE->PUMP->VESSEL->TANK_U2.
    # Three of its four edges are cut (TANK->VALVE, VALVE->PUMP,
    # PUMP->VESSEL); VESSEL->TANK_U2 stays on S4: k=3.
    full_path = next(q for q in questions if q.anchors == [TAG_TANK, TAG_TANK_U2])
    assert full_path.reference == [TAG_TANK, TAG_VALVE, TAG_PUMP, TAG_VESSEL, TAG_TANK_U2]
    assert full_path.k == 3

    # PUMP -> TANK_U2: PUMP->VESSEL->TANK_U2. Only PUMP->VESSEL is cut: k=1.
    pump_to_u2 = next(q for q in questions if q.anchors == [TAG_PUMP, TAG_TANK_U2])
    assert pump_to_u2.reference == [TAG_PUMP, TAG_VESSEL, TAG_TANK_U2]
    assert pump_to_u2.k == 1

    # VALVE -> VESSEL: VALVE->PUMP->VESSEL. Both edges are cut: k=2.
    valve_to_vessel = next(q for q in questions if q.anchors == [TAG_VALVE, TAG_VESSEL])
    assert valve_to_vessel.reference == [TAG_VALVE, TAG_PUMP, TAG_VESSEL]
    assert valve_to_vessel.k == 2


def test_no_question_text_names_an_internal_node_id() -> None:
    plant = build_toy_plant()
    manifest = build_toy_manifest()
    sheets = build_toy_sheets(plant)

    for family_questions in all_candidates(
        plant, manifest, sheets, corpus_id=_CORPUS_ID, seed=_SEED
    ).values():
        for question in family_questions:
            for internal_id in _INTERNAL_IDS:
                assert internal_id not in question.text


def test_candidate_generation_is_deterministic() -> None:
    plant = build_toy_plant()
    manifest = build_toy_manifest()
    sheets = build_toy_sheets(plant)

    first = all_candidates(plant, manifest, sheets, corpus_id=_CORPUS_ID, seed=_SEED)
    second = all_candidates(plant, manifest, sheets, corpus_id=_CORPUS_ID, seed=_SEED)

    for family in first:
        assert [q.question_id for q in first[family]] == [q.question_id for q in second[family]]


def test_every_k_is_zero_on_a_single_sheet_corpus() -> None:
    """With nothing cut, every family's evidence must report k=0 (design §16, property test)."""
    corpus = build_synthetic_corpus(
        GeneratorConfig(n_units=3, seed=0),
        # a budget far above this plant's total equipment forces one sheet
        SplitConfig(sheet_equipment_budget=1000, seed=0),
    )
    assert len(corpus.sheets) == 1, "test setup expected a single-sheet split"

    candidates = all_candidates(
        corpus.plant, corpus.manifest, corpus.sheets, corpus_id="qa-single-sheet", seed=0
    )

    for family, questions in candidates.items():
        assert questions, f"{family} produced no candidates on the single-sheet corpus"
        # an unanswerable question has no evidence, hence no k at all (design 9)
        expected_k = None if family in _UNANSWERABLE_FAMILIES else 0
        assert all(q.k == expected_k for q in questions), f"{family} had a wrong k, nothing cut"


def test_candidate_counts_and_k_distribution_on_a_25_unit_corpus() -> None:
    """Measures (not estimates) how many candidates each family yields at a realistic size."""
    corpus = build_synthetic_corpus(
        GeneratorConfig(n_units=25, seed=0), SplitConfig(sheet_equipment_budget=16, seed=0)
    )

    candidates = all_candidates(
        corpus.plant, corpus.manifest, corpus.sheets, corpus_id="qa-25-units", seed=0
    )

    report = {
        family.value: {
            "n_candidates": len(questions),
            "k_distribution": dict(sorted(Counter(q.k for q in questions).items())),
        }
        for family, questions in candidates.items()
    }
    print(f"\nQA-T6 25-unit/budget-16 candidate report: {report}")

    for family, stats in report.items():
        assert stats["n_candidates"] > 0, f"{family} produced no candidates"
