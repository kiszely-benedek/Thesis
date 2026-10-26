"""Ports, drawing groups, variant decks and the assembly helpers the patterns share."""

from __future__ import annotations

import random

import pytest
from pattern_harness import PatternHarness, config_with
from trim_harness import assert_round_trip

from graph_plant_builder_v2 import GraphPlantBuilderV2
from plantgraph.benchmark.v2.config import PatternKnobs
from plantgraph.benchmark.v2.deck import VariantDecks
from plantgraph.benchmark.v2.patterns.assembly import (
    close_run,
    line_between,
    line_containing,
    part_plan,
    spared_set,
    with_stream_kinds,
)
from plantgraph.benchmark.v2.patterns.context import PatternContext
from plantgraph.benchmark.v2.patterns.filter_package import build_filter_package
from plantgraph.benchmark.v2.patterns.ports import (
    DrawingGroups,
    PatternInstance,
    Phase,
    PortDirection,
    open_end_port,
    with_in_port_source,
)
from plantgraph.benchmark.v2.patterns.separation import build_flash_drum
from plantgraph.benchmark.v2.patterns.variants import (
    all_deck_variants,
    deck_from_weights,
    pattern_deck_variants,
    variant_label,
)
from plantgraph.benchmark.v2.plan_models import StreamKindV2
from plantgraph.benchmark.v2.trim_plan import TrimPlan
from plantgraph.benchmark.v2.vocabulary import OnOffLetter, SpareNaming, TrainConventions


def _filter() -> tuple[PatternHarness, PatternInstance]:
    h = PatternHarness()
    return h, build_filter_package(h.pctx)


# ---- ports ---------------------------------------------------------------------------------------


def test_an_out_port_names_the_last_node_and_an_in_port_the_first() -> None:
    _, instance = _filter()
    feed = instance.port("feed")
    line = line_between(instance.plan, None, instance.plan.equipment[0].node_id)
    assert feed.node_id == line.items[0].node_id and feed.line_number == line.line_number
    filtered = instance.port("filtered")
    out_line = line_containing(instance.plan, filtered.node_id)
    assert filtered.node_id == out_line.items[-1].node_id


def test_a_port_on_a_closed_end_is_refused() -> None:
    _, instance = _filter()
    closed = line_between(instance.plan, None, instance.plan.equipment[0].node_id)
    with pytest.raises(ValueError, match="not open at its dst_id"):
        open_end_port("x", PortDirection.OUT, Phase.LIQUID, closed)
    both_ends = next(line for line in instance.plan.lines if line.src_id and line.dst_id)
    with pytest.raises(ValueError, match="not open at its src_id"):
        open_end_port("x", PortDirection.IN, Phase.LIQUID, both_ends)


def test_an_unknown_port_lists_the_known_ones() -> None:
    _, instance = _filter()
    with pytest.raises(ValueError, match=r"\['feed', 'filtered'\]"):
        instance.port("nope")


def _instance_with(instance: PatternInstance, **changes: object) -> PatternInstance:
    fields = {name: getattr(instance, name) for name in type(instance).model_fields}
    return PatternInstance(**{**fields, **changes})


def test_an_instance_needs_a_group_for_every_piece_of_equipment() -> None:
    _, instance = _filter()
    with pytest.raises(ValueError, match="every piece of equipment needs exactly one"):
        _instance_with(instance, drawing_group_of={})


def test_an_instance_refuses_duplicate_port_names_and_ports_on_unknown_lines() -> None:
    _, instance = _filter()
    with pytest.raises(ValueError, match="port names must be unique"):
        _instance_with(instance, ports=(instance.ports[0], instance.ports[0]))
    stray = instance.ports[0].model_copy(update={"line_number": "6-P-99999-A1A-N"})
    with pytest.raises(ValueError, match="name lines that are not in the plan"):
        _instance_with(instance, ports=(stray,))


def test_a_machine_cannot_be_in_two_groups() -> None:
    groups = DrawingGroups()
    groups.put(["a"], "G1")
    with pytest.raises(ValueError, match="already in group 'G1'"):
        groups.put(["a"], "G2")
    groups.put(["b"], "G2", pinned=True)
    assert groups.group_of == {"a": "G1", "b": "G2"} and groups.pinned == frozenset({"G2"})


def test_joining_an_in_port_to_an_out_port_feeds_the_line_and_records_the_stream_kind() -> None:
    """The grammar's join: the out-port's node becomes the in-port line's source (oracle only)."""
    h = PatternHarness()
    drum = build_flash_drum(h.pctx)
    package = build_filter_package(h.pctx)
    joined = with_in_port_source(package, "feed", drum.port("liquid").node_id)
    line = line_containing(joined.plan, joined.port("feed").node_id)
    assert line.src_id == drum.port("liquid").node_id
    assert joined.plan.stream_kinds[line.line_number] is StreamKindV2.CROSS_UNIT
    oracle = GraphPlantBuilderV2("plant0")
    drum.plan.write(oracle)
    joined.plan.write(oracle)
    assert oracle.graph.has_edge(drum.port("liquid").node_id, joined.port("feed").node_id)


def test_only_an_in_port_can_be_joined() -> None:
    _, instance = _filter()
    with pytest.raises(ValueError, match="expected an in-port"):
        with_in_port_source(instance, "filtered", "x")


# ---- variant decks -------------------------------------------------------------------------------


def test_the_pattern_decks_hold_the_cards_of_table_13_3() -> None:
    decks = pattern_deck_variants()
    assert sorted(decks["U4.tank_count"]) == ["2", "3", "4"]
    assert decks["U4.transfer_pump"].count("CentrifugalPump") == 2
    assert decks["U4.metering"].count("none") == 4 and len(decks["U4.metering"]) == 8
    assert sorted(decks["U4.manifold"]) == ["GateValve", "GateValve", "PlugValve"]
    assert sorted(decks["U4.tank_service"]) == ["flammable", "non_flammable"]
    assert sorted(decks["U6.vessel"]) == [
        "GravitationalSeparator",
        "PressureVessel",
        "PressureVessel",
    ]


def test_the_pump_set_decks_come_from_the_declared_config_weights() -> None:
    decks = pattern_deck_variants()
    assert sorted(decks["pump_set.group"]) == [
        "own_sheet",
        "with_suction_vessel",
        "with_suction_vessel",
    ]
    assert decks["pump_set.pressure"].count("per_pump_pi") == 3
    knobs = PatternKnobs(pump_set_group_weights={"with_suction_vessel": 1.0, "own_sheet": 1.0})
    assert len(pattern_deck_variants(knobs)["pump_set.group"]) == 2


def test_a_fractional_weight_cannot_make_a_deck() -> None:
    with pytest.raises(ValueError, match="whole number"):
        deck_from_weights({"a": 1.5}, "pump_set_group_weights")


def test_all_decks_include_the_trim_role_decks() -> None:
    decks = all_deck_variants()
    assert "role:block_valve" in decks and "U6.vessel" in decks
    VariantDecks(0, decks)  # a real VariantDecks accepts the lot


def test_a_variant_label_lists_the_axes_in_order() -> None:
    assert variant_label(tanks=3, metering="none") == "tanks=3|metering=none"


# ---- context and assembly ------------------------------------------------------------------------


def test_the_context_reads_its_knobs_from_the_config() -> None:
    config = config_with(patterns={"p_single_pump": 0.5}, instruments={"p_cascade": 0.25})
    conventions = TrainConventions(on_off_letter=OnOffLetter.Y, spare_naming=SpareNaming.SUFFIX)
    decks = VariantDecks(0, all_deck_variants())
    style = PatternHarness().pctx.style
    ctx = PatternContext.from_config(config, 4, random.Random(0), conventions, decks, style)
    assert ctx.unit_no == 4
    assert ctx.knobs.p_single_pump == 0.5 and ctx.instruments.p_cascade == 0.25
    assert ctx.deal("U6.vessel") in {"PressureVessel", "GravitationalSeparator"}


def test_spared_sets_are_tagged_after_the_trains_naming() -> None:
    suffix = PatternHarness(spare_naming=SpareNaming.SUFFIX)
    tags = [m.tag for m in spared_set(suffix.pctx, "LiquidFilter", "F", 3)]
    assert [t[-1] for t in tags] == ["A", "B", "C"] and len({t[:-1] for t in tags}) == 1
    consecutive = PatternHarness(spare_naming=SpareNaming.CONSECUTIVE)
    assert len({m.tag for m in spared_set(consecutive.pctx, "LiquidFilter", "F", 3)}) == 3


def test_close_run_puts_the_run_in_one_line_and_records_its_kind() -> None:
    h = PatternHarness()
    vessel, tank = h.equipment("PressureVessel", "V"), h.equipment("Tank", "TK")
    plan = close_run(h.pctx, part_plan(h.pctx, "GateValve", "block"), vessel, tank)
    (line,) = plan.lines
    assert plan.stream_kinds == {line.line_number: StreamKindV2.PROCESS}
    plan.write(h.builder)
    assert_round_trip(h)


def test_a_line_lookup_that_finds_none_raises_and_stream_kinds_fill_only_the_gaps() -> None:
    plan = TrimPlan()
    with pytest.raises(ValueError, match="expected one line with item 'x', found 0"):
        line_containing(plan, "x")
    with pytest.raises(ValueError, match="found 0"):
        line_between(plan, None, "x")
    assert with_stream_kinds(plan) == plan
