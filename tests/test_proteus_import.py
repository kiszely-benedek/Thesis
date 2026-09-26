"""A Proteus importer tesztjei (`kg-construction.md` §3, T1).

`EX01_PATH` egy valódi, külső DEXPI-fájlra mutat (`data/` nincs verziókövetve — lásd a
CLAUDE.md megjegyzését), ezért minden rá épülő teszt üresen fut le, ha a fájl hiányzik: ez nem
hiba, csak azt jelenti, hogy ezen a gépen nincs meg a betöltendő minta.
"""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import pytest

from plantgraph.adapters.pydexpi_adapter import map_conceptual_graph
from plantgraph.adapters.pydexpi_builder import generate_plant
from plantgraph.adapters.pydexpi_io import save_proteus_equipment_only
from plantgraph.adapters.pydexpi_proteus_import import ImportedSheet, import_proteus_sheet
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.graph import schema

EX01_PATH = Path(__file__).resolve().parent.parent / "data" / "external" / "C01V04-VER.EX01.xml"

#: EX01-en mérve (kg-construction.md §2): ezek az osztályok nincsenek a séma leképezésében
_EX01_DROPPED_CLASSES = {
    "FlowInPipeOffPageConnector": 1,
    "FlowOutPipeOffPageConnector": 1,
    "ButterflyValve": 1,
    "PipeReducer": 1,
    "SpringLoadedGlobeSafetyValve": 1,
    "PipeTee": 5,
    "BlindFlange": 2,
    "ReciprocatingPump": 1,
}


def _ex01_or_skip() -> Path:
    if not EX01_PATH.exists():
        pytest.skip(f"{EX01_PATH} is absent; data/ is untracked (see CLAUDE.md)")
    return EX01_PATH


def _assert_accounting_invariant(imported: ImportedSheet) -> None:
    """Semmi nem veszhet el nyomtalanul: minden konceptuális csomópont és él sorsa ismert."""
    report = imported.report
    nodes_accounted = report.conversion.nodes_mapped + sum(
        report.conversion.nodes_dropped_per_class.values()
    )
    assert nodes_accounted == report.conceptual_nodes

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


# ---- EX01: egy valódi, külső DEXPI-fájl -------------------------------------------------------


def test_ex01_sheet_id_comes_from_the_printed_drawing_number() -> None:
    imported = import_proteus_sheet(_ex01_or_skip())
    assert imported.report.sheet_id == "123/A93"
    assert imported.report.sheet_id_source == "drawing_number"
    assert imported.sheet.sheet_id == "123/A93"
    assert imported.report.drawing_name == "DEXPI example PID"


def test_ex01_maps_23_of_36_nodes_and_16_of_39_edges() -> None:
    imported = import_proteus_sheet(_ex01_or_skip())
    report = imported.report
    assert report.conceptual_nodes == 36
    assert report.conceptual_edges == 39
    assert report.conversion.nodes_mapped == 23
    assert sum(report.conversion.edges_mapped_per_relation.values()) == 16
    assert imported.sheet.graph.number_of_nodes() == 23
    assert imported.sheet.graph.number_of_edges() == 16


def test_ex01_drops_exactly_the_classes_the_schema_does_not_map() -> None:
    imported = import_proteus_sheet(_ex01_or_skip())
    assert imported.report.conversion.nodes_dropped_per_class == _EX01_DROPPED_CLASSES


def test_ex01_counts_every_edge_lost_to_a_dropped_endpoint() -> None:
    imported = import_proteus_sheet(_ex01_or_skip())
    report = imported.report
    # a bug, amit ez a jelentés fed fel: a meglévő ConversionReport ezt nem számolja (§2)
    assert report.conversion.edges_dropped_per_label == {}
    assert sum(report.edges_lost_to_unmapped_endpoints.values()) == 23


def test_ex01_reports_three_duplicate_valve_tags_but_does_not_raise() -> None:
    imported = import_proteus_sheet(_ex01_or_skip())
    duplicate_tags = [v for v in imported.report.violations if v.kind == "duplicate_tag"]
    assert len(duplicate_tags) == 3


def test_ex01_node_ids_are_identical_across_two_imports() -> None:
    path = _ex01_or_skip()
    first = import_proteus_sheet(path)
    second = import_proteus_sheet(path)
    assert set(first.sheet.graph.nodes) == set(second.sheet.graph.nodes)


def test_ex01_accounting_invariant_holds() -> None:
    imported = import_proteus_sheet(_ex01_or_skip())
    _assert_accounting_invariant(imported)


# ---- mindig futó eset: egy legenerált üzem oda-vissza Proteuson keresztül ----------------------


def test_a_generated_plant_survives_a_proteus_round_trip(tmp_path: Path) -> None:
    generated = generate_plant(GeneratorConfig(seed=1, n_units=4))
    save_proteus_equipment_only(generated.model, tmp_path, "plant")

    imported = import_proteus_sheet(tmp_path / "plant.xml")

    assert imported.sheet.graph.number_of_nodes() > 0
    for _, attrs in imported.sheet.graph.nodes(data=True):
        assert attrs["node_class"] in schema.EQUIPMENT_CLASSES
    _assert_accounting_invariant(imported)

    # a generátor csak berendezést exportál Proteusba (§3.7) — itt tehát tartja is a számot,
    # de ez nincs garantálva minden bemenetre (kg-construction.md §11 nyitott kérdés 4)
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


# ---- hand-built conceptual gráf: PlantSection nélküli szelep ----------------------------------


def test_map_conceptual_graph_tolerates_a_valve_with_no_owning_plant_section() -> None:
    """Egy szelep, amelynek forrás-berendezésén nincs `unit_id` — `_assign_valve_units` fixje."""
    conceptual: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    conceptual.add_node("pump", label="CentrifugalPump", tagName="P1")
    conceptual.add_node("valve", label="GlobeValve", pipingComponentNumber="V1")
    conceptual.add_edge("pump", "valve", label="Pipe", attr_name="pipingSource")

    plant, report = map_conceptual_graph(conceptual, plant_id="p", stream_kind={})

    assert report.valve_units_unresolved == 1
    assert set(plant.nodes) == {"pump", "valve"}
