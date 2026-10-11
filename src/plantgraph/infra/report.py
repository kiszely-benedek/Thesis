"""`build_infra_report`: tables I1..I4 and the self-checks from parsed measurements.

Pure: no file, database or clock is touched here (loading is `report_inputs.py`, writing is
`report_render.py`), so the whole report can be tested on hand-made inputs.
"""

from __future__ import annotations

from plantgraph.infra.report_checks import run_all_checks
from plantgraph.infra.report_compute import compute_row, usable
from plantgraph.infra.report_inputs import ReportInputs
from plantgraph.infra.report_models import (
    CorpusFootprintRow,
    GrowthRow,
    InfraReport,
    MoneyRow,
    ReferencePrice,
    SelfCheck,
    StrategyComputeRow,
)
from plantgraph.infra.report_quantities import corpus_footprint

SECONDS_PER_HOUR = 3600


def build_infra_report(inputs: ReportInputs) -> InfraReport:
    """Build the report.

    Raises:
        ValueError: no corpus was given.
    """
    if not inputs.corpora:
        raise ValueError("expected at least one corpus with measurements, found none")
    footprints = [corpus_footprint(corpus) for corpus in inputs.corpora]
    compute = [compute_row(run) for run in inputs.runs if usable(run)]
    checks = run_all_checks(inputs, footprints)
    first = inputs.corpora[0].ingests[0].environment
    return InfraReport(
        machine_summary=_machine_summary(inputs),
        git_commit=first.git_commit if first else "unknown",
        git_dirty=first.git_dirty if first else False,
        checks=_with_db_replay_notice(_with_old_run_notice(checks, compute), compute),
        footprints=footprints,
        compute=compute,
        growth=growth_rows(footprints, compute),
        reference_price=inputs.price,
        money=money_rows(compute, inputs.price),
    )


def _machine_summary(inputs: ReportInputs) -> str:
    environment = inputs.corpora[0].ingests[0].environment
    if environment is None:
        return "unknown (the first ingest has no environment record)"
    machine = environment.machine
    plugged = {True: "plugged in", False: "on battery", None: "power state unknown"}
    return (
        f"{machine.cpu_name} ({machine.physical_cores} cores / {machine.logical_cores} threads), "
        f"{machine.ram_bytes / 1024**3:.1f} GiB RAM, {machine.os}, Python "
        f"{machine.python_version}, {plugged[machine.power_plugged]}"
    )


def _with_old_run_notice(
    checks: list[SelfCheck], compute: list[StrategyComputeRow]
) -> list[SelfCheck]:
    old = [f"{row.role} on {row.corpus_id}" for row in compute if row.basis == "old_run"]
    if not old:
        return checks
    notice = SelfCheck(
        name="Old-run rows",
        status="flag",
        detail=(
            "the replay missed the cache or differed from its source, so the original run's "
            "timings are shown instead: "
            + ", ".join(old)
            + " (coarse monotonic clock, concurrency 4, no split)"
        ),
    )
    return [*checks, notice]


def _with_db_replay_notice(
    checks: list[SelfCheck], compute: list[StrategyComputeRow]
) -> list[SelfCheck]:
    partial = [f"{row.role} on {row.corpus_id}" for row in compute if row.basis == "db_replay"]
    if not partial:
        return checks
    notice = SelfCheck(
        name="Database-only rows",
        status="flag",
        detail=(
            "local compute of these rows is database time only (the stored query run again plus "
            "the row formatting; no query-writing model call, no answer-prompt build, no answer "
            "parsing): "
            + ", ".join(partial)
            + ". The model latency and token cost in the same row come from the source run."
        ),
    )
    return [*checks, notice]


def growth_rows(
    footprints: list[CorpusFootprintRow], compute: list[StrategyComputeRow]
) -> list[GrowthRow]:
    """Each quantity on consecutive corpora (as given): I1 medians and I2 local-compute figures."""
    rows: list[GrowthRow] = []
    for smaller, larger in zip(footprints, footprints[1:], strict=False):
        rows += _footprint_growth(smaller, larger)
    rows += _compute_growth(compute, footprints)
    return rows


def _footprint_growth(small: CorpusFootprintRow, large: CorpusFootprintRow) -> list[GrowthRow]:
    values = {f"size.{k}": float(v) for k, v in small.sizes.items()}
    values_large = {f"size.{k}": float(v) for k, v in large.sizes.items()}
    values |= {k: v.median for k, v in small.quantities.items()}
    values_large |= {k: v.median for k, v in large.quantities.items()}
    return [
        GrowthRow(
            name=name,
            from_corpus=small.corpus_id,
            to_corpus=large.corpus_id,
            from_value=values[name],
            to_value=values_large[name],
        )
        for name in values
        if name in values_large
    ]


def _compute_growth(
    compute: list[StrategyComputeRow], footprints: list[CorpusFootprintRow]
) -> list[GrowthRow]:
    ids = [row.corpus_id for row in footprints]
    by_key = {(row.role, row.corpus_id): row for row in compute}
    rows: list[GrowthRow] = []
    for role in sorted({row.role for row in compute}):
        for small_id, large_id in zip(ids, ids[1:], strict=False):
            small, large = by_key.get((role, small_id)), by_key.get((role, large_id))
            if small is None or large is None:
                continue
            rows += [
                GrowthRow(
                    name=f"{role}.{label}",
                    from_corpus=small_id,
                    to_corpus=large_id,
                    from_value=getattr(small, field),
                    to_value=getattr(large, field),
                )
                for label, field in _COMPUTE_GROWTH_FIELDS
            ]
    return rows


#: (label, StrategyComputeRow field) pairs that table I3 compares across corpora.
_COMPUTE_GROWTH_FIELDS = (
    ("local_median_s", "local_median_s"),
    ("local_p90_s", "local_p90_s"),
    ("local_sum_s", "local_sum_s"),
    ("token_usd_per_question", "token_usd_per_question"),
)


def money_rows(compute: list[StrategyComputeRow], price: ReferencePrice | None) -> list[MoneyRow]:
    """Table I4 rows; empty without a price (the report then has no money table)."""
    if price is None:
        return []
    return [
        MoneyRow(
            role=row.role,
            corpus_id=row.corpus_id,
            marginal_usd_per_question=price.usd_per_hour * row.local_median_s / SECONDS_PER_HOUR,
            token_usd_per_question=row.token_usd_per_question,
        )
        for row in compute
    ]
