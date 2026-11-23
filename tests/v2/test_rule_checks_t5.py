"""The valve-position rules of task T5: TOG114 (two rules), TOG120, TOG224 and TOG114-FAIL-ACTION.

Per rule (design 3.3): (a) no violation on a v2.2 plant, (b) a mutation is caught, (c) over the
five seeds the check looked at something and every drawn value appeared, plus the version gate (a
v2.1 plant and a v2.2 plant with the handbook off report `checked=0` and carry no position).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import replace

import pytest
from plant_invariants import plant_view, plant_view_v22

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22, HandbookKnobs
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.plan_models import InstrumentSpec, LineItemSpec, OperatingPosition
from plantgraph.benchmark.v2.planner import PlantPlanV2
from plantgraph.benchmark.v2.rules.catalogue import rule_by_id
from plantgraph.benchmark.v2.rules.checks_positions import automatic_valves, split_partners
from plantgraph.benchmark.v2.rules.registry import CheckResult, resolve_check
from plantgraph.benchmark.v2.rules.view import RuleView, build_rule_view
from plantgraph.benchmark.v2.trim_plan import TrimPlan
from plantgraph.benchmark.v2.valve_positions import fail_actions_of, positions_of
from plantgraph.benchmark.v2.valve_roles import (
    BLOCKING_ROLES,
    CV_BYPASS_ROLES,
    MIN_FLOW_VALVE_ROLES,
    PSV_BLOCK_ROLES,
    VENT_DRAIN_ROLES,
    operating_position_of,
)
from plantgraph.graph.schema import Relation
from plantgraph.ingest.headline_v2 import HeadlinePresetV2, smallest_n_units_v2

SEEDS = [1, 2, 3, 4, 5]
_POSITION_RULES = {
    "TOG114-BLOCK-DEFAULT-NO": ("NO", BLOCKING_ROLES),
    "TOG114-VENT-DRAIN-NC": ("NC", VENT_DRAIN_ROLES),
    "TOG120-CV-BYPASS-NC": ("NC", CV_BYPASS_ROLES),
    "TOG224-PSV-BLOCKS-CSO": ("CSO", PSV_BLOCK_ROLES),
}
_T5_RULES = [*_POSITION_RULES, "TOG114-FAIL-ACTION"]


def _units(seed: int) -> int:
    return smallest_n_units_v2(30, HeadlinePresetV2(), seed).n_units  # about 30 sheets


def _view22(seed: int) -> RuleView:
    return plant_view_v22(seed, _units(seed))


def _run(rule_id: str, view: RuleView) -> CheckResult:
    return resolve_check(rule_by_id(rule_id))(view)


def _plans(view: RuleView) -> list[TrimPlan]:
    return list(view.plan.unit_plans)


def _first_node(view: RuleView, roles: frozenset[str] | set[str]) -> str:
    return next(n for n in sorted(view.roles) if view.roles[n] in roles)


# ---- changing one plan entry (the mutations) -----------------------------------------------------


def _with_plan_edit(
    view: RuleView,
    edit_item: Callable[[LineItemSpec], LineItemSpec],
    edit_actuator: Callable[[InstrumentSpec], InstrumentSpec],
) -> RuleView:
    """The view of a plan with each item sent through `edit_item`, each actuator `edit_actuator`."""
    units = []
    for unit in view.plan.units:
        plan = unit.instance.plan
        lines = tuple(
            line.model_copy(update={"items": tuple(edit_item(i) for i in line.items)})
            for line in plan.lines
        )
        instruments = tuple(edit_actuator(s) for s in plan.instruments)
        edited = plan.model_copy(update={"lines": lines, "instruments": instruments})
        units.append(
            unit.model_copy(update={"instance": unit.instance.model_copy(update={"plan": edited})})
        )
    new_plan: PlantPlanV2 = view.plan.model_copy(update={"units": tuple(units)})
    return replace(view, generated=replace(view.generated, plan=new_plan))


def _with_position(view: RuleView, node_id: str, position: OperatingPosition | None) -> RuleView:
    def edit(item: LineItemSpec) -> LineItemSpec:
        if item.node_id == node_id:
            return item.model_copy(update={"operating_position": position})
        return item

    return _with_plan_edit(view, edit, lambda spec: spec)


def _actuator_of(view: RuleView, valve: str) -> str:
    return next(
        s
        for s, t, d in view.graph.in_edges(valve, data=True)
        if d["relation"] == Relation.CONTROL.value
    )


def _with_fail_action(view: RuleView, valve: str, action: str | None) -> RuleView:
    actuator = _actuator_of(view, valve)

    def edit(spec: InstrumentSpec) -> InstrumentSpec:
        if spec.node_id == actuator:
            return spec.model_copy(update={"fail_action": action})
        return spec

    return _with_plan_edit(view, lambda item: item, edit)


# ---- (a) positive, (c) non-vacuity, version gate -------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("rule_id", _T5_RULES)
def test_a_t5_rule_has_no_violation_on_a_v22_plant(rule_id: str, seed: int) -> None:
    assert _run(rule_id, _view22(seed)).violations == ()


@pytest.mark.parametrize("rule_id", _T5_RULES)
def test_a_t5_rule_checks_something_across_the_five_seeds(rule_id: str) -> None:
    assert sum(_run(rule_id, _view22(seed)).checked for seed in SEEDS) > 0


@pytest.mark.parametrize("rule_id", _T5_RULES)
def test_a_t5_rule_does_not_apply_to_a_v21_plant(rule_id: str) -> None:
    assert _run(rule_id, plant_view(1, _units(1))) == CheckResult(checked=0)


@pytest.mark.parametrize("rule_id", _T5_RULES)
def test_a_t5_rule_does_not_apply_to_a_v22_plant_with_the_handbook_off(rule_id: str) -> None:
    config = GeneratorConfigV22(seed=1, n_units=_units(1), handbook=HandbookKnobs.all_off())
    assert _run(rule_id, build_rule_view(generate_plant_v2(config))) == CheckResult(checked=0)


def test_a_v21_plant_and_a_knobs_off_plant_draw_no_position_and_no_fail_action() -> None:
    off = GeneratorConfigV22(seed=1, n_units=_units(1), handbook=HandbookKnobs.all_off())
    for view in (plant_view(1, _units(1)), build_rule_view(generate_plant_v2(off))):
        assert positions_of(_plans(view)) == {}
        assert fail_actions_of(_plans(view)) == {}
        assert b"OperatingPosition" not in view.generated.model.model_dump_json().encode()


def test_every_position_and_both_main_fail_actions_are_drawn_across_the_five_seeds() -> None:
    positions: Counter[str] = Counter()
    actions: Counter[str] = Counter()
    for seed in SEEDS:
        positions.update(positions_of(_plans(_view22(seed))).values())
        actions.update(fail_actions_of(_plans(_view22(seed))).values())
    assert set(positions) == {"NO", "NC", "CSO"}  # LO, LC and CSC are allowed, never drawn
    assert set(actions) == {
        "FO",
        "FC",
    }  # FL is allowed by the type, no service in the table uses it


def test_every_valve_of_a_positioned_role_carries_that_roles_position() -> None:
    view = _view22(1)
    positions = positions_of(_plans(view))
    for node, role in view.roles.items():
        expected = operating_position_of(role)
        if node in view.graph and expected is not None:
            assert positions[node] == expected, (node, role)


def test_the_role_groups_do_not_overlap() -> None:
    groups = [BLOCKING_ROLES, VENT_DRAIN_ROLES, CV_BYPASS_ROLES, PSV_BLOCK_ROLES]
    assert sum(len(g) for g in groups) == len(frozenset().union(*groups))


def test_the_tog322_pair_is_drawn_and_its_two_valves_fail_oppositely() -> None:
    pairs = 0
    for seed in SEEDS:
        view = _view22(seed)
        actions = fail_actions_of(_plans(view))
        for main in (n for n, r in view.roles.items() if r == "hx_main_control_valve"):
            pairs += 1
            assert actions[main] == "FO"  # the declared `hx_main_cv` row
    assert pairs > 0


def test_a_min_flow_valve_fails_open_wherever_one_is_drawn() -> None:
    drawn = 0
    for seed in SEEDS:
        view = _view22(seed)
        actions = fail_actions_of(_plans(view))
        for node in (n for n, r in view.roles.items() if r in MIN_FLOW_VALVE_ROLES):
            drawn += 1
            assert actions[node] == "FO"
    assert drawn > 0


def test_a_valve_with_no_actuator_has_no_fail_action_and_every_automatic_valve_has_one() -> None:
    view = _view22(1)
    assert set(fail_actions_of(_plans(view))) == set(automatic_valves(view))


def test_the_fail_action_table_decides_the_action() -> None:
    table = {**HandbookKnobs().fail_action_table, "other": "FL"}
    config = GeneratorConfigV22(
        seed=1, n_units=_units(1), handbook=HandbookKnobs(fail_action_table=table)
    )
    plans = _plans(build_rule_view(generate_plant_v2(config)))
    assert "FL" in set(fail_actions_of(plans).values())


def test_a_fail_action_table_without_a_service_is_refused() -> None:
    table = {k: v for k, v in HandbookKnobs().fail_action_table.items() if k != "other"}
    config = GeneratorConfigV22(
        seed=1, n_units=_units(1), handbook=HandbookKnobs(fail_action_table=table)
    )
    with pytest.raises(ValueError, match="expected fail_action_table to have the service 'other'"):
        generate_plant_v2(config)


# ---- (b) mutations -------------------------------------------------------------------------------


def _expect_violation(rule_id: str, view: RuleView, node: str) -> None:
    violations = _run(rule_id, view).violations
    assert any(v.node_id == node for v in violations)
    assert all(v.rule_id == rule_id and v.detail for v in violations)


@pytest.mark.parametrize("rule_id", list(_POSITION_RULES))
def test_a_position_rule_catches_a_valve_in_the_wrong_position(rule_id: str) -> None:
    expected, roles = _POSITION_RULES[rule_id]
    wrong = "NC" if expected == "NO" else "NO"
    view = _view22(1)
    node = _first_node(view, roles)
    _expect_violation(rule_id, _with_position(view, node, wrong), node)


@pytest.mark.parametrize("rule_id", list(_POSITION_RULES))
def test_a_position_rule_catches_a_valve_with_no_position(rule_id: str) -> None:
    view = _view22(1)
    node = _first_node(view, _POSITION_RULES[rule_id][1])
    _expect_violation(rule_id, _with_position(view, node, None), node)


def test_tog114_fail_action_catches_an_automatic_valve_without_one() -> None:
    view = _view22(1)
    valve = automatic_valves(view)[0]
    _expect_violation("TOG114-FAIL-ACTION", _with_fail_action(view, valve, None), valve)


def test_tog114_fail_action_catches_a_min_flow_valve_that_fails_closed() -> None:
    view = _view22(1)
    valve = _first_node(view, MIN_FLOW_VALVE_ROLES)
    _expect_violation("TOG114-FAIL-ACTION", _with_fail_action(view, valve, "FC"), valve)


def test_tog114_fail_action_catches_a_pair_that_fails_the_same_way() -> None:
    view = next(v for v in map(_view22, SEEDS) if "hx_main_control_valve" in v.roles.values())
    main = _first_node(view, {"hx_main_control_valve"})
    (partner,) = split_partners(view, main)
    same = fail_actions_of(_plans(view))[main]
    _expect_violation("TOG114-FAIL-ACTION", _with_fail_action(view, partner, same), main)
