"""Class coverage: the 77 generated classes, the grounding table, and the counts in plants."""

from __future__ import annotations

from collections import Counter
from functools import cache

import pytest
from composition_fixture import hand_plan

from plantgraph.benchmark.v2.config import GENERATED_EQUIPMENT_CLASSES
from plantgraph.benchmark.v2.coverage import (
    GENERATED_CLASSES,
    IMPORT_ONLY_CLASSES,
    CoverageReport,
    coverage_report,
    grounding_of,
    render_coverage,
)
from plantgraph.benchmark.v2.planner import PlantPlanV2, plan_plant
from plantgraph.graph import schema
from plantgraph.ingest.headline_v2 import HeadlinePresetV2, smallest_n_units_v2


@cache
def _plan(target_sheets: int, seed: int) -> PlantPlanV2:
    preset = HeadlinePresetV2()
    return plan_plant(
        preset.generator_config(smallest_n_units_v2(target_sheets, preset, seed).n_units, seed)
    )


# ---- the class table -----------------------------------------------------------------------------


def test_the_generator_draws_77_classes_and_the_import_only_ones_are_the_rest() -> None:
    assert len(GENERATED_CLASSES) == 77
    assert not GENERATED_CLASSES & IMPORT_ONLY_CLASSES
    assert GENERATED_CLASSES | IMPORT_ONLY_CLASSES == schema.GENERATOR_CLASSES


def test_the_77_are_23_equipment_49_piping_and_5_instrumentation_classes() -> None:
    assert GENERATED_CLASSES & schema.EQUIPMENT_CLASSES == GENERATED_EQUIPMENT_CLASSES
    assert len(GENERATED_CLASSES & schema.PIPING_CLASSES) == 49  # 47 leaves + CheckValve + break
    assert len(GENERATED_CLASSES - schema.EQUIPMENT_CLASSES - schema.PIPING_CLASSES) == 5


def test_every_generated_class_has_one_grounding_letter_and_the_counts_match_the_design() -> None:
    letters = Counter(grounding_of(node_class) for node_class in GENERATED_CLASSES)
    assert letters == {"A": 53, "S": 7, "L": 7, "U": 10}


def test_a_few_classes_carry_the_letter_the_design_gives_them() -> None:
    assert grounding_of("CentrifugalPump") == "A"
    assert grounding_of("AirEjector") == "S"  # shown on WTP H2
    assert grounding_of("EjectorPump") == "L"  # a legend symbol only
    assert grounding_of("RotaryMixer") == "U"  # declared, no source


# ---- counting ------------------------------------------------------------------------------------


def test_the_fixture_plan_has_the_counts_and_patterns_worked_out_by_hand() -> None:
    report = coverage_report(hand_plan())
    rows = {row.node_class: row for row in report.rows}
    assert len(rows) == 77  # every generated class has a row, present or not
    assert (rows["GateValve"].count, rows["Tank"].count, rows["CentrifugalPump"].count) == (4, 3, 2)
    assert rows["Tank"].patterns == ("U4", "U6")  # unit 1 is a U4, unit 2 a U6 in the fixture
    assert rows["ProcessSignalGeneratingFunction"].count == 3  # lt, ft, lt2
    present = {name for name, row in rows.items() if row.count}
    assert len(present) == 13
    assert report.absent == tuple(sorted(GENERATED_CLASSES - present))


def test_the_rows_are_sorted_rarest_first_and_absent_classes_come_first() -> None:
    counts = [row.count for row in coverage_report(hand_plan()).rows]
    assert counts == sorted(counts) and counts[0] == 0


def test_a_class_outside_the_77_is_an_error() -> None:
    plan = hand_plan()
    unit = plan.units[0]
    first, *rest = unit.instance.plan.equipment
    changed_plan = unit.instance.plan.model_copy(
        update={"equipment": (first.model_copy(update={"node_class": "Pump"}), *rest)}
    )
    changed_unit = unit.model_copy(
        update={"instance": unit.instance.model_copy(update={"plan": changed_plan})}
    )
    bad = plan.model_copy(update={"units": (changed_unit, *plan.units[1:])})
    with pytest.raises(ValueError, match=r"generated classes, found \['Pump'\]"):
        coverage_report(bad)


def test_the_rendering_names_the_absent_classes_and_the_rarest_present_ones() -> None:
    text = render_coverage(coverage_report(hand_plan()), rarest=3)
    assert "13 / 77 generated classes present" in text
    assert "EjectorPump" in text  # absent, so listed by name
    assert text.count("[A]") <= 3  # only the three rarest present classes are shown


# ---- measured on real plants ---------------------------------------------------------------------


def test_every_one_of_the_77_classes_appears_at_d1000g2() -> None:
    """The acceptance of design 14.6: zero absent at about 1,000 sheets (plan level, seed 1)."""
    report: CoverageReport = coverage_report(_plan(1000, 1))
    assert report.absent == ()
    assert min(row.count for row in report.rows) > 0


def test_at_d100g2_seed_1_two_classes_are_absent_and_the_report_names_them() -> None:
    """Pinned from the design's measurement (14.6): a smaller plant need not draw every class."""
    assert coverage_report(_plan(100, 1)).absent == ("CentrifugalCompressor", "EjectorPump")
