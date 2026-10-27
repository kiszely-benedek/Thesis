"""The exchanger helper of U1 and U5 (`patterns/exchanger.py`) and the two trims it extended.

`utility_supply_stub` gained `inline` (a control valve inside the steam line) and
`steam_stub_relief` a `service` (the relief of a medium-pressure stub is medium-pressure steam).
"""

from __future__ import annotations

import networkx as nx
import pytest
from instrument_invariants import check_s22
from pattern_checks import assert_pattern_invariants, flow_graph, located_on, nodes_with_letters
from pattern_harness import PatternHarness
from test_column import sensor_location
from trim_harness import STYLE, ids_with_role

from plantgraph.benchmark.v2.patterns.exchanger import (
    COOLING_WATER,
    STEAM,
    SteamLoop,
    exchanger_code,
    exchanger_trims,
    utility_for,
)
from plantgraph.benchmark.v2.trims_utility import (
    steam_stub_relief,
    utility_supply_stub,
)
from plantgraph.benchmark.v2.trims_valves import control_valve

_TUBULAR = "TubularHeatExchanger"


def _heater(
    service: str | None, loop: SteamLoop | None = None, node_class: str = _TUBULAR
) -> tuple[PatternHarness, str, nx.DiGraph[str]]:
    h = PatternHarness(seed=3)
    exchanger = h.equipment(node_class, exchanger_code(node_class))
    trims = exchanger_trims(h.pctx, exchanger, node_class, service, loop)
    trims.plan.write(h.builder)
    return h, exchanger, assert_pattern_invariants(h)


def test_a_steam_loop_needs_a_steam_service() -> None:
    h = PatternHarness()
    with pytest.raises(ValueError, match="steam loop needs a steam service.*CWS"):
        exchanger_trims(h.pctx, "x", _TUBULAR, COOLING_WATER, SteamLoop(location_id="x"))
    with pytest.raises(ValueError, match="steam loop needs a steam service.*None"):
        exchanger_trims(h.pctx, "x", "ElectricHeater", None, SteamLoop(location_id="x"))


@pytest.mark.parametrize("node_class", ["AirCoolingSystem", "ElectricHeater"])
def test_air_coolers_and_electric_heaters_have_no_utility_line(node_class: str) -> None:
    _, exchanger, graph = _heater(utility_for(node_class, steam=True), node_class=node_class)
    assert {d.get("fluid_code") for _, _, d in graph.in_edges(exchanger, data=True)} == set()
    assert graph.nodes[exchanger]["node_class"] == node_class


def test_a_plain_steam_loop_puts_a_temperature_valve_in_the_steam_line() -> None:
    h = PatternHarness(seed=3)
    exchanger = h.equipment(_TUBULAR, "E")
    sensed = h.equipment("PressureVessel", "V")
    trims = exchanger_trims(h.pctx, exchanger, _TUBULAR, STEAM, SteamLoop(location_id=sensed))
    trims.plan.write(h.builder)
    graph = assert_pattern_invariants(h)
    (valve,) = nodes_with_letters(graph, "TV")
    assert sensor_location(graph, valve) == ("TIC", sensed)
    assert nx.has_path(flow_graph(graph), valve, exchanger)
    assert check_s22(graph) == 0


def test_a_cascade_steam_loop_sets_a_steam_flow_controller_from_the_temperature() -> None:
    h = PatternHarness(seed=3)
    exchanger = h.equipment(_TUBULAR, "E")
    sensed = h.equipment("PressureVessel", "V")
    loop = SteamLoop(location_id=sensed, cascade=True)
    exchanger_trims(h.pctx, exchanger, _TUBULAR, STEAM, loop).plan.write(h.builder)
    graph = assert_pattern_invariants(h)
    assert check_s22(graph) == 1 and not nodes_with_letters(graph, "TV")
    (valve,) = nodes_with_letters(graph, "FV")
    assert nx.has_path(flow_graph(graph), valve, exchanger)
    assert [s for s in located_on(graph, sensed) if graph.nodes[s]["tag"].startswith("TT")]


def test_the_exchanger_gets_monitoring_points_and_a_safety_valve_on_request() -> None:
    h = PatternHarness(seed=3)
    exchanger = h.equipment(_TUBULAR, "E")
    trims = exchanger_trims(h.pctx, exchanger, _TUBULAR, COOLING_WATER, with_psv=True)
    trims.plan.write(h.builder)
    graph = assert_pattern_invariants(h)
    assert 5 <= len(located_on(graph, exchanger)) <= 7  # monitor_points_per_major_item
    assert ids_with_role(trims.plan, "psv") and trims.pot_ids == ()


def test_utility_supply_stub_carries_the_inline_valve_between_the_block_and_the_exchanger() -> None:
    h = PatternHarness(seed=3)
    exchanger = h.equipment(_TUBULAR, "E")
    valve = control_valve(h.ctx, STYLE, "T")
    stub = utility_supply_stub(h.ctx, STYLE, STEAM, exchanger, inline=valve.run)
    stub.write(h.builder)
    valve.model_copy(update={"run": ()}).write(h.builder)
    graph = h.oracle.graph
    block = ids_with_role(stub, "utility_supply_block")[0]
    flow = flow_graph(graph)
    for (
        part
    ) in valve.run:  # every part of the valve's run is on the line: block -> part -> exchanger
        assert nx.has_path(flow, block, part.node_id) and nx.has_path(flow, part.node_id, exchanger)


def test_the_relief_of_a_medium_pressure_stub_is_medium_pressure_steam() -> None:
    h = PatternHarness(seed=3)
    engine = h.equipment("AirEjector", "EJ")
    supply = utility_supply_stub(h.ctx, STYLE, "MPS", engine, relief_tee=True)
    supply.write(h.builder)
    relief = steam_stub_relief(h.ctx, STYLE, supply.ports["relief_tee"], "MPS")
    relief.write(h.builder)
    (psv,) = ids_with_role(relief, "steam_stub_psv")
    assert {d["fluid_code"] for _, _, d in h.oracle.graph.in_edges(psv, data=True)} == {"MPS"}
    with pytest.raises(ValueError, match="steam service.*CWS"):
        steam_stub_relief(h.ctx, STYLE, supply.ports["relief_tee"], "CWS")
