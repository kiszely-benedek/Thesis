"""The six sampled alternatives of task T11: TOG34, TOG173, TOG322, TOG214, TOG309, TOG122.

Per rule (design 3.3): (a) no violation on a v2.2 plant, (b) a mutation is caught, (c) the check
looked at something and both alternatives were drawn across the five seeds, plus the version gate
(a v2.1 plant and a v2.2 plant with the handbook off report `checked=0`).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import replace

import pytest
from plant_invariants import plant_view, plant_view_v22

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22, HandbookKnobs
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.hidden_state import RefluxClass
from plantgraph.benchmark.v2.rules.catalogue import rule_by_id
from plantgraph.benchmark.v2.rules.checks_alternatives import pv_stations_by_document
from plantgraph.benchmark.v2.rules.checks_exchangers import temperature_bypass_valves
from plantgraph.benchmark.v2.rules.checks_v21_plant import flow
from plantgraph.benchmark.v2.rules.registry import CheckResult, resolve_check
from plantgraph.benchmark.v2.rules.view import RuleView, build_rule_view
from plantgraph.benchmark.v2.trims_valves import FUEL_SWITCHING_ROLES, HX_MAIN_VALVE_ROLE
from plantgraph.ingest.headline_v2 import HeadlinePresetV2, smallest_n_units_v2

SEEDS = [1, 2, 3, 4, 5]
_REDUCER, _ENLARGER = "pump_suction_reducer", "pump_discharge_enlarger"
_T11_RULES = [
    "TOG34-BL-ISOLATION",
    "TOG173-PUMP-REDUCERS",
    "TOG322-HX-BYPASS-VARIANT",
    "TOG214-FUEL-SWITCHING-VALVES",
    "TOG309-SPLIT-PAIRING",
    "TOG122-PV-NO-BYPASS",
]


def _units(seed: int) -> int:
    return smallest_n_units_v2(30, HeadlinePresetV2(), seed).n_units  # about 30 sheets


def _view22(seed: int) -> RuleView:
    return plant_view_v22(seed, _units(seed))


def _run(rule_id: str, view: RuleView) -> CheckResult:
    return resolve_check(rule_by_id(rule_id))(view)


def _first_view(has: Callable[[RuleView], bool]) -> RuleView:
    """The first seed's v2.2 plant for which `has(view)` is true."""
    for seed in SEEDS:
        if has(_view22(seed)):
            return _view22(seed)
    raise AssertionError("no seed of 1-5 draws the arrangement this mutation test needs")


def _expect_violation(rule_id: str, view: RuleView) -> None:
    result = _run(rule_id, view)
    assert len(result.violations) >= 1
    violation = result.violations[0]
    assert violation.rule_id == rule_id and violation.node_id and violation.detail


def _without_nodes(view: RuleView, nodes: list[str]) -> RuleView:
    graph = view.graph.copy()
    graph.remove_nodes_from(nodes)
    return replace(view, graph=graph)


def _role_nodes(view: RuleView, role: str) -> list[str]:
    return sorted(n for n, r in view.roles.items() if r == role)


def _count(view: RuleView, role: str) -> int:
    return len(_role_nodes(view, role))


# ---- (a) positive, (c) non-vacuity, version gate -------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("rule_id", _T11_RULES)
def test_a_t11_rule_has_no_violation_on_a_v22_plant(rule_id: str, seed: int) -> None:
    assert _run(rule_id, _view22(seed)).violations == ()


@pytest.mark.parametrize("rule_id", _T11_RULES)
def test_a_t11_rule_checks_something_across_the_five_seeds(rule_id: str) -> None:
    assert sum(_run(rule_id, _view22(seed)).checked for seed in SEEDS) > 0


@pytest.mark.parametrize("rule_id", _T11_RULES)
def test_a_t11_rule_does_not_apply_to_a_v21_plant(rule_id: str) -> None:
    assert _run(rule_id, plant_view(1, _units(1))) == CheckResult(checked=0)


@pytest.mark.parametrize("rule_id", _T11_RULES)
def test_a_t11_rule_does_not_apply_to_a_v22_plant_with_the_handbook_off(rule_id: str) -> None:
    config = GeneratorConfigV22(seed=1, n_units=_units(1), handbook=HandbookKnobs.all_off())
    assert _run(rule_id, build_rule_view(generate_plant_v2(config))) == CheckResult(checked=0)


def test_a_v21_plant_has_none_of_the_t11_parts() -> None:
    roles = Counter(plant_view(1, _units(1)).roles.values())
    for role in (
        "battery_limit_check",
        "pump_suction_reducer",
        HX_MAIN_VALVE_ROLE,
        "fuel_second_switching_valve",
    ):
        assert roles[role] == 0, role


# ---- every alternative is drawn across the five seeds --------------------------------------------


def _blinds_by_arrangement() -> Counter[str]:
    found: Counter[str] = Counter()
    for seed in SEEDS:
        view = _view22(seed)
        blinds, blocks, checks = (_count(view, r) for r in (
            "battery_limit_blind", "battery_limit_block", "battery_limit_check"))  # fmt: skip
        found["blind only"] += blinds - blocks
        found["valve and blind"] += blocks - checks
        found["valve, blind and check"] += checks
    return found


def test_tog34_all_three_battery_limit_arrangements_are_drawn() -> None:
    assert all(n > 0 for n in _blinds_by_arrangement().values())
    assert len(_blinds_by_arrangement()) == 3


def test_tog173_pumps_are_drawn_with_and_without_reducers() -> None:
    with_reducers = sum(_count(_view22(s), "pump_suction_reducer") for s in SEEDS)
    all_pumps = sum(_run("TOG173-PUMP-REDUCERS", _view22(s)).checked for s in SEEDS)
    assert 0 < with_reducers < all_pumps


def test_tog322_a_bypass_is_drawn_alone_and_with_a_valve_on_the_exchanger_branch() -> None:
    mains = sum(_count(_view22(s), HX_MAIN_VALVE_ROLE) for s in SEEDS)
    bypasses = sum(_run("TOG322-HX-BYPASS-VARIANT", _view22(s)).checked for s in SEEDS)
    assert 0 < mains < bypasses


def test_tog214_a_furnace_is_drawn_with_one_and_with_two_switching_valves() -> None:
    second = sum(_count(_view22(s), FUEL_SWITCHING_ROLES[1]) for s in SEEDS)
    first = sum(_count(_view22(s), FUEL_SWITCHING_ROLES[0]) for s in SEEDS)
    assert 0 < second < first


def test_tog309_both_reflux_classes_are_drawn() -> None:
    classes = {c for seed in SEEDS for c in _view22(seed).hidden.reflux.values()}
    assert classes == set(RefluxClass)


def test_tog122_documents_are_drawn_with_and_without_a_pv_bypass() -> None:
    flags: set[bool] = set()
    for seed in SEEDS:
        for split in pv_stations_by_document(_view22(seed)).values():
            flags |= {has for has, bodies in split.items() if bodies}
    assert flags == {True, False}


@pytest.mark.parametrize("p_no_bypass", [0.0, 1.0])
def test_tog122_the_declared_probability_forces_the_alternative(p_no_bypass: float) -> None:
    knobs = HandbookKnobs(p_pv_no_bypass_document=p_no_bypass)
    config = GeneratorConfigV22(seed=1, n_units=_units(1), handbook=knobs)
    stations = pv_stations_by_document(build_rule_view(generate_plant_v2(config)))
    drawn_with = sum(len(split[True]) for split in stations.values())
    drawn_without = sum(len(split[False]) for split in stations.values())
    assert drawn_with + drawn_without > 0
    assert (drawn_without == 0) if p_no_bypass == 0.0 else (drawn_with == 0)


def test_the_hidden_reflux_class_follows_its_declared_weight() -> None:
    weights = {RefluxClass.LOW: 1.0, RefluxClass.HIGH: 1e-9}
    config = GeneratorConfigV22(
        seed=1, n_units=_units(1), handbook=HandbookKnobs(reflux_class_weights=weights)
    )
    view = build_rule_view(generate_plant_v2(config))
    assert set(view.hidden.reflux.values()) == {RefluxClass.LOW}
    assert _run("TOG309-SPLIT-PAIRING", view).violations == ()


def test_the_reflux_class_never_reaches_the_graph_or_the_plan_dump() -> None:
    view = _view22(1)
    assert "reflux_class" not in str(sorted(map(str, view.graph.nodes(data=True))))
    assert '"reflux":' not in view.plan.model_dump_json()  # the plan's hidden-state field


# ---- (b) mutations -------------------------------------------------------------------------------


def test_tog34_catches_a_check_valve_without_an_isolation_valve() -> None:
    view = _first_view(lambda v: _count(v, "battery_limit_check") > 0)
    check = _role_nodes(view, "battery_limit_check")[0]
    (block,) = [
        p for p in view.graph.predecessors(check) if view.roles.get(p) == "battery_limit_block"
    ]
    _expect_violation("TOG34-BL-ISOLATION", _without_nodes(view, [block]))


def test_tog173_catches_a_reducer_without_its_enlarger() -> None:
    view = _first_view(lambda v: _count(v, "pump_discharge_enlarger") > 0)
    _expect_violation(
        "TOG173-PUMP-REDUCERS",
        _without_nodes(view, _role_nodes(view, "pump_discharge_enlarger")[:1]),
    )


def _pump_with_reducers_in_a_spare_set(view: RuleView) -> str | None:
    """A pump of a spare set (two or more machines) that has nozzle reducers."""
    for record in view.generated.record.spare_sets:
        for pump in record.node_ids:
            before = [p for p in view.graph.predecessors(pump) if view.roles.get(p) == _REDUCER]
            if before:
                return pump
    return None


def test_tog173_catches_a_spare_set_whose_pumps_differ() -> None:
    view = _first_view(lambda v: _pump_with_reducers_in_a_spare_set(v) is not None)
    pump = _pump_with_reducers_in_a_spare_set(view)
    assert pump is not None
    parts = [*view.graph.predecessors(pump), *view.graph.successors(pump)]
    reducers = [n for n in parts if view.roles.get(n) in (_REDUCER, _ENLARGER)]
    _expect_violation("TOG173-PUMP-REDUCERS", _without_nodes(view, reducers))  # one pump bare


def test_tog122_catches_a_document_with_a_bypassed_and_an_unbypassed_station() -> None:
    def two_bypassed_in_a_document(view: RuleView) -> bool:
        return any(len(split[True]) >= 2 for split in pv_stations_by_document(view).values())

    view = _first_view(two_bypassed_in_a_document)
    train = next(t for t, split in pv_stations_by_document(view).items() if len(split[True]) >= 2)
    body = pv_stations_by_document(view)[train][True][0]
    tee_in = _upstream_role(view, body, "cv_tee_in")
    roles = {**view.roles, tee_in: "not_a_station_tee"}
    _expect_violation("TOG122-PV-NO-BYPASS", replace(view, roles=roles))


def _upstream_role(view: RuleView, node: str, role: str) -> str:
    """Walk against the flow from `node` to the first part with `role`."""
    piping = flow(view.graph)
    while view.roles.get(node) != role:
        (node,) = piping.predecessors(node)
    return node


def test_tog214_catches_a_switching_valve_without_an_actuator() -> None:
    view = _first_view(lambda v: _count(v, FUEL_SWITCHING_ROLES[0]) > 0)
    valve = _role_nodes(view, FUEL_SWITCHING_ROLES[0])[0]
    actuators = [
        s for s, _, d in view.graph.in_edges(valve, data=True) if d["relation"] == "control"
    ]
    _expect_violation("TOG214-FUEL-SWITCHING-VALVES", _without_nodes(view, actuators))


def test_tog214_catches_a_furnace_with_no_switching_valve() -> None:
    view = _first_view(lambda v: _count(v, FUEL_SWITCHING_ROLES[0]) > 0)
    roles = {n: r for n, r in view.roles.items() if r not in FUEL_SWITCHING_ROLES}
    _expect_violation("TOG214-FUEL-SWITCHING-VALVES", replace(view, roles=roles))


def test_tog322_catches_a_main_branch_valve_whose_bypass_valve_has_no_loop() -> None:
    view = _first_view(lambda v: _count(v, HX_MAIN_VALVE_ROLE) > 0)
    paired = _run("TOG322-HX-BYPASS-VARIANT", view)
    assert paired.violations == () and paired.checked >= 2
    actuators = [  # every bypass valve loses its actuator, so the main valve has no partner
        s
        for valve in temperature_bypass_valves(view)
        for s, _, d in view.graph.in_edges(valve, data=True)
        if d["relation"] == "control"
    ]
    _expect_violation("TOG322-HX-BYPASS-VARIANT", _without_nodes(view, actuators))


def test_tog309_catches_a_column_whose_declared_class_does_not_match_its_drawing() -> None:
    view = _first_view(lambda v: RefluxClass.HIGH in v.hidden.reflux.values())
    column = next(c for c, k in view.hidden.reflux.items() if k is RefluxClass.HIGH)
    hidden = view.hidden.model_copy(
        update={"reflux": {**view.hidden.reflux, column: RefluxClass.LOW}}
    )
    record = view.generated.record.model_copy(update={"hidden_state": hidden})
    _expect_violation(
        "TOG309-SPLIT-PAIRING", replace(view, generated=replace(view.generated, record=record))
    )


def test_tog309_reports_a_column_with_no_recorded_class() -> None:
    view = _view22(1)
    record = view.generated.record.model_copy(
        update={"hidden_state": view.hidden.model_copy(update={"reflux": {}})}
    )
    result = _run(
        "TOG309-SPLIT-PAIRING", replace(view, generated=replace(view.generated, record=record))
    )
    assert result.checked > 0 and len(result.violations) == result.checked
