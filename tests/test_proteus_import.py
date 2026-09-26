"""Tests for the Proteus importer (`kg-construction.md` §3, T1).

`EX01_PATH` points to a real, external DEXPI file (`data/` is untracked — see
the CLAUDE.md note), so every test built on it is skipped if the file is
missing: not a failure, just that this machine lacks the sample to load.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from plantgraph.adapters.pydexpi_adapter import map_conceptual_graph, plant_graph
from plantgraph.adapters.pydexpi_builder import generate_plant
from plantgraph.adapters.pydexpi_io import save_proteus_equipment_only
from plantgraph.adapters.pydexpi_proteus_import import ImportedSheet, import_proteus_sheet
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.graph import schema
from plantgraph.resolution.contract import check_contract
from plantgraph.resolution.localize import localize

EX01_PATH = Path(__file__).resolve().parent.parent / "data" / "external" / "C01V04-VER.EX01.xml"

#: Measured on EX01 (kg-construction.md §2, §3.1): the schema does not curate these
#: classes directly, but since ADR-0016 the generic fallback (`GenericItem`) keeps
#: all of them — the old "dropped" list now appears, kept, as `nodes_per_dexpi_class`.
_EX01_GENERIC_CLASSES = {
    "ButterflyValve": 1,
    "PipeReducer": 1,
    "SpringLoadedGlobeSafetyValve": 1,
    "PipeTee": 5,
    "BlindFlange": 2,
    "ReciprocatingPump": 1,
}
#: the two off-page connector classes — ADR-0016 rule 3: these map to their own
#: schema class, not generic, and `sheet.connectors` stays empty (§4)
_EX01_CONNECTOR_CLASSES = {
    "FlowInPipeOffPageConnector": 1,
    "FlowOutPipeOffPageConnector": 1,
}


def _ex01_or_skip() -> Path:
    if not EX01_PATH.exists():
        pytest.skip(f"{EX01_PATH} is absent; data/ is untracked (see CLAUDE.md)")
    return EX01_PATH


def _assert_accounting_invariant(imported: ImportedSheet) -> None:
    """Nothing may be lost without a trace: every conceptual node's and edge's fate is known."""
    report = imported.report
    nodes_accounted = report.conversion.nodes_mapped + sum(
        report.conversion.nodes_dropped_per_class.values()
    )
    assert nodes_accounted == report.conceptual_nodes
    # the fallback's own counter (ADR-0016 §3.1 rule 6): must give the same count of
    # mapped nodes, just broken down by pyDEXPI class instead of by schema node_class
    assert sum(report.nodes_per_dexpi_class.values()) == report.conversion.nodes_mapped

    edges_kept = (
        sum(report.conversion.edges_mapped_per_relation.values())
        + report.conversion.parallel_edges_collapsed
    )
    edges_accounted = (
        edges_kept
        + report.conversion.parent_structure_folded
        + sum(report.conversion.edges_dropped_per_label.values())
        + sum(report.edges_lost_to_unmapped_endpoints.values())
    )
    assert edges_accounted == report.conceptual_edges


# ---- EX01: a real, external DEXPI file -------------------------------------------------------


def test_ex01_sheet_id_comes_from_the_printed_drawing_number() -> None:
    imported = import_proteus_sheet(_ex01_or_skip())
    assert imported.report.sheet_id == "123/A93"
    assert imported.report.sheet_id_source == "drawing_number"
    assert imported.sheet.sheet_id == "123/A93"
    assert imported.report.drawing_name == "DEXPI example PID"


def test_ex01_maps_36_of_36_nodes_and_39_of_39_edges() -> None:
    """T1b (ADR-0016) gate: the generic fallback keeps every node and edge (was 23/36, 16/39)."""
    imported = import_proteus_sheet(_ex01_or_skip())
    report = imported.report
    assert report.conceptual_nodes == 36
    assert report.conceptual_edges == 39
    assert report.conversion.nodes_mapped == 36
    assert sum(report.conversion.edges_mapped_per_relation.values()) == 39
    assert imported.sheet.graph.number_of_nodes() == 36
    assert imported.sheet.graph.number_of_edges() == 39


def test_ex01_drops_nothing_and_keeps_the_previously_lost_classes_as_generic() -> None:
    """Renamed from `test_ex01_drops_exactly_the_classes_the_schema_does_not_map` (T1b): nothing
    is dropped any more, so this now checks the fallback's own coverage counter instead."""
    imported = import_proteus_sheet(_ex01_or_skip())
    report = imported.report
    assert report.conversion.nodes_dropped_per_class == {}
    for dexpi_class, count in _EX01_GENERIC_CLASSES.items():
        assert report.nodes_per_dexpi_class[dexpi_class] == count
    for dexpi_class, count in _EX01_CONNECTOR_CLASSES.items():
        assert report.nodes_per_dexpi_class[dexpi_class] == count
    assert sum(report.nodes_per_dexpi_class.values()) == 36


def test_ex01_loses_no_edge_to_an_unmapped_endpoint_any_more() -> None:
    """Renamed from `test_ex01_counts_every_edge_lost_to_a_dropped_endpoint` (T1b): 23 -> 0, since
    every endpoint the fallback used to drop is now a `GenericItem` node."""
    imported = import_proteus_sheet(_ex01_or_skip())
    report = imported.report
    assert report.conversion.edges_dropped_per_label == {}
    assert report.edges_lost_to_unmapped_endpoints == {}
    assert report.related_to_collapsed == 0


def test_p4712_is_a_generic_reciprocating_pump_and_t4750_is_a_known_tank() -> None:
    """§10 T1b acceptance: P4712's `dexpi_labels`/`category`, and its exact tag (OQ1c)."""
    imported = import_proteus_sheet(_ex01_or_skip())
    p4712 = imported.sheet.graph.nodes[_node_id_by_tag(imported.sheet.graph, "P4712")]
    assert p4712["dexpi_labels"] == ["ReciprocatingPump", "Pump", "Equipment"]
    assert p4712["category"] == "equipment"
    assert p4712["dexpi_class"] == "ReciprocatingPump"
    assert p4712["node_class"] == "GenericItem"

    t4750 = imported.sheet.graph.nodes[_node_id_by_tag(imported.sheet.graph, "T4750")]
    assert t4750["node_class"] == "Tank"  # not generic: Tank is already a schema class


def test_t4750_reaches_p4712_by_a_send_to_path() -> None:
    """§10 T1b acceptance: T4750 -> P4712 is a `send_to` path (not necessarily a single edge)."""
    imported = import_proteus_sheet(_ex01_or_skip())
    t4750 = _node_id_by_tag(imported.sheet.graph, "T4750")
    p4712 = _node_id_by_tag(imported.sheet.graph, "P4712")

    send_to_graph: nx.DiGraph[str] = nx.DiGraph()
    send_to_graph.add_nodes_from(imported.sheet.graph.nodes)
    send_to_graph.add_edges_from(
        (source, target)
        for source, target, attrs in imported.sheet.graph.edges(data=True)
        if attrs.get("relation") == "send_to"
    )
    assert nx.has_path(send_to_graph, t4750, p4712)


def _node_id_by_tag(graph: nx.DiGraph[str], tag: str) -> str:
    matches = [node_id for node_id, attrs in graph.nodes(data=True) if attrs.get("tag") == tag]
    assert len(matches) == 1, f"expected exactly one node tagged {tag!r}, found {len(matches)}"
    return matches[0]


def test_ex01_sheet_has_no_off_page_connectors_recorded() -> None:
    """§4: an imported sheet's `connectors` list stays empty even though the two connector
    classes are now mapped nodes — DEXPI reference-to-schema mapping is still open (§11 OQ1b)."""
    imported = import_proteus_sheet(_ex01_or_skip())
    assert imported.sheet.connectors == []


def test_ex01_reports_seven_duplicate_valve_tags_but_does_not_raise() -> None:
    """Renamed from `..._three_duplicate_valve_tags...` (T1b): 3 -> 7. The fallback surfaces
    fitting classes (`PipeTee`, `BlindFlange`, ...) that reuse the same piping-component tag
    (`C1`..`C4`) as the valves already visible before T1b — a real sheet does this."""
    imported = import_proteus_sheet(_ex01_or_skip())
    duplicate_tags = [v for v in imported.report.violations if v.kind == "duplicate_tag"]
    assert len(duplicate_tags) == 7


def test_ex01_node_ids_are_identical_across_two_imports() -> None:
    path = _ex01_or_skip()
    first = import_proteus_sheet(path)
    second = import_proteus_sheet(path)
    assert set(first.sheet.graph.nodes) == set(second.sheet.graph.nodes)


def test_ex01_accounting_invariant_holds() -> None:
    imported = import_proteus_sheet(_ex01_or_skip())
    _assert_accounting_invariant(imported)


# ---- the printed piping-component name: an identifier, not equipment/datasheet data, which is
# ---- out of scope — not part of this thesis (ADR-0021) --------------------------------------


def test_ex01_valve_66kl21_is_findable_by_its_printed_piping_component_name() -> None:
    """ChatP&ID's flow-path reference answers name valves this way; `resolve()` cannot, because
    its tag comes from `pipingComponentNumber`, a different field that repeats across fittings
    (this valve's tag is "C1", shared with unrelated pipe fittings on the same sheet)."""
    imported = import_proteus_sheet(_ex01_or_skip())
    graph = imported.sheet.graph
    valve_66kl21 = _node_id_by_property(graph, "piping_component_name", "66KL21")
    assert graph.nodes[valve_66kl21]["tag"] == "C1"


def test_ex01_check_contract_passes_after_localize() -> None:
    imported = import_proteus_sheet(_ex01_or_skip())
    localized, _ = localize([imported.sheet])
    check_contract(localized)  # does not raise


def test_a_generated_plant_gains_no_new_property_from_import() -> None:
    """A generated plant carries no imported-file data at all (ADR-0018 A1).

    `plant_graph` is the generator's own entry point (§3.6) — it never touches
    `piping_component_name`, the one property an import can add.
    """
    generated = generate_plant(GeneratorConfig(seed=4, n_units=4))
    plant, _report = plant_graph(generated)

    for _, attrs in plant.nodes(data=True):
        assert "piping_component_name" not in attrs


def _node_id_by_property(graph: nx.DiGraph[str], key: str, value: str) -> str:
    matches = [node_id for node_id, attrs in graph.nodes(data=True) if attrs.get(key) == value]
    assert len(matches) == 1, f"expected one node with {key}={value!r}, found {len(matches)}"
    return matches[0]


# ---- always-run case: a generated plant, round-tripped through Proteus ----------------------


def test_a_generated_plant_survives_a_proteus_round_trip(tmp_path: Path) -> None:
    generated = generate_plant(GeneratorConfig(seed=1, n_units=4))
    save_proteus_equipment_only(generated.model, tmp_path, "plant")

    imported = import_proteus_sheet(tmp_path / "plant.xml")

    assert imported.sheet.graph.number_of_nodes() > 0
    for _, attrs in imported.sheet.graph.nodes(data=True):
        assert attrs["node_class"] in schema.EQUIPMENT_CLASSES
    _assert_accounting_invariant(imported)

    # the generator only exports equipment to Proteus (§3.7) — so the count matches
    # here, but this isn't guaranteed for every input (kg-construction.md §11 open question 4)
    original_equipment_count = len(generated.model.conceptualModel.taggedPlantItems)
    assert imported.report.conversion.nodes_mapped == original_equipment_count


def test_a_generated_plant_gives_the_same_node_ids_across_two_imports(tmp_path: Path) -> None:
    generated = generate_plant(GeneratorConfig(seed=2, n_units=4))
    save_proteus_equipment_only(generated.model, tmp_path, "plant")

    first = import_proteus_sheet(tmp_path / "plant.xml")
    second = import_proteus_sheet(tmp_path / "plant.xml")
    assert set(first.sheet.graph.nodes) == set(second.sheet.graph.nodes)


def test_import_proteus_sheet_rejects_a_sheet_id_containing_a_colon(tmp_path: Path) -> None:
    generated = generate_plant(GeneratorConfig(seed=3, n_units=4))
    save_proteus_equipment_only(generated.model, tmp_path, "plant")

    with pytest.raises(ValueError, match="sheet_id"):
        import_proteus_sheet(tmp_path / "plant.xml", sheet_id="a:b")


# ---- hand-built conceptual graph: a valve without a PlantSection ----------------------


def test_map_conceptual_graph_tolerates_a_valve_with_no_owning_plant_section() -> None:
    """A valve whose source equipment has no `unit_id` — the case `_assign_valve_units` fixes."""
    conceptual: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    conceptual.add_node("pump", label="CentrifugalPump", tagName="P1")
    conceptual.add_node("valve", label="GlobeValve", pipingComponentNumber="V1")
    conceptual.add_edge("pump", "valve", label="Pipe", attr_name="pipingSource")

    plant, report = map_conceptual_graph(conceptual, plant_id="p", stream_kind={})

    assert report.valve_units_unresolved == 1
    assert set(plant.nodes) == {"pump", "valve"}
