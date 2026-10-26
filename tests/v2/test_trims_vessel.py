"""Vessel and tank trims (design 6.10 to 6.12, 6.19; pid-vocabulary 5.4 flush, drain, vent)."""

from __future__ import annotations

import networkx as nx
import pytest
from trim_harness import (
    STYLE,
    TrimHarness,
    assert_round_trip,
    classes_of,
    convention,
    ids_with_role,
    send_to_path,
    sensor_tags_on,
)

from plantgraph.benchmark.v2 import trims_extra, trims_vessel
from plantgraph.benchmark.v2.config import VentDrainConvention
from plantgraph.benchmark.v2.plan_models import StreamKindV2
from plantgraph.graph.schema import EQUIPMENT_CLASSES, Relation

_SAFETY = {"SpringLoadedGlobeSafetyValve", "SpringLoadedAngleGlobeSafetyValve"}
_CAPS = {"BlindFlange", "Funnel"}


def _safety_reachable_without_equipment(graph: nx.DiGraph[str], vessel: str) -> bool:
    """Walk `send_to` from the vessel; stop at other equipment; is a safety valve met?"""
    stack, seen = [vessel], {vessel}
    while stack:
        node = stack.pop()
        for _, target, data in graph.out_edges(node, data=True):
            if data["relation"] != Relation.SEND_TO.value or target in seen:
                continue
            seen.add(target)
            if graph.nodes[target]["node_class"] in _SAFETY:
                return True
            if graph.nodes[target]["node_class"] not in EQUIPMENT_CLASSES:
                stack.append(target)
    return False


def test_6_10_psv_with_blocks_and_drain_is_vessel_block_drain_tee_psv_block_open_end() -> None:
    """Rules L10, L11 / S6: the safety valve is on the vessel's own nozzle, blocks locked open."""
    h = TrimHarness(config=convention(p_psv_blocks=1.0, p_psv_drain=1.0, p_open_drain=0.0))
    vessel = h.equipment("PressureVessel", "V")
    plan = h.write(trims_vessel.vessel_psv(h.ctx, STYLE, vessel))
    graph = assert_round_trip(h)
    psv = plan.ports["psv"]
    drain_tee = ids_with_role(plan, "psv_drain_tee")[0]
    assert send_to_path(graph, vessel, psv)[1:-1] == [
        ids_with_role(plan, "psv_inlet_block")[0],
        drain_tee,
    ]
    outlet = ids_with_role(plan, "psv_outlet_block")[0]
    assert list(graph.successors(psv)) == [outlet]
    assert graph.out_degree(outlet) == 0  # the line to the flare header ends open
    assert graph.nodes[ids_with_role(plan, "psv_drain_cap")[0]]["node_class"] == "BlindFlange"
    assert _safety_reachable_without_equipment(graph, vessel)


def test_6_10_psv_without_blocks_or_drain_is_the_valve_alone() -> None:
    h = TrimHarness(config=convention(p_psv_blocks=0.0, p_psv_drain=0.0))
    vessel = h.equipment("PressureVessel", "V")
    plan = h.write(trims_vessel.vessel_psv(h.ctx, STYLE, vessel))
    graph = assert_round_trip(h)
    assert list(graph.successors(vessel)) == [plan.ports["psv"]]
    assert graph.out_degree(plan.ports["psv"]) == 0
    assert plan.stream_kinds and all(
        kind is StreamKindV2.TRIM for kind in plan.stream_kinds.values()
    )


def test_6_10_the_psv_line_is_a_flare_line() -> None:
    h = TrimHarness()
    vessel = h.equipment("PressureVessel", "V")
    plan = h.write(trims_vessel.vessel_psv(h.ctx, STYLE, vessel))
    graph = assert_round_trip(h)
    ((_, _, data),) = graph.out_edges(vessel, data=True)
    assert data["fluid_code"] == "FL"
    assert plan.ports["psv"] in graph


def test_6_11_klm_convention_draws_both_a_drain_and_a_vent() -> None:
    """Rule L13 (KLM reading): a valved drain and a valved vent on every vessel."""
    h = TrimHarness(config=convention(vent_drain_convention=VentDrainConvention.KLM_ALL))
    vessel = h.equipment("PressureVessel", "V")
    plan = h.write(trims_vessel.vessel_vent_drain(h.ctx, STYLE, vessel))
    graph = assert_round_trip(h)
    assert sorted(plan.ports) == ["drain_valve", "vent_valve"]
    for valve in plan.ports.values():
        assert graph.has_edge(vessel, valve)
        assert graph.nodes[next(iter(graph.successors(valve)))]["node_class"] in _CAPS


@pytest.mark.parametrize(("p_hnf", "expected"), [(0.0, 0), (1.0, 2)])
def test_6_11_hnf_convention_draws_with_its_own_chance(p_hnf: float, expected: int) -> None:
    """Rule L13 (HNF reading): vent and drain only where they join a closed system."""
    config = convention(
        vent_drain_convention=VentDrainConvention.HNF_CLOSED, p_hnf_vent_drain=p_hnf
    )
    h = TrimHarness(config=config)
    vessel = h.equipment("PressureVessel", "V")
    plan = h.write(trims_vessel.vessel_vent_drain(h.ctx, STYLE, vessel))
    assert len(plan.ports) == expected
    assert_round_trip(h)


def test_6_12_top_gauge_is_on_a_nozzle_and_the_thermometer_on_the_outlet_line_tap() -> None:
    """Rule L13: one local PI on the vessel's own nozzle, one local TI on the top outlet line."""
    h = TrimHarness()
    vessel, sink = h.equipment("PressureVessel", "V"), h.equipment("Tank", "TK")
    plan = h.write(trims_vessel.vessel_top_instruments(h.ctx, STYLE, vessel), vessel, sink)
    graph = assert_round_trip(h)
    assert [tag.partition("-")[0] for tag in sensor_tags_on(graph, vessel)] == ["PI"]
    tee = plan.ports["top_outlet_tee"]
    assert send_to_path(graph, vessel, sink)[1] == tee
    flange = ids_with_role(plan, "vessel_top_ti_flange")[0]
    assert graph.has_edge(tee, flange)
    assert [tag.partition("-")[0] for tag in sensor_tags_on(graph, flange)] == ["TI"]


@pytest.mark.parametrize(
    "vessel_class",
    ["PressureVessel", "ProcessColumn", "GravitationalSeparator", "ScrubbingSeparator"],
)
def test_vessel_trims_give_every_pressure_vessel_a_safety_path(vessel_class: str) -> None:
    """Invariant S6 (rule L11) over the four classes it names."""
    h = TrimHarness()
    vessel, sink = h.equipment(vessel_class), h.equipment("Tank", "TK")
    h.write(trims_vessel.vessel_trims(h.ctx, STYLE, vessel, vessel_class), vessel, sink)
    graph = assert_round_trip(h)
    assert _safety_reachable_without_equipment(graph, vessel)


def test_vessel_trims_skip_the_safety_valve_on_other_classes() -> None:
    h = TrimHarness()
    vessel, sink = h.equipment("LiquidFilter", "F"), h.equipment("Tank", "TK")
    h.write(trims_vessel.vessel_trims(h.ctx, STYLE, vessel, "LiquidFilter"), vessel, sink)
    graph = assert_round_trip(h)
    assert not _safety_reachable_without_equipment(graph, vessel)


def test_6_19_flammable_tank_vent_is_arrestor_then_breather_valve_then_open() -> None:
    """Composition note 9.2: roof nozzle -> flame arrestor -> breather valve -> open end."""
    h = TrimHarness()
    tank = h.equipment("Tank", "TK")
    plan = h.write(trims_vessel.tank_vent(h.ctx, STYLE, tank, flammable=True))
    graph = assert_round_trip(h)
    path = send_to_path(graph, tank, plan.ports["vent_device"])
    assert classes_of(graph, path) == ["Tank", "FlameArrestor", "BreatherValve"]
    assert graph.out_degree(path[-1]) == 0


def test_6_19_a_non_flammable_tank_vents_through_a_ventilation_device() -> None:
    h = TrimHarness()
    tank = h.equipment("Tank", "TK")
    plan = h.write(trims_vessel.tank_vent(h.ctx, STYLE, tank, flammable=False))
    graph = assert_round_trip(h)
    assert send_to_path(graph, tank, plan.ports["vent_device"]) == [tank, plan.ports["vent_device"]]
    assert graph.nodes[plan.ports["vent_device"]]["node_class"] == "VentilationDevice"
    assert "tag" not in graph.nodes[plan.ports["vent_device"]]


@pytest.mark.parametrize(("viscous", "valve_class"), [(False, None), (True, "AnglePlugValve")])
def test_tank_bottom_drain_valve_class(viscous: bool, valve_class: str | None) -> None:
    h = TrimHarness(config=convention(p_open_drain=0.0))
    tank = h.equipment("Tank", "TK")
    seen = set()
    for _ in range(3):
        seen.add(h.write(trims_extra.tank_bottom_drain(h.ctx, STYLE, tank, viscous)).ports["valve"])
    graph = assert_round_trip(h)
    classes = {graph.nodes[n]["node_class"] for n in seen}
    assert classes == ({valve_class} if valve_class else {"GateValve", "AngleBallValve"})


def test_open_drain_ends_in_a_funnel_and_a_vent_never_does() -> None:
    """A drain may discharge to the open (`Funnel`); a vent always ends in a blind flange."""
    h = TrimHarness(config=convention(p_open_drain=1.0))
    vessel = h.equipment("PressureVessel", "V")
    plan = h.write(trims_vessel.vessel_vent_drain(h.ctx, STYLE, vessel))
    graph = assert_round_trip(h)
    drain_cap = next(iter(graph.successors(plan.ports["drain_valve"])))
    vent_cap = next(iter(graph.successors(plan.ports["vent_valve"])))
    assert graph.nodes[drain_cap]["node_class"] == "Funnel"
    assert graph.nodes[vent_cap]["node_class"] == "BlindFlange"


@pytest.mark.parametrize("p_flush", [1.0, 0.0])
def test_flush_connection_is_valve_coupling_cap(p_flush: float) -> None:
    """Quick-connect purge tap (samples W1): valve, [rotameter], coupling, blind flange."""
    h = TrimHarness(config=convention(p_flush_connection=p_flush))
    vessel = h.equipment("PressureVessel", "V")
    plan = h.write(trims_extra.flush_connection(h.ctx, STYLE, vessel))
    graph = assert_round_trip(h)
    if not p_flush:
        assert not plan.lines
        return
    (valve,) = graph.successors(vessel)
    chain = classes_of(graph, [valve, *nx.descendants(graph, valve)])
    assert set(chain) - {"VariableAreaFlowMeter"} == {"GateValve", "PipeCoupling", "BlindFlange"}
    assert len(chain) in (3, 4)  # the rotameter is optional (see the deck test below)


def test_flush_connection_meter_follows_its_deck() -> None:
    h = TrimHarness(config=convention(p_flush_connection=1.0))
    for _ in range(3):  # the purge-meter deck holds three cards, one of them the rotameter
        vessel = h.equipment("PressureVessel", "V")
        h.write(trims_extra.flush_connection(h.ctx, STYLE, vessel))
    graph = assert_round_trip(h)
    meters = sum(1 for _, d in graph.nodes(data=True) if d["node_class"] == "VariableAreaFlowMeter")
    assert meters == 1
