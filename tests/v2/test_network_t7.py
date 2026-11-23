"""Task T7: network and interarea sheets, and the five rules that check them.

Per rule (design 3.3): (a) no violation on the v2.2 plants of seeds 1-5, (b) a mutation of one
graph edge, one role or one level is caught, (c) the check looked at something, plus the version
gate (v2.1 and a knobs-off v2.2 plant have no network unit). The plants are the 30-sheet plants of
`t9_support`; a mutation edits a copy of the oracle graph, the plant is never regenerated.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

import pytest
from t9_support import SEEDS, view_v21, view_v22

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22, HandbookKnobs
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.hidden_state import PressureLevel
from plantgraph.benchmark.v2.network_models import NETWORK_UNIT_BASE, network_unit_no
from plantgraph.benchmark.v2.planner import plan_plant
from plantgraph.benchmark.v2.rules.catalogue import rule_by_id
from plantgraph.benchmark.v2.rules.checks_overpressure import check_merge_check
from plantgraph.benchmark.v2.rules.registry import CheckResult, resolve_check
from plantgraph.benchmark.v2.rules.verify import verify_plant
from plantgraph.benchmark.v2.rules.view import RuleView, build_rule_view
from plantgraph.ingest.headline_v2 import smallest_n_units_v2
from plantgraph.ingest.headline_v22 import HeadlinePresetV22

_RULES = [
    "TOG32-NETWORK-SHEETS",
    "TOG141-DRAIN-DESTINATION",
    "TOG360-UTILITY-NETWORKS",
    "TOG33-INTERAREA",
    "PLT-NETWORK-CLOSURE",
]


def _run(rule_id: str, view: RuleView) -> CheckResult:
    return resolve_check(rule_by_id(rule_id))(view)


def _without_nodes(view: RuleView, nodes: set[str]) -> RuleView:
    """The view with these nodes cut out of the oracle graph (the plan is untouched)."""
    graph = view.graph.copy()
    graph.remove_nodes_from(nodes)
    return replace(view, graph=graph)


def _header_tees(view: RuleView, service: str) -> set[str]:
    return {
        n
        for unit in view.plan.network_units
        if unit.service == service
        for n, role in unit.plan.roles.items()
        if role == "header_tee"
    }


# ---- (a) positive and (c) non-vacuity -------------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("rule_id", _RULES)
def test_a_network_rule_has_no_violation_on_a_v22_plant(rule_id: str, seed: int) -> None:
    assert _run(rule_id, view_v22(seed)).violations == ()


@pytest.mark.parametrize("rule_id", _RULES)
def test_a_network_rule_looks_at_something_on_every_plant(rule_id: str) -> None:
    assert all(_run(rule_id, view_v22(seed)).checked > 0 for seed in SEEDS)


@pytest.mark.parametrize("seed", SEEDS)
def test_the_whole_report_is_clean_and_nothing_is_owed(seed: int) -> None:
    report = verify_plant(view_v22(seed).generated)
    assert all(row.violations == 0 and row.owed_by is None for row in report.rows)
    assert {row.rule_id for row in report.rows} >= set(_RULES)


@pytest.mark.parametrize("seed", SEEDS)
def test_every_network_service_and_the_interarea_sheet_appear_on_some_plant(seed: int) -> None:
    services = Counter(unit.service for unit in view_v22(seed).plan.network_units)
    assert {"FL", "CHD", "INTERAREA"} <= set(services)
    assert sum(services.values()) > 8  # several (train, service) units, not one


# ---- structure: unit numbers, capacity, one connector per service per sheet -----------------


@pytest.mark.parametrize("seed", SEEDS)
def test_network_unit_numbers_come_from_the_reserved_block_and_are_unique(seed: int) -> None:
    plan = view_v22(seed).plan
    numbers = [unit.unit_no for unit in plan.network_units]
    assert len(numbers) == len(set(numbers))
    assert all(n >= NETWORK_UNIT_BASE for n in numbers)
    assert all(unit.slot.unit_no < NETWORK_UNIT_BASE for unit in plan.units)
    for unit in plan.network_units:
        assert unit.unit_no == network_unit_no(unit.train_no, unit.service)


@pytest.mark.parametrize("seed", SEEDS)
def test_a_network_sheet_holds_at_most_16_tie_ins(seed: int) -> None:
    tees = Counter(
        unit.sheets.sheet_of[node]
        for unit in view_v22(seed).plan.network_units
        for node, role in unit.plan.roles.items()
        if role == "header_tee"
    )
    assert tees and max(tees.values()) <= 16


def test_a_full_header_continues_on_the_next_sheet_and_still_closes() -> None:
    """Capacity 2 forces overflow on a small plant: more sheets per unit, same rules clean."""
    knobs = HandbookKnobs(max_tie_ins_per_network_sheet=2)
    plan = plan_plant(GeneratorConfigV22(seed=2, n_units=12, handbook=knobs))
    assert any(unit.sheets.sheet_count > 1 for unit in plan.network_units)
    view = build_rule_view(
        generate_plant_v2(GeneratorConfigV22(seed=2, n_units=12, handbook=knobs))
    )
    assert _run("PLT-NETWORK-CLOSURE", view).violations == ()
    sheet_of = view.plan.sheet_of
    continuation = [
        (u, v)
        for u, v in view.piping.edges
        if u in sheet_of
        and v in sheet_of
        and sheet_of[u] != sheet_of[v]
        and sheet_of[u].split(":")[0] == sheet_of[v].split(":")[0]
        and int(sheet_of[u].split(":")[0]) >= NETWORK_UNIT_BASE
    ]
    assert continuation  # the header goes on across sheets of one unit: a continuation connector


@pytest.mark.parametrize("seed", SEEDS)
def test_a_process_sheet_has_one_connector_per_network_service(seed: int) -> None:
    view = view_v22(seed)
    sheet_of = view.plan.sheet_of
    service_of = {
        n: u.service
        for u in view.plan.network_units
        if not u.is_interarea
        for n in u.sheets.sheet_of
    }
    crossings = Counter(
        (sheet_of[outside], service_of[inside])
        for u, v in view.piping.edges
        for inside, outside in ((u, v), (v, u))
        if inside in service_of and outside not in service_of
    )
    assert crossings and max(crossings.values()) == 1


@pytest.mark.parametrize("seed", SEEDS)
def test_every_part_of_a_network_unit_is_on_a_sheet_of_that_unit(seed: int) -> None:
    for unit in view_v22(seed).plan.network_units:
        assert all(s.startswith(f"{unit.unit_no}:") for s in unit.sheets.sheet_of.values())
        in_plan = {i.node_id for line in unit.plan.lines for i in line.items}
        assert in_plan == set(unit.sheets.sheet_of)


# ---- the sheets count toward the target -----------------------------------------------------


def test_the_size_search_counts_network_and_interarea_sheets() -> None:
    preset = HeadlinePresetV22()
    found = smallest_n_units_v2(40, preset, 3)
    plan = plan_plant(preset.generator_config(found.n_units, 3))
    assert plan.sheet_count == found.predicted_sheets >= 40
    assert plan.sheet_count > plan.process_sheet_count  # the network sheets are in the count
    fewer = plan_plant(preset.generator_config(found.n_units - 1, 3))
    assert fewer.sheet_count == found.predicted_sheets_one_unit_fewer < 40


# ---- (b) mutations --------------------------------------------------------------------------


def test_tog32_catches_a_relief_outlet_cut_off_from_the_flare_header() -> None:
    view = view_v22(1)
    cut = _without_nodes(view, _header_tees(view, "FL"))
    assert _run("TOG32-NETWORK-SHEETS", cut).violations


def test_tog141_catches_a_hydrocarbon_drain_that_misses_the_closed_drain() -> None:
    view = view_v22(1)
    cut = _without_nodes(view, _header_tees(view, "CHD"))
    assert _run("TOG141-DRAIN-DESTINATION", cut).violations


def test_tog141_catches_a_water_drain_piped_to_the_closed_drain() -> None:
    view = view_v22(1)
    drain = next(n for n in sorted(view.roles) if view.roles[n] == "pump_drain_valve")
    (before,) = view.piping.predecessors(drain)
    graph = view.graph.copy()
    graph.edges[before, drain]["fluid_code"] = "CWS"  # the same pipe, now carrying water
    assert _run("TOG141-DRAIN-DESTINATION", replace(view, graph=graph)).violations


def test_tog141_lets_a_vacuum_drain_keep_its_cap_and_counts_it() -> None:
    results = [_run("TOG141-DRAIN-DESTINATION", view_v22(seed)) for seed in SEEDS]
    assert sum(r.exceptions.get("vacuum_drain", 0) for r in results) >= 1


def test_tog360_catches_a_utility_stub_with_no_header() -> None:
    view = view_v22(1)
    cut = _without_nodes(view, _header_tees(view, "CWS") | _header_tees(view, "LPS"))
    assert _run("TOG360-UTILITY-NETWORKS", cut).violations


def test_tog33_catches_a_direct_pipe_between_two_trains() -> None:
    view = view_v22(1)
    first = next(u for u in view.plan.units if u.slot.train_no == 1)
    last = next(u for u in view.plan.units if u.slot.train_no == 2)
    a = next(iter(first.sheets.sheet_of))
    b = next(iter(last.sheets.sheet_of))
    graph = view.graph.copy()
    graph.add_edge(a, b, relation="send_to", line_number="4-P-10001-A1A-N", fluid_code="P")
    assert _run("TOG33-INTERAREA", replace(view, graph=graph)).violations


def test_network_closure_catches_a_second_connector_to_one_network() -> None:
    view = view_v22(1)
    unit = next(u for u in view.plan.network_units if u.service == "FL")
    tee, feeder = next(
        (n, p)
        for n, r in unit.plan.roles.items()
        if r == "header_tee"
        for p in view.piping.predecessors(n)
        if p not in unit.sheets.sheet_of
    )
    process_sheet = view.plan.sheet_of[feeder]
    other = next(
        n for n, s in view.plan.sheet_of.items()
        if s == process_sheet and n != feeder and n not in unit.sheets.sheet_of
    )  # fmt: skip
    graph = view.graph.copy()
    graph.add_edge(other, tee, relation="send_to", line_number="4-FL-10001-A1A-N", fluid_code="FL")
    assert _run("PLT-NETWORK-CLOSURE", replace(view, graph=graph)).violations


def test_network_closure_catches_a_header_that_ends_without_a_battery_limit() -> None:
    view = view_v22(1)
    plain = {n: ("plain" if "battery_limit" in r else r) for n, r in view.roles.items()}
    assert _run("PLT-NETWORK-CLOSURE", replace(view, roles=plain)).violations


def test_stream_closure_is_zero_and_a_removed_tie_in_reopens_an_end() -> None:
    from plantgraph.benchmark.v2.rules.checks_closure import check_stream_closure

    view = view_v22(2)
    assert check_stream_closure(view).violations == ()
    cut = _without_nodes(view, _header_tees(view, "FL"))
    assert check_stream_closure(cut).violations  # the PSV outlets stop in mid-air again


# ---- TOG156 narrowed to process lines (design 17.13 R2) -------------------------------------


def _merge_tees(view: RuleView) -> list[str]:
    piping = view.piping
    return [n for n in piping if piping.in_degree(n) >= 2 and piping.out_degree(n) == 1]


def test_tog156_leaves_the_network_tees_alone() -> None:
    """The sub-header and header tees of FL, CHD and utilities are merges, and are out of scope."""
    view = view_v22(1)
    network_tees = {
        n for n, r in view.roles.items() if r in ("sub_header_tee", "header_tee")
    } & set(_merge_tees(view))
    assert network_tees
    result = check_merge_check(view)
    assert result.violations == ()
    assert result.checked < len(_merge_tees(view))  # the network merges are not counted


def _with_levels(view: RuleView, edit: dict[str, PressureLevel]) -> RuleView:
    levels = {**view.hidden.segment_level, **edit}
    state = view.hidden.model_copy(update={"segment_level": levels})
    record = view.generated.record.model_copy(update={"hidden_state": state})
    return replace(view, generated=replace(view.generated, record=record))


def _first_with_role(role: str) -> tuple[RuleView, str]:
    for seed in SEEDS:
        view = view_v22(seed)
        for node in sorted(view.roles):
            if view.roles[node] == role:
                return view, node
    raise AssertionError(f"no plant of seeds {SEEDS} has a part with role {role!r}")


def _lower_process_streams(view: RuleView) -> list[tuple[str, str]]:
    """(tee, source) of every process stream that arrives below the level its merge tee carries."""
    found = []
    for tee in _merge_tees(view):
        (after,) = view.piping.successors(tee)
        if _service_of(view, tee, after) not in ("P", "PG"):
            continue
        carried = view.hidden.segment_level[str(view.graph.edges[tee, after]["line_number"])]
        for source in view.piping.predecessors(tee):
            line = str(view.graph.edges[source, tee]["line_number"])
            if view.hidden.segment_level[line] < carried:
                found.append((tee, source))
    return found


def _service_of(view: RuleView, upstream: str, downstream: str) -> str:
    return str(view.graph.edges[upstream, downstream]["fluid_code"])


def _check_valve_behind(view: RuleView, source: str) -> str | None:
    """The check valve on the single-file pipe before `source`, if there is one."""
    chain = [source]
    while len(before := list(view.piping.predecessors(chain[-1]))) == 1:
        chain.append(before[0])
    return next((n for n in chain if "CheckValve" in str(view.graph.nodes[n]["node_class"])), None)


def test_tog156_still_checks_a_process_merge_whose_lower_stream_has_no_check_valve() -> None:
    cases = [
        (view, tee, valve)
        for view in map(view_v22, SEEDS)
        for tee, source in _lower_process_streams(view)
        if (valve := _check_valve_behind(view, source))
    ]
    assert cases
    view, tee, valve = cases[0]
    graph = view.graph.copy()
    graph.nodes[valve]["node_class"] = "GateValve"
    flagged = check_merge_check(replace(view, graph=graph))
    assert any(v.node_id == tee for v in flagged.violations)


def test_tog156_counts_a_relief_path_instead_of_flagging_it() -> None:
    """A PD pump's relief return arrives low; a check valve there could block the relief."""
    view, relief = _first_with_role("pd_relief_valve")
    (tee,) = (n for n in view.piping.successors(relief) if view.roles.get(n) == "relief_return_tee")
    number = lambda a, b: str(view.graph.edges[a, b]["line_number"])  # noqa: E731
    low = _with_levels(view, {number(relief, tee): PressureLevel.VAC})
    result = check_merge_check(low)
    assert result.violations == ()
    assert result.exceptions.get("relief_path", 0) >= 1
    # the same stream, no longer a relief path (a plain valve, no relief role): it is flagged
    graph = low.graph.copy()
    graph.nodes[relief]["node_class"] = "GateValve"
    plain = replace(low, graph=graph, roles={**low.roles, relief: "plain_valve"})
    assert check_merge_check(plain).violations


# ---- version gates --------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [1, 3])
def test_a_v21_plant_has_no_network_unit_and_the_rules_do_not_apply(seed: int) -> None:
    view = view_v21(seed)
    assert view.plan.network_units == ()
    assert view.plan.sheet_count == view.plan.process_sheet_count
    assert "header_tee" not in view.roles.values()
    for rule_id in _RULES:
        assert _run(rule_id, view).checked == 0


def test_a_knobs_off_v22_plant_equals_the_v21_plant_and_has_no_network_unit() -> None:
    off = GeneratorConfigV22(seed=1, n_units=8, handbook=HandbookKnobs.all_off())
    plan = plan_plant(off)
    assert plan.network_units == ()
    v21 = plan_plant(off.v21_equivalent())
    assert plan.model_dump(mode="json", exclude={"config"}) == v21.model_dump(
        mode="json", exclude={"config"}
    )


def test_the_network_pass_only_adds_parts_or_drops_a_drain_cap() -> None:
    """Process ids and tags are untouched: a part is added, or a hydrocarbon drain loses its cap."""
    with_networks = plan_plant(GeneratorConfigV22(seed=1, n_units=10))
    off = HandbookKnobs(network_services=())
    without = plan_plant(GeneratorConfigV22(seed=1, n_units=10, handbook=off))
    assert without.network_units == () or all(
        u.service == "INTERAREA" for u in without.network_units
    )
    for a, b in zip(with_networks.units, without.units, strict=True):
        ids_a = {i.node_id for line in a.instance.plan.lines for i in line.items}
        ids_b = {i.node_id for line in b.instance.plan.lines for i in line.items}
        dropped = ids_b - ids_a
        assert all(b.instance.plan.roles[n].endswith(("_cap", "_open_drain")) for n in dropped)
        assert [e.node_id for e in a.instance.plan.equipment] == [
            e.node_id for e in b.instance.plan.equipment
        ]
