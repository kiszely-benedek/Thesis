"""`check_contract` — the resolver-boundary gate: raw splitter output fails, `localize()`'s passes.

This gives the two named leaks an explicit test (design `kg-construction.md`
§4.1): L1, that a duplicated equipment's reference occurrence gets the same
node_id as its home (`splitter.py:183`), and L2, that a stub node's
`OffPageConnector` pair carries the pairing answer key, even under
`DRAWING_ONLY` labelling (`connectors.py:85-106`).
"""

from __future__ import annotations

import networkx as nx
import pytest

from graph_plant_builder import GraphPlantBuilder
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.benchmark.split_models import ConnectorLabelDetail, SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.resolution.contract import check_contract
from plantgraph.resolution.localize import localize


def _generated_plant(seed: int = 8) -> nx.DiGraph[str]:
    """A 4-unit synthetic plant — the default of n_units (`GeneratorConfig`)."""
    config = GeneratorConfig(seed=seed)
    builder = GraphPlantBuilder(config.plant_id)
    plan_plant(config, builder)
    return builder.graph


def test_raw_splitter_output_at_duplication_rate_fails_contract() -> None:
    """Design §10 T2's acceptance condition: at dup=0.5, raw output must always fail.

    Which specific reason it fails for (L1 or L2) depends on the splitter's
    internal ordering — the two cases below test each in isolation.
    """
    plant = _generated_plant()
    sheets, manifest = split(
        plant, SplitConfig(sheet_equipment_budget=3, seed=0, duplication_rate=0.5)
    )
    assert manifest.identity_groups, "a tesztnek legalább egy duplikációt kell kapnia"
    with pytest.raises(ValueError):
        check_contract(sheets)


def test_shared_node_id_across_sheets_fails_contract_naming_the_id() -> None:
    """L1 in isolation: home and reference occurrences carry the same node_id (`splitter.py`)."""
    graph_a: nx.DiGraph[str] = nx.DiGraph()
    graph_a.add_node("eq-1", node_class="CentrifugalPump", tag="P-1")
    graph_b: nx.DiGraph[str] = nx.DiGraph()
    graph_b.add_node("eq-1", node_class="CentrifugalPump", tag="P-1")
    sheets = [SheetGraph(sheet_id="0", graph=graph_a), SheetGraph(sheet_id="1", graph=graph_b)]

    with pytest.raises(ValueError, match="node id 'eq-1' occurs on both sheet"):
        check_contract(sheets)


def test_raw_splitter_output_with_connectors_fails_contract_even_at_drawing_only_detail() -> None:
    """L2: OffPageConnector.partner_tag/partner_sheet_id is filled under every setting; at dup=0,
    every cross-sheet edge is cut into a connector, so the connectors list is never empty.
    """
    plant = _generated_plant()
    sheets, _ = split(
        plant,
        SplitConfig(
            sheet_equipment_budget=3,
            seed=0,
            duplication_rate=0.0,
            connector_label_detail=ConnectorLabelDetail.DRAWING_ONLY,
        ),
    )
    assert any(sheet.connectors for sheet in sheets), "a fixture-nek kell csonkot adnia"

    with pytest.raises(ValueError, match="still carries"):
        check_contract(sheets)


def test_localized_output_passes_contract() -> None:
    plant = _generated_plant()
    sheets, _ = split(plant, SplitConfig(sheet_equipment_budget=3, seed=0, duplication_rate=0.5))
    localized, _ = localize(sheets)
    check_contract(localized)  # does not raise


def test_duplicate_sheet_id_fails_contract() -> None:
    sheets = [
        SheetGraph(sheet_id="0", graph=nx.DiGraph()),
        SheetGraph(sheet_id="0", graph=nx.DiGraph()),
    ]
    with pytest.raises(ValueError, match="duplicate sheet_id"):
        check_contract(sheets)


def test_sheet_id_with_colon_fails_contract() -> None:
    sheets = [SheetGraph(sheet_id="0:1", graph=nx.DiGraph())]
    with pytest.raises(ValueError, match="local-key separator"):
        check_contract(sheets)


def test_hidden_node_property_fails_contract() -> None:
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node("n1", node_class="CentrifugalPump", tag="P-1", manufacturer="Acme")
    sheets = [SheetGraph(sheet_id="0", graph=graph)]
    with pytest.raises(ValueError, match=r"hidden properties \['manufacturer'\]"):
        check_contract(sheets)


def test_hidden_edge_property_fails_contract() -> None:
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node("a", node_class="CentrifugalPump", tag="P-1")
    graph.add_node("b", node_class="CentrifugalPump", tag="P-2")
    graph.add_edge("a", "b", relation="send_to", stream_kind="cross_unit")
    sheets = [SheetGraph(sheet_id="0", graph=graph)]
    with pytest.raises(ValueError, match=r"hidden properties \['stream_kind'\]"):
        check_contract(sheets)
