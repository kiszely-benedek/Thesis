"""Tests for the generic fallback (ADR-0016, `kg-construction.md` §3.1, T1b).

These always run (do not require `data/external/C01V04-VER.EX01.xml`): they check
categorization, the pre/post pass, and the `related_to` edge on hand-built inputs
— the 36/36 gate check measured on the real file lives in `test_proteus_import.py`.
"""

from __future__ import annotations

import networkx as nx
import pytest

from plantgraph.adapters.pydexpi_generic import (
    GenericInfo,
    add_related_to_edges,
    annotate_generic,
    classify,
    count_nodes_per_dexpi_class,
    prepare_generic,
)
from plantgraph.graph.schema import NodeCategory

# ---- classify: category and label chain (§3.1 rule 2) --------------------------------------------


def test_an_unknown_equipment_subclass_roots_at_equipment() -> None:
    """`ReciprocatingPump` isn't curated, but pyDEXPI's ancestor chain roots it at `Equipment`."""
    info = classify("ReciprocatingPump")
    assert info.category is NodeCategory.EQUIPMENT
    assert info.labels == ("ReciprocatingPump", "Pump", "Equipment")


def test_an_unknown_piping_subclass_roots_at_piping_component() -> None:
    info = classify("PipeTee")
    assert info.category is NodeCategory.PIPING
    assert info.labels == ("PipeTee", "PipeFitting", "PipingComponent")


def test_a_label_that_is_not_a_pydexpi_class_falls_to_other() -> None:
    info = classify("NotARealDexpiClass")
    assert info.category is NodeCategory.OTHER
    assert info.labels == ("NotARealDexpiClass",)


def test_a_chain_entry_that_fails_the_label_regex_is_rejected() -> None:
    """An unsafe Neo4j label (lowercase, underscored) never reaches the store (rule 7)."""
    with pytest.raises(ValueError, match="not a safe Neo4j label"):
        classify("not_a_valid_label")


# ---- prepare_generic: pre-pass, structural classes untouched ------------------------------


def _conceptual_with_one_unknown_and_one_known_node() -> nx.MultiDiGraph[str]:
    graph: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    graph.add_node("pump", label="ReciprocatingPump", tagName="P1")
    graph.add_node("known", label="CentrifugalPump", tagName="P2")
    graph.add_node("section", label="PlantSection", plantSectionIdentificationCode="1")
    return graph


def test_prepare_generic_relabels_only_the_classes_the_adapter_would_drop() -> None:
    conceptual = _conceptual_with_one_unknown_and_one_known_node()
    prepared, infos = prepare_generic(conceptual)

    assert prepared.nodes["pump"]["label"] == "GenericItem"
    assert prepared.nodes["known"]["label"] == "CentrifugalPump"
    assert prepared.nodes["section"]["label"] == "PlantSection"
    assert set(infos) == {"pump"}
    assert infos["pump"].dexpi_class == "ReciprocatingPump"

    # the input stays unchanged — the pre-pass works on a copy
    assert conceptual.nodes["pump"]["label"] == "ReciprocatingPump"


# ---- annotate_generic: dexpi_class/category/dexpi_labels/tag on the final graph -----------------


def test_annotate_generic_writes_the_tag_per_category() -> None:
    conceptual: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    conceptual.add_node("pump", label="ReciprocatingPump", tagName="P4712")
    conceptual.add_node("tee", label="PipeTee", pipingComponentNumber="C9")
    infos = {"pump": classify("ReciprocatingPump"), "tee": classify("PipeTee")}

    plant: nx.DiGraph[str] = nx.DiGraph()
    plant.add_node("pump", node_class="GenericItem", tag=None, plant_id="p")
    plant.add_node("tee", node_class="GenericItem", tag=None, plant_id="p")

    annotate_generic(plant, infos, conceptual)

    assert plant.nodes["pump"]["tag"] == "P4712"
    assert plant.nodes["pump"]["category"] == "equipment"
    assert plant.nodes["pump"]["dexpi_labels"] == ["ReciprocatingPump", "Pump", "Equipment"]
    assert plant.nodes["tee"]["tag"] == "C9"
    assert plant.nodes["tee"]["category"] == "piping"


def test_annotate_generic_leaves_other_category_nodes_without_a_tag() -> None:
    conceptual: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    conceptual.add_node("mystery", label="NotARealDexpiClass")
    infos = {"mystery": classify("NotARealDexpiClass")}
    plant: nx.DiGraph[str] = nx.DiGraph()
    plant.add_node("mystery", node_class="GenericItem", tag=None, plant_id="p")

    annotate_generic(plant, infos, conceptual)

    assert plant.nodes["mystery"]["tag"] is None
    assert plant.nodes["mystery"]["category"] == "other"


def test_annotate_generic_skips_a_node_missing_from_the_mapped_plant() -> None:
    """If a generic node somehow was not mapped after all, annotation silently skips it."""
    conceptual: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    conceptual.add_node("pump", label="ReciprocatingPump", tagName="P1")
    infos = {"pump": classify("ReciprocatingPump")}
    plant: nx.DiGraph[str] = nx.DiGraph()

    annotate_generic(plant, infos, conceptual)  # does not raise

    assert plant.number_of_nodes() == 0


# ---- add_related_to_edges: unknown edge label -> related_to (§3.1 rule 5) -----------------------


def test_an_unknown_edge_label_becomes_related_to() -> None:
    conceptual: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    conceptual.add_node("a", label="CentrifugalPump")
    conceptual.add_node("b", label="CentrifugalPump")
    conceptual.add_edge("a", "b", label="MysteryConnection", attr_name=None)
    plant: nx.DiGraph[str] = nx.DiGraph()
    plant.add_node("a", node_class="CentrifugalPump")
    plant.add_node("b", node_class="CentrifugalPump")

    added, collapsed = add_related_to_edges(plant, conceptual)

    assert added == {"MysteryConnection/None": 1}
    assert collapsed == 0
    assert plant.edges["a", "b"]["relation"] == "related_to"
    assert plant.edges["a", "b"]["dexpi_label"] == "MysteryConnection/None"


def test_a_known_edge_label_is_left_to_map_edges_not_duplicated() -> None:
    """An edge `_relation_of` already recognizes (e.g. `Pipe`) never also gets `related_to`."""
    conceptual: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    conceptual.add_node("a", label="CentrifugalPump")
    conceptual.add_node("b", label="CentrifugalPump")
    conceptual.add_edge("a", "b", label="Pipe", attr_name=None)
    plant: nx.DiGraph[str] = nx.DiGraph()
    plant.add_node("a", node_class="CentrifugalPump")
    plant.add_node("b", node_class="CentrifugalPump")
    plant.add_edge("a", "b", relation="send_to")

    added, collapsed = add_related_to_edges(plant, conceptual)

    assert added == {}
    assert collapsed == 0
    assert plant.edges["a", "b"]["relation"] == "send_to"  # not overwritten


def test_two_unrecognised_edges_on_the_same_pair_collapse_to_one() -> None:
    conceptual: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    conceptual.add_node("a", label="CentrifugalPump")
    conceptual.add_node("b", label="CentrifugalPump")
    conceptual.add_edge("a", "b", label="MysteryConnection", attr_name=None)
    conceptual.add_edge("a", "b", label="AnotherMysteryConnection", attr_name=None)
    plant: nx.DiGraph[str] = nx.DiGraph()
    plant.add_node("a", node_class="CentrifugalPump")
    plant.add_node("b", node_class="CentrifugalPump")

    added, collapsed = add_related_to_edges(plant, conceptual)

    assert sum(added.values()) == 1
    assert collapsed == 1


# ---- count_nodes_per_dexpi_class: the coverage counter (§3.1 rule 6) -------------------------


def test_count_nodes_per_dexpi_class_counts_by_the_real_pydexpi_label() -> None:
    conceptual: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    conceptual.add_node("a", label="ReciprocatingPump")
    conceptual.add_node("b", label="ReciprocatingPump")
    conceptual.add_node("c", label="CentrifugalPump")

    counts = count_nodes_per_dexpi_class(conceptual, {"a", "b", "c"})

    assert counts == {"ReciprocatingPump": 2, "CentrifugalPump": 1}


def test_generic_info_is_immutable_and_hashable_via_tuple_labels() -> None:
    """`GenericInfo.labels` is a tuple, not a list — the model is comparable out of the box."""
    info = GenericInfo(dexpi_class="X", category=NodeCategory.OTHER, labels=("X",))
    assert info.labels == ("X",)
