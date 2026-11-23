"""Shared facts of the task-T9 rule checks: the plants they run on and where they are known to fail.

Not a test module (no `test_` prefix). The T9 checks look at every plant, v2.1 and v2.2 alike, so
unlike the T3/T4 checks they do not report `checked=0` on v2.1. T9 recorded four failures here as
expected failures; T9b fixed or restated three of them, so what is left is the two v2.1
properties in `KNOWN_FAILURES_V21` (T7 closed the closure rule on v2.2).
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

#: v2.2 plants (handbook on): rule -> (seeds that fail, why). Empty since T7 tied the relief
#: outlets, bleeds and utility stubs into network headers (`rules/owed.py` is empty too).
KNOWN_FAILURES: dict[str, tuple[list[int], str]] = {}

#: v2.1 plants never get the handbook fixes (v2.1 data is not changed, design 14), so they keep
#: what T9 found: a filter package after a farm transfer puts two flow valves in series
KNOWN_FAILURES_V21: dict[str, tuple[list[int], str]] = {
    **KNOWN_FAILURES,
    "PLT-STREAM-CLOSURE": (
        SEEDS,
        "v2.1 plants keep their relief outlets and bleeds open: the network pass is v2.2 only",
    ),
    "TOG271-ONE-CV-LIQUID": (
        [1, 3, 4],
        "farm-transfer FV, then the optional FV of the filter package (v2.1 draws it), no vessel "
        "between them",
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


def without_known_failures(
    report: RuleReport, known: dict[str, tuple[list[int], str]] = KNOWN_FAILURES
) -> RuleReport:
    """The report minus the known-failure rules, so tests of the others can insist on none."""
    rows = tuple(row for row in report.rows if row.rule_id not in known)
    return RuleReport(generator_version=report.generator_version, rows=rows)
