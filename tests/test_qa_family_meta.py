"""Family split and gold need labels (gold side), the dev-old-only switch, and the import ban."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import qa_toy_plant_dev2
import qa_toy_plant_t7
from plantgraph.qa.harness.family_meta import FAMILY_META, FamilySplit, families_of_split
from plantgraph.qa.harness.need_gold import gold_need_of, gold_need_of_family
from plantgraph.qa.models import QuestionFamily
from plantgraph.qa.need.labels import NeedLabel
from plantgraph.qa.questions.families import (
    DEV_NEW_GENERATORS,
    DEV_OLD_GENERATORS,
    all_candidates,
)

_QA_DIR = Path(__file__).resolve().parent.parent / "src" / "plantgraph" / "qa"


def test_twelve_families_are_dev_old_and_six_are_dev_new() -> None:
    assert set(FAMILY_META) == set(QuestionFamily)
    assert len(families_of_split(FamilySplit.DEV_OLD)) == 12
    assert {f.value for f in families_of_split(FamilySplit.DEV_NEW)} == {
        "CONNECTED",
        "DOWNSTREAM_IN_UNIT",
        "INSTRUMENTS_OF_ITEM",
        "UPSTREAM_SOURCES",
        "SAME_UNIT",
        "LOOPS_NEAR_ITEM",
    }


def test_gold_need_of_the_dev_new_families_follows_the_design_table() -> None:
    expected = {
        QuestionFamily.CONNECTED: NeedLabel.PATH,
        QuestionFamily.DOWNSTREAM_IN_UNIT: NeedLabel.DOWNSTREAM_ALL,
        QuestionFamily.INSTRUMENTS_OF_ITEM: NeedLabel.SIGNAL_CHAIN,
        QuestionFamily.UPSTREAM_SOURCES: NeedLabel.UPSTREAM_ALL,
        QuestionFamily.SAME_UNIT: NeedLabel.ITEM,
        QuestionFamily.LOOPS_NEAR_ITEM: NeedLabel.GENERIC,
    }

    for family, label in expected.items():
        assert FAMILY_META[family].gold_need == {label}, family


def test_gold_need_of_the_dev_old_families_follows_what_each_reads() -> None:
    assert gold_need_of_family(QuestionFamily.UPSTREAM_ISOLATION) == {
        NeedLabel.UPSTREAM_TO_FIRST_VALVE
    }
    assert gold_need_of_family(QuestionFamily.LOOP_ACTUATED_VALVE) == {NeedLabel.SIGNAL_CHAIN}
    assert gold_need_of_family(QuestionFamily.COUNT_IN_UNIT) == {NeedLabel.UNIT_SCOPE}
    assert gold_need_of_family(QuestionFamily.NO_PATH) == {NeedLabel.PATH}


def test_an_unanswerable_question_takes_the_label_of_the_template_it_wraps() -> None:
    # the t7 toy's tags follow the PREFIX-unit-seq grammar, so absent tags can be minted
    plant = qa_toy_plant_t7.build_plant()
    candidates = all_candidates(
        plant,
        qa_toy_plant_t7.build_manifest(),
        qa_toy_plant_t7.build_sheets(plant),
        corpus_id="t",
        seed=0,
    )
    labels = {q.template_id: gold_need_of(q) for q in candidates[QuestionFamily.UNANSWERABLE_TAG]}

    assert labels == {
        "LOOKUP_TYPE": {NeedLabel.ITEM},
        "NEIGHBOURS_DOWNSTREAM": {NeedLabel.NEIGHBOURS_DOWNSTREAM},
        "FLOW_PATH": {NeedLabel.PATH},
    }
    assert gold_need_of_family(QuestionFamily.UNANSWERABLE_TAG) == {
        NeedLabel.ITEM,
        NeedLabel.NEIGHBOURS_DOWNSTREAM,
        NeedLabel.PATH,
    }


def test_the_dev_old_only_switch_gives_the_old_candidates_unchanged() -> None:
    plant = qa_toy_plant_dev2.build_plant()
    args = (plant, qa_toy_plant_dev2.build_manifest(), qa_toy_plant_dev2.build_sheets(plant))

    everything = all_candidates(*args, corpus_id="t", seed=0)
    old_only = all_candidates(*args, corpus_id="t", seed=0, families=list(DEV_OLD_GENERATORS))

    assert set(old_only) == set(DEV_OLD_GENERATORS)
    assert set(everything) == set(DEV_OLD_GENERATORS) | set(DEV_NEW_GENERATORS)
    assert all(old_only[f] == everything[f] for f in old_only)


# --- import ban: gold-side modules never reach a strategy or the plant API ----------------------

_BANNED_FOR_STRATEGY_SIDE = (
    "plantgraph.qa.harness",
    "plantgraph.qa.questions",
    "plantgraph.qa.corpus",
)
_STRATEGY_SIDE_FILES = tuple(
    sorted([*(_QA_DIR / "strategies").glob("*.py"), *(_QA_DIR / "need").glob("*.py")])
)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


@pytest.mark.parametrize("path", _STRATEGY_SIDE_FILES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_strategy_side_modules_never_import_the_gold_side(path: Path) -> None:
    banned = {
        module
        for module in _imported_modules(path)
        for prefix in _BANNED_FOR_STRATEGY_SIDE
        if module == prefix or module.startswith(f"{prefix}.")
    }

    assert not banned, f"{path.name} imports gold-side module(s) {banned}"


def test_the_need_label_module_imports_nothing_from_the_package() -> None:
    modules = _imported_modules(_QA_DIR / "need" / "labels.py")

    assert not {m for m in modules if m.startswith("plantgraph")}
