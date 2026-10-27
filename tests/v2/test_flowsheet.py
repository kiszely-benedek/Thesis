"""The flowsheet grammar: which units a plant has, and how their ports are wired (design 8)."""

from __future__ import annotations

import pytest
from pattern_harness import PatternHarness

from plantgraph.benchmark.v2.config import FlowsheetKnobs
from plantgraph.benchmark.v2.flowsheet import OpenOut, Slot, UnitSlot, draw_flowsheet, wire
from plantgraph.benchmark.v2.patterns.filter_package import build_filter_package
from plantgraph.benchmark.v2.patterns.ports import PatternInstance, Phase, PortDirection
from plantgraph.benchmark.v2.patterns.registry import available_patterns, build_pattern
from plantgraph.benchmark.v2.patterns.separation import build_flash_drum
from plantgraph.benchmark.v2.patterns.storage import build_tank_farm

ALL = frozenset({"U1", "U2", "U3", "U4", "U5", "U6", "U7", "U8"})
KNOBS = FlowsheetKnobs()


def _slots(seed: int, n_units: int, available: frozenset[str] = ALL) -> tuple[UnitSlot, ...]:
    return draw_flowsheet(seed, n_units, KNOBS, available)


def _train(units: tuple[UnitSlot, ...], train_no: int) -> list[UnitSlot]:
    return [unit for unit in units if unit.train_no == train_no]


# ---- the unit sequence ---------------------------------------------------------------------------


def test_unit_numbers_run_from_one_without_gaps_and_the_count_is_exact() -> None:
    units = _slots(3, 25)
    assert [unit.unit_no for unit in units] == list(range(1, 26))


def test_a_complete_train_follows_the_grammar_and_a_later_train_has_no_feed_farm() -> None:
    units = _slots(1, 60)
    first, second = _train(units, 1), _train(units, 2)
    assert first[0].slot is Slot.FEED_FARM and first[-1].slot is Slot.PRODUCT_FARM
    assert second[0].slot is not Slot.FEED_FARM and second[-1].slot is Slot.PRODUCT_FARM
    for train in (first, second):
        order = [unit.slot for unit in train]
        assert order == sorted(order, key=list(Slot).index)  # slots never go backwards
        assert order.count(Slot.CORE) in (1, 2)  # one core unit, two when it is `U3+U2`
        assert 1 <= order.count(Slot.SEPARATION) <= 3
        assert order.count(Slot.CONDITIONING) <= 2


def test_the_unit_counts_per_train_stay_in_the_design_range() -> None:
    """First train 4-9 units, later trains 3-8 (a train cut short by `n_units` is exempt)."""
    for seed in range(1, 30):
        units = _slots(seed, 200)
        last_train = units[-1].train_no
        for train_no in range(1, last_train):
            size = len(_train(units, train_no))
            low, high = (4, 9) if train_no == 1 else (3, 8)
            assert low <= size <= high, (seed, train_no, size)


def test_the_first_n_units_of_a_bigger_plant_are_the_n_unit_plant() -> None:
    """Prefix stability of the sequence (design 8.2)."""
    assert _slots(7, 30)[:12] == _slots(7, 12)


def test_the_sequence_is_deterministic_and_depends_on_the_seed() -> None:
    assert _slots(4, 30) == _slots(4, 30)
    assert _slots(4, 30) != _slots(5, 30)


def test_only_available_patterns_are_drawn() -> None:
    units = _slots(2, 60, available=frozenset({"U4", "U6", "U7"}))
    assert {unit.pattern_id for unit in units} == {"U4", "U6", "U7"}
    conditioning = {u.pattern_id for u in units if u.slot is Slot.CONDITIONING}
    assert conditioning == {"U7"}  # U5 and U8 do not exist yet


def test_a_composite_option_needs_all_its_patterns() -> None:
    knobs = FlowsheetKnobs(core_weights={"U3+U2": 1.0, "U6": 1.0})
    with_u2 = draw_flowsheet(1, 120, knobs, ALL)
    core = [u.pattern_id for u in with_u2 if u.slot is Slot.CORE]
    assert "U3" in core and core[core.index("U3") + 1] == "U2"  # U3 is always followed by U2
    without_u2 = draw_flowsheet(1, 120, knobs, ALL - {"U2"})
    assert {u.pattern_id for u in without_u2 if u.slot is Slot.CORE} == {"U6"}


def test_a_weight_of_one_option_forces_it() -> None:
    knobs = FlowsheetKnobs(core_weights={"U6": 1.0}, conditioning_count_weights={2: 1.0})
    units = draw_flowsheet(1, 40, knobs, ALL)
    train = _train(units, 1)
    assert [u.slot for u in train].count(Slot.CONDITIONING) == 2
    assert {u.pattern_id for u in units if u.slot is Slot.CORE} == {"U6"}


def test_a_required_slot_with_no_available_pattern_is_an_error() -> None:
    knobs = FlowsheetKnobs(core_weights={"U3": 1.0})
    with pytest.raises(ValueError, match="required core slot"):
        draw_flowsheet(1, 10, knobs, frozenset({"U4", "U6", "U7"}))


def test_the_grammar_needs_the_tank_farm() -> None:
    with pytest.raises(ValueError, match="needs the tank farm 'U4'"):
        draw_flowsheet(1, 5, KNOBS, frozenset({"U6"}))


def test_wiring_never_raises_on_random_configs() -> None:
    """Any valid weights, 50 seeds: the grammar always returns the units asked for."""
    knobs = FlowsheetKnobs(
        conditioning_count_weights={0: 3.0, 2: 1.0},
        separation_count_weights={1: 1.0, 3: 4.0},
        separation_weights={"U6": 1.0},
    )
    for seed in range(50):
        assert len(draw_flowsheet(seed, 33, knobs, available_patterns())) == 33


# ---- wiring --------------------------------------------------------------------------------------


def _wired_chain() -> tuple[tuple[PatternInstance, ...], tuple[OpenOut, ...]]:
    """Tank farm -> filter package -> flash drum, wired by the grammar's own `wire`."""
    h = PatternHarness()
    farm, package, drum = (
        build_tank_farm(h.pctx),
        build_filter_package(h.pctx),
        build_flash_drum(h.pctx),
    )
    farm, open_outs = wire(farm, 1, ())
    package, open_outs = wire(package, 2, open_outs)
    drum, open_outs = wire(drum, 3, open_outs)
    return (farm, package, drum), open_outs


def _source_of(instance: PatternInstance, in_port_name: str) -> str | None:
    """The `src_id` of the line behind an in-port: None while it is open."""
    line_number = instance.port(in_port_name).line_number
    return next(line.src_id for line in instance.plan.lines if line.line_number == line_number)


def test_the_first_unit_keeps_its_in_ports_open() -> None:
    (farm, _, _), _ = _wired_chain()
    in_ports = [p.name for p in farm.ports if p.direction is PortDirection.IN]
    assert in_ports and {_source_of(farm, name) for name in in_ports} == {None}


def test_a_unit_is_fed_from_the_latest_out_port_of_its_phase() -> None:
    (farm, package, drum), _ = _wired_chain()
    assert _source_of(package, "feed") == farm.port("transfer").node_id
    assert _source_of(drum, "feed") == package.port("filtered").node_id


def test_a_gas_out_port_is_never_taken_by_a_liquid_in_port() -> None:
    (_, _, drum), open_outs = _wired_chain()
    assert Phase.GAS is drum.port("vapour").phase
    open_names = {(out.unit_no, out.port.name) for out in open_outs}
    assert (3, "vapour") in open_names  # nobody took it: an open gas stub


def test_taken_out_ports_are_no_longer_open_and_the_last_ones_are() -> None:
    _, open_outs = _wired_chain()
    assert {(out.unit_no, out.port.name) for out in open_outs} == {(3, "vapour"), (3, "liquid")}


def test_the_registry_builds_every_listed_pattern_and_names_the_known_ones_on_a_miss() -> None:
    h = PatternHarness()
    assert available_patterns() == frozenset({"U1", "U2", "U3", "U4", "U5", "U6", "U7", "U8"})
    assert build_pattern("U7", h.pctx).pattern == "U7"
    # U10 (the desalter) is never generated, so it stays a good example of an unknown id
    with pytest.raises(
        ValueError, match=r"no pattern 'U10'.*\['U1', 'U2', 'U3', 'U4', 'U5', 'U6', 'U7', 'U8'\]"
    ):
        build_pattern("U10", h.pctx)
