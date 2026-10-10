"""Exports a corpus as a drawing set: `drawings.pdf` plus the sidecar `drawings.index.json`.

Reads only the localized sheets and the resolution counts - the system's own input, never the
answer key. The sidecar maps sheet -> page and carries the `DrawingReport` self-check.
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Sequence
from pathlib import Path

from plantgraph.benchmark.sheet_graph import SheetGraph
from plantgraph.demo.drawing.geometry import count_foreign_crossings, count_overlaps
from plantgraph.demo.drawing.layout import layout_sheet
from plantgraph.demo.drawing.models import (
    DrawingIndex,
    DrawingReport,
    LayoutConfig,
    SheetLayout,
)
from plantgraph.demo.drawing.render_pdf import RenderedPdf, render_drawing_set
from plantgraph.resolution.models import Resolution

PDF_NAME = "drawings.pdf"
INDEX_NAME = "drawings.index.json"


def export_drawings(
    corpus_id: str,
    sheets: Sequence[SheetGraph],
    resolution: Resolution,
    out_dir: Path,
    config: LayoutConfig | None = None,
) -> DrawingIndex:
    """Lay out and render every sheet into `out_dir/<corpus_id>/`; returns the written index.

    Raises:
        ValueError: the drawing does not match the corpus (symbols, flags or lines missing).
    """
    cfg = config or LayoutConfig()
    started = time.perf_counter()
    layouts = [layout_sheet(sheet, cfg) for sheet in sheets]
    layout_s = time.perf_counter() - started

    started = time.perf_counter()
    rendered = render_drawing_set(corpus_id, layouts, cfg)
    render_s = time.perf_counter() - started

    report = _report(layouts, rendered, layout_s, render_s)
    _check_against_corpus(report, sheets, resolution)
    index = DrawingIndex(
        corpus_id=corpus_id,
        pdf_sha256=hashlib.sha256(rendered.data).hexdigest(),
        pages=rendered.pages,
        report=report,
    )
    _write(out_dir / corpus_id, rendered.data, index)
    return index


def _report(
    layouts: Sequence[SheetLayout], rendered: RenderedPdf, layout_s: float, render_s: float
) -> DrawingReport:
    return DrawingReport(
        pages=len(rendered.pages),
        symbols=rendered.symbols,
        lines=rendered.lines,
        flags=rendered.flags,
        flags_linked=rendered.flags_linked,
        dangling_flags=rendered.dangling_flags,
        overlaps=sum(count_overlaps(layout) for layout in layouts),
        foreign_crossings=sum(count_foreign_crossings(layout) for layout in layouts),
        min_scale=rendered.min_scale,
        layout_s=round(layout_s, 3),
        render_s=round(render_s, 3),
    )


def _check_against_corpus(
    report: DrawingReport, sheets: Sequence[SheetGraph], resolution: Resolution
) -> None:
    """Acceptance: every symbol, flag and edge of the corpus is drawn, and nothing overlaps."""
    expected = {
        "symbols": resolution.report.n_occurrences,
        "flags": resolution.report.n_connectors,
        "lines": sum(sheet.graph.number_of_edges() for sheet in sheets),
        "overlaps": 0,
    }
    found = report.model_dump()
    wrong = {name: (want, found[name]) for name, want in expected.items() if found[name] != want}
    if wrong:
        raise ValueError(f"drawing does not match the corpus (name: (expected, drawn)): {wrong}")


def _write(corpus_dir: Path, pdf_bytes: bytes, index: DrawingIndex) -> None:
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / PDF_NAME).write_bytes(pdf_bytes)
    (corpus_dir / INDEX_NAME).write_text(index.model_dump_json(indent=2) + "\n", encoding="utf-8")
