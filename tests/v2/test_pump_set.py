"""The pump set (design 7.1): every variant, and the pump rules S1, S2, S3, S11, S12 on its graph.

Each test builds the set on the graph oracle and the DEXPI builder, checks the rule on the oracle
graph, and asserts the DEXPI round trip gives the same graph.
"""

from __future__ import annotations

import networkx as nx
import pytest
from instrument_harness import sources, targets
from pattern_checks import assert_pattern_invariants, flow_graph, nodes_with_letters
from pattern_harness import PatternHarness, config_with
from trim_harness import STYLE, all_send_to_paths, classes_of, ids_with_role, send_to_path

from plantgraph.benchmark.v2 import trims_valves
from plantgraph.benchmark.v2.instruments import flow_control_loop
from plantgraph.benchmark.v2.patterns.pump_set import PumpSet, build_pump_set
from plantgraph.benchmark.v2.plan_models import StreamKindV2
from plantgraph.benchmark.v2.tags import parse_tag
from plantgraph.benchmark.v2.vocabulary import SpareNaming
from plantgraph.graph.schema import Relation

_COUNT_KNOBS = {
    1: {"p_single_pump": 1.0, "p_triple_pump_set": 0.0},
    2: {"p_single_pump": 0.0, "p_triple_pump_set": 0.0},
    3: {"p_single_pump": 0.0, "p_triple_pump_set": 1.0},
}


def _build(
    count: int = 2,
    pump_class: str = "CentrifugalPump",
    trims: dict[str, object] | None = None,
    density: dict[str, object] | None = None,
    cards: dict[str, tuple[str, ...]] | None = None,
    naming: SpareNaming = SpareNaming.SUFFIX,
    header: object = None,
    feed_count: int = 0,
    seed: int = 0,
) -> tuple[PatternHarness, str, PumpSet]:
    """One pump set of `count` pumps drawing from a vessel; returns harness, vessel, set."""
    config = config_with(
        patterns=_COUNT_KNOBS[count],
        trims={"p_min_flow": 0.0, **(trims or {})},
        density=density or {},
    )
    h = PatternHarness(seed, config, spare_naming=naming, deck_cards=cards)
    vessel = h.equipment("PressureVessel", "V")
    built = build_pump_set(h.pctx, vessel, pump_class, "transfer_pump", header, feed_count)  # type: ignore[arg-type]
    built.plan.write(h.builder)
    return h, vessel, built


# ---- how many pumps, and how they are tagged ----------------------------------------------------


@pytest.mark.parametrize("count", [1, 2, 3])
def test_the_pump_count_follows_the_knobs_and_the_round_trip_holds(count: int) -> None:
    h, _, built = _build(count)
    assert len(built.pump_ids) == count
    assert assert_pattern_invariants(h).number_of_nodes() > 20


def test_spares_share_one_number_with_letter_suffixes() -> None:
    _, _, built = _build(3)
    tags = [item.tag for item in built.plan.equipment]
    assert tags == [f"{tags[0][:-1]}{letter}" for letter in "ABC"]
    assert {parse_tag(tag).unit for tag in tags} == {1}  # type: ignore[union-attr]


def test_consecutive_naming_gives_each_spare_the_next_number() -> None:
    _, _, built = _build(3, naming=SpareNaming.CONSECUTIVE)
    parsed = [parse_tag(item.tag) for item in built.plan.equipment]
    assert all(tag is not None and tag.train is None for tag in parsed)
    numbers = [tag.sequence for tag in parsed if tag]
    assert numbers == [numbers[0], numbers[0] + 1, numbers[0] + 2]


def test_a_single_pump_has_a_plain_tag_under_both_namings() -> None:
    for naming in SpareNaming:
        _, _, built = _build(1, naming=naming)
        assert parse_tag(built.plan.equipment[0].tag).train is None  # type: ignore[union-attr]


def test_s11_members_have_the_same_class_the_same_role_and_a_motor() -> None:
    h, _, built = _build(3, "RotaryPump")
    assert {item.node_class for item in built.plan.equipment} == {"RotaryPump"}
    assert {built.plan.roles[i] for i in built.pump_ids} == {"transfer_pump"}
    assert all(item.has_motor for item in built.plan.equipment)
    assert not [n for n in h.oracle.graph if n.endswith("-motor")]  # the motor is not a node


def test_a_class_without_a_suction_trim_is_refused() -> None:
    h = PatternHarness()
    with pytest.raises(ValueError, match="centrifugal, reciprocating or rotary pump"):
        build_pump_set(h.pctx, "v", "EjectorPump", "p")


# ---- the rules -----------------------------------------------------------------------------------


@pytest.mark.parametrize("count", [1, 2, 3])
def test_s1_each_pump_draws_through_a_block_valve_and_a_strainer(count: int) -> None:
    """Rule L2: vessel -> block -> strainer -> pump, for every pump of the set."""
    h, vessel, built = _build(count)
    graph = assert_pattern_invariants(h)
    for index, pump in enumerate(built.pump_ids):
        path = send_to_path(graph, vessel, pump)
        block = built.plan.ports[f"pump{index}.suction.block"]
        strainer = built.plan.ports[f"pump{index}.suction.strainer"]
        assert path.index(block) < path.index(strainer) < path.index(pump)


@pytest.mark.parametrize("count", [1, 2, 3])
def test_s2_each_discharge_has_the_gauge_before_the_check_and_the_block_after(count: int) -> None:
    """Rules L1, L3: pump -> gauge tap -> check -> block, then the header."""
    h, _, built = _build(count)
    graph = assert_pattern_invariants(h)
    gauge_tees = set(ids_with_role(built.plan, "pressure_gauge_tee"))
    for index, pump in enumerate(built.pump_ids):
        path = send_to_path(graph, pump, built.discharge.node_id)
        check = built.plan.ports[f"pump{index}.discharge.check"]
        block = built.plan.ports[f"pump{index}.discharge.block"]
        (tee,) = gauge_tees & set(path)
        assert path.index(tee) < path.index(check) < path.index(block)


@pytest.mark.parametrize("pump_class", ["RotaryPump", "ReciprocatingPump"])
def test_s3_each_pd_pump_has_a_relief_from_before_the_check_to_its_suction(pump_class: str) -> None:
    h, _, built = _build(2, pump_class)
    graph = assert_pattern_invariants(h)
    for index, pump in enumerate(built.pump_ids):
        ports = built.plan.ports
        relief = send_to_path(
            graph,
            ports[f"pump{index}.discharge.relief_tee"],
            ports[f"pump{index}.suction.relief_return_tee"],
        )
        assert classes_of(graph, relief)[1] == "SpringLoadedAngleGlobeSafetyValve"
        discharge = send_to_path(graph, pump, built.discharge.node_id)
        assert discharge.index(relief[0]) < discharge.index(ports[f"pump{index}.discharge.check"])


@pytest.mark.parametrize("count", [2, 3])
def test_s11_the_pumps_are_parallel_between_the_split_and_the_merge_tees(count: int) -> None:
    h, vessel, built = _build(count)
    graph = assert_pattern_invariants(h)
    paths = all_send_to_paths(graph, vessel, built.discharge.node_id)
    pumps = set(built.pump_ids)
    assert [len(pumps & set(path)) for path in paths] == [1] * count
    assert {pump for path in paths for pump in pumps & set(path)} == pumps
    suction = send_to_path(graph, vessel, built.pump_ids[0])
    discharge = send_to_path(graph, built.pump_ids[0], built.discharge.node_id)
    splits = [n for n in suction if n in ids_with_role(built.plan, "suction_split_tee")]
    merges = [n for n in discharge if n in ids_with_role(built.plan, "discharge_merge_tee")]
    assert len(splits) == len(merges) == count - 1
    assert all(splits[0] in path and merges[-1] in path for path in paths)  # shared by every pump


def test_s12_a_spare_never_discharges_into_the_duty_pump_and_no_pump_back_to_the_vessel() -> None:
    h, vessel, built = _build(2)
    graph = flow_graph(assert_pattern_invariants(h))
    duty, spare = built.pump_ids
    assert not nx.has_path(graph, duty, spare)
    assert not nx.has_path(graph, spare, duty)
    assert not nx.has_path(graph, duty, vessel)


def test_s12_with_the_minimum_flow_line_the_only_way_back_is_through_its_orifice() -> None:
    h, vessel, built = _build(2, trims={"p_min_flow": 1.0})
    graph = assert_pattern_invariants(h)
    for pump in built.pump_ids:
        path = send_to_path(graph, pump, vessel)
        assert "RestrictionOrifice" in classes_of(graph, path)
    kinds = list(built.plan.stream_kinds.values())
    assert kinds.count(StreamKindV2.RECYCLE) == 2  # one per pump


# ---- variants ------------------------------------------------------------------------------------


@pytest.mark.parametrize("count", [1, 2])
def test_per_pump_pressure_mode_draws_one_gauge_per_pump(count: int) -> None:
    h, _, built = _build(count, cards={"pump_set.pressure": ("per_pump_pi",)})
    graph = assert_pattern_invariants(h)
    assert len(ids_with_role(built.plan, "discharge_pi")) == count
    assert not nodes_with_letters(graph, "PT")


def test_header_pressure_mode_draws_one_transmitter_after_the_merge_tees() -> None:
    h, _, built = _build(3, cards={"pump_set.pressure": ("header_pt",)})
    graph = assert_pattern_invariants(h)
    assert not ids_with_role(built.plan, "discharge_pi")
    (transmitter,) = nodes_with_letters(graph, "PT")
    assert graph.nodes[transmitter]["tag"].startswith("PT-")
    (tee,) = ids_with_role(built.plan, "header_pressure_tee")
    path = send_to_path(graph, built.pump_ids[0], built.discharge.node_id)
    assert all(
        path.index(merge) < path.index(tee)
        for merge in ids_with_role(built.plan, "discharge_merge_tee")
    )


@pytest.mark.parametrize("count", [1, 2])
def test_flexible_connectors_sit_on_every_suction_and_discharge(count: int) -> None:
    h, _, built = _build(count, trims={"p_flex_connector": 1.0})
    graph = assert_pattern_invariants(h)
    compensators = [n for n, d in graph.nodes(data=True) if d["node_class"] == "Compensator"]
    assert len(compensators) == 2 * count


def test_without_flexible_connectors_there_are_none() -> None:
    h, _, _ = _build(2, trims={"p_flex_connector": 0.0})
    graph = assert_pattern_invariants(h)
    assert not [n for n, d in graph.nodes(data=True) if d["node_class"] == "Compensator"]


def test_an_own_sheet_set_is_marked_and_a_single_pump_never_is() -> None:
    _, _, spared = _build(2, cards={"pump_set.group": ("own_sheet",)})
    _, _, with_vessel = _build(2, cards={"pump_set.group": ("with_suction_vessel",)})
    _, _, single = _build(1, cards={"pump_set.group": ("own_sheet",)})
    assert (spared.own_sheet, with_vessel.own_sheet, single.own_sheet) == (True, False, False)
    assert "group=own_sheet" in spared.variant and "group=with_suction_vessel" in single.variant


# ---- the parts that hang on the set --------------------------------------------------------------


def test_extra_suction_feeds_come_first_on_the_first_pumps_suction_line() -> None:
    h, vessel, built = _build(2, feed_count=2)
    graph = assert_pattern_invariants(h)
    path = send_to_path(graph, vessel, built.pump_ids[0])
    feeds = list(built.feed_tee_ids)
    splits = ids_with_role(built.plan, "suction_split_tee")
    assert len(feeds) == 2 and path[1:3] == feeds
    assert path.index(feeds[-1]) < path.index(splits[0])


def test_a_header_plan_closes_the_discharge_line_and_its_last_part_is_the_out_port() -> None:
    h = PatternHarness(config=config_with(patterns=_COUNT_KNOBS[2], trims={"p_min_flow": 0.0}))
    vessel = h.equipment("PressureVessel", "V")
    element = trims_valves.flow_element(h.ctx, STYLE, "liquid")
    header = flow_control_loop(h.ctx, STYLE, element, trims_valves.control_valve(h.ctx, STYLE, "F"))
    built = build_pump_set(h.pctx, vessel, "CentrifugalPump", "p", header=header)
    built.plan.write(h.builder)
    graph = assert_pattern_invariants(h)
    assert built.discharge.node_id == header.run[-1].node_id
    path = send_to_path(graph, built.pump_ids[0], built.discharge.node_id)
    assert header.run[0].node_id in path  # the flow element is on the header


def test_every_pump_gets_a_hand_switch_with_a_start_input_and_running_status() -> None:
    h, _, built = _build(2)
    graph = assert_pattern_invariants(h)
    assert len(nodes_with_letters(graph, "HS")) == 2
    assert len(nodes_with_letters(graph, "YI")) == 2
    for pump in built.pump_ids:
        (aef,) = sources(graph, pump, Relation.CONTROL)
        assert graph.nodes[aef]["node_class"] == "ActuatingElectricalFunction"
        (switch,) = sources(graph, aef, Relation.SEND_SIGNAL_TO)
        assert graph.nodes[switch]["tag"].startswith("HS-")
    assert targets(graph, built.pump_ids[0], Relation.MEASURED_BY)  # the running-status sensor


@pytest.mark.parametrize(("chance", "expected"), [(1.0, 2), (0.0, 0)])
def test_the_bearing_thermometer_follows_its_chance(chance: float, expected: int) -> None:
    h, _, _ = _build(2, density={"p_bearing_temperature": chance})
    graph = assert_pattern_invariants(h)
    assert len(nodes_with_letters(graph, "TIAH")) == expected


# ---- decks ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("axis", "expected"),
    [
        ("group", {"group=own_sheet", "group=with_suction_vessel"}),
        ("pressure", {"pressure=per_pump_pi", "pressure=header_pt"}),
    ],
)
def test_every_pump_set_variant_appears_within_one_deck_cycle(
    axis: str, expected: set[str]
) -> None:
    """The group deck has 3 cards (2 : 1), the pressure deck 4 (3 : 1): four sets cover both."""
    h = PatternHarness(config=config_with(patterns=_COUNT_KNOBS[2]))
    labels = [build_pump_set(h.pctx, "v", "CentrifugalPump", "p").variant for _ in range(4)]
    seen = {part for label in labels for part in label.split("|") if part.startswith(axis)}
    assert seen == expected
