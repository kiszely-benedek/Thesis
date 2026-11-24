"""The composition of a plant by sheet kind: equipment and off-page connectors per sheet.

Descriptive only: no band, no verdict. A report covers one plant or several plants pooled: pooling
puts the sheets of every plant into one list, so a mean is a mean over sheets, not over plants.
The comparison with Toghraei's ch.20 sheets is `ch20_comparison.py`.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2.connector_kinds import (
    ConnectorCode,
    SheetConnectors,
    SheetKind,
    sheet_connectors,
)
from plantgraph.benchmark.v2.planner import PlantPlanV2
from plantgraph.benchmark.v2.sheet_stats import sheet_stats


class KindSummary(BaseModel):
    """The sheets of one kind: equipment and connectors per sheet, connectors by code."""

    model_config = ConfigDict(frozen=True)

    kind: SheetKind
    sheets: int
    equipment_mean: float
    equipment_median: float
    equipment_max: int
    equipment_distribution: dict[int, int]  # equipment count -> number of sheets
    connectors_mean: float
    connectors_median: float
    connectors_max: int
    total_by_code: dict[str, int]  # "P" -> connectors of that code over all sheets of the kind
    share_by_code: dict[str, float]
    mean_by_code: dict[str, float]  # per sheet
    share_without_equipment: float
    share_with_network_connector: float  # sheets with at least one N connector


class KindReport(BaseModel):
    """Every sheet kind of one run (a plant, or several pooled) under a label."""

    model_config = ConfigDict(frozen=True)

    label: str  # `100 sheets, seed 7`
    plants: int
    sheets: int
    summaries: tuple[KindSummary, ...]
    share_network_and_interarea: float
    share_without_equipment: float  # over all sheets of all kinds

    def summary_of(self, kind: SheetKind) -> KindSummary | None:
        """The summary of `kind`, or None when the run has no sheet of that kind."""
        return next((s for s in self.summaries if s.kind is kind), None)


def sheet_rows_of_plan(plan: PlantPlanV2) -> list[SheetConnectors]:
    """The per-sheet rows of one plan."""
    return sheet_connectors(plan, sheet_stats(plan))


def build_kind_report(label: str, plants: Sequence[Sequence[SheetConnectors]]) -> KindReport:
    """The report of the sheets of `plants` (one list of sheet rows per plant), pooled.

    Raises:
        ValueError: if there is no sheet at all.
    """
    rows = [row for plant in plants for row in plant]
    if not rows:
        raise ValueError(f"expected at least one sheet to report on {label!r}, got none")
    summaries = tuple(
        _summary_of(kind, [r for r in rows if r.kind is kind])
        for kind in SheetKind
        if any(r.kind is kind for r in rows)
    )
    drawn_by_network = sum(r.kind is not SheetKind.PROCESS for r in rows)
    return KindReport(
        label=label,
        plants=len(plants),
        sheets=len(rows),
        summaries=summaries,
        share_network_and_interarea=drawn_by_network / len(rows),
        share_without_equipment=sum(r.equipment == 0 for r in rows) / len(rows),
    )


def _summary_of(kind: SheetKind, rows: list[SheetConnectors]) -> KindSummary:
    equipment = [r.equipment for r in rows]
    connectors = [r.connectors for r in rows]
    by_code = {
        ConnectorCode.PROCESS.value: [r.process for r in rows],
        ConnectorCode.NETWORK.value: [r.network for r in rows],
        ConnectorCode.UTILITY.value: [r.utility for r in rows],
        ConnectorCode.SIGNAL.value: [r.signal for r in rows],
    }
    totals = {code: sum(values) for code, values in by_code.items()}
    grand_total = sum(totals.values())
    return KindSummary(
        kind=kind,
        sheets=len(rows),
        equipment_mean=statistics.fmean(equipment),
        equipment_median=statistics.median(equipment),
        equipment_max=max(equipment),
        equipment_distribution=dict(sorted(Counter(equipment).items())),
        connectors_mean=statistics.fmean(connectors),
        connectors_median=statistics.median(connectors),
        connectors_max=max(connectors),
        total_by_code=totals,
        share_by_code={c: (t / grand_total if grand_total else 0.0) for c, t in totals.items()},
        mean_by_code={c: statistics.fmean(v) for c, v in by_code.items()},
        share_without_equipment=sum(e == 0 for e in equipment) / len(rows),
        share_with_network_connector=sum(r.network > 0 for r in rows) / len(rows),
    )


def render_kind_report(report: KindReport) -> str:
    """The report as plain text, one block per sheet kind."""
    lines = [
        f"sheets by kind, {report.label}: {report.sheets} sheets, {report.plants} plant(s) pooled",
        f"  network + interarea share of all sheets   {report.share_network_and_interarea:.3f}",
        f"  sheets without equipment (all kinds)      {report.share_without_equipment:.3f}",
    ]
    for summary in report.summaries:
        lines += _render_summary(summary)
    return "\n".join(lines)


def print_kind_report(label: str, plans: Sequence[PlantPlanV2], json_path: Path | None) -> None:
    """Print the by-kind report of `plans` pooled; write it as JSON when `json_path` is given."""
    report = build_kind_report(label, [sheet_rows_of_plan(plan) for plan in plans])
    print("\n" + render_kind_report(report))
    if json_path is not None:
        text = json.dumps(report.model_dump(mode="json"), indent=2)
        json_path.write_text(text, encoding="utf-8")


def _render_summary(s: KindSummary) -> list[str]:
    codes = ", ".join(
        f"{code} {s.total_by_code[code]} "
        f"({s.share_by_code[code]:.1%}, {s.mean_by_code[code]:.2f}/sheet)"
        for code in s.total_by_code
    )
    distribution = ", ".join(f"{n}: {c}" for n, c in s.equipment_distribution.items())
    return [
        f"\n{s.kind.value} sheets: {s.sheets}",
        f"  equipment per sheet: mean {s.equipment_mean:.2f}, median {s.equipment_median:g}, "
        f"max {s.equipment_max}",
        f"  equipment distribution (items: sheets): {distribution}",
        f"  connectors per sheet: mean {s.connectors_mean:.2f}, median {s.connectors_median:g}, "
        f"max {s.connectors_max}",
        f"  connectors by code: {codes}",
        f"  share without equipment: {s.share_without_equipment:.3f}; "
        f"share with an N connector: {s.share_with_network_connector:.3f}",
    ]
