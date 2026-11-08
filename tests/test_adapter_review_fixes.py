"""F10 review fixes in the adapters and the validator; each test failed before its fix.

The tests build tiny pyDEXPI *conceptual graphs* by hand (nodes carry the `label` and the
attributes pyDEXPI's `GraphAbstractor` leaves on them), so no model or file is needed.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from plantgraph.adapters.pydexpi_adapter import map_conceptual_graph
from plantgraph.adapters.pydexpi_generic import add_related_to_edges, count_nodes_per_dexpi_class
from plantgraph.adapters.pydexpi_proteus_import import import_proteus_sheet
from plantgraph.graph import schema, validation

EX01 = Path("data/external/C01V04-VER.EX01.xml")


def _bubble(**fields: str) -> dict[str, object]:
    return {"label": "ProcessInstrumentationFunction", **fields}


def _sensor_with_carrier(*, signal_out: bool = False) -> nx.MultiDiGraph[str]:
    """A sensor measured into an untagged bubble (a "carrier"), optionally signalling onward."""
    graph: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    graph.add_node(
        "psgf",
        label="ProcessSignalGeneratingFunction",
        processSignalGeneratingFunctionNumber="PI-1",
    )
    graph.add_node("carrier", **_bubble())
    graph.add_edge("psgf", "carrier", label="MeasuringLineFunction", attr_name="x")
    if signal_out:
        graph.add_node("act", label="ActuatingFunction")
        graph.add_edge("carrier", "act", label="SignalLineFunction", attr_name="x")
    return graph


# ---- the bubble's tag carries the function letters ----


def test_a_bubble_tag_includes_the_function_letters_as_printed() -> None:
    graph: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    graph.add_node(
        "b",
        **_bubble(
            processInstrumentationFunctionCategory="P",
            processInstrumentationFunctions="ICSA",
            processInstrumentationFunctionNumber="4712.02",
        ),
    )
    plant, _ = map_conceptual_graph(graph, "plant0", {})
    assert plant.nodes["b"]["tag"] == "PICSA-4712.02"


def test_a_generated_bubble_tag_with_a_modifier_is_unchanged() -> None:
    graph: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    graph.add_node(
        "b",
        **_bubble(
            processInstrumentationFunctionCategory="F",
            processInstrumentationFunctionModifier="IC",
            processInstrumentationFunctionNumber="1-2",
        ),
    )
    plant, _ = map_conceptual_graph(graph, "plant0", {})
    assert plant.nodes["b"]["tag"] == "FIC-1-2"


@pytest.mark.skipif(not EX01.exists(), reason="the EX01 drawing is not in this checkout")
def test_ex01_bubbles_carry_their_letters() -> None:
    graph = import_proteus_sheet(EX01).sheet.graph
    bubbles = {
        a["tag"]
        for _, a in graph.nodes(data=True)
        if a["node_class"] == schema.NodeClass.PROCESS_INSTRUMENTATION_FUNCTION.value
    }
    assert bubbles == {"PI-4712.01", "PICSA-4712.02", "HS-4750.01", "TICSA-4750.03"}


# ---- carrier removal: v2 vocabulary only, and only for a bubble that sends no signal ----


def test_a_v2_carrier_with_no_outgoing_signal_is_folded() -> None:
    plant, report = map_conceptual_graph(
        _sensor_with_carrier(), "plant0", {}, vocabulary=schema.V2_IMPORTABLE_CLASSES
    )
    assert report.carrier_functions_folded == 1
    assert "carrier" not in plant
    assert plant.nodes["psgf"]["loop_tag"] == "PI-1"


def test_a_v1_import_never_folds_an_untagged_bubble() -> None:
    plant, report = map_conceptual_graph(_sensor_with_carrier(), "plant0", {})
    assert report.carrier_functions_folded == 0
    assert "carrier" in plant


def test_an_untagged_bubble_that_signals_onward_is_not_a_carrier() -> None:
    graph = _sensor_with_carrier(signal_out=True)
    plant, report = map_conceptual_graph(
        graph, "plant0", {}, vocabulary=schema.V2_IMPORTABLE_CLASSES
    )
    assert report.carrier_functions_folded == 0
    assert "carrier" in plant


# ---- validation ----


@pytest.mark.parametrize("empty_tag", ["", "   "])
def test_an_empty_tag_counts_as_missing(empty_tag: str) -> None:
    sheet: nx.DiGraph[str] = nx.DiGraph()
    sheet.add_node("t1", node_class="Tank", tag=empty_tag)
    violations = validation.validate_sheet_graph(sheet)
    assert [(v.kind, v.subject) for v in violations] == [("missing_property", "t1")]


def test_two_empty_tags_are_missing_not_duplicates() -> None:
    sheet: nx.DiGraph[str] = nx.DiGraph()
    sheet.add_node("t1", node_class="Tank", tag="")
    sheet.add_node("t2", node_class="Tank", tag="")
    kinds = {v.kind for v in validation.validate_sheet_graph(sheet)}
    assert kinds == {"missing_property"}


def test_a_signal_connector_is_refused_as_machine_control_source() -> None:
    """Not reproduced as a defect: the pair rule already rejects it (once); this pins that."""
    sheet: nx.DiGraph[str] = nx.DiGraph()
    sheet.add_node("p1", node_class="CentrifugalPump", tag="P-1")
    sheet.add_node(
        "c1",
        node_class="FlowInSignalOffPageConnector",
        connector_number="C-1",
        referenced_drawing_number="2",
    )
    sheet.add_edge("c1", "p1", relation="control")
    violations = validation.validate_sheet_graph(sheet)
    assert [(v.kind, v.subject) for v in violations] == [("bad_endpoint", "c1->p1")]


# ---- generic fallback and deterministic report order ----


def test_related_to_skips_an_edge_the_v2_rules_already_mapped() -> None:
    conceptual: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    conceptual.add_node("t", label="Tank", tagName="T-1")
    conceptual.add_node("g", label="Agitator", tagName="A-1")
    conceptual.add_edge("t", "g", label="reference", attr_name="agitator")
    plant, _ = map_conceptual_graph(
        conceptual, "plant0", {}, vocabulary=schema.V2_IMPORTABLE_CLASSES
    )
    assert plant.edges["t", "g"]["relation"] == "has_agitator"
    added, collapsed = add_related_to_edges(plant, conceptual, v2_rules=True)
    assert (added, collapsed) == ({}, 0)


def test_the_node_class_count_lists_its_keys_in_sorted_order() -> None:
    conceptual: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    for node_id, label in (("a", "Tank"), ("b", "BallValve"), ("c", "CentrifugalPump")):
        conceptual.add_node(node_id, label=label)
    counts = count_nodes_per_dexpi_class(conceptual, ["a", "b", "c"])
    assert list(counts) == ["BallValve", "CentrifugalPump", "Tank"]


@pytest.mark.skipif(not EX01.exists(), reason="the EX01 drawing is not in this checkout")
def test_every_import_report_dict_is_in_sorted_key_order() -> None:
    report = import_proteus_sheet(EX01, vocabulary="v2").report
    dicts = [
        report.nodes_per_dexpi_class,
        report.edges_lost_to_unmapped_endpoints,
        report.conversion.nodes_dropped_per_class,
        report.conversion.edges_mapped_per_relation,
        report.conversion.edges_dropped_per_label,
    ]
    assert all(list(d) == sorted(d) for d in dicts)
