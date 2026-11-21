"""The Results tab's data: recorded experiment reports, projected into what the page draws.

Nothing here is computed or typed in. Every number is read from a report file written by an
earlier experiment run (`report.json`); the page also gets the file's path, hash and date, so a
visitor can see which recorded run a figure comes from.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from plantgraph.demo.app.config import DemoCorpus, LadderSource, ResultsSources, SealedSource
from plantgraph.demo.app.results_infra import e2e_view, infra_view
from plantgraph.demo.app.results_reports import (
    IngestRecord,
    LadderReport,
    ScopeRow,
    Sealed,
    SealedReport,
    provenance,
    read_report,
)
from plantgraph.demo.app.results_views import (
    ClaimLine,
    LadderPoint,
    LadderView,
    ResultsView,
    SealedRow,
    SealedView,
)

#: Claim headlines name their scope in brackets, e.g. "K1 [held-out]: ...".
_SCOPE_TAG = re.compile(r"\[([^\]]+)\]")


# --- ladder -----------------------------------------------------------------------------------


def ladder_view(source: LadderSource) -> LadderView:
    """Project the ladder report: the configured scope's cells, with the report's claim lines."""
    report = read_report(source.report, LadderReport)
    families = report.scope_families.get(source.scope)
    if families is None:
        raise ValueError(
            f"expected scope {source.scope!r} in {source.report}, "
            f"found scopes {sorted(report.scope_families)}"
        )
    sheets = {size.corpus_id: size.n_sheets for size in report.sizes}
    points = tuple(
        LadderPoint(
            corpus_id=cell.corpus_id,
            n_sheets=sheets[cell.corpus_id],
            arm=cell.policy,
            n=cell.n,
            accuracy=cell.acc_at_120,
            cost_mean_usd=cell.cost_mean,
            latency_median_s=cell.latency_median,
        )
        for cell in report.cells
        if cell.scope == source.scope
    )
    claims = tuple(
        ClaimLine(claim_id=c.id, verdict=c.verdict, text=f"{c.wording}: {c.value}")
        for c in report.claims
    )
    return LadderView(
        scope=source.scope,
        n_families=len(families),
        cutoff_s=report.cutoff_s,
        wall_sheets=report.wall_sheets,
        points=points,
        absent=tuple(report.absent),
        claims=claims,
        source=provenance(source.report, source.result_row),
    )


# --- sealed -----------------------------------------------------------------------------------


def _plant_sheet_count(corpus_id: str, corpora: Sequence[DemoCorpus]) -> int:
    """A plant's sheet count, from its ingest record (the report names pooled scales only)."""
    corpus = next((c for c in corpora if c.corpus_id == corpus_id), None)
    if corpus is None:
        raise ValueError(
            f"expected corpus {corpus_id!r} to be a pooled scale in the report or a configured "
            f"plant {sorted(c.corpus_id for c in corpora)}, found neither"
        )
    return read_report(corpus.ingest_json, IngestRecord).counts.n_sheets


def _sealed_row(
    row: ScopeRow, sealed: Sealed, label: str, corpora: Sequence[DemoCorpus]
) -> SealedRow:
    pooled_plants = sealed.scales.get(row.corpus_id)
    pooled = pooled_plants is not None
    n_sheets = sealed.sheets.get(row.corpus_id)
    summary = row.summary
    return SealedRow(
        corpus_id=row.corpus_id,
        n_sheets=n_sheets if n_sheets is not None else _plant_sheet_count(row.corpus_id, corpora),
        policy=row.policy,
        source_label=label,
        scope=row.scope,
        n_questions=summary.n_questions,
        n_correct=summary.n_correct_at_cutoff,
        accuracy=row.accuracy,
        cost_per_question_usd=summary.cost_per_question_usd,
        latency_median_s=summary.latency_median_s,
        latency_p90_s=summary.latency_p90_s,
        pooled=pooled,
        n_plants=len(pooled_plants) if pooled_plants is not None else None,
        # a pooled figure is a mean over plants: its interval resamples plants too
        interval_method="two-stage bootstrap" if pooled else "wilson",
    )


def _selected(row: ScopeRow, source: SealedSource) -> bool:
    return (
        row.policy in source.policies
        and row.scope in source.scopes
        and (not source.corpora or row.corpus_id in source.corpora)
    )


def _claims_in_scopes(sealed: Sealed, scopes: Sequence[str]) -> tuple[ClaimLine, ...]:
    """Claim lines for the shown scopes; a line with no scope tag (a not-run claim) always shows."""
    lines = []
    for claim in sealed.claims:
        tag = _SCOPE_TAG.search(claim.headline)
        if tag is None or tag.group(1) in scopes:
            lines.append(ClaimLine(claim_id=claim.rule, verdict=claim.status, text=claim.headline))
    return tuple(lines)


def _source_rows(
    source: SealedSource, sealed: Sealed, corpora: Sequence[DemoCorpus]
) -> tuple[SealedRow, ...]:
    chosen = [row for row in sealed.scope_rows if _selected(row, source)]
    missing = [c for c in source.corpora if c not in {row.corpus_id for row in chosen}]
    if not chosen or missing:
        raise ValueError(
            f"expected rows for policies {source.policies}, scopes {source.scopes} and corpora "
            f"{source.corpora or 'any'} in {source.report}, found none for {missing or 'any'}"
        )
    return tuple(_sealed_row(row, sealed, source.label, corpora) for row in chosen)


def sealed_view(sources: Sequence[SealedSource], corpora: Sequence[DemoCorpus]) -> SealedView:
    """Project the sealed reports: each source's selected rows, in source order.

    Args:
        sources: the reports to read; the first one also supplies the claim lines.
        corpora: the configured plants, whose ingest records give a plant row its sheet count.

    Raises:
        ValueError: a source selects nothing, or a plant row has no known sheet count.
    """
    if not sources:
        raise ValueError("expected at least one sealed source, found none")
    reports = [read_report(source.report, SealedReport).sealed for source in sources]
    rows = tuple(
        row
        for source, sealed in zip(sources, reports, strict=True)
        for row in _source_rows(source, sealed, corpora)
    )
    scopes = tuple(dict.fromkeys(scope for source in sources for scope in source.scopes))
    return SealedView(
        scopes=scopes,
        rows=rows,
        claims=_claims_in_scopes(reports[0], sources[0].scopes),
        sources=tuple(provenance(source.report, source.result_row) for source in sources),
    )


def results_view(sources: ResultsSources, corpora: Sequence[DemoCorpus] = ()) -> ResultsView:
    """The views for the configured report files.

    Raises:
        FileNotFoundError: a configured report does not exist.
        ValueError: a report lacks a field the projection reads, or a row cannot be resolved.
    """
    return ResultsView(
        ladder=ladder_view(sources.ladder) if sources.ladder else None,
        sealed=sealed_view(sources.sealed, corpora) if sources.sealed else None,
        infra=infra_view(sources.infra) if sources.infra else None,
        e2e=e2e_view(sources.e2e) if sources.e2e else None,
    )


def check_results_sources(sources: ResultsSources | None, corpora: Sequence[DemoCorpus]) -> None:
    """Resolve every configured source once, so a broken one stops the app at startup.

    Raises:
        FileNotFoundError: a configured report or ingest record does not exist.
        ValueError: a plant row has no sheet count, or an infra row or e2e arm is unknown.
    """
    if sources is not None:
        results_view(sources, corpora)
