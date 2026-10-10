"""Evidence sheets of the demo: tags found in answers and questions, mapped to sheets and pages."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from demo_run_toy import question, row, write_run
from plantgraph.demo.app import estimate, evidence, models, spend
from plantgraph.demo.app.agreement import evidence_sheet_agreement
from plantgraph.demo.app.evidence import answer_sheet_links, read_sheet_links, tags_in_text
from plantgraph.demo.app.models import SheetLink
from plantgraph.qa.models import AnswerType, FinalAnswer
from qa_plant_api_toy import build_graph, toy_graph

#: The toy plant's sheets: S1 holds T1/BV1, S2 holds P1/GV2, S3 holds V2.
PAGES = {"S1": 1, "S2": 2, "S3": 3}


def _answer(value: str | list[str]) -> FinalAnswer:
    return FinalAnswer(answer=value, not_present=False)


def _sheets(links: tuple[SheetLink, ...]) -> list[tuple[str, tuple[str, ...]]]:
    return [(link.sheet_id, link.tags) for link in links]


def test_tag_set_answer_shows_the_union_of_its_items_sheets() -> None:
    links = answer_sheet_links(
        "Which items follow the pump?",
        AnswerType.TAG_SET,
        _answer(["GV2", "V2"]),
        toy_graph(),
        PAGES,
    )

    assert _sheets(links) == [("S2", ("GV2",)), ("S3", ("V2",))]
    assert [link.page for link in links] == [2, 3]


def test_boolean_answer_shows_the_sheets_of_the_questions_anchor_tags() -> None:
    links = answer_sheet_links(
        "Is T1 connected to V2?", AnswerType.BOOLEAN, _answer("yes"), toy_graph(), PAGES
    )

    assert _sheets(links) == [("S1", ("T1",)), ("S3", ("V2",))]


def test_free_text_answer_finds_tags_with_the_plant_apis_matching() -> None:
    # lower case still matches, as `ids_for_tag` folds case; plain words are not tags
    answer = _answer("The flow leaves p1 and reaches gv2, a globe valve.")
    links = answer_sheet_links("What follows?", AnswerType.FREE_TEXT, answer, toy_graph(), PAGES)

    assert _sheets(links) == [("S2", ("p1", "gv2"))]


def test_words_that_are_not_plant_tags_are_ignored() -> None:
    assert tags_in_text("Is X9 near T1 on page 4?", toy_graph()) == ["T1"]


def test_an_item_drawn_on_two_sheets_shows_both() -> None:
    graph = build_graph({"A1": ("Tank", "1", ("S1", "S3"))}, [])
    links = answer_sheet_links("Where is A1?", AnswerType.COUNT, _answer("2"), graph, PAGES)

    assert [link.sheet_id for link in links] == ["S1", "S3"]


def test_a_sheet_missing_from_the_drawing_index_is_refused() -> None:
    with pytest.raises(ValueError, match="missing"):
        answer_sheet_links("T1?", AnswerType.BOOLEAN, _answer("yes"), toy_graph(), {"S2": 2})


def test_read_sheets_link_to_pages_without_tags() -> None:
    links = read_sheet_links(["S3", "S1"], PAGES)

    assert _sheets(links) == [("S1", ()), ("S3", ())]


def test_agreement_measures_precision_and_recall_against_gold(tmp_path: Path) -> None:
    questions = [
        question("q1", "Is T1 connected to V2?", AnswerType.BOOLEAN, ["S1", "S2", "S3"]),
        question("q2", "Which items follow P1?", AnswerType.TAG_SET, ["S2"]),
    ]
    rows = [row("q1", "s", 0.0, "yes"), row("q2", "s", 0.0, ["GV2", "V2"])]
    run_dir = write_run(tmp_path, "toy-run", "TOY", rows)

    report = evidence_sheet_agreement(run_dir, "s", questions, toy_graph())

    # q1 shows S1,S3 (both gold, 2 of 3 gold found); q2 shows P1's S2 plus GV2's S2 and V2's S3
    assert report.n_questions == 2
    assert report.precision == pytest.approx((1.0 + 0.5) / 2)
    assert report.recall == pytest.approx((2 / 3 + 1.0) / 2)


def test_display_code_imports_no_gold_module() -> None:
    for module in (evidence, estimate, spend, models):
        tree = ast.parse(Path(module.__file__ or "").read_text(encoding="utf-8"))
        imported = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert [m for m in imported if "gold" in m] == [], module.__name__
