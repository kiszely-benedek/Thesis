"""Assembles the drawing-set PDF: one A3 landscape page per sheet, bookmarks, flag links.

The renderer knows nothing about graphs: it takes finished `SheetLayout`s. Output is
deterministic (fixed creation date, producer and compression), so two exports of the same
layouts are byte-identical.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from fpdf import FPDF

from plantgraph.demo.drawing.furniture import draw_furniture
from plantgraph.demo.drawing.glyphs import draw_line, draw_symbol
from plantgraph.demo.drawing.models import LayoutConfig, PlacedSymbol, SheetLayout

BOOKMARK_GROUP_SIZE = 100  # sheets per top-level bookmark ("DWG 0-99", "DWG 100-199", ...)
_FIXED_DATE = datetime(2026, 1, 1, tzinfo=UTC)  # fpdf2 would stamp "now" otherwise
_PRODUCER = "plantgraph demo drawing"


@dataclass(frozen=True)
class RenderedPdf:
    """The finished file plus what the renderer counted while drawing."""

    data: bytes
    pages: dict[str, int]  # sheet_id -> 1-based page number
    symbols: int
    lines: int
    flags: int
    flags_linked: int
    min_scale: float

    @property
    def dangling_flags(self) -> int:
        """Flags drawn without a link: their target sheet is not in the corpus."""
        return self.flags - self.flags_linked


@dataclass
class _Counts:
    symbols: int = 0
    lines: int = 0
    flags: int = 0
    flags_linked: int = 0


def sheet_order_key(sheet_id: str) -> tuple[int, int, str]:
    """Natural order: numeric ids as integers first, then any other id as a string."""
    return (0, int(sheet_id), "") if sheet_id.isdigit() else (1, 0, sheet_id)


def render_drawing_set(
    corpus_id: str, layouts: Sequence[SheetLayout], config: LayoutConfig | None = None
) -> RenderedPdf:
    """Draw every sheet on its own page and return the PDF bytes with the drawing counts."""
    cfg = config or LayoutConfig()
    ordered = sorted(layouts, key=lambda layout: sheet_order_key(layout.sheet_id))
    pages = {layout.sheet_id: number for number, layout in enumerate(ordered, start=1)}
    if len(pages) != len(ordered):
        raise ValueError("sheet ids must be unique; found a repeated id among the layouts")

    pdf = _new_pdf(corpus_id, cfg)
    # one link per page, created up front so a flag can point at a page drawn later
    link_ids = {sheet_id: pdf.add_link(page=number) for sheet_id, number in pages.items()}
    counts = _Counts()
    for number, layout in enumerate(ordered, start=1):
        group = _group_label(ordered, number)
        _draw_page(pdf, layout, number, group, corpus_id, cfg, link_ids, counts)
    return RenderedPdf(
        data=bytes(pdf.output()),
        pages=pages,
        symbols=counts.symbols,
        lines=counts.lines,
        flags=counts.flags,
        flags_linked=counts.flags_linked,
        min_scale=min((layout.scale for layout in ordered), default=1.0),
    )


def _new_pdf(corpus_id: str, cfg: LayoutConfig) -> FPDF:
    # the tuple is the portrait size; "L" swaps it, giving exactly the layout's A3 landscape page
    pdf = FPDF(orientation="L", unit="pt", format=(cfg.page_height, cfg.page_width))
    pdf.set_auto_page_break(False)
    pdf.set_creation_date(_FIXED_DATE)
    pdf.set_producer(_PRODUCER)
    pdf.set_title(f"{corpus_id} drawing set")
    return pdf


def _draw_page(
    pdf: FPDF,
    layout: SheetLayout,
    number: int,
    group: str | None,
    corpus_id: str,
    cfg: LayoutConfig,
    link_ids: dict[str, int],
    counts: _Counts,
) -> None:
    pdf.add_page()
    _add_bookmarks(pdf, layout, group)
    draw_furniture(pdf, layout, corpus_id, cfg)
    for line in layout.lines:  # lines first: the white-filled symbols then cover any overshoot
        draw_line(pdf, line, layout.scale)
        counts.lines += 1
    for symbol in layout.symbols:
        draw_symbol(pdf, symbol, layout.scale)
        counts.symbols += 1
        if symbol.family in ("pipe_flag", "signal_flag"):
            counts.flags += 1
            counts.flags_linked += _link_flag(pdf, symbol, link_ids)


def _link_flag(pdf: FPDF, symbol: PlacedSymbol, link_ids: dict[str, int]) -> int:
    """Make the flag clickable if its target sheet is in the corpus; returns 1 if linked."""
    link_id = link_ids.get(symbol.target_sheet) if symbol.target_sheet is not None else None
    if link_id is None:
        return 0
    pdf.link(
        symbol.x - symbol.width / 2,
        symbol.y - symbol.height / 2,
        symbol.width,
        symbol.height,
        link_id,
    )
    return 1


def _group_label(ordered: Sequence[SheetLayout], number: int) -> str | None:
    """The top-level bookmark title if page `number` starts a group of 100 pages, else None."""
    if (number - 1) % BOOKMARK_GROUP_SIZE != 0:
        return None
    last = min(number - 1 + BOOKMARK_GROUP_SIZE, len(ordered)) - 1
    return f"DWG {ordered[number - 1].sheet_id} - {ordered[last].sheet_id}"


def _add_bookmarks(pdf: FPDF, layout: SheetLayout, group: str | None) -> None:
    """Level 0: one entry per group of 100 pages; level 1: one entry per sheet."""
    if group is not None:
        pdf.start_section(group, level=0)
    units = f" - units {', '.join(layout.units)}" if layout.units else ""
    pdf.start_section(f"DWG {layout.sheet_id}{units}", level=1)
