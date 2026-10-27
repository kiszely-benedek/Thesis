"""Invariants S13-S16 and S20 on the split corpus of a v2 plant (design 12.2, pid-vocabulary 8).

Where each invariant of S1-S24 is tested: S1-S12, S19, S21-S24 in `test_invariants_plant.py`;
S13-S16 and S20 here; S17 (the v1 goldens) in `tests/test_v1_goldens.py`; S18 in
`tests/test_schema_vocabulary.py`. The corpus is `corpus_v2.corpus(30)`: the real path (plan,
generate, split, localize, resolve) at about 30 sheets, with the headline preset.
"""

from __future__ import annotations

import os
import random
import re
import subprocess
import sys

import networkx as nx
from corpus_v2 import SEED, corpus
from plant_v2 import graph_of

from plantgraph.benchmark.generator_dispatch import generate_plant_graph_any
from plantgraph.benchmark.split_models import ConnectorLabelDetail
from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.graph import validation
from plantgraph.graph.schema import NodeClass, Relation
from plantgraph.ingest.headline_v2 import HeadlinePresetV2, smallest_n_units_v2
from plantgraph.ingest.pipeline import build_synthetic_corpus, run_synthetic

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


# ---- S13: a sound plant graph --------------------------------------------------------------------


def test_s13_the_plant_is_one_connected_graph_that_validates() -> None:
    c = corpus(30)
    assert nx.is_weakly_connected(c.plant)
    assert validation.validate_plant_graph(c.plant) == []


def test_s13_every_sheet_graph_validates_before_and_after_localize() -> None:
    c = corpus(30)
    for sheet in [*c.sheets, *c.localized_sheets]:
        assert validation.validate_sheet_graph(sheet.graph) == [], sheet.sheet_id


def test_s13_the_dexpi_conversion_drops_no_node_and_no_edge() -> None:
    _, report = graph_of(SEED, 12)
    assert set(report.nodes_dropped_per_class) <= {"ProcessPlant", "PlantSection"}
    assert report.edges_dropped_per_label == {}


# ---- S14: determinism ----------------------------------------------------------------------------

_DIGEST_SCRIPT = """
import hashlib
from pydexpi.loaders.json_serializer import JsonSerializer
from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.generate import generate_plant_v2
plant = generate_plant_v2(GeneratorConfigV2(seed=3, n_units=10))
print(hashlib.sha256(JsonSerializer().export_to_bytes(plant.model)).hexdigest())
"""


def _model_digest(hash_seed: int) -> str:
    env = {**os.environ, "PYTHONHASHSEED": str(hash_seed)}
    done = subprocess.run(
        [sys.executable, "-c", _DIGEST_SCRIPT], env=env, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def test_s14_the_pydexpi_json_bytes_are_the_same_under_hash_seeds_1_2_3() -> None:
    assert len({_model_digest(hash_seed) for hash_seed in (1, 2, 3)}) == 1


def test_s14_building_a_corpus_leaves_the_global_random_stream_alone() -> None:
    preset = HeadlinePresetV2()
    config = preset.generator_config(smallest_n_units_v2(6, preset, SEED).n_units, SEED)
    random.seed(123)
    expected = random.random()
    random.seed(123)
    build_synthetic_corpus(config, preset.split_config(SEED))
    assert random.random() == expected


def test_s14_no_identifier_is_a_random_uuid() -> None:
    plant = generate_plant_v2(GeneratorConfigV2(seed=2, n_units=6))
    graph, _ = plant.graph()
    assert not [n for n in graph.nodes if _UUID.fullmatch(str(n))]
    taggable = plant.model.conceptualModel.taggedPlantItems  # type: ignore[union-attr]
    assert not [item.id for item in taggable if _UUID.fullmatch(str(item.id))]


# ---- S15: prefix stability -----------------------------------------------------------------------


def test_s15_the_first_units_of_a_bigger_plant_have_the_same_nodes_gold_and_sheets() -> None:
    """The answer key of unit *u* (roles, groups, sheets) does not depend on later units."""
    small = generate_plant_v2(GeneratorConfigV2(seed=6, n_units=7))
    large = generate_plant_v2(GeneratorConfigV2(seed=6, n_units=16))
    assert small.plan.units == large.plan.units[:7]
    shared = small.record.node_gold
    assert shared and all(large.record.node_gold[node] == gold for node, gold in shared.items())
    assert small.record.spare_sets == large.record.spare_sets[: len(small.record.spare_sets)]


def test_s15_the_size_search_prefix_sum_matches_the_planned_sheets() -> None:
    preset = HeadlinePresetV2()
    result = smallest_n_units_v2(30, preset, SEED)
    planned = plan_plant(preset.generator_config(result.n_units, SEED))
    assert planned.sheet_count == result.predicted_sheets


# ---- S16: one unit per sheet, and the resolver gates ---------------------------------------------


def test_s16_every_sheet_graph_shows_one_unit() -> None:
    for sheet in corpus(30).sheets:
        units = {d["unit_id"] for _, d in sheet.graph.nodes(data=True) if "unit_id" in d}
        assert len(units) == 1, f"sheet {sheet.sheet_id} shows units {sorted(units)}"


def test_s16_gate_g1_holds_at_drawing_only_and_identity_is_perfect_at_exact_tags() -> None:
    preset = HeadlinePresetV2()
    assert preset.connector_label_detail is ConnectorLabelDetail.DRAWING_ONLY
    assert preset.exact_match_tags
    config = preset.generator_config(smallest_n_units_v2(30, preset, SEED).n_units, SEED)
    result = run_synthetic(
        corpus_id="invariants",
        generator_config=config,
        split_config=preset.split_config(SEED),
        check=True,
        settings=None,
    )
    assert result.gate_equal is True and result.gate_differences == []
    assert result.resolution_score is not None
    identity = result.resolution_score.identity
    assert (identity.precision, identity.recall) == (1.0, 1.0)
    assert identity.true_positives > 0  # the preset's duplication gave something to resolve


# ---- S20: machine wiring is never cut ------------------------------------------------------------


def test_s20_no_agitator_link_and_no_motor_control_edge_crosses_a_sheet() -> None:
    preset = HeadlinePresetV2()
    config = preset.generator_config(smallest_n_units_v2(30, preset, SEED).n_units, SEED)
    plant = generate_plant_graph_any(config)
    wiring = [
        (s, t)
        for s, t, d in plant.edges(data=True)
        if d["relation"] == Relation.HAS_AGITATOR.value
        or (
            d["relation"] == Relation.CONTROL.value
            and plant.nodes[s]["node_class"] == NodeClass.ACTUATING_ELECTRICAL_FUNCTION.value
        )
    ]
    assert wiring, "the plant has no machine wiring to check"
    assert all(plant.nodes[s]["sheet_group"] == plant.nodes[t]["sheet_group"] for s, t in wiring)
    # and the cut sheets keep every one of those edges: none became an off-page connector
    wanted = set(wiring)
    kept = sum(1 for sheet in corpus(30).sheets for edge in sheet.graph.edges if edge in wanted)
    assert kept == len(wiring)
