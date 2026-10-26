"""The importer's `vocabulary` switch (ADR-0058, design pid-vocabulary section 4).

Under `v1` a real DEXPI file maps exactly as before (the golden in `test_v1_goldens.py` pins it);
under `v2` the classes on the allowlist keep their own names. Nothing here touches Neo4j: the
ingest runs with `--no-neo4j`, which still builds the full load plan.
"""

from __future__ import annotations

import collections
import json
from pathlib import Path

import networkx as nx
import pytest

from plantgraph.adapters.pydexpi_adapter import topology_node_class
from plantgraph.adapters.pydexpi_generic import classify, prepare_generic
from plantgraph.adapters.pydexpi_proteus_import import VocabularyName, import_proteus_sheet
from plantgraph.graph import schema
from plantgraph.ingest.__main__ import main as ingest_main
from plantgraph.ingest.pipeline import run_proteus
from plantgraph.qa.corpus import load_corpus_artifacts

_EX01_PATH = Path(__file__).resolve().parent.parent / "data" / "external" / "C01V04-VER.EX01.xml"

#: EX01's classes that v1 turns into `GenericItem` and v2 keeps; the counts were read from a run
_EX01_V2_KEPT = {
    "ReciprocatingPump": 1,
    "SwingCheckValve": 1,
    "PipeTee": 5,
    "BlindFlange": 2,
    "PipeReducer": 1,
    "PlateHeatExchanger": 1,
    "TubularHeatExchanger": 1,
}


def _require_ex01() -> Path:
    if not _EX01_PATH.exists():
        pytest.skip(f"{_EX01_PATH} is absent; data/ is untracked (see CLAUDE.md)")
    return _EX01_PATH


def _node_classes(vocabulary: VocabularyName) -> collections.Counter[str]:
    graph = import_proteus_sheet(_require_ex01(), vocabulary=vocabulary).sheet.graph
    return collections.Counter(attrs["node_class"] for _, attrs in graph.nodes(data=True))


# ---- the class mapping ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "under_v1", "under_v2"),
    [
        ("ReciprocatingPump", None, "ReciprocatingPump"),  # an allowlist class maps to itself
        ("CentrifugalPump", "CentrifugalPump", "CentrifugalPump"),
        ("CustomPump", None, "Pump"),  # Custom*: nearest allowlist ancestor
        ("CustomVessel", None, "Vessel"),
        ("CustomMixer", None, "Mixer"),
        ("CustomOperatedValve", None, "OperatedValve"),
        ("CustomCheckValve", "CheckValve", "CheckValve"),
        ("CustomCompressor", "Compressor", "Compressor"),
        ("CustomHeatExchanger", "HeatExchanger", "HeatExchanger"),
        ("CustomEquipment", None, None),  # no allowlist ancestor: the generic fallback takes it
        ("CustomPipingComponent", None, None),
        ("CustomBlower", None, None),  # `Blower` is not on the allowlist either
        ("Pipe", None, None),  # a segment, not a node
    ],
)
def test_custom_classes_map_to_their_nearest_allowlist_ancestor(
    label: str, under_v1: str | None, under_v2: str | None
) -> None:
    assert topology_node_class(label) == under_v1
    assert topology_node_class(label, schema.V2_IMPORTABLE_CLASSES) == under_v2


@pytest.mark.parametrize(
    ("label", "category", "first_label"),
    [
        ("CustomEquipment", schema.NodeCategory.EQUIPMENT, "CustomEquipment"),
        ("CustomPipingComponent", schema.NodeCategory.PIPING, "CustomPipingComponent"),
    ],
)
def test_custom_roots_become_generic_items_that_keep_their_label_chain(
    label: str, category: schema.NodeCategory, first_label: str
) -> None:
    conceptual: nx.MultiDiGraph[str] = nx.MultiDiGraph()
    conceptual.add_node("n1", label=label)

    prepared, infos = prepare_generic(conceptual, schema.V2_IMPORTABLE_CLASSES)

    assert prepared.nodes["n1"]["label"] == "GenericItem"
    assert infos["n1"] == classify(label)
    assert infos["n1"].category is category
    assert infos["n1"].labels[0] == first_label


def test_type_name_is_not_a_visible_property() -> None:
    assert "typeName" not in schema.VISIBLE_NODE_PROPERTIES
    assert "type_name" not in schema.VISIBLE_NODE_PROPERTIES


def test_the_default_vocabulary_is_v1_and_v2_is_the_wider_one() -> None:
    assert schema.IMPORT_VOCABULARIES == {
        "v1": schema.V1_IMPORTABLE_CLASSES,
        "v2": schema.V2_IMPORTABLE_CLASSES,
    }
    assert schema.V1_IMPORTABLE_CLASSES < schema.V2_IMPORTABLE_CLASSES


# ---- EX01 under both vocabularies ----------------------------------------------------------


def test_ex01_under_v2_keeps_the_true_classes() -> None:
    v1_counts, v2_counts = _node_classes("v1"), _node_classes("v2")

    for name, count in _EX01_V2_KEPT.items():
        assert v1_counts[name] == 0, f"{name} is a GenericItem under v1"
        assert v2_counts[name] == count
    assert v2_counts["GenericItem"] == 0


def test_ex01_has_the_same_nodes_and_edges_under_both_vocabularies() -> None:
    v1 = import_proteus_sheet(_require_ex01(), vocabulary="v1")
    v2 = import_proteus_sheet(_EX01_PATH, vocabulary="v2")

    assert sorted(v1.sheet.graph.nodes) == sorted(v2.sheet.graph.nodes)
    assert sorted(v1.sheet.graph.edges) == sorted(v2.sheet.graph.edges)
    assert v1.report.violations == v2.report.violations


# ---- the import record and the ingest CLI --------------------------------------------------


def test_the_v1_record_has_no_vocabulary_field_and_the_v2_record_has_one() -> None:
    path = _require_ex01()

    v1 = run_proteus(corpus_id="pytest-voc-v1", path=path, settings=None)
    v2 = run_proteus(corpus_id="EX01v2", path=path, settings=None, vocabulary="v2")

    assert v1.config == {"source_file": str(path)}
    assert v2.config == {"source_file": str(path), "vocabulary": "v2"}
    assert '"vocabulary"' not in v1.model_dump_json()


def test_ex01v2_ingests_without_neo4j_and_round_trips(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _require_ex01()

    ingest_main(
        ["proteus", str(path), "--vocabulary", "v2", "--corpus-id", "EX01v2"]
        + ["--no-neo4j", "--out", str(tmp_path)]
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["corpus_id"] == "EX01v2"
    assert payload["config"]["vocabulary"] == "v2"
    assert payload["load_report"] is None  # --no-neo4j: the plan was built, nothing was loaded
    artifacts = load_corpus_artifacts("EX01v2", tmp_path / "ingest.json")
    labels = artifacts.load_plan.expected_node_labels
    assert "PipeTee" in labels
    assert "GenericItem" not in labels


def test_the_cli_vocabulary_defaults_to_v1_and_rejects_other_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _require_ex01()
    ingest_main(["proteus", str(path), "--no-neo4j"])
    assert "vocabulary" not in json.loads(capsys.readouterr().out)["config"]

    with pytest.raises(SystemExit):
        ingest_main(["proteus", str(path), "--vocabulary", "v3", "--no-neo4j"])
