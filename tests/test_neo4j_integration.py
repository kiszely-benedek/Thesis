"""Opt-in integration test: `load_corpus` against a live Neo4j database (design §7.7).

The whole module is skipped unless `NEO4J_URI`, `NEO4J_USERNAME` and
`NEO4J_PASSWORD` are all set (directly, or via the git-ignored `.env` file
`neo4j_settings.py` reads) *and* the database actually answers within a few
seconds (`conftest.neo4j_skip_reason`) — no other test in the suite touches a
live database. Every test here loads a dedicated, disposable `corpus_id` and
wipes it again in a `finally`, so a run can never leave data behind or
collide with another corpus in the same database.

Only a tiny corpus is loaded here: a 4-unit generated plant, and EX01 (36
nodes) when the file is present. The first load at plant scale (SMOKE-05,
~2,900 units) is judged separately against the K-NEO kill threshold
(`kg-construction.md` §7.6) and does not belong in a pytest run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import neo4j_skip_reason
from graph_plant_builder import GraphPlantBuilder
from plantgraph.adapters.pydexpi_proteus_import import import_proteus_sheet
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.resolution.localize import localize
from plantgraph.resolution.models import Resolution
from plantgraph.resolution.resolver import resolve
from plantgraph.store.neo4j_loader import LoadReport, load_corpus, wipe_corpus
from plantgraph.store.neo4j_plan import build_load_plan
from plantgraph.store.neo4j_settings import Neo4jSettings, from_env

_EX01_PATH = Path(__file__).resolve().parent.parent / "data" / "external" / "C01V04-VER.EX01.xml"

#: never a real experiment's id, so this test can never collide with one.
_CORPUS_ID = "pytest-kg-construction"

_skip_reason = neo4j_skip_reason()
pytestmark = pytest.mark.skipif(_skip_reason is not None, reason=_skip_reason or "")


def _small_corpus() -> tuple[list[SheetGraph], Resolution]:
    """A 4-unit generated plant, split so a connector pair and an identity group both exist."""
    generator_config = GeneratorConfig(seed=7)
    builder = GraphPlantBuilder(generator_config.plant_id)
    plan_plant(generator_config, builder)
    split_config = SplitConfig(sheet_equipment_budget=2, seed=7, duplication_rate=0.5)
    sheets, _manifest = split(builder.graph, split_config)
    localized, _occurrence_map = localize(sheets)
    return localized, resolve(localized)


def _ex01_corpus() -> tuple[list[SheetGraph], Resolution] | None:
    """`None` (not a pytest skip) when the untracked file is absent — the caller skips instead."""
    if not _EX01_PATH.exists():
        return None
    imported = import_proteus_sheet(_EX01_PATH)
    localized, _occurrence_map = localize([imported.sheet])
    return localized, resolve(localized)


def _settings() -> Neo4jSettings:
    settings = from_env()
    if settings is None:
        raise RuntimeError("pytestmark should have skipped this module when settings are absent")
    return settings


def _expected_node_count(sheets: list[SheetGraph]) -> int:
    corpus_and_sheets = 1 + len(sheets)
    occurrences = sum(sheet.graph.number_of_nodes() for sheet in sheets)
    units = len(_drawn_values(sheets, "unit_id"))
    plants = len(_drawn_values(sheets, "plant_id"))
    return corpus_and_sheets + occurrences + units + plants


def _drawn_values(sheets: list[SheetGraph], key: str) -> set[object]:
    """Distinct values of one visible node property, read straight from the sheets."""
    return {
        attrs[key]
        for sheet in sheets
        for _node_id, attrs in sheet.graph.nodes(data=True)
        if key in attrs
    }


def _located_in_count(sheets: list[SheetGraph]) -> int:
    """Occurrences that show a unit, plus one unit -> plant link per unit with a plant."""
    with_unit = [
        attrs
        for sheet in sheets
        for _node_id, attrs in sheet.graph.nodes(data=True)
        if "unit_id" in attrs
    ]
    units_in_plants = {attrs["unit_id"] for attrs in with_unit if "plant_id" in attrs}
    return len(with_unit) + len(units_in_plants)


def _expected_relationship_count(sheets: list[SheetGraph], resolution: Resolution) -> int:
    has_sheet = len(sheets)
    is_drawn_on = sum(sheet.graph.number_of_nodes() for sheet in sheets)
    topology = sum(sheet.graph.number_of_edges() for sheet in sheets)
    continues_as = len(resolution.connector_pairs)
    same_tagged_item_as = sum(len(group.references) for group in resolution.identity_groups)
    is_located_in = _located_in_count(sheets)
    return has_sheet + is_drawn_on + topology + continues_as + same_tagged_item_as + is_located_in


def _assert_matches_the_plan(
    report: LoadReport, sheets: list[SheetGraph], resolution: Resolution
) -> None:
    assert report.corpus_id == _CORPUS_ID
    assert report.nodes_written == _expected_node_count(sheets)
    assert report.relationships_written == _expected_relationship_count(sheets, resolution)
    assert report.neo4j_version is not None, "the live server should report its own version"
    # `load_corpus` itself raises on a count mismatch (its own verify step, §7.4);
    # reaching this line at all is therefore already part of what is being checked.


@pytest.mark.parametrize("corpus_factory", [_small_corpus, _ex01_corpus])
def test_load_corpus_matches_the_plan_and_is_idempotent(corpus_factory) -> None:  # type: ignore[no-untyped-def]
    corpus = corpus_factory()
    if corpus is None:
        pytest.skip(f"{_EX01_PATH} is absent; data/ is untracked (see CLAUDE.md)")
    sheets, resolution = corpus
    settings = _settings()
    plan = build_load_plan(_CORPUS_ID, sheets, resolution)

    try:
        first = load_corpus(settings, plan)
        _assert_matches_the_plan(first, sheets, resolution)

        # wipe -> schema -> reload from the same plan must land on identical counts.
        second = load_corpus(settings, plan)
        _assert_matches_the_plan(second, sheets, resolution)
    finally:
        wipe_corpus(settings, _CORPUS_ID)
