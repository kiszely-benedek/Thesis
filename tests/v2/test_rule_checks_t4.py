"""The v2.2 min-flow rules of task T4: the hidden pump power band and what it decides.

Per rule (design 3.3): (a) no violation on a v2.2 plant, (b) a mutation is caught, (c) the check
looked at something over the five seeds, plus the version gate. The band is a declared parameter
kept in `HiddenDesignState`; it must never reach the DEXPI model or the graph under retrieval.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace

import pytest
from plant_invariants import plant_view, plant_view_v22

from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22, HandbookKnobs
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.hidden_state import HiddenDesignState, PumpPowerBand
from plantgraph.benchmark.v2.rules.catalogue import rule_by_id
from plantgraph.benchmark.v2.rules.registry import CheckResult, resolve_check
from plantgraph.benchmark.v2.rules.view import RuleView, build_rule_view
from plantgraph.benchmark.v2.trims_min_flow import CONTROL_VALVE_ROLE, SWITCH_VALVE_ROLE
from plantgraph.ingest.headline_v2 import HeadlinePresetV2, smallest_n_units_v2

SEEDS = [1, 2, 3, 4, 5]
_T4_RULES = ["TOG177-MINFLOW-NEED", "TOG313-MINFLOW-METHOD"]


def _units(seed: int) -> int:
    return smallest_n_units_v2(30, HeadlinePresetV2(), seed).n_units  # about 30 sheets


def _view22(seed: int) -> RuleView:
    return plant_view_v22(seed, _units(seed))


def _run(rule_id: str, view: RuleView) -> CheckResult:
    return resolve_check(rule_by_id(rule_id))(view)


def _band_counts() -> Counter[PumpPowerBand]:
    return Counter(b for seed in SEEDS for b in _view22(seed).hidden.pump_power.values())


# ---- (a) positive, (c) non-vacuity, version gate -------------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("rule_id", _T4_RULES)
def test_a_t4_rule_has_no_violation_on_a_v22_plant(rule_id: str, seed: int) -> None:
    assert _run(rule_id, _view22(seed)).violations == ()


@pytest.mark.parametrize("rule_id", _T4_RULES)
def test_a_t4_rule_checks_something_across_the_five_seeds(rule_id: str) -> None:
    assert sum(_run(rule_id, _view22(seed)).checked for seed in SEEDS) > 0


def test_every_power_band_is_drawn_at_least_once_across_the_five_seeds() -> None:
    assert set(_band_counts()) == set(PumpPowerBand)


@pytest.mark.parametrize("rule_id", _T4_RULES)
def test_a_t4_rule_does_not_apply_to_a_v21_plant(rule_id: str) -> None:
    assert _run(rule_id, plant_view(1, _units(1))) == CheckResult(checked=0)


def test_a_v22_plant_with_the_handbook_off_is_not_checked_and_has_no_hidden_band() -> None:
    config = GeneratorConfigV22(seed=1, n_units=6, handbook=HandbookKnobs.all_off())
    view = build_rule_view(generate_plant_v2(config))
    assert all(_run(rule_id, view).checked == 0 for rule_id in _T4_RULES)
    assert view.hidden.pump_power == {}


def test_a_v21_plant_has_an_empty_hidden_state() -> None:
    assert plant_view(1, _units(1)).hidden == HiddenDesignState()


def test_the_band_is_gold_only_and_never_reaches_the_graph_or_the_plan_dump() -> None:
    view = _view22(1)
    graph_text = str(sorted(map(str, view.graph.nodes(data=True))))
    assert "pump_power" not in graph_text and "5-20" not in graph_text
    assert "pump_power" not in view.plan.model_dump_json()


# ---- the generator follows the declared weights --------------------------------------------------


def test_a_band_with_a_larger_weight_is_drawn_more_often() -> None:
    heavy = {band: 1.0 for band in PumpPowerBand} | {PumpPowerBand.ABOVE_35: 50.0}
    config = GeneratorConfigV22(
        seed=1, n_units=_units(1), handbook=HandbookKnobs(pump_power_weights=heavy)
    )
    bands = Counter(build_rule_view(generate_plant_v2(config)).hidden.pump_power.values())
    assert bands.most_common(1)[0][0] is PumpPowerBand.ABOVE_35


# ---- (b) mutations -------------------------------------------------------------------------------


def _with_hidden(view: RuleView, hidden: HiddenDesignState) -> RuleView:
    record = view.generated.record.model_copy(update={"hidden_state": hidden})
    return replace(view, generated=replace(view.generated, record=record))


def _redeclared(view: RuleView, drawn: PumpPowerBand, declared: PumpPowerBand) -> RuleView:
    """A view whose first pump of band `drawn` is declared to be of band `declared`."""
    pump = next(p for p, band in view.hidden.pump_power.items() if band is drawn)
    bands = {**view.hidden.pump_power, pump: declared}
    return _with_hidden(view, view.hidden.model_copy(update={"pump_power": bands}))


def _first_view_with(band: PumpPowerBand) -> RuleView:
    for seed in SEEDS:
        if band in _view22(seed).hidden.pump_power.values():
            return _view22(seed)
    raise AssertionError(f"no seed draws a pump of band {band}")


def _expect_violation(rule_id: str, view: RuleView) -> None:
    result = _run(rule_id, view)
    assert len(result.violations) >= 1
    violation = result.violations[0]
    assert violation.rule_id == rule_id and violation.node_id and violation.detail


_BELOW, _MID, _HIGH = PumpPowerBand.BELOW_5, PumpPowerBand.B5_20, PumpPowerBand.ABOVE_35


def test_need_catches_a_small_pump_that_has_a_spillback() -> None:
    view = _first_view_with(_MID)
    _expect_violation("TOG177-MINFLOW-NEED", _redeclared(view, _MID, _BELOW))


def test_need_catches_a_big_pump_without_a_spillback() -> None:
    view = _first_view_with(_BELOW)
    _expect_violation("TOG177-MINFLOW-NEED", _redeclared(view, _BELOW, _HIGH))


def test_need_reports_a_pump_with_no_recorded_band() -> None:
    view = _with_hidden(_view22(1), HiddenDesignState())
    result = _run("TOG177-MINFLOW-NEED", view)
    assert result.checked > 0 and len(result.violations) == result.checked


@pytest.mark.parametrize(
    ("drawn", "declared"),
    [
        (_MID, PumpPowerBand.B20_35),
        (PumpPowerBand.B20_35, _HIGH),
        (_HIGH, _MID),
        (_BELOW, _MID),
    ],
)
def test_method_catches_a_line_that_does_not_match_the_band(
    drawn: PumpPowerBand, declared: PumpPowerBand
) -> None:
    view = _first_view_with(drawn)
    _expect_violation("TOG313-MINFLOW-METHOD", _redeclared(view, drawn, declared))


@pytest.mark.parametrize("role", [SWITCH_VALVE_ROLE, CONTROL_VALVE_ROLE])
def test_method_catches_a_valve_whose_driving_loop_was_removed(role: str) -> None:
    """Cut the actuator behind the method's valve: the method is no longer shown."""
    band = PumpPowerBand.B20_35 if role == SWITCH_VALVE_ROLE else _HIGH
    view = _first_view_with(band)
    valve = next(n for n, r in view.roles.items() if r == role)
    graph = view.graph.copy()
    actuators = [s for s, _, d in graph.in_edges(valve, data=True) if d["relation"] == "control"]
    graph.remove_nodes_from(actuators)
    _expect_violation("TOG313-MINFLOW-METHOD", replace(view, graph=graph))
