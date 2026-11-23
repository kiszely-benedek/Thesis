"""The pressure-level rules of task T8: PRS-MONOTONE, TOG82, PRS-SPEC-CLASS, TOG156, PLT-RECYCLE
and API14C-A4.

Per rule (design 3.3): (a) no violation on a v2.2 plant, (b) a mutation is caught, (c) over the
five seeds the check looked at something, plus the version gate (a v2.1 plant and a v2.2 plant with
the handbook off report `checked=0` and carry no level). A mutation changes one hidden level or one
node class in a copy of the view: the plant itself is never regenerated.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import replace

import pytest
from plant_invariants import plant_view, plant_view_v22

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22, HandbookKnobs
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.hidden_state import PressureLevel
from plantgraph.benchmark.v2.plan_models import LineSpec
from plantgraph.benchmark.v2.rules.catalogue import rule_by_id
from plantgraph.benchmark.v2.rules.checks_pressure import edge_level, line_number_of
from plantgraph.benchmark.v2.rules.registry import CheckResult, resolve_check
from plantgraph.benchmark.v2.rules.view import RuleView, build_rule_view
from plantgraph.benchmark.v2.trims_machine import DISCHARGE_BREAK_ROLE
from plantgraph.graph.schema import EQUIPMENT_CLASSES
from plantgraph.ingest.headline_v2 import HeadlinePresetV2, smallest_n_units_v2

SEEDS = [1, 2, 3, 4, 5]
_T8_RULES = [
    "PRS-MONOTONE",
    "TOG82-SPEC-BREAK",
    "PRS-SPEC-CLASS",
    "TOG156-MERGE-CHECK",
    "PLT-RECYCLE-CLOSURE",
    "API14C-A4-OVERPRESSURE",
]


def _units(seed: int) -> int:
    return smallest_n_units_v2(30, HeadlinePresetV2(), seed).n_units  # about 30 sheets


def _view22(seed: int) -> RuleView:
    return plant_view_v22(seed, _units(seed))


def _run(rule_id: str, view: RuleView) -> CheckResult:
    return resolve_check(rule_by_id(rule_id))(view)


def _class(view: RuleView, node: str) -> str:
    return str(view.graph.nodes[node]["node_class"])


def _first_node(view: RuleView, role: str) -> str:
    return next(n for n in sorted(view.roles) if view.roles[n] == role)


# ---- changing one level or one class (the mutations) --------------------------------------------


def _with_levels(view: RuleView, edit: Callable[[dict[str, PressureLevel]], None]) -> RuleView:
    """The view of the same plant with its hidden levels changed by `edit`."""
    levels = dict(view.hidden.segment_level)
    edit(levels)
    state = view.hidden.model_copy(update={"segment_level": levels})
    record = view.generated.record.model_copy(update={"hidden_state": state})
    return replace(view, generated=replace(view.generated, record=record))


def _with_class(view: RuleView, node: str, node_class: str) -> RuleView:
    """The view with one node drawn as another class (the oracle graph is copied first)."""
    graph = view.graph.copy()
    graph.nodes[node]["node_class"] = node_class
    return replace(view, graph=graph)


def _break_sides(view: RuleView, spec_break: str) -> tuple[str, str]:
    """The line numbers before and behind a spec break."""
    (before,) = view.piping.predecessors(spec_break)
    (after,) = view.piping.successors(spec_break)
    return line_number_of(view, before, spec_break), line_number_of(view, spec_break, after)


def _swapped_around(view: RuleView, spec_break: str) -> RuleView:
    """The view with the two levels on either side of a break exchanged."""
    before, after = _break_sides(view, spec_break)
    levels = view.hidden.segment_level
    return _with_levels(view, lambda lv: lv.update({before: levels[after], after: levels[before]}))


def _machine_before(view: RuleView, spec_break: str) -> str:
    """The pump or compressor a discharge break stands behind (past its nozzle parts)."""
    node = spec_break
    while _class(view, node) not in EQUIPMENT_CLASSES:
        node = next(iter(view.piping.predecessors(node)))
    return node


def _expect_violation(rule_id: str, view: RuleView, node: str) -> None:
    violations = _run(rule_id, view).violations
    assert any(v.node_id == node for v in violations), [v.node_id for v in violations[:5]]
    assert all(v.rule_id == rule_id and v.detail for v in violations)


# ---- (a) positive, (c) non-vacuity, version gate ------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("rule_id", _T8_RULES)
def test_a_t8_rule_has_no_violation_on_a_v22_plant(rule_id: str, seed: int) -> None:
    assert _run(rule_id, _view22(seed)).violations == ()


@pytest.mark.parametrize("rule_id", _T8_RULES)
def test_a_t8_rule_checks_something_across_the_five_seeds(rule_id: str) -> None:
    assert sum(_run(rule_id, _view22(seed)).checked for seed in SEEDS) > 0


@pytest.mark.parametrize("rule_id", _T8_RULES)
def test_a_t8_rule_does_not_apply_to_a_v21_plant(rule_id: str) -> None:
    assert _run(rule_id, plant_view(1, _units(1))) == CheckResult(checked=0)


@pytest.mark.parametrize("rule_id", _T8_RULES)
def test_a_t8_rule_does_not_apply_to_a_v22_plant_with_the_handbook_off(rule_id: str) -> None:
    config = GeneratorConfigV22(seed=1, n_units=_units(1), handbook=HandbookKnobs.all_off())
    assert _run(rule_id, build_rule_view(generate_plant_v2(config))) == CheckResult(checked=0)


def test_a_v21_plant_and_a_knobs_off_plant_draw_no_level_and_no_discharge_break() -> None:
    off = GeneratorConfigV22(seed=1, n_units=_units(1), handbook=HandbookKnobs.all_off())
    for view in (plant_view(1, _units(1)), build_rule_view(generate_plant_v2(off))):
        assert view.hidden.segment_level == {}
        assert DISCHARGE_BREAK_ROLE not in set(view.roles.values())


def test_every_level_but_the_unused_high_one_occurs_across_the_five_seeds() -> None:
    found: Counter[PressureLevel] = Counter()
    for seed in SEEDS:
        found.update(_view22(seed).hidden.segment_level.values())
    assert set(found) == {PressureLevel.VAC, PressureLevel.ATM, PressureLevel.LP, PressureLevel.MP}


def test_the_merge_and_overpressure_checks_meet_the_cases_they_are_for() -> None:
    lower_streams, tolerated = 0, 0
    for seed in SEEDS:
        view = _view22(seed)
        lower_streams += len(_lower_streams_into_merges(view))
        tolerated += _run("API14C-A4-OVERPRESSURE", view).exceptions.get("scope:non_hydrocarbon", 0)
    assert lower_streams > 0 and tolerated > 0


# ---- (b) mutations ------------------------------------------------------------------------------


def test_prs_monotone_catches_a_branch_that_runs_above_its_main_line() -> None:
    view = _view22(1)
    root = _first_node(view, "discharge_pi_root")  # a gauge branch off the pump's discharge tee
    (tee,) = view.piping.predecessors(root)
    number = line_number_of(view, tee, root)
    raised = _with_levels(view, lambda lv: lv.__setitem__(number, PressureLevel.HP))
    _expect_violation("PRS-MONOTONE", raised, tee)


def test_prs_monotone_catches_a_letdown_that_climbs() -> None:
    view = _view22(1)
    spec_break = _first_node(view, "spec_break")
    _expect_violation("PRS-MONOTONE", _swapped_around(view, spec_break), spec_break)


def test_tog82_catches_a_level_change_at_a_part_that_is_no_spec_break() -> None:
    view = _view22(1)
    spec_break = _first_node(view, "spec_break")
    _expect_violation("TOG82-SPEC-BREAK", _with_class(view, spec_break, "GateValve"), spec_break)


def test_tog82_catches_a_pump_whose_discharge_break_raises_nothing() -> None:
    view = _view22(1)
    spec_break = _first_node(view, DISCHARGE_BREAK_ROLE)
    before, after = _break_sides(view, spec_break)
    level = view.hidden.segment_level[before]
    flat = _with_levels(view, lambda lv: lv.__setitem__(after, level))
    _expect_violation("TOG82-SPEC-BREAK", flat, _machine_before(view, spec_break))


def test_prs_spec_class_catches_a_pump_break_with_the_light_class_on_the_high_side() -> None:
    view = _view22(1)
    spec_break = _first_node(view, DISCHARGE_BREAK_ROLE)
    _expect_violation("PRS-SPEC-CLASS", _swapped_around(view, spec_break), spec_break)


def test_prs_spec_class_catches_a_letdown_with_the_light_class_on_the_high_side() -> None:
    view = _view22(1)
    spec_break = _first_node(view, "spec_break")
    _expect_violation("PRS-SPEC-CLASS", _swapped_around(view, spec_break), spec_break)


def _chain_behind(view: RuleView, node: str) -> list[str]:
    """`node` and the parts before it, while the way back is a single pipe."""
    chain = [node]
    while len(before := list(view.piping.predecessors(chain[-1]))) == 1:
        chain.append(before[0])
    return chain


def _lower_streams_into_merges(view: RuleView) -> list[tuple[str, str]]:
    """(tee, source) for every stream that arrives below the level its merge tee carries on."""
    piping = view.piping
    found = []
    for tee in (n for n in sorted(piping) if view.roles.get(n) == "recycle_merge_tee"):
        (after,) = piping.successors(tee)
        found += [
            (tee, source)
            for source in piping.predecessors(tee)
            if edge_level(view, source, tee) < edge_level(view, tee, after)
        ]
    return found


def test_tog156_catches_a_lower_stream_with_no_check_valve() -> None:
    view = next(v for v in map(_view22, SEEDS) if _lower_streams_into_merges(v))
    tee, source = _lower_streams_into_merges(view)[0]
    valve = next(n for n in _chain_behind(view, source) if "CheckValve" in _class(view, n))
    _expect_violation("TOG156-MERGE-CHECK", _with_class(view, valve, "GateValve"), tee)


def _recycle_line_with(view: RuleView, role: str) -> LineSpec:
    return next(
        line
        for unit in view.plan.units
        for line in unit.instance.plan.lines
        if any(view.roles.get(i.node_id) == role for i in line.items)
    )


def test_plt_recycle_closure_catches_a_recycle_that_does_not_fall() -> None:
    view = _view22(1)
    line = _recycle_line_with(view, "min_flow_block")
    flat = _with_levels(view, lambda lv: lv.__setitem__(line.line_number, PressureLevel.VAC))
    _expect_violation("PLT-RECYCLE-CLOSURE", flat, line.items[0].node_id)


def test_plt_recycle_closure_catches_a_recycle_without_a_reducing_part() -> None:
    view = _view22(1)
    line = _recycle_line_with(view, "restriction_orifice")
    orifice = next(i.node_id for i in line.items if view.roles[i.node_id] == "restriction_orifice")
    plain = _with_class(view, orifice, "Flange")
    _expect_violation("PLT-RECYCLE-CLOSURE", plain, line.items[0].node_id)


def test_plt_recycle_closure_leaves_a_reactors_recycle_gas_loop_alone() -> None:
    view = next(v for v in map(_view22, SEEDS) if "recycle_gas_block" in v.roles.values())
    assert _recycle_line_with(view, "recycle_gas_block")  # the loop is there, as a RECYCLE line
    assert _run("PLT-RECYCLE-CLOSURE", view).violations == ()


def test_api14c_a4_catches_a_vessel_whose_safety_valve_is_gone() -> None:
    """Draw every safety valve as a gate valve: each A.4 vessel then has none (T10 re-cite, R5)."""
    view = _view22(1)
    graph = view.graph.copy()
    for _, data in graph.nodes(data=True):
        if str(data["node_class"]).endswith("SafetyValve"):
            data["node_class"] = "GateValve"
    result = _run("API14C-A4-OVERPRESSURE", replace(view, graph=graph))
    assert result.violations
    assert all(v.rule_id == "API14C-A4-OVERPRESSURE" and v.detail for v in result.violations)
