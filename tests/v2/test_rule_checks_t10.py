"""The protection rules of task T10: API14C-SAC, API14C-3.4-TWO-LEVELS, TOG207 PSD, TOG236.

Per rule (design 3.3): (a) no violation on a v2.2 plant, (b) a mutation is caught, (c) over the five
seeds the check looked at something, plus the version gate. The pass that adds the devices is
tested for what it must not do: move a draw or change a part the patterns drew.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import replace

import networkx as nx
import pytest
from plant_invariants import plant_view, plant_view_v22

import plantgraph.benchmark.v2.planner as planner_module
from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22, HandbookKnobs
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.hidden_state import FluidClass
from plantgraph.benchmark.v2.patterns.ports import PatternInstance
from plantgraph.benchmark.v2.protection import add_protection
from plantgraph.benchmark.v2.protection_valves import EMERGENCY_VENT_ROLE, SUCTION_PSV_ROLE
from plantgraph.benchmark.v2.rules.catalogue import all_rules, rule_by_id
from plantgraph.benchmark.v2.rules.registry import CheckResult, RuleStatus, resolve_check
from plantgraph.benchmark.v2.rules.sac import SAC_ITEMS, sac_item
from plantgraph.benchmark.v2.rules.view import RuleView, build_rule_view
from plantgraph.benchmark.v2.trim_context import TrimContext
from plantgraph.ingest.headline_v2 import HeadlinePresetV2, smallest_n_units_v2

SEEDS = [1, 2, 3, 4, 5]
_T10_RULES = [
    "API14C-SAC",
    "API14C-3.4-TWO-LEVELS",
    "TOG207-HX-PSD-BOTH-SIDES",
    "TOG236-TANK-EMERGENCY-VENT",
]


def _units(seed: int) -> int:
    return smallest_n_units_v2(30, HeadlinePresetV2(), seed).n_units


def _view22(seed: int) -> RuleView:
    return plant_view_v22(seed, _units(seed))


def _run(rule_id: str, view: RuleView) -> CheckResult:
    return resolve_check(rule_by_id(rule_id))(view)


def _nodes_with_role(view: RuleView, role: str) -> list[str]:
    return sorted(n for n, r in view.roles.items() if r == role)


def _letters(view: RuleView, node: str) -> str:
    return str(view.graph.nodes[node].get("tag", "")).split("-")[0]


def _without(view: RuleView, nodes: list[str]) -> RuleView:
    """The view with these nodes removed from the oracle graph (a device that was never drawn)."""
    graph: nx.DiGraph[str] = view.graph.copy()
    graph.remove_nodes_from(nodes)
    return replace(view, graph=graph)


# ---- (a) positive, (c) non-vacuity, version gate ------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("rule_id", _T10_RULES)
def test_a_t10_rule_has_no_violation_on_a_v22_plant(rule_id: str, seed: int) -> None:
    assert _run(rule_id, _view22(seed)).violations == ()


@pytest.mark.parametrize("rule_id", _T10_RULES)
def test_a_t10_rule_checks_something_across_the_five_seeds(rule_id: str) -> None:
    assert sum(_run(rule_id, _view22(seed)).checked for seed in SEEDS) > 0


@pytest.mark.parametrize("rule_id", _T10_RULES)
def test_a_t10_rule_does_not_apply_to_a_v21_plant(rule_id: str) -> None:
    assert _run(rule_id, plant_view(1, _units(1))) == CheckResult(checked=0)


@pytest.mark.parametrize("rule_id", _T10_RULES)
def test_a_t10_rule_does_not_apply_to_a_v22_plant_with_the_handbook_off(rule_id: str) -> None:
    config = GeneratorConfigV22(seed=1, n_units=_units(1), handbook=HandbookKnobs.all_off())
    assert _run(rule_id, build_rule_view(generate_plant_v2(config))) == CheckResult(checked=0)


def test_every_exception_code_a_check_reports_is_declared_by_its_rule() -> None:
    for rule_id in _T10_RULES:
        declared = set(rule_by_id(rule_id).exception_codes)
        reported = {code for seed in SEEDS for code in _run(rule_id, _view22(seed)).exceptions}
        assert reported <= declared, (rule_id, sorted(reported - declared))


def test_all_54_rules_are_wired_and_the_sac_gaps_are_deferred_rows() -> None:
    encoded = [r for r in all_rules() if r.status is RuleStatus.ENCODED]
    assert len(encoded) == 54
    assert not [r.rule_id for r in encoded if r.check is None or r.check.startswith("pending")]
    deferred = {r.rule_id for r in all_rules() if r.status is RuleStatus.DEFERRED}
    assert {"API14C-SAC-A4-PSL", "API14C-SAC-A7-PSH-PSL", "API14C-SAC-A8-SDV-BDV-ASH"} <= deferred


# ---- (b) mutations ------------------------------------------------------------------------------


def test_sac_catches_a_vessel_that_lost_its_pressure_switch() -> None:
    view = _view22(2)
    sensors = [n for n in view.graph if str(view.graph.nodes[n].get("tag", "")).startswith("PSHH")]
    assert sensors, "expected the pass to have drawn a PSHH on seed 2"
    broken = _run("API14C-SAC", _without(view, sensors))
    assert broken.violations
    assert all(v.rule_id == "API14C-SAC" and v.detail for v in broken.violations)


def test_sac_catches_a_compressor_without_its_suction_psv() -> None:
    view = next(v for v in map(_view22, SEEDS) if _nodes_with_role(v, SUCTION_PSV_ROLE))
    valves = _nodes_with_role(view, SUCTION_PSV_ROLE)
    assert _run("API14C-SAC", _without(view, valves)).violations


def test_tank_rule_catches_a_tank_without_its_emergency_vent() -> None:
    view = _view22(1)
    vents = _nodes_with_role(view, EMERGENCY_VENT_ROLE)
    assert vents, "expected an emergency vent on seed 1"
    broken = _run("TOG236-TANK-EMERGENCY-VENT", _without(view, vents[:1]))
    assert [v.detail for v in broken.violations] == [
        f"expected an emergency vent on {broken.violations[0].node_id} or an omission code, "
        "found neither"
    ]


def test_two_levels_catches_a_vessel_without_a_sensor_trip() -> None:
    view = _view22(2)
    switches = [n for n in view.graph if _letters(view, n)[1:2] == "S"]
    assert _run("API14C-3.4-TWO-LEVELS", _without(view, switches)).violations


# ---- the scope and the declarations ------------------------------------------------------------


def test_non_flammable_farm_tanks_are_declared_and_get_no_emergency_vent() -> None:
    view = _view22(1)
    fluids = view.hidden.fluid_of_tank
    assert FluidClass.NON_FLAMMABLE in fluids.values()
    assert FluidClass.HYDROCARBON in fluids.values()
    result = _run("TOG236-TANK-EMERGENCY-VENT", view)
    assert result.exceptions["scope:non_hydrocarbon"] == sum(
        f is FluidClass.NON_FLAMMABLE for f in fluids.values()
    )
    assert len(_nodes_with_role(view, EMERGENCY_VENT_ROLE)) == sum(
        f is FluidClass.HYDROCARBON for f in fluids.values()
    )


def test_a4_overpressure_counts_the_condensate_pots_as_scope_and_has_no_old_code() -> None:
    for seed in SEEDS:
        view = _view22(seed)
        result = _run("API14C-A4-OVERPRESSURE", view)
        pots = len(_nodes_with_role(view, "condensate_drain_pot"))
        assert result.exceptions.get("scope:non_hydrocarbon", 0) == pots
        assert "source_cannot_exceed" not in result.exceptions


def test_the_recycle_check_counts_the_switching_valve_apart() -> None:
    counts = [
        _run("PLT-RECYCLE-CLOSURE", _view22(s)).exceptions.get("switching_valve", 0) for s in SEEDS
    ]
    assert sum(counts) > 0


def test_every_sac_item_has_a_unique_id_and_a_page_in_its_table() -> None:
    ids = [item.item_id for item in SAC_ITEMS]
    assert len(ids) == len(set(ids))
    assert sac_item("A-8.2", "e").device == "PSV"
    with pytest.raises(KeyError, match="expected a checked SAC item"):
        sac_item("A-4.2", "b")  # the vessel PSL is a deferred row, not a checked item


def test_a_furnace_with_a_skillet_blind_gets_a_tube_psv_and_one_without_does_not() -> None:
    roles = Counter(
        role
        for seed in SEEDS
        for role in _view22(seed).roles.values()
        if role in {"heater_tube_psv", "skillet_blind"}
    )
    assert roles["heater_tube_psv"] > 0
    assert roles["heater_tube_psv"] <= roles["skillet_blind"]


# ---- the pass changes nothing that was drawn ----------------------------------------------------


def _capture_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[], tuple[list[PatternInstance], list[PatternInstance], list[tuple[object, ...]]]]:
    """Wrap `add_protection` so the instances before and after it, and the streams, are kept."""
    seen: dict[str, object] = {}

    def wrapper(instances, trims, style):  # type: ignore[no-untyped-def]
        before_state = [_stream_state(trim) for trim in trims]
        after = add_protection(instances, trims, style)
        seen.update(
            before=list(instances),
            after=after,
            states=list(zip(before_state, map(_stream_state, trims), strict=True)),
        )
        return after

    monkeypatch.setattr(planner_module, "add_protection", wrapper)
    return lambda: (seen["before"], seen["after"], seen["states"])  # type: ignore[return-value]


def _stream_state(trim: TrimContext) -> tuple[object, ...]:
    rule_streams = trim._rule_streams
    return (
        trim.rng.getstate(),
        trim._handbook_rng.getstate(),
        {name: rng.getstate() for name, rng in rule_streams.items()},
    )


def test_the_pass_draws_nothing_and_changes_nothing_the_patterns_drew(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    taken = _capture_pass(monkeypatch)
    generate_plant_v2(GeneratorConfigV22(seed=3, n_units=_units(3)))
    before, after, states = taken()
    assert all(start == end for start, end in states), "the pass moved a random stream"
    for old, new in zip(before, after, strict=True):
        assert new.plan.equipment == old.plan.equipment
        new_lines = {line.line_number: line for line in new.plan.lines}
        for line in old.plan.lines:
            kept = new_lines[line.line_number]
            assert [i for i in kept.items if i in line.items] == list(line.items)  # tees only
            assert (kept.src_id, kept.dst_id) == (line.src_id, line.dst_id)
        assert set(old.plan.instruments) <= set(new.plan.instruments)
        assert {k: v for k, v in new.plan.roles.items() if k in old.plan.roles} == old.plan.roles


def test_the_pass_adds_something_on_a_plant_that_has_vessels_and_tanks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    taken = _capture_pass(monkeypatch)
    generate_plant_v2(GeneratorConfigV22(seed=2, n_units=_units(2)))
    before, after, _ = taken()
    added = sum(
        len(n.plan.instruments) - len(o.plan.instruments)
        for o, n in zip(before, after, strict=True)
    )
    assert added > 0


def test_the_fuel_pressure_switch_sits_on_a_tee_between_the_pv_and_the_tv() -> None:
    for seed in SEEDS:
        view = _view22(seed)
        for tee in _nodes_with_role(view, "fuel_gas_psh_tee"):
            before, after = _fuel_valves_around(view, tee)
            assert before.startswith("PV") and after.startswith("TV"), (before, after)
            assert any(_letters(view, s).startswith("PSHH") for s in view.graph.successors(tee))


def _fuel_valves_around(view: RuleView, tee: str) -> tuple[str, str]:
    """The tags of the nearest loop valve upstream and downstream of the tee on the fuel line."""

    def nearest(step: Callable[[str], list[str]]) -> str:
        node = tee
        while True:
            node = step(node)[0]
            tag = str(view.graph.nodes[node].get("tag") or "")
            if tag[:2] in {"PV", "TV"}:
                return tag

    return nearest(lambda n: list(view.piping.predecessors(n))), nearest(
        lambda n: list(view.piping.successors(n))
    )
