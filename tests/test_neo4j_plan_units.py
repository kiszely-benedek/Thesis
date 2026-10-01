"""Unit and plant nodes in the load plan: only from what the sheets show (ADR-0026).

Split from `test_neo4j_plan.py` for the 400-line limit. Every expectation is
recomputed from the sheets and the resolution, never from the plan's own rows.
"""

from __future__ import annotations

import networkx as nx
import pytest

from graph_plant_builder import GraphPlantBuilder
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.graph import schema
from plantgraph.resolution.localize import localize
from plantgraph.resolution.models import Resolution, ResolutionReport
from plantgraph.resolution.resolver import resolve
from plantgraph.store.neo4j_plan import LoadPlan, build_load_plan

_CORPUS_ID = "acme-plant-01"


def _small_corpus() -> tuple[list[SheetGraph], Resolution]:
    """A 4-unit generated plant, split at `duplication_rate=0.5` so an identity group exists."""
    generator_config = GeneratorConfig(seed=7)
    builder = GraphPlantBuilder(generator_config.plant_id)
    plan_plant(generator_config, builder)
    split_config = SplitConfig(sheet_equipment_budget=2, seed=7, duplication_rate=0.5)
    sheets, _manifest = split(builder.graph, split_config)
    localized, _occurrence_map = localize(sheets)
    return localized, resolve(localized)


def _drawn_values(sheets: list[SheetGraph], key: str) -> set[str]:
    return {
        attrs[key]
        for sheet in sheets
        for _node_id, attrs in sheet.graph.nodes(data=True)
        if key in attrs
    }


def _resolution_with_no_links() -> Resolution:
    report = ResolutionReport(
        n_sheets=1,
        n_occurrences=1,
        n_connectors=0,
        pairs_by_rule={},
        unresolved_by_reason={},
        n_identity_groups=0,
        ambiguous_tag_keys=0,
        edge_attribute_conflicts=0,
    )
    return Resolution(
        plant=nx.DiGraph(), connector_pairs=[], identity_groups=[], unresolved=[], report=report
    )


def test_schema_statements_include_the_unit_id_index() -> None:
    sheets, resolution = _small_corpus()
    plan = build_load_plan(_CORPUS_ID, sheets, resolution)
    queries = [statement.query for statement in plan.schema_statements]
    assert any("INDEX corpus_node_unit_id" in query and "(n.unit_id)" in query for query in queries)


# --- unit and plant nodes: only from what the sheets show (ADR-0026) ------------------------


def _located_in_endpoints(plan: LoadPlan) -> list[tuple[str, str]]:
    return [
        (row["source_uid"], row["target_uid"])
        for statement in plan.relationship_statements
        if "[r:is_located_in]" in statement.query
        for row in statement.parameters["rows"]
    ]


def test_every_unit_bearing_occurrence_and_no_other_is_located_in_its_unit() -> None:
    sheets, resolution = _small_corpus()
    plan = build_load_plan(_CORPUS_ID, sheets, resolution)

    expected_links = {
        f"{_CORPUS_ID}|{sheet.sheet_id}:{node_id}": f"{_CORPUS_ID}|unit:{attrs['unit_id']}"
        for sheet in sheets
        for node_id, attrs in sheet.graph.nodes(data=True)
        if "unit_id" in attrs
    }
    occurrence_links = {
        source: target for source, target in _located_in_endpoints(plan) if "|unit:" not in source
    }

    assert occurrence_links == expected_links


def test_reference_occurrences_and_connector_stubs_have_no_is_located_in() -> None:
    sheets, resolution = _small_corpus()
    assert resolution.identity_groups, "duplication 0.5 must give at least one reference"
    plan = build_load_plan(_CORPUS_ID, sheets, resolution)
    sources = {source for source, _target in _located_in_endpoints(plan)}

    references = {
        f"{_CORPUS_ID}|{key}" for group in resolution.identity_groups for key in group.references
    }
    stubs = {
        f"{_CORPUS_ID}|{sheet.sheet_id}:{node_id}"
        for sheet in sheets
        for node_id, attrs in sheet.graph.nodes(data=True)
        if attrs["node_class"] in schema.CONNECTOR_CLASSES
    }

    assert references and stubs
    assert not (sources & references)
    assert not (sources & stubs)


def test_each_plant_section_is_located_in_one_process_plant() -> None:
    sheets, resolution = _small_corpus()
    plan = build_load_plan(_CORPUS_ID, sheets, resolution)
    section_links = [
        (source, target) for source, target in _located_in_endpoints(plan) if "|unit:" in source
    ]

    assert sorted(source for source, _target in section_links) == sorted(
        f"{_CORPUS_ID}|unit:{unit_id}" for unit_id in _drawn_values(sheets, "unit_id")
    )
    assert all("|plant:" in target for _source, target in section_links)


def test_a_unit_drawn_with_two_plant_ids_is_rejected() -> None:
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node("a", node_class="CentrifugalPump", tag="P-1", unit_id="1", plant_id="x")
    graph.add_node("b", node_class="CentrifugalPump", tag="P-2", unit_id="1", plant_id="y")
    sheet = SheetGraph(sheet_id="0", graph=graph)

    with pytest.raises(ValueError, match="expected exactly one"):
        build_load_plan(_CORPUS_ID, [sheet], _resolution_with_no_links())
