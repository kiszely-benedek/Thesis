"""`localize()` — a resolver-határ átnevezése (design `kg-construction.md` §4.2-4.3).

A kerek-út teszt (`test_splitter.py`) a splitter saját invariánsait nézi; ez a
fájl azt nézi, hogy a `localize()` valóban lezárja a splitter válaszkulcs-
szivárgásait, mielőtt bármi downstream (resolver, Neo4j, prompt) meglátná a
lapokat.
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
    """Egy 4-egységes szintetikus üzem — n_units alapértéke (`GeneratorConfig`)."""
    config = GeneratorConfig(seed=seed)
    builder = GraphPlantBuilder(config.plant_id)
    plan_plant(config, builder)
    return builder.graph


def _split_with_duplication_and_connectors() -> tuple[list[SheetGraph], SplitManifest]:
    """dup=0.5, DRAWING_ONLY: mindkét nevesített szivárgás (L1, L2) egyszerre jelen van."""
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
    assert manifest.identity_groups, "a tesztnek legalább egy duplikációt kell kapnia"
    assert any(sheet.connectors for sheet in sheets), "a tesztnek legalább egy csonkot kell adnia"
    return sheets, manifest


def _find_local_key(occurrence_map: OccurrenceMap, sheet_id: str, node_id: str) -> str:
    """Visszakeresi, melyik helyi kulcs tartozik egy adott (lap, eredeti node_id) párhoz."""
    original_key = f"{sheet_id}:{node_id}"
    for local_key, mapped in occurrence_map.local_to_original.items():
        if mapped == original_key:
            return local_key
    raise AssertionError(f"no local key maps to {original_key!r}")


def test_no_leaked_property_survives_localize() -> None:
    """Se a connectors lista, se egy fehérlistán kívüli tulajdonság nem éli túl."""
    sheets, _ = _split_with_duplication_and_connectors()
    localized, _ = localize(sheets)

    for sheet in localized:
        assert sheet.connectors == [], f"sheet {sheet.sheet_id!r} still carries connectors"
        for _, attrs in sheet.graph.nodes(data=True):
            assert set(attrs) <= VISIBLE_NODE_PROPERTIES
        for _, _, attrs in sheet.graph.edges(data=True):
            assert set(attrs) <= VISIBLE_EDGE_PROPERTIES

    check_contract(localized)  # a szerződés a fő állítás: nem dob kivételt


def test_localize_renames_the_duplicated_node_id_differently_on_each_sheet() -> None:
    """L1 közvetlenül: a home és a reference előfordulás a nyers kimeneten azonos node_id."""
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
    # a dict-kulcsok garantálják, hogy helyi -> eredeti irányban injektív legyen;
    # a bijekcióhoz azt is meg kell nézni, hogy az eredeti oldal is egyedi maradt
    assert len(set(occurrence_map.local_to_original.values())) == total_occurrences


def test_different_salt_produces_disjoint_local_keys() -> None:
    sheets, _ = _split_with_duplication_and_connectors()
    localized_plain, map_plain = localize(sheets, salt="")
    localized_salted, map_salted = localize(sheets, salt="renamed")

    plain_keys = set(map_plain.local_to_original)
    salted_keys = set(map_salted.local_to_original)
    assert plain_keys.isdisjoint(salted_keys)

    # mindkét oldal ugyanazokat az eredeti kulcsokat fedi le — csak az álnevek térnek el
    assert set(map_plain.local_to_original.values()) == set(map_salted.local_to_original.values())
    assert {sheet.sheet_id for sheet in localized_plain} == {
        sheet.sheet_id for sheet in localized_salted
    }


def test_original_node_id_strips_only_the_leading_sheet_id() -> None:
    """A csonk-id-k ('opc:sheet:0') maguk is ':'-t tartalmaznak — ez nem téveszthet meg."""
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
    """`localize()` minden termelőre vonatkozik, nemcsak a splitterre (design §4.2)."""
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node("eq-1", node_class="CentrifugalPump", tag="P-1")
    sheets = [SheetGraph(sheet_id="123/A93", graph=graph)]

    localized, occurrence_map = localize(sheets)
    check_contract(localized)
    assert localized[0].graph.number_of_nodes() == 1
    (local_key,) = localized[0].graph.nodes
    assert occurrence_map.original_node_id(f"123/A93:{local_key}") == "eq-1"
