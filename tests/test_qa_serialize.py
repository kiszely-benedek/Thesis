"""`serialize.py` — visible-only, deterministic GraphML text (`qa-system.md` §5, §18 QA-T3).

The strongest "no gold key" check available to a unit test reads the
`OccurrenceMap` and `SplitManifest` themselves (produced by the generator and
the splitter) to look for their exact values inside the serialized text —
that is a stronger claim than merely checking for the string `"uid"`.
`graph_view.py` and `serialize.py` are never allowed to import either type
themselves (`test_qa_graph_view_imports.py`); nothing stops a *test* from
using them as an oracle, the same way `test_neo4j_plan.py` does.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import networkx as nx
import pytest

from graph_plant_builder import GraphPlantBuilder
from plantgraph.adapters.pydexpi_proteus_import import import_proteus_sheet
from plantgraph.benchmark.generator import plan_plant
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.models import SplitManifest
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.splitter import split
from plantgraph.qa.graph_view import NetworkxGraphView
from plantgraph.qa.serialize import serialize_graph, serialize_occurrence_graph
from plantgraph.resolution.localize import OccurrenceMap, localize
from plantgraph.resolution.resolver import resolve

_CORPUS_ID = "acme-plant-01"
_EX01_PATH = Path(__file__).resolve().parent.parent / "data" / "external" / "C01V04-VER.EX01.xml"


def _four_unit_corpus() -> tuple[NetworkxGraphView, SplitManifest, OccurrenceMap]:
    generator_config = GeneratorConfig(seed=7)
    builder = GraphPlantBuilder(generator_config.plant_id)
    plan_plant(generator_config, builder)
    split_config = SplitConfig(sheet_equipment_budget=2, seed=7, duplication_rate=0.5)
    sheets, manifest = split(builder.graph, split_config)
    localized, occurrence_map = localize(sheets)
    resolution = resolve(localized)
    return NetworkxGraphView(_CORPUS_ID, localized, resolution), manifest, occurrence_map


def test_serialization_is_deterministic() -> None:
    view, _manifest, _occurrence_map = _four_unit_corpus()
    first = serialize_occurrence_graph(view)
    second = serialize_occurrence_graph(view)
    assert first.text == second.text
    assert first.character_count == len(first.text)


def test_serialized_text_contains_no_original_node_id() -> None:
    """The strongest available check: no id `localize()` renamed away is readable in the output."""
    view, manifest, occurrence_map = _four_unit_corpus()
    serialized = serialize_occurrence_graph(view)

    for original_key in occurrence_map.local_to_original.values():
        _sheet_id, _, original_node_id = original_key.partition(":")
        assert original_node_id not in serialized.text
    for pair in manifest.connector_pairs:
        if pair.original_edge is None:
            continue
        for original_node_id in pair.original_edge:
            assert original_node_id not in serialized.text


def test_serialized_text_reports_a_measured_character_count() -> None:
    view, _manifest, _occurrence_map = _four_unit_corpus()
    serialized = serialize_occurrence_graph(view)
    assert serialized.character_count > 0
    assert serialized.character_count == len(serialized.text)


def test_a_hidden_property_never_reaches_the_output() -> None:
    """`serialize_graph` enforces the whitelist itself — it does not trust its input's hygiene."""
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node(
        "S0:occ1",
        sheet_id="S0",
        node_class="CentrifugalPump",
        tag="P-1",
        uid="acme-plant-01|S0:occ1",
        corpus_id="acme-plant-01",
        stream_kind="process",
    )

    serialized = serialize_graph(graph)

    assert "uid" not in serialized.text
    assert "corpus_id" not in serialized.text
    assert "stream_kind" not in serialized.text
    assert "P-1" in serialized.text  # a visible property still comes through


def test_a_list_valued_property_is_flattened_for_graphml() -> None:
    """`dexpi_labels` is the one visible property that is a list (ADR-0016)."""
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node(
        "S0:occ1",
        sheet_id="S0",
        node_class="GenericItem",
        dexpi_class="ButterflyValve",
        dexpi_labels=["ButterflyValve", "OperatedValve", "PipingComponent"],
    )

    serialized = serialize_graph(graph)

    assert "ButterflyValve|OperatedValve|PipingComponent" in serialized.text


def test_node_without_sheet_id_is_rejected() -> None:
    graph: nx.DiGraph[str] = nx.DiGraph()
    graph.add_node("S0:occ1", node_class="CentrifugalPump", tag="P-1")
    with pytest.raises(ValueError, match="sheet_id"):
        serialize_graph(graph)


def test_serialize_graph_accepts_any_graph_not_only_the_occurrence_view() -> None:
    """ADR-0022 is still *proposed*: switching from S1 to S2 must be a one-line call-site change.

    `serialize_graph` never assumes its input came from `NetworkxGraphView` —
    a hand-built graph with the same node shape (an occurrence id, `sheet_id`,
    visible properties) serializes exactly the same way a merged `Resolution.plant`
    would, without any change to this module.
    """
    merged_plant: nx.DiGraph[str] = nx.DiGraph()
    merged_plant.add_node("S0:occ1", sheet_id="S0", node_class="CentrifugalPump", tag="P-1")
    merged_plant.add_node("S1:occ2", sheet_id="S1", node_class="GlobeValve", tag="GV-1")
    merged_plant.add_edge("S0:occ1", "S1:occ2", relation="send_to")

    serialized = serialize_graph(merged_plant)

    assert "P-1" in serialized.text
    assert "send_to" in serialized.text


def test_ex01_serializes_with_a_measured_character_count() -> None:
    if not _EX01_PATH.exists():
        pytest.skip(f"{_EX01_PATH} is absent; data/ is untracked (see CLAUDE.md)")

    imported = import_proteus_sheet(_EX01_PATH)
    localized, _occurrence_map = localize([imported.sheet])
    resolution = resolve(localized)
    view = NetworkxGraphView("ex01", localized, resolution)

    serialized = serialize_occurrence_graph(view)

    assert serialized.character_count == len(serialized.text)
    assert "66KL21" in serialized.text
    # PROMPT-03 (2026-09-27); unchanged by ADR-0044's untagged-node handling
    assert serialized.character_count == 17_693
    assert hashlib.sha256(serialized.text.encode()).hexdigest() == (
        "1bbec3f836fbbed046479dcd78e3e5430016ac7cf394e5b08102f2335f44eb9c"
    )
