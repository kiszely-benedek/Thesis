"""The sheets of a v2.2 plant by kind: process, network (header) and interarea (design 6.6, 7).

The composition bands (ADR-0059) are judged on process sheets only: a network sheet holds pipes,
not equipment, so "equipment per sheet" would fail on it by design. These numbers are reported
beside the bands, with no verdict.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from plantgraph.benchmark.v2.network_models import area_of_train, is_network_unit_no
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


def sheets_per_area(plan: PlantPlanV2, trains_per_area: int) -> dict[int, int]:
    """Area -> its sheets: the process sheets of its trains plus its header sheets.

    The plant interarea sheets belong to no area. The last area may hold fewer trains than the
    others, so its total is smaller; the choice of `trains_per_area` is made on the median.
    """
    totals: Counter[int] = Counter()
    for unit in plan.units:
        totals[area_of_train(unit.slot.train_no, trains_per_area)] += unit.sheets.sheet_count
    for network in plan.network_units:
        if not network.is_interarea:
            totals[network.area_no] += network.sheets.sheet_count
    return dict(sorted(totals.items()))


def _tie_ins_of(plan: PlantPlanV2, sheet_group: str) -> int:
    """The tees of the header on this network sheet (one per tie-in); 0 on an interarea sheet."""
    return sum(
        1
        for unit in plan.network_units
        for node, role in unit.plan.roles.items()
        if role == "header_tee" and unit.sheets.sheet_of[node] == sheet_group
    )
