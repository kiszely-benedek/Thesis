"""Trims on a line (design 6.7 to 6.9, 6.17, 6.18, and the line trims of pid-vocabulary 5.4)."""

from __future__ import annotations

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

from plantgraph.benchmark.v2 import trims_extra, trims_valves
from plantgraph.benchmark.v2.class_decks import ROLE_CLASSES
from plantgraph.benchmark.v2.tags import parse_tag
from plantgraph.benchmark.v2.vocabulary import ItemKind, OnOffLetter, item_kind
from plantgraph.graph.schema import CONTROL_VALVE_BODY_CLASSES, Relation

_BLOCKS = {"GateValve", "ButterflyValve"}


def _two_hosts(h: TrimHarness) -> tuple[str, str]:
    return h.equipment("PressureVessel", "V"), h.equipment("Tank", "TK")


def test_6_7_station_has_two_blocks_and_a_bypass_between_the_same_two_tees() -> None:
    """Rule L9 / S5: tee -> block -> body -> block -> tee, and tee -> globe valve -> tee."""
    h = TrimHarness(config=convention(p_cv_station=1.0, p_cv_reducers=0.0, p_cv_drain=0.0))
    src, dst = _two_hosts(h)
    plan = h.write(trims_valves.control_valve(h.ctx, STYLE, "F"), src, dst)
    graph = assert_round_trip(h)
    tee_in, tee_out = plan.ports["tee_in"], plan.ports["tee_out"]
    bypass_path, main_path = all_send_to_paths(graph, tee_in, tee_out)
    assert main_path == [
        tee_in, plan.ports["block_in"], plan.ports["body"], plan.ports["block_out"], tee_out
    ]  # fmt: skip
    assert bypass_path == [tee_in, plan.ports["bypass_valve"], tee_out]
    assert classes_of(graph, [main_path[1], main_path[3]])[0] in _BLOCKS
    assert graph.nodes[plan.ports["bypass_valve"]]["node_class"] == "GlobeValve"


def test_6_7_the_body_is_a_control_valve_numbered_for_its_loop() -> None:
    """Rules L17, S4: the body class is a control-valve body and its tag is `FV-<loop number>`."""
    h = TrimHarness(config=convention(p_cv_station=1.0))
    src, dst = _two_hosts(h)
    plan = h.write(trims_valves.control_valve(h.ctx, STYLE, "F"), src, dst)
    graph = assert_round_trip(h)
    body = graph.nodes[plan.ports["body"]]
    assert body["node_class"] in CONTROL_VALVE_BODY_CLASSES
    parsed = parse_tag(body["tag"])
    assert parsed is not None
    assert parsed.letters == "FV"
    assert item_kind(body["node_class"], parsed.letters) is ItemKind.CONTROL_VALVE


def test_6_7_reducers_come_as_a_pair_and_the_drain_sits_between_block_and_body() -> None:
    h = TrimHarness(config=convention(p_cv_station=1.0, p_cv_reducers=1.0, p_cv_drain=1.0))
    src, dst = _two_hosts(h)
    plan = h.write(trims_valves.control_valve(h.ctx, STYLE, "P"), src, dst)
    graph = assert_round_trip(h)
    through = all_send_to_paths(graph, plan.ports["tee_in"], plan.ports["tee_out"])[-1]
    classes = classes_of(graph, through)
    assert classes.count("PipeReducer") == 2
    assert classes[2] == "PipeTee"  # the drain tee, right after the upstream block
    drain_tee = through[2]
    drain_valve = ids_with_role(plan, "cv_drain_valve")[0]
    assert graph.has_edge(drain_tee, drain_valve)
    cap = next(iter(graph.successors(drain_valve)))
    assert graph.nodes[cap]["node_class"] in {"BlindFlange", "Funnel"}


def test_6_7_station_knobs_at_zero_leave_only_blocks_and_bypass() -> None:
    h = TrimHarness(config=convention(p_cv_station=1.0, p_cv_reducers=0.0, p_cv_drain=0.0))
    src, dst = _two_hosts(h)
    plan = h.write(trims_valves.control_valve(h.ctx, STYLE, "T"), src, dst)
    assert not ids_with_role(plan, "cv_reducer")
    assert not ids_with_role(plan, "cv_drain_valve")


def test_6_8_bare_control_valve_is_the_body_alone() -> None:
    """Rule L9 "in general": with `p_cv_station` 0 the line has the body and nothing else."""
    h = TrimHarness(config=convention(p_cv_station=0.0))
    src, dst = _two_hosts(h)
    plan = h.write(trims_valves.control_valve(h.ctx, STYLE, "F"), src, dst)
    graph = assert_round_trip(h)
    assert send_to_path(graph, src, dst) == [src, plan.ports["body"], dst]
    assert "tee_in" not in plan.ports


def test_control_valve_bodies_for_a_letdown_are_angle_bodies() -> None:
    h = TrimHarness(config=convention(p_cv_station=0.0))
    seen = set()
    for _ in range(4):  # the letdown deck holds four cards
        src, dst = _two_hosts(h)
        plan = h.write(trims_valves.control_valve(h.ctx, STYLE, "L", letdown=True), src, dst)
        seen.add(plan.ports["body"])
    graph = assert_round_trip(h)
    assert {graph.nodes[n]["node_class"] for n in seen} == set(
        ROLE_CLASSES["letdown_control_valve_body"]
    )


def test_a_loop_letter_that_is_not_a_control_valve_raises() -> None:
    h = TrimHarness()
    with pytest.raises(ValueError, match="control-valve tag"):
        trims_valves.bare_control_valve(h.ctx, STYLE, "X")


@pytest.mark.parametrize("letter", [OnOffLetter.X, OnOffLetter.Y])
def test_6_9_on_off_valve_takes_the_trains_letter_and_both_limit_switches(
    letter: OnOffLetter,
) -> None:
    """ISA X is the on-off valve: a ball valve `XV-n` (or `YV-n`), `ZSO-n` and `ZSC-n` on it."""
    h = TrimHarness(config=convention(p_limit_switches=1.0), on_off=letter)
    src, dst = _two_hosts(h)
    plan = h.write(trims_valves.on_off_valve(h.ctx, STYLE), src, dst)
    graph = assert_round_trip(h)
    valve = graph.nodes[plan.ports["valve"]]
    assert valve["node_class"] == "BallValve"
    number = valve["tag"].partition("-")[2]
    assert valve["tag"] == f"{letter.value}V-{number}"
    assert item_kind("BallValve", f"{letter.value}V") is ItemKind.ON_OFF_VALVE
    assert sensor_tags_on(graph, plan.ports["valve"]) == [f"ZSC-{number}", f"ZSO-{number}"]


def test_6_9_without_limit_switches_the_valve_has_no_sensor() -> None:
    h = TrimHarness(config=convention(p_limit_switches=0.0))
    src, dst = _two_hosts(h)
    plan = h.write(trims_valves.on_off_valve(h.ctx, STYLE), src, dst)
    graph = assert_round_trip(h)
    assert sensor_tags_on(graph, plan.ports["valve"]) == []


def test_6_17_battery_limit_is_block_valve_then_line_blind() -> None:
    h = TrimHarness(config=convention(p_battery_limit=1.0))
    src, dst = _two_hosts(h)
    h.write(trims_valves.battery_limit(h.ctx, STYLE), src, dst)
    graph = assert_round_trip(h)
    classes = classes_of(graph, send_to_path(graph, src, dst))[1:-1]
    assert classes[0] in _BLOCKS
    assert classes[1:] == ["LineBlind"]


def test_6_17_battery_limit_at_zero_chance_adds_nothing() -> None:
    h = TrimHarness(config=convention(p_battery_limit=0.0))
    plan = trims_valves.battery_limit(h.ctx, STYLE)
    assert plan.run == () and not plan.lines


@pytest.mark.parametrize(
    ("service", "role"), [("liquid", "flow_element_liquid"), ("gas", "flow_element_gas")]
)
def test_6_18_flow_element_class_comes_from_its_service_deck(service: str, role: str) -> None:
    """The element is an `FE-n` primary element; its class is one card of the service deck."""
    h = TrimHarness()
    seen = set()
    for _ in range(_deck_size(role)):
        src, dst = _two_hosts(h)
        plan = h.write(trims_valves.flow_element(h.ctx, STYLE, service), src, dst)  # type: ignore[arg-type]
        seen.add(plan.ports["element"])
    graph = assert_round_trip(h)
    assert {graph.nodes[n]["node_class"] for n in seen} == set(ROLE_CLASSES[role])
    assert all(graph.nodes[n]["tag"].startswith("FE-") for n in seen)


def _deck_size(role: str) -> int:
    return sum(ROLE_CLASSES[role].values())


def test_double_block_and_bleed_is_valve_tee_valve_with_a_bleed_valve_on_the_tee() -> None:
    """Fuel-gas isolation: three on-off valves, all tagged with the train's letter."""
    h = TrimHarness(on_off=OnOffLetter.Y)
    src, dst = _two_hosts(h)
    plan = h.write(trims_valves.double_block_and_bleed(h.ctx, STYLE), src, dst)
    graph = assert_round_trip(h)
    path = send_to_path(graph, src, dst)
    assert path[1:-1] == [
        plan.ports["first"],
        ids_with_role(plan, "dbb_tee")[0],
        plan.ports["second"],
    ]
    tee = path[2]
    assert set(graph.successors(tee)) == {plan.ports["second"], plan.ports["bleed"]}
    for name in ("first", "second", "bleed"):
        assert graph.nodes[plan.ports[name]]["tag"].startswith("YV-")
    assert graph.out_degree(plan.ports["bleed"]) == 0  # the bleed line ends open


def test_skillet_blind_is_a_spade_or_a_spacer_and_is_tagged_sb() -> None:
    h = TrimHarness(config=convention(p_skillet=1.0))
    seen = set()
    for _ in range(2):
        src, dst = _two_hosts(h)
        plan = h.write(trims_extra.skillet_blind(h.ctx, STYLE), src, dst)
        seen.add(plan.ports["skillet"])
    graph = assert_round_trip(h)
    assert {graph.nodes[n]["node_class"] for n in seen} == {"PipeFlangeSpade", "PipeFlangeSpacer"}
    assert all(graph.nodes[n]["tag"].startswith("SB-") for n in seen)
    assert (
        trims_extra.skillet_blind(TrimHarness(config=convention(p_skillet=0.0)).ctx, STYLE).run
        == ()
    )


def test_spec_break_is_inline_untagged_and_never_a_sensing_location() -> None:
    """The break marks a spec change; pyDEXPI cannot place a sensor on it, so none is planned."""
    h = TrimHarness()
    src, dst = _two_hosts(h)
    plan = h.write(trims_extra.spec_break(h.ctx, STYLE), src, dst)
    graph = assert_round_trip(h)
    spec_break = plan.ports["spec_break"]
    assert send_to_path(graph, src, dst) == [src, spec_break, dst]
    assert "tag" not in graph.nodes[spec_break]
    assert not any(
        link.relation is Relation.MEASURED_BY and link.source_id == spec_break
        for link in plan.links
    )


def test_sight_glass_and_dosing_isolation_deal_their_decks() -> None:
    h = TrimHarness()
    glasses, valves = set(), set()
    for _ in range(3):
        src, dst = _two_hosts(h)
        glasses.add(h.write(trims_extra.sight_glass(h.ctx, STYLE), src, dst).ports["sight_glass"])
        src, dst = _two_hosts(h)
        valves.add(h.write(trims_extra.dosing_isolation(h.ctx, STYLE), src, dst).ports["valve"])
    graph = assert_round_trip(h)
    assert {graph.nodes[n]["node_class"] for n in glasses} == set(ROLE_CLASSES["sight_glass"])
    assert {graph.nodes[n]["node_class"] for n in valves} == set(ROLE_CLASSES["dosing_isolation"])
