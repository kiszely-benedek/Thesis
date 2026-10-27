"""The composition report of a v2 plant, and its command line (design realism 12.1, vocabulary 14).

A **P&ID sheet** is one drawing page; the report says whether the generated sheets look like real
ones: how many symbols (drawn shapes), valves, instruments and off-page stubs a sheet holds. Every
number is counted on the **plan** (`sheet_stats`), the one counting rule; `composition_corpus.py`
adds the checks that need the split sheet graphs. Each row is `(quantity, value, band, verdict)`.

    python -m plantgraph.benchmark.v2.composition --target-sheets 100 --seeds 1 2 3 [--corpus]
        [--coverage] [--json PATH]

Seeds 5000-5999 are test seeds and are refused unless `--allow-test-seed` is given: the tuning
instrument must never look at a test plant (design 14.5).
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from plantgraph.benchmark.generator_dispatch import generate_plant_graph_any
from plantgraph.benchmark.v2.composition_bands import (
    CORPUS_BANDS,
    PLAN_BANDS,
    Band,
    Verdict,
)
from plantgraph.benchmark.v2.composition_corpus import corpus_rows, split_sheets
from plantgraph.benchmark.v2.coverage import coverage_report, render_coverage
from plantgraph.benchmark.v2.planner import PlantPlanV2, plan_plant
from plantgraph.benchmark.v2.sheet_stats import SheetStats, share_at_most, sheet_stats, spread
from plantgraph.ingest.headline_v2 import (
    TEST_SEED_RANGE,
    HeadlinePresetV2,
    headline_corpus_id_v2,
    smallest_n_units_v2,
)

#: the symbol range of the real sheets the design measured (OPEN100, 40-134); a reported share
SYMBOL_RANGE = (40, 134)
_EQUIPMENT_SOFT_LIMIT = 10
_STUB_LIMIT = 21


class CompositionRow(BaseModel):
    """One statistic of the report: its value, the band it is judged against, and the verdict."""

    model_config = ConfigDict(frozen=True)

    quantity: str
    value: float
    band: str
    verdict: Verdict


class PatternRow(BaseModel):
    """The sheets of one pattern and layout: who sits outside the symbol and stub limits."""

    model_config = ConfigDict(frozen=True)

    label: str  # `U1 combined sheet 1/2`
    sheets: int
    symbols_mean: float
    symbols_low: int
    symbols_high: int
    stubs_mean: float
    stubs_high: int
    over_134_symbols: int
    under_40_symbols: int
    over_21_stubs: int

    @property
    def misses(self) -> bool:
        """True when any sheet of the group is outside 40-134 symbols or above 21 stubs."""
        return bool(self.over_134_symbols or self.under_40_symbols or self.over_21_stubs)


class CompositionReport(BaseModel):
    """The composition of one plant: plan rows, optional corpus rows, rows per pattern."""

    model_config = ConfigDict(frozen=True)

    corpus_id: str
    seed: int
    n_units: int
    n_sheets: int
    plan_rows: tuple[CompositionRow, ...]
    corpus_rows: tuple[CompositionRow, ...] = ()
    per_pattern: tuple[PatternRow, ...] = ()

    @property
    def failures(self) -> tuple[CompositionRow, ...]:
        """The rows whose verdict is `fail`."""
        rows = (*self.plan_rows, *self.corpus_rows)
        return tuple(row for row in rows if row.verdict is Verdict.FAIL)


def make_row(quantity: str, value: float, bands: dict[str, Band]) -> CompositionRow:
    """The row of `quantity`, judged against its band in `bands`."""
    band = bands[quantity]
    return CompositionRow(
        quantity=quantity, value=value, band=band.label, verdict=band.verdict(value)
    )


# ---- plan rows -----------------------------------------------------------------------------------


def plan_values(plan: PlantPlanV2, stats: Sequence[SheetStats]) -> list[tuple[str, float]]:
    """`(quantity, value)` of every plan row, counted per sheet by `sheet_stats`."""
    symbols = [s.symbols for s in stats]
    valves = spread([s.valves for s in stats])
    instruments = spread([s.instruments for s in stats])
    stubs = spread([s.stubs for s in stats])
    equipment = [s.equipment for s in stats]
    low, high = SYMBOL_RANGE
    inside = [low <= count <= high for count in symbols]
    return [
        ("symbols per sheet, mean", spread(symbols).mean),
        ("sheets with 40-134 symbols (share)", sum(inside) / len(inside)),
        ("valves per sheet, mean", valves.mean),
        ("instruments per sheet, mean", instruments.mean),
        ("instruments : valves", instruments.mean / valves.mean),
        ("off-page stubs per sheet, mean", stubs.mean),
        ("off-page stubs per sheet, max", float(stubs.high)),
        ("equipment per sheet, min", float(min(equipment))),
        ("equipment per sheet, max", float(max(equipment))),
        (
            "sheets with at most 10 equipment (share)",
            share_at_most(equipment, _EQUIPMENT_SOFT_LIMIT),
        ),
        ("equipment in A/B(/C) sets (share)", _spare_share(plan)),
        ("units drawn on 2 or more sheets (share)", _multi_sheet_share(plan)),
        ("signal cuts per sheet, mean", spread([s.signal_cuts for s in stats]).mean),
    ]


def _spare_share(plan: PlantPlanV2) -> float:
    """Equipment that belongs to a spare set, over all equipment of the plant."""
    plans = [unit.instance.plan for unit in plan.units]
    total = sum(len(p.equipment) for p in plans)
    spared = sum(len(members) for p in plans for members in p.spare_sets)
    return spared / total


def _multi_sheet_share(plan: PlantPlanV2) -> float:
    return sum(unit.sheets.sheet_count >= 2 for unit in plan.units) / len(plan.units)


# ---- per pattern ---------------------------------------------------------------------------------


def pattern_rows(plan: PlantPlanV2, stats: Sequence[SheetStats]) -> tuple[PatternRow, ...]:
    """One row per pattern, layout and sheet position (`U1 combined sheet 1/2`), sorted by label."""
    units = {unit.slot.unit_no: unit for unit in plan.units}
    groups: dict[str, list[SheetStats]] = {}
    for sheet in stats:
        unit_no, _, number = sheet.sheet_group.partition(":")
        unit = units[int(unit_no)]
        label = _sheet_label(
            unit.instance.pattern, unit.instance.variant, int(number), unit.sheets.sheet_count
        )
        groups.setdefault(label, []).append(sheet)
    return tuple(_pattern_row(label, group) for label, group in sorted(groups.items()))


def _sheet_label(pattern: str, variant: str, number: int, count: int) -> str:
    layout = re.search(r"layout=([a-z_]+)", variant)
    name = f"{pattern} {layout.group(1)}" if layout else pattern
    return f"{name} sheet {number}/{count}"


def _pattern_row(label: str, group: list[SheetStats]) -> PatternRow:
    low, high = SYMBOL_RANGE
    symbols = spread([s.symbols for s in group])
    stubs = spread([s.stubs for s in group])
    return PatternRow(
        label=label,
        sheets=len(group),
        symbols_mean=symbols.mean,
        symbols_low=symbols.low,
        symbols_high=symbols.high,
        stubs_mean=stubs.mean,
        stubs_high=stubs.high,
        over_134_symbols=sum(s.symbols > high for s in group),
        under_40_symbols=sum(s.symbols < low for s in group),
        over_21_stubs=sum(s.stubs > _STUB_LIMIT for s in group),
    )


# ---- the report ----------------------------------------------------------------------------------


def build_report(
    plan: PlantPlanV2,
    corpus_id: str,
    preset: HeadlinePresetV2 | None = None,
) -> CompositionReport:
    """The report of `plan`; pass a `preset` to add the corpus rows (builds the sheet graphs)."""
    stats = sheet_stats(plan)
    rows = tuple(make_row(name, value, PLAN_BANDS) for name, value in plan_values(plan, stats))
    extra = _corpus_report_rows(plan, stats, preset) if preset is not None else ()
    return CompositionReport(
        corpus_id=corpus_id,
        seed=plan.config.seed,
        n_units=plan.config.n_units,
        n_sheets=plan.sheet_count,
        plan_rows=rows,
        corpus_rows=extra,
        per_pattern=pattern_rows(plan, stats),
    )


def _corpus_report_rows(
    plan: PlantPlanV2, stats: Sequence[SheetStats], preset: HeadlinePresetV2
) -> tuple[CompositionRow, ...]:
    """Generate the plant once, split it at duplication 0 and at the preset's rate, compare."""
    seed = plan.config.seed
    plant = generate_plant_graph_any(plan.config)
    exact = split_sheets(plant, preset, seed, 0.0)
    at_preset = split_sheets(plant, preset, seed, preset.duplication_rate)
    values = corpus_rows(stats, exact, at_preset)
    return tuple(make_row(name, value, CORPUS_BANDS) for name, value in values)


def render_report(report: CompositionReport) -> str:
    """The report as a fixed-width text table."""
    lines = [
        f"{report.corpus_id}: seed {report.seed}, {report.n_units} units, {report.n_sheets} sheets",
        _table("plan (the counting rule)", report.plan_rows),
    ]
    if report.corpus_rows:
        lines.append(_table("corpus (sheet graphs)", report.corpus_rows))
    lines.append(_pattern_table(report.per_pattern))
    return "\n".join(lines)


def _table(title: str, rows: Sequence[CompositionRow]) -> str:
    out = [f"\n{title}", f"  {'quantity':<64}{'value':>9}  {'band':<42}verdict"]
    out += [f"  {r.quantity:<64}{r.value:>9.3f}  {r.band:<42}{r.verdict.value}" for r in rows]
    return "\n".join(out)


def _pattern_table(rows: Sequence[PatternRow]) -> str:
    head = (
        f"  {'pattern, layout, sheet':<34}{'n':>5}{'symbols mean (min-max)':>26}"
        f"{'stubs mean (max)':>20}  misses"
    )
    out = ["\nper pattern (misses = sheets > 134 or < 40 symbols, > 21 stubs)", head]
    for r in rows:
        misses = (
            f">134: {r.over_134_symbols}, <40: {r.under_40_symbols}, >21 stubs: {r.over_21_stubs}"
        )
        symbols = f"{r.symbols_mean:.1f} ({r.symbols_low}-{r.symbols_high})"
        stubs = f"{r.stubs_mean:.1f} ({r.stubs_high})"
        out.append(
            f"  {r.label:<34}{r.sheets:>5}{symbols:>26}{stubs:>20}  {misses if r.misses else ''}"
        )
    return "\n".join(out)


# ---- command line --------------------------------------------------------------------------------


def require_no_test_seeds(seeds: Sequence[int], allow_test_seed: bool) -> None:
    """Refuse the test range 5000-5999 unless `allow_test_seed` (design 14.5).

    Raises:
        ValueError: if a seed is a test seed and the flag is not given.
    """
    test = [seed for seed in seeds if seed in TEST_SEED_RANGE]
    if test and not allow_test_seed:
        raise ValueError(
            f"expected tuning seeds (0-999), got test seeds {test}: they stay unseen until the "
            "freeze; pass --allow-test-seed only after it"
        )


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m plantgraph.benchmark.v2.composition")
    parser.add_argument("--target-sheets", type=int, default=100)
    parser.add_argument("--seeds", type=int, nargs="+", default=[1])
    parser.add_argument("--corpus", action="store_true", help="also build the sheet graphs")
    parser.add_argument("--coverage", action="store_true", help="also print the class coverage")
    parser.add_argument("--json", type=Path, default=None, help="write the reports as JSON")
    parser.add_argument("--allow-test-seed", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Print the report of every seed; exit 1 when a pass/fail band fails, 0 otherwise."""
    args = _parse_args(argv)
    try:
        require_no_test_seeds(args.seeds, args.allow_test_seed)
    except ValueError as error:
        raise SystemExit(f"error: {error}") from error
    preset = HeadlinePresetV2()
    reports = []
    for seed in args.seeds:
        n_units = smallest_n_units_v2(args.target_sheets, preset, seed).n_units
        plan = plan_plant(preset.generator_config(n_units, seed))
        corpus_id = headline_corpus_id_v2(args.target_sheets, seed, preset.duplication_rate)
        report = build_report(plan, corpus_id, preset if args.corpus else None)
        print(render_report(report))
        if args.coverage:
            print(render_coverage(coverage_report(plan)))
        reports.append(report)
    if args.json is not None:
        args.json.write_text(
            json.dumps([r.model_dump(mode="json") for r in reports], indent=2), encoding="utf-8"
        )
    return 1 if any(report.failures for report in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
