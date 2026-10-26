"""U4, the tank farm (design 7.2, pid-vocabulary 13.3): each variant, and its trips and trims.

Each test builds the farm on the graph oracle and the DEXPI builder and checks the round trip and
the invariants S4, S7, S8, S9, S22 (`assert_pattern_invariants`) plus the rule it names.
"""

from __future__ import annotations

import networkx as nx
import pytest
from instrument_harness import sources
from pattern_checks import (
    assert_line_numbers_unique_and_valid,
    assert_pattern_invariants,
    located_on,
    nodes_of_class,
    nodes_with_letters,
)
from pattern_harness import PatternHarness, config_with
from trim_harness import classes_of, ids_with_role, send_to_path

from plantgraph.benchmark.v2.patterns.ports import PatternInstance, Phase, PortDirection
from plantgraph.benchmark.v2.patterns.storage import build_tank_farm
from plantgraph.benchmark.v2.tags import parse_tag
from plantgraph.graph.schema import Relation


def _farm(
    cards: dict[str, tuple[str, ...]] | None = None,
    seed: int = 0,
    density: dict[str, object] | None = None,
    patterns: dict[str, object] | None = None,
) -> tuple[PatternHarness, PatternInstance, nx.DiGraph[str]]:
    """Build one farm in a harness; returns the harness, the instance and the oracle graph."""
    config = config_with(density=density or {}, patterns=patterns or {})
    h = PatternHarness(seed, config, deck_cards=cards)
    instance = build_tank_farm(h.pctx)
    instance.plan.write(h.builder)
    return h, instance, assert_pattern_invariants(h)


def _tanks(instance: PatternInstance) -> list[str]:
    return [e.node_id for e in instance.plan.equipment if e.node_class == "Tank"]


def _pumps(instance: PatternInstance) -> list[str]:
    return [e.node_id for e in instance.plan.equipment if e.node_class != "Tank"]


# ---- variants ------------------------------------------------------------------------------------


@pytest.mark.parametrize("count", ["2", "3", "4"])
def test_tank_count_variant_gives_that_many_tanks_two_to_a_group(count: str) -> None:
    _, instance, _ = _farm({"U4.tank_count": (count,)})
    tanks = _tanks(instance)
    groups = [instance.drawing_group_of[t] for t in tanks]
    assert len(tanks) == int(count)
    assert groups == ["G1", "G1", "G2", "G2"][: int(count)]


def test_the_pumps_join_the_last_tanks_group_or_get_a_pinned_sheet() -> None:
    two_pumps = {"p_single_pump": 0.0, "p_triple_pump_set": 0.0}
    tanks = {"U4.tank_count": ("3",)}
    _, joined, _ = _farm(tanks | {"pump_set.group": ("with_suction_vessel",)}, patterns=two_pumps)
    _, own, _ = _farm(tanks | {"pump_set.group": ("own_sheet",)}, patterns=two_pumps)
    assert {joined.drawing_group_of[p] for p in _pumps(joined)} == {"G2"}
    assert joined.pinned_groups == frozenset()
    assert {own.drawing_group_of[p] for p in _pumps(own)} == {"G3"}
    assert own.pinned_groups == frozenset({"G3"})


@pytest.mark.parametrize("pump_class", ["CentrifugalPump", "RotaryPump"])
def test_transfer_pump_variant_sets_the_class_and_the_tank_drain_valve(pump_class: str) -> None:
    """Rotary pumps move viscous liquid, so the tank drain is an angle plug valve."""
    _, instance, graph = _farm({"U4.transfer_pump": (pump_class,)})
    assert {graph.nodes[p]["node_class"] for p in _pumps(instance)} == {pump_class}
    drains = ids_with_role(instance.plan, "tank_drain_valve")
    assert len(drains) == len(_tanks(instance))
    plug = {graph.nodes[d]["node_class"] == "AnglePlugValve" for d in drains}
    assert plug == {pump_class == "RotaryPump"}


@pytest.mark.parametrize(
    "metering",
    [
        "none",
        "MassFlowMeasuringElement",
        "PositiveDisplacementFlowMeter",
        "TurbineFlowMeter",
        "VolumeFlowMeasuringElement",
    ],
)
def test_metering_variant_adds_one_element_with_a_totaliser_or_nothing(metering: str) -> None:
    _, instance, graph = _farm({"U4.metering": (metering,)})
    totalisers = nodes_with_letters(graph, "FQI")
    if metering == "none":
        assert not totalisers
        return
    (meter,) = nodes_of_class(graph, metering)
    assert graph.nodes[meter]["tag"].startswith("FE-")
    (totaliser,) = totalisers
    assert (
        parse_tag(graph.nodes[totaliser]["tag"]).sequence
        == parse_tag(graph.nodes[meter]["tag"]).sequence
    )
    out = instance.port("transfer").node_id
    assert meter in send_to_path(graph, _pumps(instance)[0], out)


@pytest.mark.parametrize("manifold", ["GateValve", "PlugValve"])
def test_manifold_variant_sets_the_class_of_the_receipt_and_tank_valves(manifold: str) -> None:
    _, instance, graph = _farm({"U4.manifold": (manifold,)})
    manifold_roles = ("receipt_manifold_valve", "tank_inlet_block", "tank_outlet_block")
    valves = [v for role in manifold_roles for v in ids_with_role(instance.plan, role)]
    assert valves and {graph.nodes[v]["node_class"] for v in valves} == {manifold}


@pytest.mark.parametrize("service", ["flammable", "non_flammable"])
def test_tank_service_variant_picks_the_vent_arrangement(service: str) -> None:
    """6.19: flame arrestor and breather valve for flammable contents, else a plain vent."""
    _, instance, graph = _farm({"U4.tank_service": (service,)})
    tanks = len(_tanks(instance))
    arrestors = nodes_of_class(graph, "FlameArrestor")
    breathers = nodes_of_class(graph, "BreatherValve")
    plain = nodes_of_class(graph, "VentilationDevice")
    if service == "flammable":
        assert (len(arrestors), len(breathers), len(plain)) == (tanks, tanks, 0)
    else:
        assert (len(arrestors), len(breathers), len(plain)) == (0, 0, tanks)


def _farm_with_receipts(count: int) -> tuple[PatternHarness, PatternInstance, nx.DiGraph[str]]:
    for seed in range(20):
        h = PatternHarness(seed)
        instance = build_tank_farm(h.pctx)
        if len(instance.ports) == count + 1:
            instance.plan.write(h.builder)
            return h, instance, assert_pattern_invariants(h)
    raise AssertionError(f"no seed below 20 gave {count} receipt lines")


def test_one_receipt_line_is_one_in_port_and_the_transfer_line_is_the_out_port() -> None:
    _, instance, _ = _farm_with_receipts(1)
    assert instance.port_names == ["receipt1", "transfer"]
    receipt, transfer = instance.port("receipt1"), instance.port("transfer")
    assert (receipt.direction, receipt.phase) == (PortDirection.IN, Phase.LIQUID)
    assert (transfer.direction, transfer.phase) == (PortDirection.OUT, Phase.LIQUID)


def test_a_second_receipt_line_joins_the_first_at_a_merge_tee() -> None:
    _, instance, graph = _farm_with_receipts(2)
    assert instance.port_names == ["receipt1", "receipt2", "transfer"]
    (merge,) = ids_with_role(instance.plan, "receipt_merge_tee")
    second = instance.port("receipt2")
    assert graph.has_edge(second.node_id, merge)
    first = instance.port("receipt1")
    assert merge in send_to_path(graph, first.node_id, _tanks(instance)[-1])


# ---- trips and trims -----------------------------------------------------------------------------


def test_every_tank_inlet_has_one_valve_for_the_hand_switch_and_one_for_the_overfill_trip() -> None:
    """One driver per XV: two on-off valves in series, driven by `HS` and by `LT -> LSHH`."""
    _, instance, graph = _farm({"U4.tank_count": ("3",)})
    first = instance.port("receipt1").node_id
    for tank in _tanks(instance):
        path = send_to_path(graph, first, tank)
        on_off = [n for n in path if (graph.nodes[n].get("tag") or "")[:2] in ("XV", "YV")]
        assert len(on_off) == 2
        drivers = []
        for valve in on_off:
            (actuator,) = sources(graph, valve, Relation.CONTROL)
            (driver,) = sources(graph, actuator, Relation.SEND_SIGNAL_TO)
            drivers.append(graph.nodes[driver]["tag"].partition("-")[0])
        assert sorted(drivers) == ["HS", "LSHH"]


def test_the_overfill_transmitter_is_located_on_the_tank_it_protects() -> None:
    _, instance, graph = _farm({"U4.tank_count": ("2",)})
    for tank in _tanks(instance):
        letters = {graph.nodes[s]["tag"].partition("-")[0] for s in located_on(graph, tank)}
        assert {"LT", "TI"} <= letters


def test_every_tank_has_a_level_indicator_a_vent_and_a_drain() -> None:
    _, instance, graph = _farm({"U4.tank_count": ("4",), "U4.tank_service": ("flammable",)})
    for tank in _tanks(instance):
        assert any(
            classes_of(graph, [t])[0] == "FlameArrestor" for t in graph.successors(tank)
        )  # the vent starts at the roof nozzle
    assert len(ids_with_role(instance.plan, "tank_drain_valve")) == 4
    assert len(nodes_with_letters(graph, "LI", "LIAH")) == 4


@pytest.mark.parametrize(("chance", "expected"), [(1.0, True), (0.0, False)])
def test_optional_level_alarms_follow_their_chances(chance: float, expected: bool) -> None:
    density = {"p_optional_instrument": chance, "p_point_level_switch": chance}
    _, _, graph = _farm({"U4.tank_count": ("2",)}, density=density)
    assert bool(nodes_with_letters(graph, "LSLL")) is expected
    assert bool(nodes_with_letters(graph, "LSH", "LSL")) is expected


def test_the_transfer_rate_is_held_by_a_flow_loop_on_the_pump_header() -> None:
    _, instance, graph = _farm()
    path = send_to_path(graph, _pumps(instance)[0], instance.port("transfer").node_id)
    letters = [(graph.nodes[n].get("tag") or "").partition("-")[0] for n in path]
    assert "FE" in letters and "FV" in letters
    assert nodes_with_letters(graph, "FIC")


# ---- suction, lines, decks -----------------------------------------------------------------------


def test_s1_the_pumps_draw_from_the_last_tank_and_the_others_feed_the_suction_header() -> None:
    _, instance, graph = _farm({"U4.tank_count": ("3",)})
    tanks, pump = _tanks(instance), _pumps(instance)[0]
    roles = [instance.plan.roles.get(n) for n in send_to_path(graph, tanks[-1], pump)]
    assert roles.index("suction_block") < roles.index("suction_strainer")
    for tank in tanks[:-1]:
        roles = [instance.plan.roles.get(n) for n in send_to_path(graph, tank, pump)]
        assert "tank_outlet_block" in roles and "suction_feed_tee" in roles


def test_line_numbers_are_unique_and_valid() -> None:
    _, instance, _ = _farm()
    assert_line_numbers_unique_and_valid(instance.plan.lines)


def test_an_unknown_port_name_lists_the_known_ones() -> None:
    _, instance, _ = _farm()
    with pytest.raises(ValueError, match="receipt1"):
        instance.port("nope")


def test_every_tank_farm_variant_appears_within_one_deck_cycle() -> None:
    """The metering deck has 8 cards, the longest: eight farms deal every card of every deck."""
    h = PatternHarness(config=config_with())
    labels = [build_tank_farm(h.pctx).variant for _ in range(8)]
    axes = [dict(part.split("=") for part in label.split("|")) for label in labels]
    assert {a["tanks"] for a in axes} == {"2", "3", "4"}
    assert {a["transfer_pump"] for a in axes} == {"CentrifugalPump", "RotaryPump"}
    assert {a["manifold"] for a in axes} == {"GateValve", "PlugValve"}
    assert {a["service"] for a in axes} == {"flammable", "non_flammable"}
    assert {a["metering"] for a in axes} == {
        "none",
        "MassFlowMeasuringElement",
        "PositiveDisplacementFlowMeter",
        "TurbineFlowMeter",
        "VolumeFlowMeasuringElement",
    }
