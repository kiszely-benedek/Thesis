"""The v2.2 handbook-rule checks of task T3 on plants of seeds 1-5, and on plants broken on purpose.

Per rule (design 3.3): (a) no violation on a v2.2 plant, (b) a mutation is caught, (c) the check
looked at something over the five seeds. On a v2.1 plant (or with the handbook off) each check
reports `checked == 0`: the rules are v2.2 behaviours, and the v2.1 goldens stay pinned.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest
from plant_invariants import plant_view, plant_view_v22
from t9_support import without_known_failures

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22, HandbookKnobs
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.rules import checks_compressors, checks_pumps
from plantgraph.benchmark.v2.rules.catalogue import rule_by_id
from plantgraph.benchmark.v2.rules.checks_compressors import pd_stages
from plantgraph.benchmark.v2.rules.checks_v21_plant import flow, reach
from plantgraph.benchmark.v2.rules.registry import CheckResult, resolve_check
from plantgraph.benchmark.v2.rules.verify import raise_on_violations, verify_plant
from plantgraph.benchmark.v2.rules.view import RuleView, build_rule_view
from plantgraph.graph.schema import Relation
from plantgraph.ingest.headline_v2 import HeadlinePresetV2, smallest_n_units_v2

SEEDS = [1, 2, 3, 4, 5]
_T3_RULES = [
    "TOG192-RECIP-NO-CHECK",
    "TOG192-PD-NO-MINFLOW",
    "TOG177-MINFLOW-TAKEOFF",
    "TOG314-PD-NO-THROTTLE",
    "TOG319-ANTISURGE-DYNAMIC",
    "TOG316-PD-COMP-CAPACITY",
]
_PD_PUMPS = ("ReciprocatingPump", "RotaryPump")


def _units(seed: int) -> int:
    return smallest_n_units_v2(30, HeadlinePresetV2(), seed).n_units  # about 30 sheets


def _view22(seed: int) -> RuleView:
    return plant_view_v22(seed, _units(seed))


def _run(rule_id: str, view: RuleView) -> CheckResult:
    return resolve_check(rule_by_id(rule_id))(view)


# ---- (a) positive, (c) non-vacuity, version gate -------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("rule_id", _T3_RULES)
def test_a_t3_rule_has_no_violation_on_a_v22_plant(rule_id: str, seed: int) -> None:
    assert _run(rule_id, _view22(seed)).violations == ()


@pytest.mark.parametrize("rule_id", _T3_RULES)
def test_a_t3_rule_checks_something_across_the_five_seeds(rule_id: str) -> None:
    assert sum(_run(rule_id, _view22(seed)).checked for seed in SEEDS) > 0


@pytest.mark.parametrize("rule_id", _T3_RULES)
def test_a_t3_rule_does_not_apply_to_a_v21_plant(rule_id: str) -> None:
    view = plant_view(1, _units(1))
    assert _run(rule_id, view) == CheckResult(checked=0)


def test_a_v22_plant_with_the_handbook_off_is_not_checked_either() -> None:
    config = GeneratorConfigV22(seed=1, n_units=6, handbook=HandbookKnobs.all_off())
    view = build_rule_view(generate_plant_v2(config))
    assert all(_run(rule_id, view).checked == 0 for rule_id in _T3_RULES)


@pytest.mark.parametrize("seed", SEEDS)
def test_every_wired_rule_holds_on_a_v22_plant(seed: int) -> None:
    """Includes the version-aware S1-S3 behind TOG175-PUMP-TRIM and TOG219-PD-RELIEF."""
    # the T9 rules that fail on v2.2 plants are expected failures (test_rule_checks_t9.py)
    raise_on_violations(without_known_failures(verify_plant(_view22(seed).generated)))


def test_the_fixes_changed_the_plant_where_they_should() -> None:
    """The v2.2 plants really contain what each rule is about, not only the v2.1 shapes."""
    classes = {
        data["node_class"] for seed in SEEDS for _, data in _view22(seed).graph.nodes(data=True)
    }
    assert {"ReciprocatingPump", "RotaryPump"} <= classes
    assert {"ReciprocatingCompressor", "RotaryCompressor"} & classes


# ---- (b) mutations -------------------------------------------------------------------------------


def _with_role_of(view: RuleView, pump_classes: tuple[str, ...], role: str) -> tuple[str, str]:
    """(pump, node) of the first pump of `pump_classes` whose discharge has a node with `role`."""
    piping = flow(view.graph)
    for pump in checks_pumps.pumps_of_classes(view, pump_classes):
        parts = reach(piping, view.graph, pump, up=False)[0]
        found = checks_pumps.nodes_with_role(view, parts, [role])
        if found:
            return pump, found[0]
    raise AssertionError(f"no pump of {pump_classes} with a {role!r} found to break")


def _first_view(has: Callable[[RuleView], bool]) -> RuleView:
    for seed in SEEDS:
        if has(_view22(seed)):
            return _view22(seed)
    raise AssertionError("no seed has the part this mutation needs")


def _has_role_after(classes: tuple[str, ...], role: str) -> Callable[[RuleView], bool]:
    def has(view: RuleView) -> bool:
        try:
            _with_role_of(view, classes, role)
        except AssertionError:
            return False
        return True

    return has


def _insert_after(view: RuleView, node: str, new_id: str, node_class: str, tag: str) -> RuleView:
    """A copy of the view with a new valve on every pipe leaving `node`."""
    graph = view.graph.copy()
    pipes = [
        (t, d) for _, t, d in view.graph.out_edges(node, data=True)
        if d["relation"] == Relation.SEND_TO.value
    ]  # fmt: skip
    graph.add_node(
        new_id,
        node_class=node_class,
        tag=tag,
        unit_id=view.graph.nodes[node]["unit_id"],
        plant_id=view.graph.nodes[node]["plant_id"],
    )
    for target, data in pipes:
        graph.remove_edge(node, target)
        graph.add_edge(node, new_id, **data)
        graph.add_edge(new_id, target, **data)
    return replace(view, graph=graph)


def _mutate_recip_check(view: RuleView) -> RuleView:
    _, block = _with_role_of(view, ("ReciprocatingPump",), "discharge_block")
    return replace(view, roles={**view.roles, block: "discharge_check"})


def _mutate_pd_minflow(view: RuleView) -> RuleView:
    _, block = _with_role_of(view, _PD_PUMPS, "discharge_block")
    return replace(view, roles={**view.roles, block: "min_flow_tee"})


def _mutate_takeoff(view: RuleView) -> RuleView:
    """A new tee, marked as the min-flow take-off, between a check valve and what follows it."""
    _, check = _with_role_of(view, ("CentrifugalPump",), "discharge_check")
    mutated = _insert_after(view, check, "mutant-tee", "PipeTee", "")
    return replace(mutated, roles={**mutated.roles, "mutant-tee": "min_flow_tee"})


def _mutate_throttle(view: RuleView) -> RuleView:
    _, block = _with_role_of(view, _PD_PUMPS, "discharge_block")
    return _insert_after(view, block, "mutant-valve", "GlobeValve", "FV-99999")


def _a_pd_stage_valve(view: RuleView) -> tuple[str, str]:
    stage = pd_stages(view)[0]
    return stage.machine, stage.recycle_valves[0]


def _mutate_antisurge(view: RuleView) -> RuleView:
    """Turn a PD compressor's pressure recycle valve back into an anti-surge flow valve."""
    _, valve = _a_pd_stage_valve(view)
    graph = view.graph.copy()
    graph.nodes[valve]["tag"] = "FV-" + str(graph.nodes[valve]["tag"])[3:]
    return replace(view, graph=graph)


def _mutate_compressor_capacity(view: RuleView) -> RuleView:
    machine, _ = _a_pd_stage_valve(view)
    return _insert_after(view, machine, "mutant-valve", "GlobeValve", "PV-99999")


def _has_pd_stage(view: RuleView) -> bool:
    return bool(pd_stages(view))


_RECIP = _has_role_after(("ReciprocatingPump",), "discharge_block")
_PD = _has_role_after(_PD_PUMPS, "discharge_block")
_CENTRIFUGAL = _has_role_after(("CentrifugalPump",), "discharge_check")

#: rule id -> (the mutation, which plants it can be applied to)
_MUTATIONS: dict[str, tuple[Callable[[RuleView], RuleView], Callable[[RuleView], bool]]] = {
    "TOG192-RECIP-NO-CHECK": (_mutate_recip_check, _RECIP),
    "TOG192-PD-NO-MINFLOW": (_mutate_pd_minflow, _PD),
    "TOG177-MINFLOW-TAKEOFF": (_mutate_takeoff, _CENTRIFUGAL),
    "TOG314-PD-NO-THROTTLE": (_mutate_throttle, _PD),
    "TOG319-ANTISURGE-DYNAMIC": (_mutate_antisurge, _has_pd_stage),
    "TOG316-PD-COMP-CAPACITY": (_mutate_compressor_capacity, _has_pd_stage),
}


def test_every_t3_rule_has_a_mutation_test() -> None:
    assert sorted(_MUTATIONS) == sorted(_T3_RULES)


@pytest.mark.parametrize("rule_id", _T3_RULES)
def test_a_t3_rule_catches_a_plant_broken_on_purpose(rule_id: str) -> None:
    mutate, applicable = _MUTATIONS[rule_id]
    result = _run(rule_id, mutate(_first_view(applicable)))
    assert len(result.violations) >= 1
    violation = result.violations[0]
    assert violation.rule_id == rule_id and violation.node_id and violation.detail


# ---- the version-scoped S2 and S3 ---------------------------------------------------------------


def test_a_v22_reciprocating_pump_has_a_block_valve_but_no_external_check() -> None:
    view = _first_view(_has_role_after(("ReciprocatingPump",), "discharge_block"))
    pump, _ = _with_role_of(view, ("ReciprocatingPump",), "discharge_block")
    parts = reach(flow(view.graph), view.graph, pump, up=False)[0]
    assert not checks_pumps.nodes_with_role(view, parts, ["discharge_check"])


def test_v21_s2_still_demands_a_check_valve_on_every_pump() -> None:
    """The version scope must not loosen v2.1: remove a check from a v2.1 plant and S2 fails."""
    view = plant_view(1, _units(1))
    roles = {n: r for n, r in view.roles.items() if r != "discharge_check"}
    with pytest.raises(ValueError):  # S2 unpacks the single check: none found
        resolve_check(rule_by_id("TOG175-PUMP-TRIM"))(replace(view, roles=roles))


def test_the_compressor_module_is_imported_by_the_catalogue() -> None:
    assert checks_compressors.check_antisurge_dynamic is resolve_check(
        rule_by_id("TOG319-ANTISURGE-DYNAMIC")
    )
