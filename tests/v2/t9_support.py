"""Shared facts of the task-T9 rule checks: the plants they run on and where they are known to fail.

Not a test module (no `test_` prefix). The T9 checks look at every plant, v2.1 and v2.2 alike, so
unlike the T3/T4 checks they do not report `checked=0` on v2.1. Four of the ten fail on plants the
generator draws today. Design rule for T9: a check never changes the generator to make itself
pass; the failure is recorded here (rule, version, seeds, one example) and the test is an
expected failure until the architect decides on a fix. `KNOWN_FAILURES` is that record.
"""

from __future__ import annotations

from plant_invariants import plant_view, plant_view_v22

from plantgraph.benchmark.v2.rules.registry import RuleReport
from plantgraph.benchmark.v2.rules.view import RuleView
from plantgraph.ingest.headline_v2 import HeadlinePresetV2, smallest_n_units_v2

SEEDS = [1, 2, 3, 4, 5]
T9_RULES = [
    "TOG271-ONE-CV-LIQUID",
    "TOG267-FE-UPSTREAM-FV",
    "TOG295-INVENTORY-ONCE",
    "TOG270-PUMP-FLOW-CONTROLLED",
    "TOG320-HX-NONTARGET",
    "TOG224-PSV-PIPE-CLEAN",
    "TOG24-NO-VISITING-STREAM",
    "PLT-STREAM-CLOSURE",
    "TOG207-HX-NO-ISOLATION",
    "TOG326-STEAM-CONDENSATE",
]

#: rule -> (seeds that fail, on v2.1 and on v2.2 alike; why and one example). Counts per seed are in
#: the report; the examples are node ids of the 30-sheet plant of that seed on v2.2.
KNOWN_FAILURES: dict[str, tuple[list[int], str]] = {
    "TOG271-ONE-CV-LIQUID": (
        SEEDS,
        "two control valves in series between two vessels: seed 1 u13-t28 (FV, transfer line) "
        "then u15-t16 (TV, process bypass of the next unit), route u13-t1 to u15-t5",
    ),
    "TOG295-INVENTORY-ONCE": (
        [2, 3, 4],
        "seed 2: additive tank u2-t2 has a level transmitter but no level loop and is no "
        "tank-farm tank; blend vessel u11-t3 has gas outlets but no pressure loop",
    ),
    "PLT-STREAM-CLOSURE": (
        SEEDS,
        "process lines end open at a plain pipe part, no declared end: seed 1 line "
        "6-P-20002-A1A-N ends at tee u2-t6 (34 to 41 such open ends per plant)",
    ),
    "TOG207-HX-NO-ISOLATION": (
        SEEDS,
        "block valve on a utility nozzle (utility_supply_block): seed 1 condenser u4-t30 "
        "with valve u4-t31; seed 5 compressor_discharge_block in front of aftercooler u10-t3",
    ),
}


def units_for_30_sheets(seed: int) -> int:
    """The unit count that gives a plant of about 30 sheets for this seed."""
    return smallest_n_units_v2(30, HeadlinePresetV2(), seed).n_units


def view_v21(seed: int) -> RuleView:
    """The v2.1 plant of this seed, about 30 sheets."""
    return plant_view(seed, units_for_30_sheets(seed))


def view_v22(seed: int) -> RuleView:
    """The v2.2 plant (handbook on) of this seed, about 30 sheets."""
    return plant_view_v22(seed, units_for_30_sheets(seed))


def without_known_failures(report: RuleReport) -> RuleReport:
    """The report minus the `KNOWN_FAILURES` rules, so tests of the others can insist on none."""
    rows = tuple(row for row in report.rows if row.rule_id not in KNOWN_FAILURES)
    return RuleReport(generator_version=report.generator_version, rows=rows)
