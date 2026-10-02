"""RU-T8: `SHEETS_OF_TAG`, its `SHEET_SET` answer type, scoring and the format instruction."""

from __future__ import annotations

import networkx as nx

from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.models import IdentityGroup, SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.ingest.pipeline import build_synthetic_corpus
from plantgraph.qa.models import AnswerType, FinalAnswer, Outcome, Question, QuestionFamily
from plantgraph.qa.questions.availability import KBin, k_bin_of
from plantgraph.qa.questions.families import FAMILY_CANDIDATE_GENERATORS
from plantgraph.qa.questions.families_identity import sheets_of_tag_candidates
from plantgraph.qa.scoring import score_answer, score_set
from qa_toy_plant import (
    N_VALVE,
    SHEET_1,
    SHEET_2,
    SHEET_3,
    TAG_VALVE,
    build_toy_manifest,
    build_toy_plant,
    build_toy_sheets,
)

_CORPUS = "toy"


def _valve_drawn_on_three_sheets() -> tuple[nx.DiGraph[str], list[SheetGraph], SplitManifest]:
    """The toy plant with VALVE (home S2) also drawn on S1 and S3."""
    plant = build_toy_plant()
    sheets = build_toy_sheets(plant)
    for sheet in sheets:
        if sheet.sheet_id in (SHEET_1, SHEET_3):
            sheet.graph.add_node(N_VALVE, **plant.nodes[N_VALVE])
    manifest = build_toy_manifest()
    manifest.identity_groups = [
        IdentityGroup(
            tag=TAG_VALVE,
            home=f"{SHEET_2}:{N_VALVE}",
            references=[f"{SHEET_1}:{N_VALVE}", f"{SHEET_3}:{N_VALVE}"],
        )
    ]
    return plant, sheets, manifest


def _toy_candidates() -> list[Question]:
    plant, sheets, manifest = _valve_drawn_on_three_sheets()
    return sheets_of_tag_candidates(plant, manifest, sheets, corpus_id=_CORPUS, seed=0)


def test_the_family_is_registered() -> None:
    assert FAMILY_CANDIDATE_GENERATORS[QuestionFamily.SHEETS_OF_TAG] is sheets_of_tag_candidates


def test_group_question_lists_home_and_reference_sheets_with_k_equal_to_the_references() -> None:
    group_question = next(q for q in _toy_candidates() if q.anchors == [TAG_VALVE])

    assert group_question.text == f"On which sheets is {TAG_VALVE} drawn?"
    assert group_question.answer_type is AnswerType.SHEET_SET
    assert group_question.reference == [SHEET_1, SHEET_2, SHEET_3]
    assert (group_question.k, group_question.k_connector, group_question.k_identity) == (2, 0, 2)
    assert group_question.evidence_sheets == [SHEET_1, SHEET_2, SHEET_3]
    assert k_bin_of(group_question) is KBin.K2


def test_every_group_gets_one_single_sheet_control_with_k_zero() -> None:
    questions = _toy_candidates()
    controls = [q for q in questions if q.anchors != [TAG_VALVE]]

    assert len(questions) == 2
    assert len(controls) == 1
    assert controls[0].k == 0
    assert isinstance(controls[0].reference, list) and len(controls[0].reference) == 1


def test_candidates_are_deterministic_and_the_seed_moves_only_the_controls() -> None:
    plant, sheets, manifest = _valve_drawn_on_three_sheets()

    def run(seed: int) -> list[Question]:
        return sheets_of_tag_candidates(plant, manifest, sheets, corpus_id=_CORPUS, seed=seed)

    assert run(3) == run(3)
    assert [q.question_id for q in run(3) if q.k] == [q.question_id for q in run(4) if q.k]


def test_no_identity_groups_means_no_candidates() -> None:
    plant = build_toy_plant()

    questions = sheets_of_tag_candidates(
        plant, build_toy_manifest(), build_toy_sheets(plant), corpus_id=_CORPUS, seed=0
    )

    assert questions == []


def test_references_on_a_duplicated_synthetic_corpus_equal_the_manifest_group_sheets() -> None:
    corpus = build_synthetic_corpus(
        GeneratorConfig(n_units=10, seed=0),
        SplitConfig(sheet_equipment_budget=8, seed=0, duplication_rate=0.25),
    )
    groups = {group.tag: group for group in corpus.manifest.identity_groups}
    assert groups

    questions = sheets_of_tag_candidates(
        corpus.plant, corpus.manifest, corpus.sheets, corpus_id=_CORPUS, seed=0
    )

    by_tag = {q.anchors[0]: q for q in questions}
    for tag, group in groups.items():
        occurrence_keys = [group.home, *group.references]
        expected = sorted({key.split(":")[0] for key in occurrence_keys})
        assert by_tag[tag].reference == expected
        assert by_tag[tag].k == len(group.references) >= 1
    controls = [q for q in questions if q.anchors[0] not in groups]
    assert len(controls) == len(groups)
    assert all(q.k == 0 and len(q.evidence_sheets) == 1 for q in controls)


def test_sheet_set_scoring_ignores_order_case_and_duplicates() -> None:
    result = score_set(["S1", "S2", "S3"], ["s3", "S1", "S2", "S2"])

    assert result.correct is True


def test_sheet_set_answer_with_a_missing_sheet_is_wrong_but_has_partial_f1() -> None:
    question = _toy_candidates()[0]

    scored = score_answer(
        question, Outcome.ANSWERED, FinalAnswer(answer=["S2", "S1"], not_present=False)
    )

    assert scored.correct is False
    assert scored.f1 is not None and 0.0 < scored.f1 < 1.0


def test_sheet_set_answer_in_another_order_scores_correct_end_to_end() -> None:
    question = _toy_candidates()[0]

    scored = score_answer(
        question, Outcome.ANSWERED, FinalAnswer(answer=["S3", "S1", "S2"], not_present=False)
    )

    assert scored.correct is True
