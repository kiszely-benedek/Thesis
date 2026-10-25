"""Goldens that freeze the v1 generator and importer (ADR-0057, design generator-v2-realism.md §2).

v2 adds new schema classes next to v1's. These digests prove that v1 output (generated plants,
ingest configs, the CypherRAG schema text, the EX01 import) stays byte-identical while it grows.
All values were recorded at HEAD `41820c9`, before V2-T0 touched any code. If one fails, a change
altered a frozen v1 artefact: fix the change, never the constant.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from plantgraph.adapters.pydexpi_builder import generate_plant
from plantgraph.adapters.pydexpi_io import save_json
from plantgraph.adapters.pydexpi_proteus_import import import_proteus_sheet
from plantgraph.benchmark.generator_models import GeneratorConfig
from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.graph import schema
from plantgraph.ingest.headline import HeadlinePreset
from plantgraph.ingest.pipeline import run_synthetic
from plantgraph.qa.final_answer import _answer_format_instruction
from plantgraph.qa.models import AnswerType
from plantgraph.qa.schema_text import build_schema_text
from plantgraph.store.plant_rows import StoreProfile
from qa_cypher_corpus import four_unit_corpus, load_plan_of

EX01_PATH = Path(__file__).resolve().parent.parent / "data" / "external" / "C01V04-VER.EX01.xml"

#: sha256 of the pyDEXPI JSON bytes of `generate_plant(GeneratorConfig(seed=s))`
_GOLDEN_DEXPI_JSON = {
    0: "43df47407927761013878bb34274fd9a329ab41f3cbcba441399c4841bae60f8",
    1: "9c49f18e1e42fc691454bc4794d71a7820fab312c34493c7c04af4baa650fe7f",
    2: "3e2840f2fa29f5ee7d9eea2469b2890a419625127d4376f913fd808b213aa7bb",
}
#: same, for the headline preset at 5 units, seed 1
_GOLDEN_DEXPI_JSON_HEADLINE_5_UNITS = (
    "8a94d88789b44c4331939ff850f52fd51cd0b88cfa005d279273f21d23ee3edd"
)
#: sha256 of the `config` block `run_synthetic` records (generator + split), as sorted JSON bytes
_GOLDEN_RUN_CONFIG = {
    0: "8a23d9b739f9509d12411eb323ac8c73b30f0717acc94ea953c062b4ef38372a",
    1: "a9e585a51d05d5b8eb2e35e795840446baf7fd0dfadfd7e298f10da26e0260c9",
    2: "b554011cc080da6ee70071a24574ccf0827f4dbaaa925c98ba7c960987a41dce",
}
_GOLDEN_RUN_CONFIG_HEADLINE_5_UNITS = (
    "213fc5a707244f0858d3d5b6da915584a92a97aabf3709f97a54830ce2ea5c70"
)
#: sha256 of `build_schema_text` for `four_unit_corpus()`, per store profile
_GOLDEN_SCHEMA_TEXT = {
    "occurrence": "8eb49a91c0ccee86d04f26ff30fef31a3464350c68654d134b906529f73ee7ff",
    "plant": "b5523639ddd13e1fa484d47d16fb15062a723dfe217950164d28200870a79022",
}
#: sha256 of the EX01 import: sorted (node_class, tag) pairs, sorted edges, ImportReport counts
_GOLDEN_EX01_IMPORT = "2df71dcc496820ea3d37c637f04199cec14c1892e92f76b04b1b450d83d71e24"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dexpi_json_sha256(config: GeneratorConfig) -> str:
    """Hash the bytes `JsonSerializer` writes for a generated plant (the publishable form)."""
    model = generate_plant(config).model
    with tempfile.TemporaryDirectory() as directory:
        save_json(model, Path(directory), "plant.json")
        return _sha256((Path(directory) / "plant.json").read_bytes())


def _run_config_sha256(generator_config: GeneratorConfig, split_config: SplitConfig) -> str:
    """Hash the `config` block of `run_synthetic`'s result, serialized with sorted keys."""
    result = run_synthetic(
        corpus_id="golden",
        generator_config=generator_config,
        split_config=split_config,
        check=False,
        settings=None,
    )
    config = result.config
    # `SplitConfig.equipment_classes` is a `set`, so its JSON list order follows PYTHONHASHSEED;
    # sort it so the digest pins the set's content, which is what v2 must not change.
    config["split"]["equipment_classes"] = sorted(config["split"]["equipment_classes"])
    return _sha256(json.dumps(config, sort_keys=True).encode())


def _small_split_config() -> SplitConfig:
    return SplitConfig(strategy="flow_greedy", sheet_equipment_budget=3, seed=0)


def _ex01_import_sha256() -> str:
    """Hash EX01's imported nodes, edges with relations, and the counts of its ImportReport."""
    imported = import_proteus_sheet(EX01_PATH)
    graph = imported.sheet.graph
    report = imported.report
    snapshot = {
        "nodes": sorted((d["node_class"], d.get("tag", "")) for _, d in graph.nodes(data=True)),
        "edges": sorted(
            (graph.nodes[u].get("tag", u), graph.nodes[v].get("tag", v), d["relation"])
            for u, v, d in graph.edges(data=True)
        ),
        "report": {
            "conceptual_nodes": report.conceptual_nodes,
            "conceptual_edges": report.conceptual_edges,
            "nodes_mapped": report.conversion.nodes_mapped,
            "edges_mapped_per_relation": report.conversion.edges_mapped_per_relation,
            "nodes_per_dexpi_class": report.nodes_per_dexpi_class,
            "edges_lost_to_unmapped_endpoints": report.edges_lost_to_unmapped_endpoints,
            "related_to_collapsed": report.related_to_collapsed,
            "violations": len(report.violations),
        },
    }
    return _sha256(json.dumps(snapshot, sort_keys=True).encode())


@pytest.mark.parametrize("seed", sorted(_GOLDEN_DEXPI_JSON))
def test_the_dexpi_json_of_a_default_plant_is_unchanged(seed: int) -> None:
    assert _dexpi_json_sha256(GeneratorConfig(seed=seed)) == _GOLDEN_DEXPI_JSON[seed]


def test_the_dexpi_json_of_the_headline_preset_is_unchanged() -> None:
    config = HeadlinePreset().generator_config(5, 1)
    assert _dexpi_json_sha256(config) == _GOLDEN_DEXPI_JSON_HEADLINE_5_UNITS


@pytest.mark.parametrize("seed", sorted(_GOLDEN_RUN_CONFIG))
def test_the_run_synthetic_config_block_of_a_default_plant_is_unchanged(seed: int) -> None:
    digest = _run_config_sha256(GeneratorConfig(seed=seed), _small_split_config())
    assert digest == _GOLDEN_RUN_CONFIG[seed]


def test_the_run_synthetic_config_block_of_the_headline_preset_is_unchanged() -> None:
    preset = HeadlinePreset()
    digest = _run_config_sha256(preset.generator_config(5, 1), preset.split_config(1))
    assert digest == _GOLDEN_RUN_CONFIG_HEADLINE_5_UNITS


@pytest.mark.parametrize("profile", sorted(_GOLDEN_SCHEMA_TEXT))
def test_the_cypher_rag_schema_text_is_unchanged(profile: StoreProfile) -> None:
    plan = load_plan_of(four_unit_corpus(), "golden", profile)
    assert _sha256(build_schema_text(plan).encode()) == _GOLDEN_SCHEMA_TEXT[profile]


@pytest.mark.skipif(not EX01_PATH.exists(), reason="EX01 file absent from data/external/")
def test_the_ex01_import_is_unchanged() -> None:
    assert _ex01_import_sha256() == _GOLDEN_EX01_IMPORT


# ---- the V1_* pins -----------------------------------------------------------------------------


_LIVE_AND_PINNED = [
    (schema.EQUIPMENT_CLASSES, schema.V1_EQUIPMENT_CLASSES),
    (schema.VALVE_CLASSES, schema.V1_VALVE_CLASSES),
    (schema.OPERATED_VALVE_CLASSES, schema.V1_OPERATED_VALVE_CLASSES),
    (schema.IMPORTABLE_CLASSES, schema.V1_IMPORTABLE_CLASSES),
    (schema.KNOWN_CLASSES, schema.V1_NODE_CLASSES),
]


@pytest.mark.parametrize(("live", "pinned"), _LIVE_AND_PINNED)
def test_each_v1_pin_is_a_proper_subset_of_its_live_schema_constant(
    live: frozenset[str], pinned: frozenset[str]
) -> None:
    """Since V2-T1 the live sets are larger; the pins stay the v1 vocabulary inside them."""
    assert pinned < live


@pytest.mark.parametrize(("live", "pinned"), _LIVE_AND_PINNED)
def test_the_live_constant_restricted_to_v1_classes_equals_the_pin(
    live: frozenset[str], pinned: frozenset[str]
) -> None:
    """Growing the schema added classes only; it did not move a v1 class in or out of a set."""
    assert live & schema.V1_NODE_CLASSES == pinned


def test_the_class_name_answer_instruction_lists_exactly_the_21_v1_classes() -> None:
    """The CLASS_NAME prompt text is pinned to v1 while the enum grows (ADR-0057, ADR-0058 Q3)."""
    v1_names = (
        "ActuatingFunction, BallValve, CentrifugalPump, CheckValve, Compressor, DrawingSet, "
        "FlowInPipeOffPageConnector, FlowInSignalOffPageConnector, FlowOutPipeOffPageConnector, "
        "FlowOutSignalOffPageConnector, GenericItem, GlobeValve, HeatExchanger, PlantSection, "
        "PressureVessel, ProcessColumn, ProcessInstrumentationFunction, ProcessPlant, "
        "ProcessSignalGeneratingFunction, Sheet, Tank"
    )
    expected = f"Answer with one of these class names, exactly as written: {v1_names}."
    assert _answer_format_instruction(AnswerType.CLASS_NAME) == expected


def test_the_v1_classes_keep_their_label_chains_and_tag_prefixes() -> None:
    """The ancestry rule reproduces every v1 row; the 16 chains and 9 prefixes are literals."""
    chains = {
        "CentrifugalPump": ("CentrifugalPump", "Pump", "Equipment", "TaggedPlantItem"),
        "Compressor": ("Compressor", "Equipment", "TaggedPlantItem"),
        "Tank": ("Tank", "Vessel", "Equipment", "TaggedPlantItem"),
        "PressureVessel": ("PressureVessel", "Vessel", "Equipment", "TaggedPlantItem"),
        "ProcessColumn": ("ProcessColumn", "Equipment", "TaggedPlantItem"),
        "HeatExchanger": ("HeatExchanger", "Equipment", "TaggedPlantItem"),
        "GlobeValve": ("GlobeValve", "OperatedValve", "PipingComponent"),
        "BallValve": ("BallValve", "OperatedValve", "PipingComponent"),
        "CheckValve": ("CheckValve", "PipingComponent"),
        "ProcessSignalGeneratingFunction": ("ProcessSignalGeneratingFunction",),
        "ProcessInstrumentationFunction": ("ProcessInstrumentationFunction",),
        "ActuatingFunction": ("ActuatingFunction",),
        "FlowOutPipeOffPageConnector": ("FlowOutPipeOffPageConnector", "PipeOffPageConnector"),
        "FlowInPipeOffPageConnector": ("FlowInPipeOffPageConnector", "PipeOffPageConnector"),
        "FlowOutSignalOffPageConnector": (
            "FlowOutSignalOffPageConnector",
            "SignalOffPageConnector",
        ),
        "FlowInSignalOffPageConnector": ("FlowInSignalOffPageConnector", "SignalOffPageConnector"),
    }
    prefixes = {
        "CentrifugalPump": "P", "Compressor": "C", "Tank": "TK", "PressureVessel": "V",
        "ProcessColumn": "T", "HeatExchanger": "E", "GlobeValve": "GV", "BallValve": "BV",
        "CheckValve": "CHV", "ProcessSignalGeneratingFunction": "{var}T",
        "ProcessInstrumentationFunction": "{var}IC",
    }  # fmt: skip
    for name, labels in chains.items():
        spec = schema.CLASS_SPECS[schema.NodeClass(name)]
        assert spec.labels == labels, name
        assert spec.tag_prefix == prefixes.get(name), name
