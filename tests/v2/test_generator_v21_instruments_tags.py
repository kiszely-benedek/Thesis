"""Generator v2.1, F8c: instruments sit where they measure, and tags say what they are.

Each rule is a test on one reactor system or one micro plan; the seeded counts (seed 1, 60 units)
show the same rule over a whole plant. Counts recorded before the fix are in each docstring.
"""

from __future__ import annotations

import networkx as nx
import pytest
from instrument_harness import sources
from pattern_checks import located_on, nodes_with_letters
from plant_v2 import generated, graph_of
from test_column import letters
from test_reaction import one, reactor
from trim_harness import STYLE, TrimHarness, ids_with_role

from plantgraph.adapters.pydexpi_adapter_v2 import plant_graph_v2
from plantgraph.adapters.pydexpi_builder_v2 import DexpiPlantBuilderV2
from plantgraph.adapters.pydexpi_builder_v2_equipment import split_spare_suffix
from plantgraph.benchmark.v2 import trims_extra
from plantgraph.benchmark.v2.plan_models import EquipmentSpec, GenerationRecordV2
from plantgraph.benchmark.v2.tags import parse_line_number
from plantgraph.benchmark.v2.trim_plan import main_line
from plantgraph.benchmark.v2.vocabulary import LINE_SPECS
from plantgraph.graph.schema import EQUIPMENT_CLASSES, Relation
from v2_micro_plans import motor_pump, plan_base

_SEED, _UNITS = 1, 60
_PIPE_TEE = "PipeTee"


# ---- fuel-gas and heater-outlet sensors ---------------------------------------------------------


def _fuel_gas_controllers(graph: nx.DiGraph[str]) -> list[str]:
    """The controllers whose valve sits on a fuel-gas (`FG`) line."""
    controllers = []
    for valve in nodes_with_letters(graph, "PV", "TV"):
        lines = [d.get("fluid_code") for *_, d in [*graph.in_edges(valve, data=True)]]
        if "FG" not in lines:
            continue
        (actuator,) = sources(graph, valve, Relation.CONTROL)
        controllers += sources(graph, actuator, Relation.SEND_SIGNAL_TO)
    return controllers


def _sensor_locations(graph: nx.DiGraph[str], controller: str) -> list[str]:
    sensors = [
        s
        for s in sources(graph, controller, Relation.SEND_SIGNAL_TO)
        if graph.nodes[s]["node_class"] == "ProcessSignalGeneratingFunction"
    ]
    return [place for sensor in sensors for place in sources(graph, sensor, Relation.MEASURED_BY)]


def test_the_fuel_gas_loops_sense_pipe_tees_and_no_loop_sensor_sits_on_the_furnace() -> None:
    _, instance, graph = reactor()
    furnace = one(instance, "fired_heater")
    where = {letters(graph, c): _sensor_locations(graph, c) for c in _fuel_gas_controllers(graph)}
    pressure_tee, outlet_tee = (
        one(instance, "fuel_gas_pressure_tee"),
        one(instance, "heater_outlet_tee"),
    )
    assert where == {"PIC": [pressure_tee], "TIC": [outlet_tee]}
    assert {graph.nodes[n]["node_class"] for n in (pressure_tee, outlet_tee)} == {_PIPE_TEE}
    assert all(
        graph.nodes[s]["loop_tag"][:3] not in {"PIC", "TIC"} for s in located_on(graph, furnace)
    )


def test_the_heater_outlet_gauge_sits_on_the_heater_outlet_line() -> None:
    _, instance, graph = reactor()
    (gauge,) = ids_with_role(instance.plan, "heater_outlet_pi")
    assert sources(graph, gauge, Relation.MEASURED_BY) == [one(instance, "heater_outlet_tee")]


def test_seeded_plant_no_control_loop_measures_a_furnace() -> None:
    """Seed 1, 60 units: loops with one sensor on one equipment item, located on a furnace.

    Before F8c every U3 furnace had its fuel-gas `PIC` and `TIC` here (2 per U3 unit); after, none:
    those loops sense a pipe tee, which LOOP_MEASURED_EQUIPMENT leaves out (it names an item the
    loop measures, and a furnace is not what a fuel-gas pressure loop measures).
    """
    graph, _ = graph_of(_SEED, _UNITS)
    furnaces = {n for n, d in graph.nodes(data=True) if d["node_class"] == "Furnace"}
    fuel_loops = _fuel_gas_controllers(graph)
    assert furnaces and len(fuel_loops) == 2 * len(furnaces)  # both loops of every furnace
    for controller in fuel_loops:
        locations = _sensor_locations(graph, controller)
        assert len(locations) == 1
        assert graph.nodes[locations[0]]["node_class"] not in EQUIPMENT_CLASSES


# ---- reactor type code --------------------------------------------------------------------------


def test_the_reactor_is_tagged_r() -> None:
    _, instance, _ = reactor()
    (spec,) = [e for e in instance.plan.equipment if e.node_id == one(instance, "reactor")]
    assert spec.tag.startswith("R-")


def test_seeded_plant_every_reactor_tag_starts_with_r() -> None:
    """Seed 1, 60 units: before F8c no equipment tag started `R-`; after, one per U3 unit."""
    plant = generated(_SEED, _UNITS)
    plans = [unit.instance.plan for unit in plant.plan.units]
    reactors = [e for p in plans for e in p.equipment if p.roles[e.node_id] == "reactor"]
    assert reactors and all(e.tag.startswith("R-") for e in reactors)
    graph, _ = graph_of(_SEED, _UNITS)
    assert sum(str(d.get("tag", "")).startswith("R-") for _, d in graph.nodes(data=True)) == len(
        reactors
    )


# ---- service code of a branch line --------------------------------------------------------------


def _lines_with_role(plan_lines: tuple, roles: dict[str, str], role: str) -> list:  # type: ignore[type-arg]
    return [line for line in plan_lines if any(roles.get(i.node_id) == role for i in line.items)]


def test_a_gas_vessel_drains_liquid_and_a_psv_drain_is_flare() -> None:
    """The separator sits on a gas line (`PG`) but its drain carries liquid (`P`)."""
    _, instance, _ = reactor(trims={"p_psv_drain": 1.0, "p_psv_blocks": 0.5})
    plan = instance.plan
    drains = _lines_with_role(plan.lines, plan.roles, "vessel_drain_valve")
    assert drains and {line.fluid_code for line in drains} == {"P"}
    psv_drains = _lines_with_role(plan.lines, plan.roles, "psv_drain_valve")
    assert psv_drains and {line.fluid_code for line in psv_drains} == {"FL"}


def test_seeded_plant_no_vessel_drain_is_gas_coded() -> None:
    """Seed 1, 60 units: vessel drains coded `PG` before F8c (drains of vessels on a gas line)."""
    plant = generated(_SEED, _UNITS)
    gas_coded = [
        line
        for unit in plant.plan.units
        for line in _lines_with_role(
            unit.instance.plan.lines, unit.instance.plan.roles, "vessel_drain_valve"
        )
        if line.fluid_code == "PG"
    ]
    assert gas_coded == []


# ---- the multivariable controller's inputs ------------------------------------------------------


def test_the_multivariable_controller_inputs_measure_temperature_and_pressure() -> None:
    """`TT` and `PT` feeding a `UC` carried `U` (the controller's letter) before F8c."""
    _, _, graph = reactor(density={"p_multivariable": 1.0})
    (controller,) = nodes_with_letters(graph, "UC")
    inputs = sources(graph, controller, Relation.SEND_SIGNAL_TO)
    measured = {letters(graph, s): graph.nodes[s]["measured_variable"] for s in inputs}
    assert measured == {"TT": "T", "PT": "P"}
    assert graph.nodes[controller]["measured_variable"] == "U"


# ---- spec break: lighter class after the pressure drop -------------------------------------------


@pytest.mark.parametrize("spec", LINE_SPECS)
def test_the_class_after_a_spec_break_is_lighter_than_before(spec: str) -> None:
    """Before F8c the stretch after the letdown valve went one class *up* in rating."""
    h = TrimHarness()
    style = STYLE.model_copy(update={"spec": spec})
    src, dst = h.equipment("PressureVessel", "V"), h.equipment("Tank", "TK")
    line = main_line(h.ctx, style, src, trims_extra.spec_break(h.ctx, style).run, dst)
    before, after = (parse_line_number(number) for number in line.line_numbers)
    assert before is not None and after is not None
    assert LINE_SPECS.index(before.spec) > LINE_SPECS.index(after.spec)


# ---- the spare letter is a tag suffix, not part of the sequence number ----------------------


@pytest.mark.parametrize(
    ("number", "expected"),
    [("1203", ("1203", None)), ("1203A", ("1203", "A")), ("12007C", ("12007", "C"))],
)
def test_split_spare_suffix(number: str, expected: tuple[str, str | None]) -> None:
    assert split_spare_suffix(number) == expected


def test_a_spare_pump_keeps_its_tag_and_stores_the_letter_as_suffix() -> None:
    builder = DexpiPlantBuilderV2("plant0")
    plan_base(builder)
    motor_pump(builder, "spare-a", 60)  # tag P-160: unit 1, sequence 60
    spare = builder.build()
    record = GenerationRecordV2(
        plant_id="plant0", seed=0, generator_config="{}", pydexpi_version="t"
    )
    graph, _ = plant_graph_v2(spare, record)
    assert graph.nodes["spare-a"]["tag"] == "P-160"  # a plain number keeps no suffix

    builder = DexpiPlantBuilderV2("plant0")
    plan_base(builder)
    builder.add_equipment(
        EquipmentSpec(node_id="p-b", node_class="CentrifugalPump", unit_no=1, tag="P-170B")
    )
    model = builder.build()
    (pump,) = [e for e in model.conceptualModel.taggedPlantItems if getattr(e, "id", None) == "p-b"]
    assert (pump.tagNamePrefix, pump.tagNameSequenceNumber, pump.tagNameSuffix) == (
        "P",
        "170",
        "B",
    )
    assert pump.tagName == "P-170B"
    graph, _ = plant_graph_v2(model, record)
    assert graph.nodes["p-b"]["tag"] == "P-170B"
