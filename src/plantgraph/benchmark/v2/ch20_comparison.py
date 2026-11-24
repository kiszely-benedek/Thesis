"""The Toghraei ch.20 values beside the v2.2 values of one or more runs (descriptive, no verdict).

    python -m plantgraph.benchmark.v2.ch20_comparison RUN.json [RUN.json ...]
        [--json PATH] [--md PATH]

Each `RUN.json` is a `KindReport` written by `composition --by-kind --kind-json`. The table prints
as Markdown; `--json` writes the same rows as data. The ch.20 numbers are in `toghraei_ch20.py`.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.v2 import toghraei_ch20 as ch20
from plantgraph.benchmark.v2.connector_kinds import SheetKind
from plantgraph.benchmark.v2.kind_report import KindReport, KindSummary

Value = int | float | str | None


class ComparisonRow(BaseModel):
    """One measure: the ch.20 value and the value of each run (None where it does not exist)."""

    model_config = ConfigDict(frozen=True)

    measure: str
    ch20: Value
    runs: dict[str, Value]  # run label -> value


def _of_kind(
    kind: SheetKind, pick: Callable[[KindSummary], Value]
) -> Callable[[KindReport], Value]:
    """A getter that reads `pick` from the summary of `kind`, or None when the run has none."""

    def get(report: KindReport) -> Value:
        summary = report.summary_of(kind)
        return None if summary is None else pick(summary)

    return get


def _distribution(summary: KindSummary) -> str:
    return ", ".join(f"{n}: {c}" for n, c in summary.equipment_distribution.items())


def _share_of(code: str) -> Callable[[KindSummary], Value]:
    return lambda summary: summary.share_by_code[code]


def _spec(report: KindReport) -> list[tuple[str, Value, Value]]:
    """`(measure, ch20 value, this run's value)` for every row of the table."""
    process = _of_kind(SheetKind.PROCESS, lambda s: s.sheets)(report)
    p = ch20.PROCESS_CONNECTORS_BY_CODE
    total = sum(p.values())
    rows: list[tuple[str, Value, Value]] = [
        ("Sheets", ch20.SHEETS, report.sheets),
        (
            "Network + interarea share of all sheets",
            ch20.NETWORK_AND_INTERAREA_SHEETS / ch20.SHEETS,
            report.share_network_and_interarea,
        ),
        (
            "Share of all sheets without equipment (ch.20 includes 3 auxiliary sheets)",
            ch20.SHEETS_WITHOUT_EQUIPMENT / ch20.SHEETS,
            report.share_without_equipment,
        ),
        ("Process sheets", ch20.PROCESS_SHEETS, process),
        (
            "Process: equipment per sheet, mean",
            ch20.PROCESS_EQUIPMENT_MEAN,
            _of_kind(SheetKind.PROCESS, lambda s: s.equipment_mean)(report),
        ),
        (
            "Process: equipment per sheet, median",
            ch20.PROCESS_EQUIPMENT_MEDIAN,
            _of_kind(SheetKind.PROCESS, lambda s: s.equipment_median)(report),
        ),
        (
            "Process: equipment per sheet, max",
            ch20.PROCESS_EQUIPMENT_MAX,
            _of_kind(SheetKind.PROCESS, lambda s: s.equipment_max)(report),
        ),
        (
            "Process: equipment distribution (items: sheets)",
            ", ".join(f"{n}: {c}" for n, c in ch20.PROCESS_EQUIPMENT_DISTRIBUTION.items()),
            _of_kind(SheetKind.PROCESS, _distribution)(report),
        ),
        (
            "Process: connectors per sheet, mean",
            ch20.PROCESS_CONNECTORS_MEAN,
            _of_kind(SheetKind.PROCESS, lambda s: s.connectors_mean)(report),
        ),
        (
            "Process: connectors per sheet, median",
            ch20.PROCESS_CONNECTORS_MEDIAN,
            _of_kind(SheetKind.PROCESS, lambda s: s.connectors_median)(report),
        ),
        (
            "Process: connectors per sheet, max",
            ch20.PROCESS_CONNECTORS_MAX,
            _of_kind(SheetKind.PROCESS, lambda s: s.connectors_max)(report),
        ),
    ]
    for code in p:
        rows.append(
            (
                f"Process: share of connectors coded {code}",
                p[code] / total,
                _of_kind(SheetKind.PROCESS, _share_of(code))(report),
            )
        )
    rows += [
        (
            "Process: share of sheets with at least one N connector",
            ch20.PROCESS_SHEETS_WITH_N / ch20.PROCESS_SHEETS,
            _of_kind(SheetKind.PROCESS, lambda s: s.share_with_network_connector)(report),
        ),
        (
            "Network sheets",
            ch20.NETWORK_SHEETS,
            _of_kind(SheetKind.NETWORK, lambda s: s.sheets)(report),
        ),
        (
            "Network: connectors per sheet, mean",
            ch20.NETWORK_CONNECTORS_MEAN,
            _of_kind(SheetKind.NETWORK, lambda s: s.connectors_mean)(report),
        ),
        (
            "Network: connectors per sheet, median",
            ch20.NETWORK_CONNECTORS_MEDIAN,
            _of_kind(SheetKind.NETWORK, lambda s: s.connectors_median)(report),
        ),
        (
            "Network: connectors per sheet, max",
            ch20.NETWORK_CONNECTORS_MAX,
            _of_kind(SheetKind.NETWORK, lambda s: s.connectors_max)(report),
        ),
        (
            "Interarea sheets",
            ch20.INTERAREA_SHEETS,
            _of_kind(SheetKind.INTERAREA, lambda s: s.sheets)(report),
        ),
        (
            "Interarea: connectors per sheet, mean",
            ch20.INTERAREA_CONNECTORS_MEAN,
            _of_kind(SheetKind.INTERAREA, lambda s: s.connectors_mean)(report),
        ),
        (
            "Interarea: connectors per sheet, max",
            ch20.INTERAREA_CONNECTORS_MAX,
            _of_kind(SheetKind.INTERAREA, lambda s: s.connectors_max)(report),
        ),
    ]
    return rows


def compare(reports: Sequence[KindReport]) -> list[ComparisonRow]:
    """The table rows: ch.20 first, then one value per run.

    Raises:
        ValueError: if there is no run, or two runs share a label.
    """
    if not reports:
        raise ValueError("expected at least one run to compare, got none")
    labels = [r.label for r in reports]
    if len(set(labels)) != len(labels):
        raise ValueError(f"expected distinct run labels, got {labels}")
    per_run = [_spec(report) for report in reports]
    return [
        ComparisonRow(
            measure=measure,
            ch20=value,
            runs={r.label: spec[i][2] for r, spec in zip(reports, per_run, strict=True)},
        )
        for i, (measure, value, _) in enumerate(per_run[0])
    ]


def _cell(value: Value) -> str:
    if value is None:
        return "–"
    if isinstance(value, str | int):  # counts print whole
        return str(value)
    return f"{value:.3f}" if abs(value) < 1.0 and value != 0 else f"{value:.2f}"


def render_markdown(rows: Sequence[ComparisonRow]) -> str:
    """The comparison as a Markdown table."""
    labels = list(rows[0].runs)
    head = ["Measure", "Toghraei ch.20", *[f"v2.2: {label}" for label in labels]]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for row in rows:
        cells = [row.measure, _cell(row.ch20), *[_cell(row.runs[label]) for label in labels]]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append(f"\nch.20 source: `{ch20.NOTE_PATH}` (hand counts, 35 textbook sheets).")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Read the run reports, print the Markdown table, optionally write it and the JSON rows."""
    parser = argparse.ArgumentParser(prog="python -m plantgraph.benchmark.v2.ch20_comparison")
    parser.add_argument("runs", type=Path, nargs="+", help="KindReport JSON files")
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--md", type=Path, default=None)
    args = parser.parse_args(argv)
    reports = [KindReport.model_validate_json(p.read_text(encoding="utf-8")) for p in args.runs]
    rows = compare(reports)
    markdown = render_markdown(rows)
    print(markdown)
    if args.md is not None:
        args.md.write_text(markdown + "\n", encoding="utf-8")
    if args.json is not None:
        payload = {"source": ch20.NOTE_PATH, "rows": [r.model_dump(mode="json") for r in rows]}
        args.json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
