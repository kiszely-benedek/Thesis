"""Pump and compressor trims (design 6.1 to 6.6, 6.16): each rule as a path in the graph.

Every test builds the trim on the graph oracle and the DEXPI builder, checks the rule on the
oracle graph, and asserts the DEXPI round trip gives the same graph (`assert_round_trip`).
"""

from __future__ import annotations

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

from plantgraph.benchmark.v2 import trims
from plantgraph.benchmark.v2.plan_models import StreamKindV2

_BLOCKS = {"GateValve", "ButterflyValve"}


def _suction_harness(pump_class: str) -> tuple[TrimHarness, str, str]:
    h = TrimHarness(config=convention(p_flex_connector=0.0))
    return h, h.equipment("PressureVessel", "V"), h.equipment(pump_class, "P")


def test_6_1_centrifugal_suction_is_vessel_block_strainer_pump() -> None:
    """Rule L2 / S1: vessel -> block -> strainer (between flanges) -> pump."""
    h, vessel, pump = _suction_harness("CentrifugalPump")
    plan = h.write(trims.centrifugal_suction(h.ctx, STYLE), vessel, pump)
    graph = assert_round_trip(h)
    path = send_to_path(graph, vessel, pump)
    assert classes_of(graph, path)[2:-1] == [
        "FlangedConnection",
        "ConicalStrainer",
        "FlangedConnection",
    ]
    assert classes_of(graph, path)[1] in _BLOCKS
    assert path[1:2] == ids_with_role(plan, "suction_block")
    assert plan.ports["strainer"] in path


def test_6_2_pd_suction_has_a_permanent_strainer_and_the_relief_return_tee() -> None:
    """Rule L2: a rotary pump's strainer is permanent (no spool); the tee takes the 6.5 relief."""
    h, vessel, pump = _suction_harness("RotaryPump")
    plan = h.write(trims.positive_displacement_suction(h.ctx, STYLE), vessel, pump)
    graph = assert_round_trip(h)
    classes = classes_of(graph, send_to_path(graph, vessel, pump))
    assert classes[2:] == ["Strainer", "PipeTee", "RotaryPump"]
    assert plan.ports["relief_return_tee"] in graph


@pytest.mark.parametrize(
    ("pump_class", "expected"),
    [
        ("CentrifugalPump", trims.centrifugal_suction),
        ("RotaryPump", trims.positive_displacement_suction),
        ("ReciprocatingPump", trims.positive_displacement_suction),
    ],
)
def test_suction_trim_follows_the_pump_class(pump_class: str, expected: object) -> None:
    assert trims.suction_for(pump_class) is expected


def test_an_ejector_pump_has_no_suction_trim() -> None:
    with pytest.raises(ValueError, match="centrifugal, reciprocating or rotary pump"):
        trims.suction_for("EjectorPump")


def test_6_3_discharge_has_the_gauge_before_the_check_and_the_block_after() -> None:
    """Rules L1, L3 / S2: pump -> gauge tap -> check -> block; the PI is on the tap branch."""
    h = TrimHarness(config=convention(p_flex_connector=0.0))
    pump, header = h.equipment("CentrifugalPump", "P"), h.equipment("Tank", "TK")
    plan = h.write(trims.pump_discharge(h.ctx, STYLE, True, False, False), pump, header)
    graph = assert_round_trip(h)
    path = send_to_path(graph, pump, header)
    assert classes_of(graph, path)[1:-1] == [
        "PipeTee",
        "SwingCheckValve",
        classes_of(graph, path)[3],
    ]
    assert classes_of(graph, path)[3] in _BLOCKS
    gauge_tee = ids_with_role(plan, "pressure_gauge_tee")[0]
    flange = ids_with_role(plan, "discharge_pi_flange")[0]
    assert classes_of(graph, send_to_path(graph, gauge_tee, flange))[-1] == "BlindFlange"
    assert sensor_tags_on(graph, flange)[0].startswith("PI-")


def test_6_3_without_the_gauge_tap_the_discharge_has_no_gauge() -> None:
    h = TrimHarness()
    pump, header = h.equipment("CentrifugalPump", "P"), h.equipment("Tank", "TK")
    plan = h.write(trims.pump_discharge(h.ctx, STYLE, False, False, False), pump, header)
    assert "pressure_gauge" not in plan.ports
    assert not ids_with_role(plan, "pressure_gauge_tee")


@pytest.mark.parametrize("p_vent_drain", [1.0, 0.0])
def test_6_4_vent_and_drain_are_valve_and_blind_flange(p_vent_drain: float) -> None:
    """Rule L4: casing nozzle -> valve -> blind flange, one vent and one drain, or nothing."""
    h = TrimHarness(config=convention(p_pump_vent_drain=p_vent_drain, p_open_drain=0.0))
    pump = h.equipment("CentrifugalPump", "P")
    plan = h.write(trims.pump_vent_drain(h.ctx, STYLE, pump))
    graph = assert_round_trip(h)
    valves = [plan.ports[name] for name in ("vent_valve", "drain_valve") if name in plan.ports]
    assert len(valves) == (2 if p_vent_drain else 0)
    for valve in valves:
        cap = next(iter(graph.successors(valve)))
        assert graph.has_edge(pump, valve)
        assert graph.nodes[cap]["node_class"] == "BlindFlange"
        assert graph.nodes[valve]["node_class"] in {"GateValve", "BallValve"}


def test_6_5_relief_runs_from_the_discharge_tee_back_to_the_suction_tee() -> None:
    """Rule L5 / S3: relief tee (before the check) -> relief valve -> suction tee."""
    h = TrimHarness(config=convention(p_min_flow=0.0))
    vessel, pump = h.equipment("PressureVessel", "V"), h.equipment("RotaryPump", "P")
    header = h.equipment("Tank", "TK")
    plan = h.write(trims.pump_trims(h.ctx, STYLE, pump, "RotaryPump", vessel, header))
    graph = assert_round_trip(h)
    relief_tee = plan.ports["discharge.relief_tee"]
    suction_tee = plan.ports["suction.relief_return_tee"]
    relief = send_to_path(graph, relief_tee, suction_tee)
    assert classes_of(graph, relief) == ["PipeTee", "SpringLoadedAngleGlobeSafetyValve", "PipeTee"]
    discharge = send_to_path(graph, pump, header)
    assert discharge.index(relief_tee) < discharge.index(plan.ports["discharge.check"])
    assert send_to_path(graph, vessel, pump)[-2] == suction_tee  # the tee is on the suction line


@pytest.mark.parametrize("pump_class", ["CentrifugalPump", "RotaryPump", "ReciprocatingPump"])
def test_6_5_only_pd_pumps_get_an_external_relief(pump_class: str) -> None:
    h = TrimHarness(config=convention(p_min_flow=0.0))
    vessel, pump = h.equipment("PressureVessel", "V"), h.equipment(pump_class, "P")
    header = h.equipment("Tank", "TK")
    plan = h.write(trims.pump_trims(h.ctx, STYLE, pump, pump_class, vessel, header))
    graph = assert_round_trip(h)
    relief_valves = [n for n, d in graph.nodes(data=True) if "AngleGlobeSafety" in d["node_class"]]
    assert bool(relief_valves) is trims.needs_external_relief(pump_class)
    assert ("discharge.relief_tee" in plan.ports) is trims.needs_external_relief(pump_class)


def test_6_6_min_flow_returns_to_the_suction_vessel_after_the_check() -> None:
    """Rule L6: tee after the check -> orifice set -> check -> gate valve -> suction vessel."""
    h = TrimHarness(config=convention(p_min_flow=1.0, p_flex_connector=0.0))
    vessel, pump = h.equipment("PressureVessel", "V"), h.equipment("CentrifugalPump", "P")
    header = h.equipment("Tank", "TK")
    plan = h.write(trims.pump_trims(h.ctx, STYLE, pump, "CentrifugalPump", vessel, header))
    graph = assert_round_trip(h)
    tee = plan.ports["discharge.min_flow_tee"]
    path = send_to_path(graph, tee, vessel)
    assert classes_of(graph, path) == [
        "PipeTee", "Flange", "RestrictionOrifice", "Flange", "GlobeCheckValve", "GateValve",
        "PressureVessel",
    ]  # fmt: skip
    discharge = send_to_path(graph, pump, header)
    assert discharge.index(plan.ports["discharge.check"]) < discharge.index(tee)
    assert discharge.index(tee) < discharge.index(plan.ports["discharge.block"])
    recycle_lines = [n for n, k in plan.stream_kinds.items() if k is StreamKindV2.RECYCLE]
    assert len(recycle_lines) == 1


def test_6_6_without_min_flow_the_pump_never_discharges_back_to_its_suction() -> None:
    """Rule S12: a centrifugal pump reaches its suction vessel only through the 6.6 line."""
    h = TrimHarness(config=convention(p_min_flow=0.0))
    vessel, pump = h.equipment("PressureVessel", "V"), h.equipment("CentrifugalPump", "P")
    header = h.equipment("Tank", "TK")
    h.write(trims.pump_trims(h.ctx, STYLE, pump, "CentrifugalPump", vessel, header))
    graph = assert_round_trip(h)
    with pytest.raises(Exception, match="No path"):
        send_to_path(graph, pump, vessel)


def test_header_pressure_mode_leaves_out_the_per_pump_gauge() -> None:
    h = TrimHarness()
    vessel, pump = h.equipment("PressureVessel", "V"), h.equipment("CentrifugalPump", "P")
    header = h.equipment("Tank", "TK")
    plan = h.write(
        trims.pump_trims(h.ctx, STYLE, pump, "CentrifugalPump", vessel, header, "header_pt")
    )
    assert not ids_with_role(plan, "discharge_pi")
    assert not ids_with_role(plan, "pressure_gauge_tee")


def test_6_16_compressor_has_suction_strainer_and_discharge_check_with_a_safety_valve() -> None:
    """Rule L16: butterfly block -> strainer on suction; safety valve tee -> check -> block."""
    h = TrimHarness(config=convention(p_flex_connector=0.0))
    drum, machine = h.equipment("PressureVessel", "V"), h.equipment("CentrifugalCompressor", "K")
    after = h.equipment("PressureVessel", "V")
    h.write(trims.compressor_suction(h.ctx, STYLE), drum, machine)
    discharge = h.write(trims.compressor_discharge(h.ctx, STYLE), machine, after)
    graph = assert_round_trip(h)
    suction = classes_of(graph, send_to_path(graph, drum, machine))
    assert suction == [
        "PressureVessel", "ButterflyValve", "FlangedConnection", "ConicalStrainer",
        "FlangedConnection", "CentrifugalCompressor",
    ]  # fmt: skip
    out = classes_of(graph, send_to_path(graph, machine, after))
    assert out[1:3] == ["PipeTee", "CheckValve"]
    tee = ids_with_role(discharge, "discharge_psv_tee")[0]
    safety = discharge.ports["psv"]
    assert graph.nodes[safety]["node_class"].endswith("SafetyValve")
    assert send_to_path(graph, tee, safety) == [tee, safety]
