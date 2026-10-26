"""Exchanger and utility trims (design 6.13 to 6.15; pid-vocabulary 5.4 condensate and steam)."""

from __future__ import annotations

import networkx as nx
import pytest
from trim_harness import (
    STYLE,
    TrimHarness,
    all_send_to_paths,
    assert_round_trip,
    classes_of,
    convention,
    ids_with_role,
    send_to_path,
    sensor_tags_on,
)

from plantgraph.benchmark.v2 import trims_utility
from plantgraph.benchmark.v2.config import CondensateMode
from plantgraph.benchmark.v2.plan_models import StreamKindV2
from plantgraph.benchmark.v2.tags import parse_line_number
from plantgraph.benchmark.v2.vocabulary import ItemKind, item_kind

_BLOCKS = {"GateValve", "ButterflyValve"}


def _exchanger(h: TrimHarness) -> str:
    return h.equipment("TubularHeatExchanger", "E")


def _line_into(graph: nx.DiGraph[str], node_id: str) -> dict[str, str]:
    """The properties of the single `send_to` edge entering `node_id`."""
    ((_, _, data),) = graph.in_edges(node_id, data=True)
    return dict(data)


@pytest.mark.parametrize("service", ["CWS", "LPS"])
def test_6_13_supply_stub_starts_open_with_a_block_valve(service: str) -> None:
    """Rule C4: the utility line starts at the sheet edge: open start, block, [tap], nozzle."""
    h = TrimHarness()
    exchangers = [_exchanger(h) for _ in range(4)]
    plans = [
        h.write(trims_utility.utility_supply_stub(h.ctx, STYLE, service, e)) for e in exchangers
    ]
    graph = assert_round_trip(h)
    for exchanger, plan in zip(exchangers, plans, strict=True):
        block = plan.ports["block"]
        assert graph.in_degree(block) == 0  # nothing feeds the block: the line enters from outside
        assert graph.nodes[block]["node_class"] in _BLOCKS
        assert nx.has_path(nx.DiGraph(graph.edges), block, exchanger)
        line = parse_line_number(_line_into(graph, exchanger)["line_number"])
        assert line is not None and line.service == service
        stub_kinds = list(plan.stream_kinds.values()).count(StreamKindV2.UTILITY_STUB)
        assert stub_kinds == 1  # the stub itself; its tap branch is a plain trim line
    kinds = [tag.partition("-")[0] for tag in _all_sensor_tags(graph)]
    if service == "LPS":  # rule L15: steam supply always has a pressure gauge
        assert kinds == ["PI"] * 4
    else:  # cooling water: an optional thermometer, never a pressure gauge
        assert set(kinds) <= {"TI"}


def _all_sensor_tags(graph: nx.DiGraph[str]) -> list[str]:
    return sorted(
        d["tag"]
        for _, d in graph.nodes(data=True)
        if d["node_class"] == "ProcessSignalGeneratingFunction"
    )


def test_6_13_an_unknown_utility_service_raises() -> None:
    h = TrimHarness()
    with pytest.raises(ValueError, match="a supply service"):
        trims_utility.utility_supply_stub(h.ctx, STYLE, "P", _exchanger(h))


def test_6_14_cooling_water_return_has_a_thermal_relief_before_the_block_valve() -> None:
    """Rule L12: outlet -> relief tee (relief valve on its branch) -> block valve -> open end."""
    h = TrimHarness(config=convention(p_thermal_relief=1.0))
    exchanger = _exchanger(h)
    plan = h.write(trims_utility.utility_return_stub(h.ctx, STYLE, "CWS", exchanger))
    graph = assert_round_trip(h)
    tee = ids_with_role(plan, "thermal_relief_tee")[0]
    relief = ids_with_role(plan, "thermal_relief_valve")[0]
    block = plan.ports["block"]
    assert nx.has_path(nx.DiGraph(graph.edges), exchanger, tee)
    assert send_to_path(graph, tee, block) == [tee, block]
    assert graph.has_edge(tee, relief)
    assert graph.nodes[relief]["node_class"].endswith("SafetyValve")
    assert graph.out_degree(block) == 0  # open end
    assert _line_into(graph, block)["fluid_code"] == "CWR"


def test_6_14_thermal_relief_can_be_switched_off() -> None:
    h = TrimHarness(config=convention(p_thermal_relief=0.0))
    plan = h.write(trims_utility.utility_return_stub(h.ctx, STYLE, "CWS", _exchanger(h)))
    assert not ids_with_role(plan, "thermal_relief_valve")
    assert_round_trip(h)


def _steam_return(mode: CondensateMode) -> tuple[TrimHarness, nx.DiGraph[str], str, object]:
    h = TrimHarness(config=convention(condensate_mode_weights={mode: 1.0}))
    exchanger = _exchanger(h)
    plan = h.write(trims_utility.utility_return_stub(h.ctx, STYLE, "LPS", exchanger))
    return h, assert_round_trip(h), exchanger, plan


def test_6_14_condensate_trap_comes_before_the_block_valve() -> None:
    """Rule L15 and 5.4: a steam trap lets condensate out; its line is `CD`; a PI is on it."""
    _, graph, exchanger, plan = _steam_return("trap")
    trap = ids_with_role(plan, "condensate_trap")[0]  # type: ignore[arg-type]
    block = ids_with_role(plan, "condensate_block")[0]  # type: ignore[arg-type]
    path = send_to_path(graph, exchanger, block)
    assert path.index(trap) < path.index(block)
    assert graph.nodes[trap]["node_class"] == "SteamTrap"
    assert _line_into(graph, block)["fluid_code"] == "CD"
    assert any(tag.startswith("PI-") for tag in _all_sensor_tags(graph))


def test_6_14_trap_station_is_a_trap_between_two_blocks_with_a_bypass() -> None:
    _, graph, _, plan = _steam_return("trap_station")
    tee_in = ids_with_role(plan, "trap_tee_in")[0]  # type: ignore[arg-type]
    tee_out = ids_with_role(plan, "trap_tee_out")[0]  # type: ignore[arg-type]
    bypass, through = all_send_to_paths(graph, tee_in, tee_out)
    assert classes_of(graph, through[1:-1]) == [
        classes_of(graph, through[1:2])[0],
        "SteamTrap",
        classes_of(graph, through[3:4])[0],
    ]
    assert classes_of(graph, through[1:2])[0] in _BLOCKS
    assert classes_of(graph, bypass[1:-1]) == ["GlobeValve"]


def test_6_14_drain_pot_has_a_level_valve_and_a_trip_valve_on_its_outlet() -> None:
    """The pot is a small `PressureVessel` (equipment added by the trim); the valves leave it."""
    h, graph, exchanger, plan = _steam_return("drain_pot")
    (pot,) = [e.node_id for e in plan.equipment]  # type: ignore[attr-defined]
    assert graph.nodes[pot]["node_class"] == "PressureVessel"
    assert nx.has_path(nx.DiGraph(graph.edges), exchanger, pot)
    level = ids_with_role(plan, "pot_level_valve")[0]  # type: ignore[arg-type]
    trip = ids_with_role(plan, "pot_trip_valve")[0]  # type: ignore[arg-type]
    assert send_to_path(graph, pot, trip) == [pot, level, trip]
    level_tag = graph.nodes[level]["tag"]
    assert (
        item_kind(graph.nodes[level]["node_class"], level_tag.partition("-")[0])
        is ItemKind.CONTROL_VALVE
    )
    assert graph.nodes[trip]["tag"].startswith("XV-")


def test_6_14_condensate_modes_are_drawn_in_the_configured_ratio() -> None:
    """`condensate_mode_weights` 2 : 1 : 1 by default: all three modes occur over 40 draws."""
    h = TrimHarness()
    modes = {trims_utility._draw_condensate_mode(h.ctx) for _ in range(40)}
    assert modes == {"trap", "trap_station", "drain_pot"}


def test_6_15_exchanger_vent_and_drain_are_valve_and_cap_on_the_exchanger() -> None:
    """Rule L15 (KLM): a shell drain and a channel vent, or nothing."""
    h = TrimHarness(config=convention(p_exchanger_vent_drain=1.0, p_open_drain=0.0))
    exchanger = _exchanger(h)
    plan = h.write(trims_utility.exchanger_vent_drain(h.ctx, STYLE, exchanger))
    graph = assert_round_trip(h)
    for name in ("drain_valve", "vent_valve"):
        valve = plan.ports[name]
        assert graph.has_edge(exchanger, valve)
        assert graph.nodes[next(iter(graph.successors(valve)))]["node_class"] == "BlindFlange"
    off = TrimHarness(config=convention(p_exchanger_vent_drain=0.0))
    assert not trims_utility.exchanger_vent_drain(off.ctx, STYLE, "x").lines


def test_steam_stub_relief_discharges_to_the_atmosphere() -> None:
    """A PSV on the steam stub: tee -> safety valve -> open end."""
    h = TrimHarness()
    exchanger = _exchanger(h)
    supply = h.write(trims_utility.utility_supply_stub(h.ctx, STYLE, "MPS", exchanger, True))
    relief = h.write(trims_utility.steam_stub_relief(h.ctx, STYLE, supply.ports["relief_tee"]))
    graph = assert_round_trip(h)
    assert send_to_path(graph, supply.ports["relief_tee"], relief.ports["psv"]) == [
        supply.ports["relief_tee"], relief.ports["psv"]
    ]  # fmt: skip
    assert graph.out_degree(relief.ports["psv"]) == 0


def test_ejector_discharge_passes_a_silencer_and_ends_open() -> None:
    h = TrimHarness()
    ejector = h.equipment("AirEjector", "EJ")
    plan = h.write(trims_utility.ejector_discharge_silencer(h.ctx, STYLE, ejector))
    graph = assert_round_trip(h)
    assert list(graph.successors(ejector)) == [plan.ports["silencer"]]
    assert graph.nodes[plan.ports["silencer"]]["node_class"] == "Silencer"
    assert graph.out_degree(plan.ports["silencer"]) == 0
    assert sensor_tags_on(graph, plan.ports["silencer"]) == []
