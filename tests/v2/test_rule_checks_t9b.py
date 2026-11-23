"""Task T9b: the narrowed and restated plant checks, the U7 flow indicator, build-time verification.

Counts quoted here were measured on seeds 1-5 (30-sheet plants) when the task landed; they pin the
behaviour, so a change that moves one is a decision to review, not noise.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
import t9b_mutations
from t9_mutations import Broken
from t9_support import SEEDS, units_for_30_sheets, view_v21, view_v22

from plantgraph.benchmark.split_models import SplitConfig
from plantgraph.benchmark.v2.config import GeneratorConfigV2
from plantgraph.benchmark.v2.config_v22 import GeneratorConfigV22
from plantgraph.benchmark.v2.generate import generate_plant_v2
from plantgraph.benchmark.v2.rules import owed
from plantgraph.benchmark.v2.rules.catalogue import rule_by_id
from plantgraph.benchmark.v2.rules.control_graph import split_valves
from plantgraph.benchmark.v2.rules.registry import CheckResult, resolve_check
from plantgraph.benchmark.v2.rules.verify import RuleViolationError, verify_plant
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.benchmark.v2.trims_valves import HX_MAIN_VALVE_ROLE
from plantgraph.ingest.__main__ import _write_result
from plantgraph.ingest.pipeline import run_synthetic


def _run(rule_id: str, view: RuleView) -> CheckResult:
    return resolve_check(rule_by_id(rule_id))(view)


# ---- TOG271: split valves, and the U7 flow indicator ---------------------------------------------


@pytest.mark.parametrize("seed", SEEDS)
def test_every_main_branch_valve_of_a_tog322_pair_is_a_split_valve(seed: int) -> None:
    view = view_v22(seed)
    mains = {n for n, role in view.roles.items() if role == HX_MAIN_VALVE_ROLE}
    assert mains <= split_valves(view)


def test_the_check_reports_how_often_it_left_a_split_valve_out() -> None:
    counts = [_run("TOG271-ONE-CV-LIQUID", view_v22(seed)).exceptions for seed in SEEDS]
    assert all(c.get("split_valve", 0) > 0 for c in counts)


def test_v21_plants_keep_the_filter_package_flow_valve_and_so_the_t9_counts() -> None:
    """v2.1 data is never changed: the narrowed check still finds the U7 pairs (1, 0, 1, 2, 0)."""
    found = [len(_run("TOG271-ONE-CV-LIQUID", view_v21(seed)).violations) for seed in SEEDS]
    assert found == [1, 0, 1, 2, 0]


def _filter_package_tags(view: RuleView) -> list[tuple[str, set[str]]]:
    """(variant label, tags of every node of the unit) for each U7 unit."""
    found = []
    for unit in view.plan.units:
        if unit.instance.pattern == "U7":
            unit_id = str(unit.slot.unit_no)
            nodes = view.graph.nodes(data=True)
            tags = {str(d.get("tag", "")) for _, d in nodes if d["unit_id"] == unit_id}
            found.append((unit.instance.variant, tags))
    return found


def test_a_v22_filter_package_has_a_flow_indicator_never_a_flow_valve() -> None:
    drawn = 0
    for seed in SEEDS:
        for variant, tags in _filter_package_tags(view_v22(seed)):
            assert not any(t.startswith(("FV-", "FIC-")) for t in tags), variant
            drawn += "flow_loop=True" in variant and any(t.startswith("FI-") for t in tags)
    assert drawn > 0


# ---- TOG295: derived exceptions ------------------------------------------------------------------


def test_the_inventory_check_counts_the_optional_pressure_loops() -> None:
    kinds = {c for s in SEEDS for c in _run("TOG295-INVENTORY-ONCE", view_v22(s)).exceptions}
    assert "pressure_optional" in kinds and "storage_tank_batch" in kinds


@pytest.mark.parametrize("break_it", t9b_mutations.ALL, ids=lambda f: f.__name__)
def test_the_inventory_check_catches_the_t9b_breaks(break_it: Callable[[RuleView], Broken]) -> None:
    view = view_v22(1)
    before = {v.node_id for v in _run("TOG295-INVENTORY-ONCE", view).violations}
    broken, node = break_it(view)
    after = {v.node_id for v in _run("TOG295-INVENTORY-ONCE", broken).violations}
    assert node in after - before


# ---- PLT-STREAM-CLOSURE on the joined graph ------------------------------------------------------


def test_the_closure_check_finds_the_58_ends_left_after_the_plant_boundary_closes() -> None:
    """127 after T9c (28, 26, 27, 22, 24), minus the 69 boundary ends T7a closes (design 17.4).

    The 58 left are relief outlets and fuel-gas bleeds; T7 closes them: update this when it lands.
    """
    found = [len(_run("PLT-STREAM-CLOSURE", view_v22(seed)).violations) for seed in SEEDS]
    assert found == [10, 13, 12, 9, 14]


def test_a_relief_outlet_is_an_open_end_the_closure_check_reports() -> None:
    details = [v.detail for v in _run("PLT-STREAM-CLOSURE", view_v22(1)).violations]
    assert any("psv_outlet_block" in d for d in details)


# ---- TOG207: process side only -------------------------------------------------------------------


def test_utility_side_blocks_are_counted_not_failed() -> None:
    results = [_run("TOG207-HX-NO-ISOLATION", view_v22(seed)) for seed in SEEDS]
    assert all(r.violations == () for r in results)
    assert sum(r.exceptions.get("utility_side_block", 0) for r in results) > 0


# ---- API14C-A8 -----------------------------------------------------------------------------------


@pytest.mark.parametrize("rule_id", ["API14C-A8-FSV", "API14C-A8-PSV"])
def test_every_compressor_has_its_discharge_check_valve_and_safety_valve(rule_id: str) -> None:
    results = [_run(rule_id, view_v22(seed)) for seed in SEEDS]
    assert all(r.violations == () for r in results)
    assert sum(r.checked for r in results) > 0


# ---- build-time verification, the owed list, rules.json ------------------------------------------


def _config_with_open_ends() -> GeneratorConfigV22:
    """A plant that still has relief outlets open: after T7a a 6-unit plant has none."""
    return GeneratorConfigV22(seed=1, n_units=units_for_30_sheets(1))


def test_the_only_owed_fix_is_the_closure_rule_and_it_is_not_raised() -> None:
    assert owed.OWED_FIXES == {"PLT-STREAM-CLOSURE": "T7"}
    report = generate_plant_v2(_config_with_open_ends()).rules
    assert report is not None
    rows = {row.rule_id: row for row in report.rows}
    assert rows["PLT-STREAM-CLOSURE"].violations > 0
    assert rows["PLT-STREAM-CLOSURE"].owed_by == "T7"
    assert all(row.owed_by is None for row in report.rows if row.violations == 0)


def test_generation_raises_once_the_owed_rule_is_no_longer_owed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(owed, "OWED_FIXES", {})
    with pytest.raises(RuleViolationError, match="PLT-STREAM-CLOSURE"):
        generate_plant_v2(_config_with_open_ends())


def test_the_generated_report_equals_the_one_verify_plant_gives() -> None:
    generated = generate_plant_v2(GeneratorConfigV22(seed=1, n_units=6))
    assert generated.rules == verify_plant(generated)


def test_a_v21_plant_is_not_verified_at_generation() -> None:
    assert generate_plant_v2(GeneratorConfigV2(seed=1, n_units=6)).rules is None


def test_ingest_out_writes_rules_json_for_a_v22_corpus(tmp_path: Path) -> None:
    result = run_synthetic(
        corpus_id="t9b",
        generator_config=GeneratorConfigV22(seed=1, n_units=6),
        split_config=SplitConfig(sheet_equipment_budget=3, seed=0),
        check=False,
        settings=None,
    )
    _write_result(result, tmp_path)
    rows = json.loads((tmp_path / "rules.json").read_text(encoding="utf-8"))["rows"]
    assert {row["rule_id"] for row in rows} >= {"TOG271-ONE-CV-LIQUID", "PLT-STREAM-CLOSURE"}
    assert "rules" not in json.loads((tmp_path / "ingest.json").read_text(encoding="utf-8"))
