"""U3, the heater-reactor-separator (design 7.2, pid-vocabulary 5.2, 5.4, 13.3): loops, trims.

Each test builds one reactor system on the graph oracle and the DEXPI builder and checks the round
trip and the invariants S4, S7, S8, S9, S22 (`assert_pattern_invariants`) plus the rule it names.
S19 and S20 cover the agitated variant; the spec break is the line-number rule L20 (S10).
"""

from __future__ import annotations

import networkx as nx
import pytest
from instrument_harness import sources, targets
from instrument_invariants import check_s22
from machine_checks import check_s19, check_s20
from pattern_checks import (
    assert_line_numbers_unique_and_valid,
    assert_pattern_invariants,
    flow_graph,
    located_on,
    nodes_of_class,
    nodes_with_letters,
    reaches_a_safety_device,
)
from pattern_harness import PatternHarness, config_with
from test_column import letters, sensor_location
from trim_harness import ids_with_role

from plantgraph.benchmark.v2.config import GENERATED_EQUIPMENT_CLASSES
from plantgraph.benchmark.v2.patterns.ports import PatternInstance, Phase, PortDirection, PortKind
from plantgraph.benchmark.v2.patterns.reaction import build_reactor_system
from plantgraph.graph.schema import Relation

_PLAIN = {"U3.reactor": ("plain",)}
_TWO_PUMPS = {"p_single_pump": 0.0, "p_triple_pump_set": 0.0}
_STAY = {"pump_set.group": ("with_suction_vessel",)}


def reactor(
    cards: dict[str, tuple[str, ...]] | None = None, seed: int = 0, **sections: dict[str, object]
) -> tuple[PatternHarness, PatternInstance, nx.DiGraph[str]]:
    """Build one system: `sections` override knob groups (`trims={"p_skillet": 1.0}`)."""
    sections["patterns"] = {**_TWO_PUMPS, **sections.get("patterns", {})}
    deck_cards = {**_PLAIN, **_STAY, **(cards or {})}
    h = PatternHarness(seed, config_with(**sections), deck_cards=deck_cards)
    instance = build_reactor_system(h.pctx)
    instance.plan.write(h.builder)
    return h, instance, assert_pattern_invariants(h)


def one(instance: PatternInstance, role: str) -> str:
    """The id of the single node planned for `role`."""
    (node_id,) = ids_with_role(instance.plan, role)
    return node_id


def classes(graph: nx.DiGraph[str], node_ids: list[str] | set[str]) -> set[str]:
    """The node classes of `node_ids`."""
    return {graph.nodes[n]["node_class"] for n in node_ids}


# ---- ports and flow -----------------------------------------------------------------------------


def test_the_ports_are_feed_and_recycle_gas_in_then_gas_and_liquid_out_with_liquid_last() -> None:
    _, instance, graph = reactor()
    assert instance.port_names == ["feed", "recycle_gas", "gas", "liquid"]
    kinds = {p.name: (p.direction, p.phase, p.kind) for p in instance.ports}
    assert kinds == {
        "feed": (PortDirection.IN, Phase.LIQUID, PortKind.PROCESS),
        "recycle_gas": (PortDirection.IN, Phase.GAS, PortKind.RECYCLE),
        "gas": (PortDirection.OUT, Phase.GAS, PortKind.PROCESS),
        "liquid": (PortDirection.OUT, Phase.LIQUID, PortKind.PROCESS),
    }
    lines = {line.line_number: line for line in instance.plan.lines}
    for name in ("feed", "recycle_gas"):
        assert lines[instance.port(name).line_number].src_id is None
    for name in ("gas", "liquid"):
        assert lines[instance.port(name).line_number].dst_id is None
        assert instance.port(name).node_id in graph


def test_the_process_runs_exchanger_furnace_reactor_exchanger_cooler_separator() -> None:
    _, instance, graph = reactor()
    flow = flow_graph(graph)
    ids = [
        one(instance, r)
        for r in (
            "feed_effluent_exchanger",
            "fired_heater",
            "reactor",
            "effluent_cooler",
            "separator",
        )
    ]
    exchanger, furnace, reactor_id, cooler, separator = ids
    chain = [(exchanger, furnace), (furnace, reactor_id), (reactor_id, exchanger)]
    chain += [(exchanger, cooler), (cooler, separator)]
    for source, target in chain:
        assert nx.has_path(flow, source, target), (source, target)
    assert nx.has_path(flow, instance.port("feed").node_id, exchanger)
    assert nx.has_path(flow, separator, instance.port("gas").node_id)
    assert nx.has_path(flow, separator, instance.port("liquid").node_id)
    assert nx.has_path(flow, instance.port("recycle_gas").node_id, exchanger)


def test_the_furnace_has_no_blower_or_chimney_and_there_is_no_drain_pot() -> None:
    _, instance, _ = reactor()
    classes_planned = {e.node_class for e in instance.plan.equipment}
    assert classes_planned <= GENERATED_EQUIPMENT_CLASSES
    assert not {"CentrifugalBlower", "AxialFan"} & classes_planned
    assert "condensate_drain_pot" not in instance.plan.roles.values()  # S6: nothing to guard
    group_of = instance.drawing_group_of
    assert [n for n, g in group_of.items() if g == "G1"] == [one(instance, "fired_heater")]


# ---- fuel gas -----------------------------------------------------------------------------------


def test_fuel_gas_enters_the_furnace_through_pressure_and_temperature_valves_in_that_order() -> (
    None
):
    _, instance, graph = reactor()
    furnace = one(instance, "fired_heater")
    at_furnace = {
        letters(graph, v): v
        for v in nodes_with_letters(graph, "PV", "TV")
        if sensor_location(graph, v)[1] == furnace
    }
    assert set(at_furnace) == {"PV", "TV"}
    assert sensor_location(graph, at_furnace["PV"])[0] == "PIC"
    assert sensor_location(graph, at_furnace["TV"])[0] == "TIC"
    flow = flow_graph(graph)
    assert nx.has_path(flow, at_furnace["PV"], at_furnace["TV"])
    assert nx.has_path(flow, at_furnace["TV"], furnace)
    into_furnace = [d.get("fluid_code") for _, _, d in graph.in_edges(furnace, data=True)]
    assert "FG" in into_furnace


def test_fuel_gas_isolation_is_a_double_block_and_bleed_each_valve_with_one_driver() -> None:
    """F1 [HC]: XV, XV and a bleed XV on a tee between them; flame trip + two hand switches."""
    _, instance, graph = reactor()
    furnace = one(instance, "fired_heater")
    names = ("dbb_block_first", "dbb_block_second", "dbb_bleed_valve")
    first, second, bleed = (one(instance, role) for role in names)
    flow = flow_graph(graph)
    assert nx.has_path(flow, first, second) and not nx.has_path(flow, second, first)
    assert nx.has_path(flow, second, furnace)
    assert not nx.has_path(flow, bleed, furnace)  # the bleed vents to a safe place
    tee = one(instance, "dbb_tee")
    assert set(graph.successors(tee)) >= {second, bleed}
    driver_letters = {}
    for valve in (first, second, bleed):
        (actuator,) = sources(graph, valve, Relation.CONTROL)
        (bubble,) = sources(graph, actuator, Relation.SEND_SIGNAL_TO)
        driver_letters[valve] = letters(graph, bubble)
    assert driver_letters == {first: "BSL", second: "HS", bleed: "HS"}


def test_the_flame_sensor_is_on_the_furnace() -> None:
    _, instance, graph = reactor()
    (flame,) = nodes_with_letters(graph, "BE")
    assert sources(graph, flame, Relation.MEASURED_BY) == [one(instance, "fired_heater")]


# ---- reactor loops and protection ----------------------------------------------------------------


def test_the_reactor_inlet_temperature_moves_a_valve_on_a_bypass_around_the_exchanger() -> None:
    _, instance, graph = reactor()
    split, merge = one(instance, "bypass_split_tee"), one(instance, "bypass_merge_tee")
    reactor_id = one(instance, "reactor")
    bypass = [
        v
        for v in nodes_with_letters(graph, "TV")
        if nx.has_path(flow_graph(graph), split, v) and nx.has_path(flow_graph(graph), v, merge)
    ]
    assert len(bypass) == 1
    assert sensor_location(graph, bypass[0]) == ("TIC", reactor_id)
    assert merge in nx.descendants(flow_graph(graph), one(instance, "feed_effluent_exchanger"))


def test_the_reactor_has_a_safety_valve_and_a_rupture_disc() -> None:
    _, instance, graph = reactor()
    reactor_id = one(instance, "reactor")
    assert reaches_a_safety_device(graph, reactor_id)
    (disc,) = nodes_of_class(graph, "RuptureDisc")
    assert graph.has_edge(reactor_id, disc)
    assert graph.out_degree(disc) == 0  # its line ends open, toward the flare


def test_the_reactor_has_several_bed_temperatures_and_a_pressure_drop_tap() -> None:
    _, instance, graph = reactor()
    reactor_id = one(instance, "reactor")
    beds = [s for s in located_on(graph, reactor_id) if letters(graph, s) in {"TT", "TI"}]
    assert len(beds) >= 3
    (dp,) = nodes_with_letters(graph, "PDT")
    assert nx.has_path(flow_graph(graph), one(instance, "fired_heater"), reactor_id)
    assert dp in graph and "reactor_dp_tee" in set(instance.plan.roles.values())


@pytest.mark.parametrize(("chance", "expected"), [(1.0, True), (0.0, False)])
def test_the_multivariable_controller_reads_temperature_and_pressure_of_the_reactor(
    chance: float, expected: bool
) -> None:
    _, instance, graph = reactor(density={"p_multivariable": chance})
    assert bool(nodes_with_letters(graph, "UC")) is expected
    if expected:
        (controller,) = nodes_with_letters(graph, "UC")
        inputs = sources(graph, controller, Relation.SEND_SIGNAL_TO)
        assert sorted(letters(graph, s) for s in inputs) == ["PT", "TT"]
        assert all(
            sources(graph, s, Relation.MEASURED_BY) == [one(instance, "reactor")] for s in inputs
        )


@pytest.mark.parametrize("p_skillet", [1.0, 0.0])
def test_skillet_blinds_sit_at_the_furnace_and_reactor_inlets(p_skillet: float) -> None:
    _, instance, graph = reactor(trims={"p_skillet": p_skillet})
    skillets = nodes_of_class(graph, "PipeFlangeSpade", "PipeFlangeSpacer")
    furnace = one(instance, "fired_heater")
    at_furnace = [s for s in skillets if graph.has_edge(s, furnace)]  # last part before the furnace
    at_reactor = [s for s in skillets if graph.has_edge(furnace, s)]  # first part after it
    assert (len(skillets), len(at_furnace), len(at_reactor)) == (
        (2, 1, 1) if p_skillet else (0, 0, 0)
    )


# ---- separator ----------------------------------------------------------------------------------


def test_separator_pressure_moves_the_gas_valve_and_high_pressure_shuts_its_inlet() -> None:
    _, instance, graph = reactor()
    separator = one(instance, "separator")
    gas_valves = [
        v for v in nodes_with_letters(graph, "PV") if sensor_location(graph, v)[1] == separator
    ]
    assert len(gas_valves) == 1
    assert nx.has_path(flow_graph(graph), gas_valves[0], instance.port("gas").node_id)
    (switch,) = nodes_with_letters(graph, "PSHH")
    (sensor,) = sources(graph, switch, Relation.SEND_SIGNAL_TO)
    assert sources(graph, sensor, Relation.MEASURED_BY) == [separator]
    (actuator,) = targets(graph, switch, Relation.SEND_SIGNAL_TO)
    (trip_valve,) = targets(graph, actuator, Relation.CONTROL)
    assert graph.has_edge(trip_valve, separator) or nx.has_path(
        flow_graph(graph), trip_valve, separator
    )
    assert nx.has_path(flow_graph(graph), one(instance, "effluent_cooler"), trip_valve)


def test_separator_level_moves_a_letdown_valve_on_the_pump_discharge() -> None:
    _, instance, graph = reactor(instruments={"p_cascade": 0.0})
    separator = one(instance, "separator")
    (valve,) = nodes_with_letters(graph, "LV")
    assert graph.nodes[valve]["node_class"].startswith("Angle")
    assert sensor_location(graph, valve) == ("LIC", separator)
    pump = ids_with_role(instance.plan, "liquid_pump")[0]
    assert nx.has_path(flow_graph(graph), pump, valve)
    assert nx.has_path(flow_graph(graph), valve, instance.port("liquid").node_id)


def test_a_cascade_lets_the_level_controller_set_a_flow_controller() -> None:
    _, instance, graph = reactor(instruments={"p_cascade": 1.0})
    separator = one(instance, "separator")
    (valve,) = nodes_with_letters(graph, "FV")
    assert sensor_location(graph, valve)[0] == "FIC"
    assert not nodes_with_letters(graph, "LV")  # the letdown valve carries the flow loop's tag
    assert check_s22(graph) == 1
    (master,) = nodes_with_letters(graph, "LIC")
    assert sources(
        graph, next(iter(sources(graph, master, Relation.SEND_SIGNAL_TO))), Relation.MEASURED_BY
    ) == [separator]


def test_l20_the_letdown_valve_is_followed_by_a_spec_break_and_the_line_number_changes() -> None:
    _, instance, graph = reactor(instruments={"p_cascade": 0.0})
    (spec_break,) = nodes_of_class(graph, "PropertyBreak")
    (before,) = [(s, d) for s, _, d in graph.in_edges(spec_break, data=True)]
    (after,) = [(t, d) for _, t, d in graph.out_edges(spec_break, data=True)]
    assert before[1]["line_number"] != after[1]["line_number"]
    (valve,) = nodes_with_letters(graph, "LV")
    assert nx.has_path(flow_graph(graph), valve, spec_break)
    assert "tag" not in graph.nodes[spec_break]
    assert not located_on(graph, spec_break)  # nothing may sense a property break
    assert graph.nodes[after[0]]["node_class"].endswith("Valve")
    breaking = [line for line in instance.plan.lines if line.line_number_after_break]
    assert len(breaking) == 1
    assert instance.port("liquid").line_number == breaking[0].line_number


# ---- agitated variant ---------------------------------------------------------------------------


def test_the_agitated_reactor_has_a_motor_driven_agitator_started_from_a_hand_switch() -> None:
    _, instance, graph = reactor({"U3.reactor": ("agitated",)})
    reactor_id, agitator = one(instance, "reactor"), one(instance, "agitator")
    assert targets(graph, reactor_id, Relation.HAS_AGITATOR) == [agitator]
    assert graph.nodes[agitator]["node_class"] == "Agitator"
    assert any(e.node_id == agitator and e.has_motor for e in instance.plan.equipment)
    assert check_s19(graph) == 3  # two pumps and the agitator
    (actuator,) = sources(graph, agitator, Relation.CONTROL)
    (switch,) = sources(graph, actuator, Relation.SEND_SIGNAL_TO)
    assert letters(graph, switch) == "HS"
    assert "reactor=agitated" in instance.variant


def test_s20_the_agitator_and_its_drive_stay_on_the_reactor_sheet() -> None:
    _, instance, _ = reactor({"U3.reactor": ("agitated",)})
    assert (
        instance.drawing_group_of[one(instance, "agitator")]
        == instance.drawing_group_of[one(instance, "reactor")]
    )
    assert check_s20(instance) == 4  # has_agitator, the agitator's AEF and the two pumps' AEFs


def test_the_plain_reactor_has_no_agitator() -> None:
    _, instance, graph = reactor({"U3.reactor": ("plain",)})
    assert not nodes_of_class(graph, "Agitator")
    assert check_s19(graph) == 2  # the two pump motors' hand switches
    assert check_s20(instance) == 2


# ---- sheets and numbering -----------------------------------------------------------------------


def test_the_drawing_groups_are_furnace_exchanger_and_reactor_then_cooler_separator_pumps() -> None:
    _, instance, _ = reactor()
    group = instance.drawing_group_of
    assert group[one(instance, "fired_heater")] == "G1"
    assert (
        group[one(instance, "feed_effluent_exchanger")] == group[one(instance, "reactor")] == "G2"
    )
    assert group[one(instance, "effluent_cooler")] == group[one(instance, "separator")] == "G3"
    assert {group[p] for p in ids_with_role(instance.plan, "liquid_pump")} == {"G3"}


def test_a_pump_set_on_its_own_sheet_is_a_pinned_fourth_group() -> None:
    _, instance, _ = reactor({"pump_set.group": ("own_sheet",)})
    pumps = ids_with_role(instance.plan, "liquid_pump")
    assert {instance.drawing_group_of[p] for p in pumps} == {"G4"}
    assert instance.pinned_groups == {"G4"}


def test_line_numbers_are_unique_and_valid() -> None:
    _, instance, _ = reactor()
    assert_line_numbers_unique_and_valid(instance.plan.lines)


@pytest.mark.parametrize("seed", range(8))
def test_only_generated_equipment_classes_appear_and_s6_holds(seed: int) -> None:
    _, instance, graph = reactor(seed=seed)
    assert {e.node_class for e in instance.plan.equipment} <= GENERATED_EQUIPMENT_CLASSES
    for role in ("reactor", "separator"):
        assert reaches_a_safety_device(graph, one(instance, role))
