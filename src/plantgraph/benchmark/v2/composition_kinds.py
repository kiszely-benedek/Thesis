"""The sheets of a v2.2 plant by kind: process, network (header) and interarea (design 6.6, 7).

The composition bands (ADR-0059) are judged on process sheets only: a network sheet holds pipes,
not equipment, so "equipment per sheet" would fail on it by design. These numbers are reported
beside the bands, with no verdict.
"""

from __future__ import annotations

from collections.abc import Sequence

from plantgraph.benchmark.v2.network_models import is_network_unit_no
from plantgraph.benchmark.v2.planner import PlantPlanV2
from plantgraph.benchmark.v2.sheet_stats import SheetStats, spread


def is_process_sheet(sheet_group: str) -> bool:
    """True for a sheet of a process unit (`3:1`); network and interarea units start at 9000."""
    return not is_network_unit_no(int(sheet_group.partition(":")[0]))


def kind_values(plan: PlantPlanV2, stats: Sequence[SheetStats]) -> list[tuple[str, float]]:
    """`(quantity, value)`: sheets by kind, and the tie-ins and connectors of a network sheet.

    Empty for a plant without network units (v2.1).
    """
    if not plan.network_units:
        return []
    network = [s for s in stats if not is_process_sheet(s.sheet_group)]
    interarea = sum(n.sheets.sheet_count for n in plan.network_units if n.is_interarea)
    tie_ins = [_tie_ins_of(plan, s.sheet_group) for s in network]
    stubs = spread([s.stubs for s in network])
    return [
        ("sheets: process", float(plan.process_sheet_count)),
        ("sheets: network (headers)", float(len(network) - interarea)),
        ("sheets: interarea", float(interarea)),
        ("sheets: network and interarea (share of all)", len(network) / plan.sheet_count),
        ("tie-ins per network sheet, mean", sum(tie_ins) / len(tie_ins)),
        ("tie-ins per network sheet, max", float(max(tie_ins))),
        ("connectors per network sheet, mean", stubs.mean),
        ("connectors per network sheet, max", float(stubs.high)),
    ]


def _tie_ins_of(plan: PlantPlanV2, sheet_group: str) -> int:
    """The tees of the header on this network sheet (one per tie-in); 0 on an interarea sheet."""
    return sum(
        1
        for unit in plan.network_units
        for node, role in unit.plan.roles.items()
        if role == "header_tee" and unit.sheets.sheet_of[node] == sheet_group
    )
