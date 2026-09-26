"""`localize()` — renaming at the resolver boundary (design `kg-construction.md` §4.2-4.3).

The round-trip test (`test_splitter.py`) checks the splitter's own invariants;
this file checks that `localize()` really does seal off the splitter's
answer-key leaks before any downstream code (resolver, Neo4j, prompt) sees the
sheets.
"""

from __future__ import annotations

import networkx as nx
import pytest

from graph_plant_builder import GraphPlantBuilder
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import ConnectorLabelDetail, SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.graph.schema import VISIBLE_EDGE_PROPERTIES, VISIBLE_NODE_PROPERTIES
from plantgraph.resolution.contract import check_contract
from plantgraph.resolution.localize import OccurrenceMap, localize


def _generated_plant(seed: int = 8) -> nx.DiGraph[str]:
    """A 4-unit synthetic plant — the default of n_units (`GeneratorConfig`)."""
    config = GeneratorConfig(seed=seed)
    builder = GraphPlantBuilder(config.plant_id)
    plan_plant(config, builder)
    return builder.graph


def _split_with_duplication_and_connectors() -> tuple[list[SheetGraph], SplitManifest]:
    """dup=0.5, DRAWING_ONLY: both named leaks (L1, L2) are present at the same time."""
    plant = _generated_plant()
    sheets, manifest = split(
        plant,
        SplitConfig(
            sheet_equipment_budget=3,
            seed=0,
            duplication_rate=0.5,
            connector_label_detail=ConnectorLabelDetail.DRAWING_ONLY,
        ),
    )
    assert manifest.identity_groups, "the test must get at least one duplication"
    assert any(sheet.connectors for sheet in sheets), "the test must get at least one stub"
    return sheets, manifest


def _find_local_key(occurrence_map: OccurrenceMap, sheet_id: str, node_id: str) -> str:
    """Find which local key belongs to a given (sheet, original node_id) pair."""
    original_key = f"{sheet_id}:{node_id}"
    for local_key, mapped in occurrence_map.local_to_original.items():
        if mapped == original_key:
            return local_key
    raise AssertionError(f"no local key maps to {original_key!r}")


def test_no_leaked_property_survives_localize() -> None:
    """Neither the connectors list nor an off-whitelist property survives."""
    sheets, _ = _split_with_duplication_and_connectors()
    localized, _ = localize(sheets)

    for sheet in localized:
        assert sheet.connectors == [], f"sheet {sheet.sheet_id!r} still carries connectors"
        for _, attrs in sheet.graph.nodes(data=True):
            assert set(attrs) <= VISIBLE_NODE_PROPERTIES
        for _, _, attrs in sheet.graph.edges(data=True):
            assert set(attrs) <= VISIBLE_EDGE_PROPERTIES

    check_contract(localized)  # the contract is the main claim: does not raise


def test_localize_renames_the_duplicated_node_id_differently_on_each_sheet() -> None:
    """L1 directly: the home and reference occurrences share a node_id in the raw output."""
    sheets, manifest = _split_with_duplication_and_connectors()
    group = manifest.identity_groups[0]
    home_sheet_id, node_id = group.home.split(":", 1)
    reference_sheet_id = group.references[0].split(":", 1)[0]

    localized, occurrence_map = localize(sheets)

    home_local_key = _find_local_key(occurrence_map, home_sheet_id, node_id)
    reference_local_key = _find_local_key(occurrence_map, reference_sheet_id, node_id)
    assert home_local_key != reference_local_key
    check_contract(localized)


def test_occurrence_map_is_a_bijection() -> None:
    sheets, _ = _split_with_duplication_and_connectors()
    _, occurrence_map = localize(sheets)

    total_occurrences = sum(sheet.graph.number_of_nodes() for sheet in sheets)
    assert len(occurrence_map.local_to_original) == total_occurrences
    # dict keys already guarantee injectivity in the local -> original direction;
    # a bijection also needs the original side to remain unique
    assert len(set(occurrence_map.local_to_original.values())) == total_occurrences


def test_different_salt_produces_disjoint_local_keys() -> None:
    sheets, _ = _split_with_duplication_and_connectors()
    localized_plain, map_plain = localize(sheets, salt="")
    localized_salted, map_salted = localize(sheets, salt="renamed")

    plain_keys = set(map_plain.local_to_original)
    salted_keys = set(map_salted.local_to_original)
    assert plain_keys.isdisjoint(salted_keys)

    # both sides cover the same original keys — only the aliases differ
    assert set(map_plain.local_to_original.values()) == set(map_salted.local_to_original.values())
    assert {sheet.sheet_id for sheet in localized_plain} == {
        sheet.sheet_id for sheet in localized_salted
    }


def test_original_node_id_strips_only_the_leading_sheet_id() -> None:
    """Stub ids ('opc:sheet:0') contain ':' themselves — this must not cause confusion."""
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node("opc:0:0", node_class="FlowOutPipeOffPageConnector", connector_number="A")
    sheets = [SheetGraph(sheet_id="0", graph=graph)]
    localized, occurrence_map = localize(sheets)

    (local_key,) = localized[0].graph.nodes
    assert occurrence_map.original_node_id(f"0:{local_key}") == "opc:0:0"
    assert occurrence_map.original_key(f"0:{local_key}") == "0:opc:0:0"


def test_original_key_raises_on_an_unknown_local_key() -> None:
    _, occurrence_map = localize([SheetGraph(sheet_id="0", graph=nx.DiGraph())])
    with pytest.raises(ValueError, match="not in this occurrence map"):
        occurrence_map.original_key("0:does-not-exist")


def test_localize_works_on_a_single_hand_built_sheet_without_connectors() -> None:
    """`localize()` applies to every producer, not only the splitter (design §4.2)."""
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node("eq-1", node_class="CentrifugalPump", tag="P-1")
    sheets = [SheetGraph(sheet_id="123/A93", graph=graph)]

    localized, occurrence_map = localize(sheets)
    check_contract(localized)
    assert localized[0].graph.number_of_nodes() == 1
    (local_key,) = localized[0].graph.nodes
    assert occurrence_map.original_node_id(f"123/A93:{local_key}") == "eq-1"
