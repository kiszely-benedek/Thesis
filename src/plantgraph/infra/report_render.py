"""Write an `InfraReport` as Markdown: header with the self-checks, then tables I1..I4."""

from __future__ import annotations

from pathlib import Path

from plantgraph.infra.report_models import (
    CorpusFootprintRow,
    GrowthRow,
    InfraReport,
    MoneyRow,
    ReferencePrice,
    Spread,
    StrategyComputeRow,
)

_STATUS_WORD = {"pass": "PASS", "fail": "FAIL", "flag": "FLAG"}
_MISSING = "-"

_FIXED_LABELS = {
    "ingest.build_total": "ingest total (stages above)",
    "store.data_bytes": "store on disk (data + indexes)",
    "store.tx_log_bytes": "transaction logs on disk (follow retention, not the corpus)",
    "store.page_cache_needed_bytes": "page cache needed (derived: disk x 1.2, Neo4j manual)",
    "store.metrics_bytes": "store size per server metric (secondary, may lag)",
    "startup.total": "startup total",
    "startup.without_rebuild": "startup without rebuild (total - rebuild)",
    "startup.context_rag_build": "ContextRAG prompt build",
    "process.baseline_bytes": "app process peak after imports",
    "process.peak_bytes": "app process peak at end of probe",
    "neo4j.rss_bytes": "Neo4j process resident memory",
    "neo4j.page_cache_used_bytes": "page cache in use (usage ratio x size)",
    "memory.view_bytes": "graph view in memory (tracemalloc net)",
    "memory.item_graph_bytes": "plant graph in memory (tracemalloc net)",
    "memory.traced_peak_bytes": "traced peak during both builds",
}


def label_of(name: str) -> str:
    """A reader-friendly name for a quantity key."""
    if name in _FIXED_LABELS:
        return _FIXED_LABELS[name]
    group, _, rest = name.partition(".")
    return f"{group}: {rest}" if group in ("ingest", "startup", "size") else name


def format_value(name: str, value: float) -> str:
    """Format by the quantity's unit, which its key tells: bytes, a count, dollars or seconds."""
    if name.endswith("_bytes"):
        return f"{value / 1024**2:,.1f} MiB"
    if name.startswith("size."):
        return f"{value:,.0f}"
    if name.endswith("_usd_per_question"):
        return f"${value:.5f}"
    return f"{value:,.4f} s" if abs(value) < 1 else f"{value:,.2f} s"


def _cell(name: str, spread: Spread | None) -> str:
    if spread is None:
        return _MISSING
    text = format_value(name, spread.median)
    if spread.n_repeats == 1:
        return text
    low, high = format_value(name, spread.minimum), format_value(name, spread.maximum)
    return f"{text} ({low} to {high}){' !' if spread.flagged else ''}"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return lines + ["| " + " | ".join(row) + " |" for row in rows]


def _ratio(ratio: float | None) -> str:
    return f"x{ratio:.2f}" if ratio is not None else _MISSING


def render_header(report: InfraReport) -> list[str]:
    """Machine, code version and the self-check table."""
    dirty = " (uncommitted changes)" if report.git_dirty else ""
    lines = [
        "# Infrastructure cost report",
        "",
        f"Machine: {report.machine_summary}",
        f"Code: commit {report.git_commit}{dirty}",
        "",
        "## Self-checks",
        "",
    ]
    rows = [[c.name, _STATUS_WORD[c.status], c.detail] for c in report.checks]
    return lines + _table(["Check", "Result", "Detail"], rows) + [""]


def render_footprint(footprints: list[CorpusFootprintRow]) -> list[str]:
    """Table I1: one row per quantity, one column per corpus ('!' marks a spread above x1.5)."""
    header = ["Quantity", *[f"{row.corpus_id}" for row in footprints]]
    names: list[str] = []
    for row in footprints:
        names += [f"size.{k}" for k in row.sizes if f"size.{k}" not in names]
    for row in footprints:
        names += [k for k in row.quantities if k not in names]
    rows = [[label_of(name), *_footprint_cells(name, footprints)] for name in names]
    lines = ["## I1 - corpus footprint (median, then min to max over the repeats)", ""]
    lines += _table(header, rows) + [""]
    notes = [f"- {row.corpus_id}: {note}" for row in footprints for note in row.notes]
    return lines + notes + ([""] if notes else [])


def _footprint_cells(name: str, footprints: list[CorpusFootprintRow]) -> list[str]:
    cells: list[str] = []
    for row in footprints:
        if name.startswith("size."):
            count = row.sizes.get(name.removeprefix("size."))
            cells.append(_MISSING if count is None else format_value(name, count))
        else:
            cells.append(_cell(name, row.quantities.get(name)))
    return cells


def _yes(flag: bool) -> str:
    return "yes" if flag else "no"


def _seconds(value: float | None) -> str:
    return _MISSING if value is None else format_value("t", value)


def render_compute(rows: list[StrategyComputeRow]) -> list[str]:
    """Table I2: per-question local compute for each strategy and corpus."""
    header = [
        "Strategy", "Corpus", "Basis", "DB server", "Graph in memory", "Questions", "Median",
        "p90", "Max", "Sum", "DB client", "DB server time", "Graph API", "Other",
        "Local share of latency", "Token $/question",
    ]  # fmt: skip
    body = [
        [
            f"{r.role} ({r.strategy})", r.corpus_id, r.basis, _yes(r.needs_database),
            _yes(r.needs_memory_graph), str(r.n_questions), _seconds(r.local_median_s),
            _seconds(r.local_p90_s), _seconds(r.local_max_s), _seconds(r.local_sum_s),
            _seconds(r.db_client_sum_s), _seconds(r.db_server_sum_s), _seconds(r.graph_api_sum_s),
            _seconds(r.other_sum_s), f"{r.local_share_of_latency:.1%}",
            format_value("_usd_per_question", r.token_usd_per_question)
            + (f" ({r.n_cost_missing} unpriced)" if r.n_cost_missing else ""),
        ]
        for r in rows
    ]  # fmt: skip
    return ["## I2 - local compute per strategy and corpus", ""] + _table(header, body) + [""]


def render_growth(rows: list[GrowthRow]) -> list[str]:
    """Table I3: how each quantity grows from a smaller to the next larger corpus."""
    body = [
        [
            label_of(r.name),
            f"{r.from_corpus} to {r.to_corpus}",
            format_value(r.name, r.from_value),
            format_value(r.name, r.to_value),
            _ratio(r.ratio),
        ]
        for r in rows
    ]
    return (
        ["## I3 - growth", ""] + _table(["Quantity", "Corpora", "From", "To", "Ratio"], body) + [""]
    )


def render_money(rows: list[MoneyRow], price: ReferencePrice | None) -> list[str]:
    """Table I4, or nothing when no hand-filled price file was given."""
    if price is None:
        return []
    lines = [
        "## I4 - money (derived from a reference price)",
        "",
        f"Reference: {price.provider} {price.instance} in {price.region}, {price.vcpu} vCPU, "
        f"{price.ram_gib:g} GiB, ${price.usd_per_hour}/h; {price.url}, accessed {price.accessed}.",
        "Marginal cost assumes one question at a time per instance (an upper bound). Standing "
        "cost per question is `$/h / questions per hour`; the query volume was not measured.",
        "",
    ]
    body = [
        [
            r.role, r.corpus_id, f"${r.marginal_usd_per_question:.8f}",
            f"${r.token_usd_per_question:.5f}",
        ]
        for r in rows
    ]  # fmt: skip
    table = _table(["Strategy", "Corpus", "Marginal compute $/question", "Token $/question"], body)
    return lines + table + [""]


def render_report(report: InfraReport) -> str:
    """The whole report as Markdown text."""
    lines = render_header(report) + render_footprint(report.footprints)
    lines += render_compute(report.compute) + render_growth(report.growth)
    lines += render_money(report.money, report.reference_price)
    return "\n".join(lines)


def write_infra_report(report: InfraReport, out: Path) -> Path:
    """Write the Markdown to `out` (UTF-8) and the report's JSON next to it."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_report(report), encoding="utf-8")
    out.with_suffix(".json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return out
