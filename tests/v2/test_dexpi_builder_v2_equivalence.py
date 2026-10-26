"""The DEXPI backend against the graph oracle, JSON, hash seeds, the stock loader, and bad input."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import networkx as nx
import pytest
from pydexpi.loaders.graph_loader import GraphLoader
from pydexpi.loaders.json_serializer import JsonSerializer

from graph_plant_builder_v2 import GraphPlantBuilderV2
from plantgraph.adapters.pydexpi_adapter import LinearGraphLoader
from plantgraph.adapters.pydexpi_adapter_v2 import plant_graph_v2
from plantgraph.adapters.pydexpi_builder_v2 import DexpiPlantBuilderV2
from plantgraph.adapters.pydexpi_io import load_json, save_json
from plantgraph.benchmark.v2.plan_models import (
    EquipmentSpec,
    GenerationRecordV2,
    LinkSpec,
)
from plantgraph.graph.schema import Relation
from v2_micro_plans import (
    instrument,
    item,
    line,
    link,
    plan_all,
    plan_base,
)

_NODE_KEYS = ("node_class", "tag", "plant_id", "unit_id", "loop_tag", "measured_variable")
_EDGE_KEYS = ("relation", "line_number", "fluid_code")
_RECORD = GenerationRecordV2(plant_id="plant0", seed=0, generator_config="{}", pydexpi_version="t")


def _project(graph: nx.DiGraph[str]) -> tuple[list[object], list[object]]:
    nodes = sorted(
        (n, tuple((k, d[k]) for k in _NODE_KEYS if k in d)) for n, d in graph.nodes(data=True)
    )
    edges = sorted(
        (s, t, tuple((k, d[k]) for k in _EDGE_KEYS if k in d)) for s, t, d in graph.edges(data=True)
    )
    return nodes, edges


def _dexpi_graph() -> nx.DiGraph[str]:
    builder = DexpiPlantBuilderV2("plant0")
    plan_all(builder)
    return plant_graph_v2(builder.build(), _RECORD)[0]


def test_dexpi_path_equals_the_oracle_on_node_and_edge_properties() -> None:
    oracle = GraphPlantBuilderV2("plant0")
    plan_all(oracle)
    assert _project(_dexpi_graph()) == _project(oracle.graph)


def test_json_round_trip_gives_the_same_graph(tmp_path: Path) -> None:
    builder = DexpiPlantBuilderV2("plant0")
    plan_all(builder)
    model = builder.build()
    save_json(model, tmp_path, "plant")
    reloaded, _ = plant_graph_v2(load_json(tmp_path, "plant"), _RECORD)
    assert _project(reloaded) == _project(plant_graph_v2(model, _RECORD)[0])


def test_linear_loader_equals_the_stock_loader() -> None:
    builder = DexpiPlantBuilderV2("plant0")
    plan_all(builder)
    model = builder.build()
    linear = LinearGraphLoader().dexpi_to_graph(model)
    stock = GraphLoader().dexpi_to_graph(model)
    assert list(linear.nodes) == list(stock.nodes)
    assert sorted(linear.nodes(data="label")) == sorted(stock.nodes(data="label"))
    assert sorted(linear.edges(keys=True)) == sorted(stock.edges(keys=True))


_DIGEST_SCRIPT = """
from plantgraph.adapters.pydexpi_builder_v2 import DexpiPlantBuilderV2
from pydexpi.loaders.json_serializer import JsonSerializer
import hashlib
from v2_micro_plans import plan_all
b = DexpiPlantBuilderV2("plant0"); plan_all(b)
print(hashlib.sha256(JsonSerializer().export_to_bytes(b.build())).hexdigest())
"""


def _digest_under_hash_seed(seed: int) -> str:
    env = {**os.environ, "PYTHONHASHSEED": str(seed), "PYTHONPATH": str(Path(__file__).parents[1])}
    result = subprocess.run(
        [sys.executable, "-c", _DIGEST_SCRIPT], env=env, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def test_model_json_is_identical_under_hash_seeds_1_to_3() -> None:
    digests = {_digest_under_hash_seed(seed) for seed in (1, 2, 3)}
    assert len(digests) == 1
    in_process = DexpiPlantBuilderV2("plant0")
    plan_all(in_process)
    assert digests == {
        hashlib.sha256(JsonSerializer().export_to_bytes(in_process.build())).hexdigest()
    }


# ---- refusals: every bad input raises with a message ----------------------------------------


def _base() -> DexpiPlantBuilderV2:
    builder = DexpiPlantBuilderV2("plant0")
    plan_base(builder)
    return builder


def test_duplicate_ids_and_unknown_references_raise() -> None:
    builder = _base()
    with pytest.raises(ValueError, match="added twice"):
        builder.add_equipment(
            EquipmentSpec(node_id="eq1", node_class="Tank", unit_no=1, tag="TK-109")
        )
    with pytest.raises(ValueError, match="never added via add_section"):
        builder.add_line(line(1, "eq1", (item("a", "GateValve", "GTV-1001"),), "eq2", unit=7))
    with pytest.raises(ValueError, match="'nope'"):
        builder.add_line(line(1, "eq1", (), "nope"))
    with pytest.raises(ValueError, match="same node id twice"):
        twin = item("a", "GateValve", "GTV-1001")
        builder.add_line(line(1, "eq1", (twin, twin), "eq2"))


def test_a_line_may_end_only_at_equipment_or_a_tee() -> None:
    builder = _base()
    builder.add_line(line(1, "eq1", (item("v", "GateValve", "GTV-1001"),), "eq2"))
    with pytest.raises(ValueError, match="must name added equipment or a PipeTee"):
        builder.add_line(line(2, "v", (item("w", "GateValve", "GTV-1002"),), None))


def test_a_bad_line_number_and_a_bad_class_raise_before_anything_is_built() -> None:
    builder = _base()
    bad = line(1, "eq1", (item("v", "GateValve", "GTV-1001"),), "eq2").model_copy(
        update={"line_number": "L1"}
    )
    with pytest.raises(ValueError, match="SIZE-SERVICE"):
        builder.add_line(bad)
    with pytest.raises(ValueError, match="expected a piping class"):
        builder.add_line(line(1, "eq1", (item("v", "Tank", "TK-1"),), "eq2"))
    assert builder._equipment["eq1"].nozzles == []  # no nozzle was left behind


@pytest.mark.parametrize(
    "action",
    [
        lambda b: b.add_line(line(1, "eq1", (item("p", "PropertyBreak"),), "eq2")),
        lambda b: b.add_instrument(instrument("a", "ActuatingElectricalFunction", None, "HS-1001")),
        lambda b: b.add_link(
            LinkSpec(relation=Relation.HAS_AGITATOR, source_id="eq4", target_id="eq1")
        ),
    ],
    ids=["property_break", "electrical_actuator", "has_agitator"],
)
def test_t5_constructs_are_refused(action: object) -> None:
    builder = _base()
    with pytest.raises(ValueError, match="T5|expected ProcessSignal"):
        action(builder)  # type: ignore[operator]


def test_wiring_mistakes_raise() -> None:
    builder = _base()
    builder.add_line(line(1, "eq1", (item("v", "GlobeValve", "FV-1001"),), "eq2"))
    builder.add_instrument(
        instrument("t", "ProcessSignalGeneratingFunction", "FT-1001", "FIC-1001")
    )
    builder.add_instrument(
        instrument("c", "ProcessInstrumentationFunction", "FIC-1001", "FIC-1001")
    )
    builder.add_instrument(
        instrument("o", "ProcessInstrumentationFunction", "FIC-1002", "FIC-1002")
    )
    builder.add_instrument(instrument("a", "ActuatingFunction", None, "FIC-1001"))
    with pytest.raises(ValueError, match="expected 'FIC-1002'"):
        link(
            builder, Relation.SEND_SIGNAL_TO, "t", "o"
        )  # sensor says loop FIC-1001, bubble is FIC-1002
    link(builder, Relation.SEND_SIGNAL_TO, "t", "c")
    with pytest.raises(ValueError, match="already feeds a bubble"):
        link(builder, Relation.SEND_SIGNAL_TO, "t", "o")
    with pytest.raises(ValueError, match="no signal runs from"):
        link(builder, Relation.SEND_SIGNAL_TO, "a", "c")
    with pytest.raises(ValueError, match="expected a sensor as the target"):
        link(builder, Relation.MEASURED_BY, "eq1", "c")
    with pytest.raises(ValueError, match="expected added equipment or an inline part"):
        link(builder, Relation.MEASURED_BY, "c", "t")
    with pytest.raises(ValueError, match="control valve body"):
        link(builder, Relation.CONTROL, "a", "eq1")


def test_build_refuses_loose_ends() -> None:
    builder = _base()
    builder.add_instrument(instrument("t", "ProcessSignalGeneratingFunction", "PI-1001", "PI-1001"))
    with pytest.raises(ValueError, match="senses nothing"):
        builder.build()
    link(builder, Relation.MEASURED_BY, "eq1", "t")
    builder.add_instrument(instrument("a", "ActuatingFunction", None, "FIC-1001"))
    with pytest.raises(ValueError, match="operates no valve"):
        builder.build()


def test_a_local_instrument_must_be_its_own_loop() -> None:
    builder = _base()
    builder.add_instrument(
        instrument("t", "ProcessSignalGeneratingFunction", "PI-1001", "FIC-1001")
    )
    link(builder, Relation.MEASURED_BY, "eq1", "t")
    with pytest.raises(ValueError, match="is its own loop"):
        builder.build()
